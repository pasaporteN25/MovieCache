"""Metadata orchestration across the supported external sources."""

from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from movie_inbox.domain.catalog import external_source_name, normalize_tags, source_url_field
from movie_inbox.domain.titles import (
    clean_title,
    clean_whitespace,
    infer_kind_from_text,
    looks_like_external_id,
)
from movie_inbox.external.filmaffinity import fetch_filmaffinity_metadata
from movie_inbox.external.imdb import fetch_wikipedia_by_imdb_id, imdb_id_from_text
from movie_inbox.external.jikan import fetch_jikan_metadata
from movie_inbox.external.tmdb import fetch_tmdb_metadata
from movie_inbox.external.wikidata import fetch_wikidata_metadata
from movie_inbox.external.wikipedia import (
    fetch_wikipedia_by_title,
    fetch_wikipedia_by_wikidata_title,
    fetch_wikipedia_metadata,
)


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


def fetch_metadata(url: str, *, tmdb_read_access_token: str = "") -> dict[str, Any]:
    detected_source = external_source_name(url)
    if detected_source == "tmdb":
        return fetch_tmdb_metadata(url, tmdb_read_access_token)
    if detected_source == "jikan":
        return fetch_jikan_metadata(url)

    wikipedia_metadata = fetch_wikipedia_metadata(url)
    if wikipedia_metadata:
        return wikipedia_metadata

    imdb_id = imdb_id_from_text(url)
    if imdb_id:
        wikidata_metadata = fetch_wikipedia_by_imdb_id(imdb_id)
        if wikidata_metadata:
            wikidata_metadata["imdb_url"] = f"https://www.imdb.com/title/{imdb_id}/"
            return wikidata_metadata

    if detected_source == "filmaffinity":
        filmaffinity_metadata = fetch_filmaffinity_metadata(url)
        if filmaffinity_metadata:
            return filmaffinity_metadata

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
    title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.page_title
        or guess_title_from_url(url)
    )
    description = parser.meta.get("og:description") or parser.meta.get("description") or ""
    link_field = source_url_field(source_name(urlparse(url).netloc), url)
    metadata: dict[str, Any] = {
        "title": clean_title(title),
        "description": clean_whitespace(description),
        "og_type": parser.meta.get("og:type", ""),
    }
    inferred_kind = infer_kind_from_text(
        parser.meta.get("og:type", ""),
        metadata["title"],
        metadata["description"],
    )
    if inferred_kind:
        metadata["kind"] = inferred_kind
    source = external_source_name(url)
    if source == "imdb":
        metadata["english_title"] = metadata["title"]
    elif source == "filmaffinity":
        metadata["spanish_title"] = metadata["title"]
    if link_field:
        metadata[link_field] = url
    return metadata


def fetch_metadata_by_title(title: str, year: str = "") -> dict[str, Any]:
    title = clean_title(title)
    year = str(year or "").strip()
    if not title or looks_like_external_id(title):
        return {}

    candidates: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(fetch_wikipedia_by_wikidata_title, title, year),
            executor.submit(fetch_wikipedia_by_title, title, year),
        ]
        for future in as_completed(futures):
            try:
                metadata = future.result()
            except (HTTPError, URLError, TimeoutError, ValueError, OSError):
                metadata = {}
            if metadata:
                candidates.append(metadata)
    if not candidates:
        return {}
    return max(candidates, key=lambda metadata: _metadata_quality(metadata, year))


def _metadata_quality(metadata: dict[str, Any], expected_year: str) -> tuple[int, int]:
    score = 0
    if metadata.get("wikidata_id"):
        score += 20
    if metadata.get("wikipedia_url") or metadata.get("url"):
        score += 10
    if expected_year and str(metadata.get("year") or "") == expected_year:
        score += 10
    for field in ("original_title", "spanish_title", "english_title", "description", "page_image"):
        if metadata.get(field):
            score += 2
    aliases = normalize_tags(metadata.get("alternative_titles"))
    score += min(len(aliases), 10)
    return score, len(aliases)


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


__all__ = [
    "fetch_filmaffinity_metadata",
    "fetch_metadata",
    "fetch_metadata_by_title",
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
