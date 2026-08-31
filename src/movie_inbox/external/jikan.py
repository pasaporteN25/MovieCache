"""Jikan search parsing for the live-anime source designed in tareas.md [F2].

The adapter deliberately stays out of the default registry until [F2.2] adds
``mal_id``/``myanimelist_url`` to the canonical catalog schema.  Registering it
earlier would make search appear to work while silently discarding its identity
when a result is persisted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode, urlparse

from movie_inbox.domain.catalog import merge_lists
from movie_inbox.domain.releases import normalize_release_dates
from movie_inbox.domain.search import parse_search_query
from movie_inbox.external.common import clean_text, fetch_json, object_dict, object_list

JIKAN_API_BASE_URL = "https://api.jikan.moe/v4"
_MAL_ANIME_PATH = re.compile(r"^/anime/(\d+)(?:/|$)", flags=re.IGNORECASE)


class JikanAdapter:
    name = "jikan"
    label = "Jikan / MyAnimeList"

    def search(self, query: str) -> list[dict[str, Any]]:
        intent = parse_search_query(query)
        # Jikan's anime endpoint searches works, not people. Treating a director
        # surname as a title would create noisy cards and would contradict [Q4].
        if intent.director_query:
            return []
        if intent.source and intent.source != self.name:
            return []
        lookup = intent.title or query.strip()
        if not lookup:
            return []
        raw = fetch_json(f"{JIKAN_API_BASE_URL}/anime?{urlencode({'q': lookup, 'limit': 8})}")
        results: list[dict[str, Any]] = []
        for row in object_list(raw.get("data")):
            parsed = jikan_anime_result(row)
            if parsed is not None:
                results.append(parsed)
        return results


def jikan_anime_result(value: Any) -> dict[str, Any] | None:
    """Map one untrusted Jikan anime object to Movie Inbox's search shape."""
    if not isinstance(value, Mapping):
        return None
    row = dict(value)
    mal_id = _positive_id(row.get("mal_id"))
    title = clean_text(str(row.get("title") or ""))
    if not mal_id or not title:
        return None

    url = f"https://myanimelist.net/anime/{mal_id}"
    original_title = clean_text(str(row.get("title_japanese") or ""))
    english_title = clean_text(str(row.get("title_english") or ""))
    alternative_titles = _alternative_titles(row, title, original_title, english_title)
    images = object_dict(row.get("images"))
    jpg = object_dict(images.get("jpg"))
    webp = object_dict(images.get("webp"))
    page_image = str(
        jpg.get("large_image_url")
        or webp.get("large_image_url")
        or jpg.get("image_url")
        or webp.get("image_url")
        or ""
    )
    result: dict[str, Any] = {
        "source": "jikan",
        "title": title,
        "original_title": original_title,
        "spanish_title": "",
        "english_title": english_title,
        "alternative_titles": alternative_titles,
        "kind": "anime",
        "year": _anime_year(row),
        "url": url,
        "myanimelist_url": url,
        "mal_id": mal_id,
        "description": clean_text(str(row.get("synopsis") or "")),
        "page_image": page_image,
        "genres": _named_rows(row.get("genres")),
        "producers": _named_rows(row.get("producers")),
    }
    release_dates = _release_dates(row, url)
    if release_dates:
        result["release_dates"] = release_dates
    return result


def fetch_jikan_metadata(url: str) -> dict[str, Any]:
    """Load the full object for a selected MAL anime URL, never for a result shelf."""
    mal_id = jikan_anime_id(url)
    if not mal_id:
        return {}
    raw = fetch_json(f"{JIKAN_API_BASE_URL}/anime/{mal_id}/full")
    parsed = jikan_anime_result(raw.get("data"))
    return parsed or {}


def jikan_anime_id(value: str) -> str:
    try:
        parsed = urlparse(value)
    except ValueError:
        return ""
    hostname = (parsed.hostname or "").casefold().removeprefix("www.")
    if hostname != "myanimelist.net":
        return ""
    match = _MAL_ANIME_PATH.match(parsed.path)
    return _positive_id(match.group(1)) if match else ""


def _positive_id(value: Any) -> str:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return ""
    return str(normalized) if normalized > 0 else ""


def _alternative_titles(
    row: Mapping[str, Any], title: str, original_title: str, english_title: str
) -> list[str]:
    candidates: list[str] = []
    for title_row in object_list(row.get("titles")):
        if isinstance(title_row, Mapping):
            candidates.append(clean_text(str(title_row.get("title") or "")))
    candidates.extend(
        clean_text(str(value or "")) for value in object_list(row.get("title_synonyms"))
    )
    primary = {value.casefold() for value in (title, original_title, english_title) if value}
    return [value for value in merge_lists([], candidates) if value.casefold() not in primary]


def _named_rows(value: Any) -> list[str]:
    return merge_lists(
        [],
        [
            clean_text(str(row.get("name") or ""))
            for row in object_list(value)
            if isinstance(row, Mapping)
        ],
    )


def _anime_year(row: Mapping[str, Any]) -> str:
    year = _positive_id(row.get("year"))
    if year:
        return year
    aired = object_dict(row.get("aired"))
    aired_properties = object_dict(aired.get("prop"))
    aired_from = object_dict(aired_properties.get("from"))
    year = _positive_id(aired_from.get("year"))
    if year:
        return year
    match = re.match(r"^(\d{4})", str(aired.get("from") or ""))
    return match.group(1) if match else ""


def _release_dates(row: Mapping[str, Any], url: str) -> list[dict[str, Any]]:
    aired = object_dict(row.get("aired"))
    raw_date = str(aired.get("from") or "").split("T", 1)[0]
    if not raw_date:
        return []
    return normalize_release_dates(
        [
            {
                "date": raw_date,
                "source": "jikan",
                "source_url": url,
                "is_primary": True,
            }
        ]
    )


__all__ = [
    "JIKAN_API_BASE_URL",
    "JikanAdapter",
    "fetch_jikan_metadata",
    "jikan_anime_id",
    "jikan_anime_result",
]
