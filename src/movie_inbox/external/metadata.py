"""Metadata orchestration across Wikipedia, IMDb and generic HTML pages."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from movie_inbox.domain.catalog import external_source_name, source_url_field
from movie_inbox.domain.titles import clean_title, clean_whitespace
from movie_inbox.external.imdb import fetch_wikipedia_by_imdb_id, imdb_id_from_text
from movie_inbox.external.wikipedia import (
    fetch_wikipedia_by_title,
    fetch_wikipedia_by_wikidata_title,
    fetch_wikipedia_metadata,
)
from movie_inbox.external.wikidata import fetch_wikidata_metadata


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            name = (attr.get("property") or attr.get("name") or "").lower()
            content = attr.get("content", "").strip()
            if name and content:
                self.meta[name] = html.unescape(content)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def page_title(self) -> str:
        return clean_title(" ".join(self.title_parts))


def fetch_metadata(url: str) -> dict[str, Any]:
    wikipedia_metadata = fetch_wikipedia_metadata(url)
    if wikipedia_metadata:
        return wikipedia_metadata

    imdb_id = imdb_id_from_text(url)
    if imdb_id:
        wikidata_metadata = fetch_wikipedia_by_imdb_id(imdb_id)
        if wikidata_metadata:
            wikidata_metadata["imdb_url"] = f"https://www.imdb.com/title/{imdb_id}/"
            return wikidata_metadata

    request = Request(
        url,
        headers={
            "User-Agent": "MovieInboxImporter/0.2 (+local personal catalog)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            if "html" not in content_type:
                return {}
            raw = response.read(800_000).decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return {}

    parser = MetadataParser()
    parser.feed(raw)
    title = parser.meta.get("og:title") or parser.meta.get("twitter:title") or parser.page_title or guess_title_from_url(url)
    description = parser.meta.get("og:description") or parser.meta.get("description") or ""
    link_field = source_url_field(source_name(urlparse(url).netloc), url)
    metadata: dict[str, Any] = {
        "title": clean_title(title),
        "description": clean_whitespace(description),
        "og_type": parser.meta.get("og:type", ""),
    }
    source = external_source_name(url)
    if source == "imdb":
        metadata["english_title"] = metadata["title"]
    elif source == "filmaffinity":
        metadata["spanish_title"] = metadata["title"]
    if link_field:
        metadata[link_field] = url
    return metadata


def source_name(netloc: str) -> str:
    try:
        host = (urlparse(f"//{netloc}").hostname or "").encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return ""
    host = host.lower().rstrip(".").removeprefix("www.")
    source = external_source_name(f"https://{host}/")
    if source:
        return source
    if host == "letterboxd.com" or host.endswith(".letterboxd.com"):
        return "letterboxd"
    return host


def guess_title_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    if not slug and parsed.netloc:
        return parsed.netloc
    slug = re.sub(r"\.[a-zA-Z0-9]+$", "", slug)
    return clean_title(unquote(slug).replace("_", " ").replace("-", " "))


def looks_like_external_id(value: str) -> bool:
    return bool(re.fullmatch(r"(tt|nm)\d+", value.strip(), flags=re.IGNORECASE)) or bool(
        re.fullmatch(r"film\d+", value.strip(), flags=re.IGNORECASE)
    )


__all__ = [
    "fetch_metadata",
    "fetch_wikidata_metadata",
    "fetch_wikipedia_by_imdb_id",
    "fetch_wikipedia_by_title",
    "fetch_wikipedia_by_wikidata_title",
    "fetch_wikipedia_metadata",
    "guess_title_from_url",
    "imdb_id_from_text",
    "looks_like_external_id",
    "source_name",
]
