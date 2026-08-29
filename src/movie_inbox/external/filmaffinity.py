"""FilmAffinity search client."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote

from movie_inbox.domain.catalog import external_source_name
from movie_inbox.domain.search import parse_search_query
from movie_inbox.domain.titles import infer_year
from movie_inbox.external.common import clean_text, fetch_text
from movie_inbox.external.query_variants import VARIANT_RETRY_TIMEOUT_SECONDS, alias_variants


class FilmAffinityAdapter:
    name = "filmaffinity"
    label = "FilmAffinity"

    def search(self, query: str) -> list[dict[str, Any]]:
        intent = parse_search_query(query)
        if intent.source:
            return []
        search_text = intent.title or query
        results = self._fetch(search_text)
        if results:
            return results
        # [Q3] tareas.md: the only source with no fallback of its own -- a
        # Wikidata-confirmed alias (prioritized towards its Spanish market
        # title, see query_variants._priority_order) gets one retry each.
        for variant in alias_variants(self.name, search_text):
            try:
                results = self._fetch(variant, timeout=VARIANT_RETRY_TIMEOUT_SECONDS)
            except Exception:
                continue
            if results:
                return results
        return results

    def _fetch(self, text: str, timeout: float = 8.0) -> list[dict[str, Any]]:
        parser = FilmAffinityParser()
        parser.feed(
            fetch_text(
                f"https://www.filmaffinity.com/es/search.php?stext={quote(text)}",
                timeout=timeout,
            )
        )
        return parser.results[:8]


class FilmAffinityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, Any]] = []
        self.current_href = ""
        self.capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        href = attributes.get("href", "")
        if tag == "a" and "/film" in href:
            self.current_href = href
            self.capture_title = True
        if tag in {"div", "span"} and "mc-title" in attributes.get("class", ""):
            self.capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.capture_title = False

    def handle_data(self, data: str) -> None:
        title = clean_text(data)
        url = self.absolute_url(self.current_href)
        if not self.capture_title or not self.current_href or len(title) < 2:
            return
        if any(existing["url"] == url for existing in self.results):
            return
        self.results.append(
            {
                "source": "filmaffinity",
                "title": title,
                "original_title": "",
                "spanish_title": title,
                "english_title": "",
                "alternative_titles": [],
                "year": infer_year(title),
                "url": url,
                "description": "",
            }
        )

    @staticmethod
    def absolute_url(href: str) -> str:
        return href if href.startswith("http") else "https://www.filmaffinity.com" + href


class FilmAffinityMetadataParser(HTMLParser):
    """Reads the schema.org microdata on a FilmAffinity film detail page.

    Most fields (year, genre, cast, director, synopsis) carry an itemprop
    attribute. "Titulo original" and "Guion" (writers) do not -- those are
    read positionally, by pairing each <dt> label with the <dd> that follows.
    """

    _NAME_TARGETS = {"director": "directors", "actor": "cast"}

    def __init__(self) -> None:
        super().__init__()
        self.display_title = ""
        self.original_title = ""
        self.year = ""
        self.description = ""
        self.genres: list[str] = []
        self.directors: list[str] = []
        self.writers: list[str] = []
        self.cast: list[str] = []
        self._pending = ""
        self._name_target = ""
        self._in_dt = False
        self._current_dt = ""
        self._in_writers_dd = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        itemprop = attributes.get("itemprop", "")
        # Tag-shaped state (dt/dd pairing, the h1 title, writer links) and
        # itemprop-shaped state are independent -- a tag can carry both (a
        # <dd itemprop="datePublished"> must update _pending from the second
        # block even though the first already matched on tag == "dd").
        if tag == "h1" and attributes.get("id") == "main-title":
            self._pending = "display_title"
        if tag == "dt":
            self._in_dt = True
        if tag == "dd":
            self._in_writers_dd = self._current_dt == "Guion"
            if self._current_dt == "Título original":
                self._pending = "original_title"
        if tag == "a" and self._in_writers_dd:
            title_attr = attributes.get("title", "").strip()
            if title_attr:
                self.writers.append(title_attr)

        if itemprop == "datePublished":
            self._pending = "year"
        elif itemprop == "genre":
            self._pending = "genre"
        elif itemprop == "description":
            self._pending = "description"
        elif itemprop in self._NAME_TARGETS:
            self._name_target = self._NAME_TARGETS[itemprop]
        elif itemprop == "name" and self._name_target:
            self._pending = self._name_target

    def handle_endtag(self, tag: str) -> None:
        if tag == "dt":
            self._in_dt = False
        elif tag == "dd":
            self._in_writers_dd = False

    def handle_data(self, data: str) -> None:
        text = clean_text(data)
        if not text:
            return
        if self._in_dt:
            self._current_dt = text
            return
        if self._pending == "display_title":
            self.display_title = text
        elif self._pending == "original_title":
            self.original_title = text
        elif self._pending == "year":
            self.year = text
        elif self._pending == "genre":
            self.genres.append(text)
        elif self._pending == "description":
            self.description = f"{self.description} {text}".strip()
        elif self._pending in self._NAME_TARGETS.values():
            getattr(self, self._pending).append(text)
        self._pending = ""


def fetch_filmaffinity_metadata(url: str) -> dict[str, Any]:
    if external_source_name(url) != "filmaffinity":
        return {}
    parser = FilmAffinityMetadataParser()
    parser.feed(fetch_text(url))
    title = parser.display_title or parser.original_title
    if not title:
        return {}
    return {
        "url": url,
        "filmaffinity_url": url,
        "title": title,
        "original_title": parser.original_title,
        "spanish_title": parser.display_title,
        "year": parser.year,
        "description": parser.description,
        "genres": parser.genres,
        "directors": parser.directors,
        "writers": parser.writers,
        "cast": parser.cast[:20],
    }
