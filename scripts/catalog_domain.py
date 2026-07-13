#!/usr/bin/env python3
"""Shared catalog normalization, matching, duplicate and merge rules."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from catalog_schema import (
    METADATA_FIELDS,
    merge_local_files,
    normalize_locked_fields,
    normalize_local_files,
    normalize_metadata_sources,
)


KNOWN_LINK_HOSTS = ("wikipedia.org", "imdb.com", "filmaffinity.com")
LIST_FIELDS = {"alternative_titles", "genres", "directors", "writers", "cast"}


def normalize_item(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["local_files"] = normalize_local_files(
        item.get("local_files"),
        str(item.get("local_name") or ""),
        str(item.get("local_path") or ""),
    )
    if item["local_files"]:
        first_local_file = item["local_files"][0]
        item["local_name"] = item.get("local_name") or first_local_file.get("name", "")
        item["local_path"] = item.get("local_path") or first_local_file.get("path", "")
    item["added_at"] = str(item.get("added_at") or item.get("addedAt") or "")
    item["tags"] = normalize_tags(item.get("tags"))
    item["alternative_titles"] = normalize_tags(item.get("alternative_titles") or item.get("alternativeTitles"))
    item["genres"] = normalize_tags(item.get("genres") or item.get("genre"))
    item["directors"] = normalize_tags(item.get("directors") or item.get("director"))
    item["writers"] = normalize_tags(item.get("writers") or item.get("writer") or item.get("screenwriters"))
    item["cast"] = normalize_tags(item.get("cast") or item.get("actors") or item.get("actor"))
    item["locked_fields"] = normalize_locked_fields(item.get("locked_fields"))
    item["metadata_sources"] = normalize_metadata_sources(item.get("metadata_sources"))
    string_fields = {
        "id",
        "url",
        "source",
        "title",
        "original_title",
        "spanish_title",
        "english_title",
        "year",
        "description",
        "wikipedia_url",
        "imdb_url",
        "filmaffinity_url",
        "wikipedia_title",
        "wikidata_id",
        "page_image",
        "wikipedia_extract",
        "local_name",
        "local_path",
        "notes",
        "review",
    }
    for field in string_fields:
        item[field] = str(item.get(field) or "")
    for field in LIST_FIELDS:
        item[field] = normalize_tags(item.get(field))
    item["kind"] = normalize_kind(item.get("kind"))
    item["status"] = normalize_status(item.get("status"))
    item["watched_at"] = normalize_date(item.get("watched_at"))
    item["rating"] = normalize_rating(item.get("rating"))
    item["en_catalogo"] = normalize_bool(item.get("en_catalogo"))
    if not item["id"]:
        seed = item["url"] or item["local_path"] or item["local_name"] or f"{item['title']} {item['year']}".strip()
        item["id"] = stable_id(seed) if seed else ""
    item["metadata_sources"] = ensure_metadata_sources(item)
    return item


def normalize_status(value: Any) -> str:
    text = str(value or "to_watch").strip().lower()
    return text if text in {"to_watch", "watched"} else "to_watch"


def normalize_date(value: Any) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value or "").strip())
    return match.group(1) if match else ""


def today_date() -> str:
    return datetime.now().date().isoformat()


def normalize_rating(value: Any) -> int:
    try:
        rating = int(float(str(value or 0).strip()))
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, rating))


def normalize_kind(value: Any) -> str:
    text = str(value or "pelicula").strip().lower()
    mapping = {
        "movie": "pelicula",
        "film": "pelicula",
        "película": "pelicula",
        "pelicula": "pelicula",
        "series": "serie",
        "tvseries": "serie",
        "tv series": "serie",
        "episode": "serie",
        "tv episode": "serie",
        "serie": "serie",
        "anime": "anime",
        "documentary": "documental",
        "documental": "documental",
    }
    return mapping.get(text, "pelicula")


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, str):
        rows = value.split(",")
    else:
        rows = []
    return list(dict.fromkeys(str(row).strip() for row in rows if str(row).strip()))


def merge_lists(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in primary + secondary:
        key = value.casefold().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(value)
    return merged


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "si", "sí"}


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def canonical_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower() or 'https'}://{parsed.netloc.lower()}{path}"


def trusted_external_url(url: str) -> str:
    canonical = canonical_url(url)
    return canonical if any(host in canonical for host in KNOWN_LINK_HOSTS) else ""


def source_url_field(source: str, url: str = "") -> str:
    text = f"{source} {url}".lower()
    if "wikipedia" in text:
        return "wikipedia_url"
    if "imdb" in text:
        return "imdb_url"
    if "filmaffinity" in text:
        return "filmaffinity_url"
    return ""


def external_urls(item: dict[str, Any]) -> set[str]:
    urls = {
        trusted_external_url(str(item.get("url") or "")),
        trusted_external_url(str(item.get("wikipedia_url") or "")),
        trusted_external_url(str(item.get("imdb_url") or "")),
        trusted_external_url(str(item.get("filmaffinity_url") or "")),
    }
    return {url for url in urls if url}


def has_external_link(item: dict[str, Any]) -> bool:
    return bool(external_urls(item))


def title_match_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", html.unescape(value).lower())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_path_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", html.unescape(value).lower())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"[\\/]+", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def title_values_for_item(item: dict[str, Any]) -> list[str]:
    local_values = [
        str(value)
        for local_file in normalize_local_files(item.get("local_files"))
        for value in (local_file.get("name", ""), local_file.get("path", ""))
        if value
    ]
    return [
        str(item.get("title") or ""),
        str(item.get("original_title") or ""),
        str(item.get("spanish_title") or ""),
        str(item.get("english_title") or ""),
        *normalize_tags(item.get("alternative_titles")),
        str(item.get("wikipedia_title") or ""),
        str(item.get("local_name") or ""),
        *local_values,
    ]


def title_match_keys_for_item(item: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys(key for key in (title_match_key(value) for value in title_values_for_item(item)) if key))


def title_similarity(left: str, right: str) -> float:
    left_terms = set(left.split())
    right_terms = set(right.split())
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / max(len(left_terms), len(right_terms))


def same_catalog_item(item: dict[str, Any], item_id: str, item_url: str, title: str, year: str, local_name: str) -> bool:
    if item_id and str(item.get("id") or "") == item_id:
        return True
    target_url = canonical_url(item_url)
    if target_url and canonical_url(str(item.get("url") or "")) == target_url:
        return True
    target_title = title_match_key(title or local_name)
    item_year = str(item.get("year") or "")
    if target_title and target_title in title_match_keys_for_item(item) and (not year or not item_year or item_year == year):
        return True
    item_local = normalize_path_text(str(item.get("local_name") or item.get("local_path") or ""))
    target_local = normalize_path_text(local_name)
    return bool(item_local and target_local and item_local == target_local)


def possible_duplicate_candidates(items: list[dict[str, Any]], item: dict[str, Any]) -> list[dict[str, Any]]:
    item_titles = title_match_keys_for_item(item)
    item_year = str(item.get("year") or "")
    candidates: list[dict[str, Any]] = []
    for existing in items:
        existing_titles = title_match_keys_for_item(existing)
        existing_year = str(existing.get("year") or "")
        exact = bool(set(existing_titles) & set(item_titles))
        similar = any(title_similarity(left, right) >= 0.75 for left in existing_titles for right in item_titles)
        if not item_titles or not existing_titles or (not exact and not similar):
            continue
        if item_year and existing_year and item_year != existing_year:
            continue
        candidates.append(
            {
                "id": existing.get("id", ""),
                "title": existing.get("title", ""),
                "year": existing.get("year", ""),
                "source": existing.get("source", ""),
                "url": existing.get("url", ""),
                "en_catalogo": existing.get("en_catalogo", False),
                "local_name": existing.get("local_name", ""),
            }
        )
    return candidates


def annotate_duplicate_items(items: list[dict[str, Any]]) -> None:
    if not items:
        return
    parents = list(range(len(items)))
    owners: dict[str, int] = {}

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for index, item in enumerate(items):
        for field in ("_duplicate_count", "_duplicate_ids", "_duplicate_reason"):
            item.pop(field, None)
        keys = [f"url:{url}" for url in sorted(external_urls(item))]
        year = str(item.get("year") or "").strip()
        if year:
            keys.extend(f"title-year:{title}:{year}" for title in title_match_keys_for_item(item))
        for key in keys:
            union(index, owners[key]) if key in owners else owners.setdefault(key, index)

    groups: dict[int, list[int]] = {}
    for index in range(len(items)):
        groups.setdefault(root(index), []).append(index)
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        ids = [str(items[index].get("id") or "") for index in indexes]
        for index in indexes:
            item = items[index]
            item["_duplicate_count"] = len(indexes) - 1
            item["_duplicate_ids"] = [value for value in ids if value and value != str(item.get("id") or "")]
            item["_duplicate_reason"] = "misma URL o titulo/ano"


def metadata_source_record(source: str, url: str, inferred: bool, updated_at: str = "") -> dict[str, Any]:
    return {
        "source": source or "unknown",
        "url": url,
        "updated_at": updated_at or datetime.now(timezone.utc).isoformat(),
        "inferred": inferred,
    }


def metadata_origin(item: dict[str, Any]) -> tuple[str, str]:
    source = str(item.get("source") or "").strip()
    url = str(item.get("url") or "").strip()
    source_urls = {
        "wikipedia": str(item.get("wikipedia_url") or ""),
        "imdb": str(item.get("imdb_url") or ""),
        "filmaffinity": str(item.get("filmaffinity_url") or ""),
    }
    if source in source_urls:
        return source, source_urls[source] or url
    if source:
        return source, url
    for known_source, known_url in source_urls.items():
        if known_url:
            return known_source, known_url
    return "legacy", url


def ensure_metadata_sources(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    sources = normalize_metadata_sources(item.get("metadata_sources"))
    source, url = metadata_origin(item)
    for field in METADATA_FIELDS:
        value = item.get(field)
        if field not in sources and value not in (None, "", [], {}):
            sources[field] = metadata_source_record(source, url, True, str(item.get("added_at") or ""))
    return sources


def merge_metadata_field(existing: dict[str, Any], incoming: dict[str, Any], field: str) -> None:
    if field in normalize_locked_fields(existing.get("locked_fields")):
        return
    before = existing.get(field)
    incoming_value = incoming.get(field)
    after: Any = merge_lists(normalize_tags(before), normalize_tags(incoming_value)) if field in LIST_FIELDS else before or incoming_value
    if after == before:
        return
    existing[field] = after
    incoming_sources = ensure_metadata_sources(incoming)
    sources = ensure_metadata_sources(existing)
    if field in incoming_sources:
        sources[field] = dict(incoming_sources[field])
    else:
        source, url = metadata_origin(incoming)
        sources[field] = metadata_source_record(source, url, False)
    existing["metadata_sources"] = sources


def is_wikipedia_item(item: dict[str, Any]) -> bool:
    return (
        str(item.get("source") or "") == "wikipedia"
        or "wikipedia.org" in canonical_url(str(item.get("url") or ""))
        or "wikipedia.org" in canonical_url(str(item.get("wikipedia_url") or ""))
    )


def merge_into_existing(items: list[dict[str, Any]], incoming: dict[str, Any], target_id: str) -> bool:
    incoming = normalize_item(incoming)
    for existing in items:
        if str(existing.get("id") or "") != target_id:
            continue
        incoming_url = str(incoming.get("url") or "")
        incoming_source_field = source_url_field(str(incoming.get("source") or ""), incoming_url)
        existing["url"] = existing.get("url") or incoming_url
        existing["source"] = incoming.get("source") if existing.get("source") in {"", "local_files"} else existing.get("source")
        for field in METADATA_FIELDS:
            if field != "kind":
                merge_metadata_field(existing, incoming, field)
        existing["kind"] = normalize_kind(existing.get("kind") or incoming.get("kind"))
        statuses = {normalize_status(existing.get("status")), normalize_status(incoming.get("status"))}
        existing["status"] = "watched" if "watched" in statuses else "to_watch"
        existing["watched_at"] = existing.get("watched_at") or incoming.get("watched_at", "")
        existing["rating"] = normalize_rating(existing.get("rating")) or normalize_rating(incoming.get("rating"))
        if incoming_source_field and incoming_url:
            existing[incoming_source_field] = existing.get(incoming_source_field) or incoming_url
        for field in ("wikipedia_url", "imdb_url", "filmaffinity_url"):
            existing[field] = existing.get(field) or incoming.get(field, "")
        if not existing.get("wikipedia_url") and is_wikipedia_item(incoming):
            existing["wikipedia_url"] = incoming_url
        if not existing.get("wikipedia_title") and is_wikipedia_item(incoming):
            merge_metadata_field(existing, {**incoming, "wikipedia_title": incoming.get("title", "")}, "wikipedia_title")
        existing["en_catalogo"] = bool(existing.get("en_catalogo") or incoming.get("en_catalogo"))
        existing["local_files"] = merge_local_files(
            normalize_local_files(existing.get("local_files"), existing.get("local_name", ""), existing.get("local_path", "")),
            normalize_local_files(incoming.get("local_files"), incoming.get("local_name", ""), incoming.get("local_path", "")),
        )
        for field in ("local_name", "local_path", "notes", "review", "added_at"):
            existing[field] = existing.get(field) or incoming.get(field, "")
        existing["tags"] = sorted(set(normalize_tags(existing.get("tags")) + normalize_tags(incoming.get("tags"))))
        existing["locked_fields"] = normalize_locked_fields(existing.get("locked_fields"))
        existing["metadata_sources"] = ensure_metadata_sources(existing)
        return True
    return False
