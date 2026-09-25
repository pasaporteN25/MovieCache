"""FilmAffinity search client."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote

from movie_inbox.domain.catalog import external_source_name
from movie_inbox.domain.search import parse_search_query
from movie_inbox.domain.titles import infer_year
from movie_inbox.external.common import clean_text, fetch_text
from movie_inbox.external.query_variants import (
    VARIANT_RETRY_TIMEOUT_SECONDS,
    alias_variants,
    needs_alias_retry,
    with_alias_identity,
)


class FilmAffinityAdapter:
    name = "filmaffinity"
    label = "FilmAffinity"

    def search(self, query: str) -> list[dict[str, Any]]:
        intent = parse_search_query(query)
        if intent.source:
            return []
        search_text = intent.title or intent.director_query or query
        results = self._fetch(search_text)
        if not needs_alias_retry(intent, results):
            return results
        # [Q3] tareas.md: the only source with no fallback of its own -- a
        # Wikidata-confirmed alias (prioritized towards its Spanish market
        # title, see query_variants._priority_order) gets one retry each.
        for variant in alias_variants(self.name, search_text):
            try:
                found = self._fetch(variant.title, timeout=VARIANT_RETRY_TIMEOUT_SECONDS)
            except Exception:
                continue
            # The row comes back titled in Spanish and is about to be scored
            # against a query that is not: carry the alias across or the retry
            # finds the film and the floor throws it away.
            annotated = with_alias_identity(found, variant)
            if not needs_alias_retry(intent, annotated):
                return annotated
        return results

    def _fetch(self, text: str, timeout: float = 8.0) -> list[dict[str, Any]]:
        body = fetch_text(
            f"https://www.filmaffinity.com/es/search.php?stext={quote(text)}",
            timeout=timeout,
        )
        single = _result_from_film_page(body)
        if single is not None:
            return [single]
        parser = FilmAffinityParser()
        parser.feed(body)
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


def _result_from_film_page(body: str) -> dict[str, Any] | None:
    """One result from a search that resolved straight to a film's own page.

    Measured against the live site, not assumed: searching "Sen to Chihiro no
    kamikakushi" or "Addio zio Tom" does not return a listing at all -- the
    site serves the film's page. Reading that page with the listing parser
    produced its navigation ("Ficha", "Imagenes") and its related-films rail
    as if they were search results, so the film Movie Inbox was looking for
    arrived titled "Ficha" and scored 10.2, under the 28.0 relevance floor.
    Every other row was a different Ghibli film. The source had the answer at
    the top of the response and contributed nothing.

    The page says what it is, so this reads it with the parser that already
    exists for it, which recovers the original title -- the one field that
    makes such a row score at all against a query in its own language.
    """

    parser = FilmAffinityMetadataParser()
    parser.feed(body)
    if not parser.is_film_page:
        return None
    title = parser.display_title or parser.original_title
    if not title:
        return None
    return {
        "source": "filmaffinity",
        "title": title,
        "original_title": parser.original_title,
        "spanish_title": parser.display_title,
        "english_title": "",
        "alternative_titles": [],
        "year": parser.year or infer_year(title),
        "url": parser.canonical_film_url,
        "description": parser.description,
    }


class FilmAffinityMetadataParser(HTMLParser):
    """Reads the schema.org microdata on a FilmAffinity film detail page.

    Most fields (year, genre, cast, director, synopsis) carry an itemprop
    attribute. "Titulo original" and "Guion" (writers) do not -- those are
    read positionally, by pairing each <dt> label with the <dd> that follows.
    """

    _NAME_TARGETS = {"director": "directors", "actor": "cast"}

    # A search that resolves to a single film does not return a listing: the
    # site serves the film's own page, which says so in its Open Graph tags
    # (og:type "video.", og:url the film's canonical address). Capturing them
    # is what lets a caller tell the two responses apart.
    _FILM_PAGE_URL = re.compile(r"^https://www\.filmaffinity\.com/[a-z]{2}/film\d+\.html$")

    def __init__(self) -> None:
        super().__init__()
        # HTMLParser keeps its own state in underscore attributes of this same
        # instance, and patch releases add to them: 3.11.16 and 3.14.7 added
        # `_pending`, which this parser used to overwrite with a string. State
        # here stays in plain names; tests/test_external_html_parsers.py checks.
        self.display_title = ""
        self.original_title = ""
        self.canonical_film_url = ""
        self.og_type = ""
        self.year = ""
        self.description = ""
        self.genres: list[str] = []
        self.directors: list[str] = []
        self.writers: list[str] = []
        self.cast: list[str] = []
        self.pending_field = ""
        self.name_target = ""
        self.in_dt = False
        self.current_dt = ""
        self.in_writers_dd = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        itemprop = attributes.get("itemprop", "")
        if tag == "meta":
            self._read_open_graph(attributes)
        # Tag-shaped state (dt/dd pairing, the h1 title, writer links) and
        # itemprop-shaped state are independent -- a tag can carry both (a
        # <dd itemprop="datePublished"> must update pending_field from the second
        # block even though the first already matched on tag == "dd").
        if tag == "h1" and attributes.get("id") == "main-title":
            self.pending_field = "display_title"
        if tag == "dt":
            self.in_dt = True
        if tag == "dd":
            self.in_writers_dd = self.current_dt == "Guion"
            if self.current_dt == "Título original":
                self.pending_field = "original_title"
        if tag == "a" and self.in_writers_dd:
            title_attr = attributes.get("title", "").strip()
            if title_attr:
                self.writers.append(title_attr)

        if itemprop == "datePublished":
            self.pending_field = "year"
        elif itemprop == "genre":
            self.pending_field = "genre"
        elif itemprop == "description":
            self.pending_field = "description"
        elif itemprop in self._NAME_TARGETS:
            self.name_target = self._NAME_TARGETS[itemprop]
        elif itemprop == "name" and self.name_target:
            self.pending_field = self.name_target

    def _read_open_graph(self, attributes: dict[str, str]) -> None:
        name = attributes.get("property", "")
        content = attributes.get("content", "").strip()
        if name == "og:type":
            self.og_type = content
        elif name == "og:url" and self._FILM_PAGE_URL.match(content):
            self.canonical_film_url = content

    @property
    def is_film_page(self) -> bool:
        """Whether the body parsed is a film's own page rather than a listing.

        A listing declares og:type "website" and points og:url back at the
        search; a film page declares "video." and points at itself."""
        return bool(self.canonical_film_url and self.og_type.startswith("video"))

    def handle_endtag(self, tag: str) -> None:
        if tag == "dt":
            self.in_dt = False
        elif tag == "dd":
            self.in_writers_dd = False

    def handle_data(self, data: str) -> None:
        text = clean_text(data)
        if not text:
            return
        if self.in_dt:
            self.current_dt = text
            return
        if self.pending_field == "display_title":
            self.display_title = text
        elif self.pending_field == "original_title":
            self.original_title = text
        elif self.pending_field == "year":
            self.year = text
        elif self.pending_field == "genre":
            self.genres.append(text)
        elif self.pending_field == "description":
            self.description = f"{self.description} {text}".strip()
        elif self.pending_field in self._NAME_TARGETS.values():
            getattr(self, self.pending_field).append(text)
        self.pending_field = ""


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
