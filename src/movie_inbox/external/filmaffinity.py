"""FilmAffinity search client."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote

from movie_inbox.domain.titles import infer_year
from movie_inbox.external.common import clean_text, fetch_text


class FilmAffinityAdapter:
    name = "filmaffinity"
    label = "FilmAffinity"

    def search(self, query: str) -> list[dict[str, Any]]:
        parser = FilmAffinityParser()
        parser.feed(fetch_text(f"https://www.filmaffinity.com/es/search.php?stext={quote(query)}"))
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
