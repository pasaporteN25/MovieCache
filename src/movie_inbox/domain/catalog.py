#!/usr/bin/env python3
"""Shared catalog normalization, matching, duplicate and merge rules."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from movie_inbox.domain.curation import (
    curation_item_reference,
    duplicate_decision_status,
    normalize_duplicate_decisions,
    normalize_link_curation_status,
)
from movie_inbox.domain.metadata import (
    METADATA_FIELDS,
    merge_local_files,
    normalize_local_files,
    normalize_locked_fields,
    normalize_metadata_sources,
)
from movie_inbox.domain.models import CatalogItem
from movie_inbox.domain.normalization import (
    normalize_bool,
    normalize_kind,
    normalize_rating,
    normalize_status,
)
from movie_inbox.domain.releases import merge_release_dates, normalize_release_dates
from movie_inbox.domain.titles import infer_kind_from_text, looks_like_external_id

KNOWN_LINK_HOSTS = {
    "wikipedia": "wikipedia.org",
    "imdb": "imdb.com",
    "filmaffinity": "filmaffinity.com",
}
LIST_FIELDS = {"alternative_titles", "genres", "directors", "writers", "cast"}


def normalize_item(row: Mapping[str, Any]) -> CatalogItem:
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
    item["alternative_titles"] = normalize_tags(
        item.get("alternative_titles") or item.get("alternativeTitles")
    )
    item["genres"] = normalize_tags(item.get("genres") or item.get("genre"))
    item["directors"] = normalize_tags(item.get("directors") or item.get("director"))
    item["writers"] = normalize_tags(
        item.get("writers") or item.get("writer") or item.get("screenwriters")
    )
    item["cast"] = normalize_tags(item.get("cast") or item.get("actors") or item.get("actor"))
    item["release_dates"] = normalize_release_dates(
        item.get("release_dates") or item.get("releaseDates")
    )
    if not str(item.get("year") or "").strip() and item["release_dates"]:
        item["year"] = str(item["release_dates"][0]["date"])[:4]
    item["locked_fields"] = normalize_locked_fields(item.get("locked_fields"))
    item["metadata_sources"] = normalize_metadata_sources(item.get("metadata_sources"))
    alias_values = {
        "original_title": item.get("original_title") or item.get("originalTitle"),
        "spanish_title": item.get("spanish_title") or item.get("spanishTitle"),
        "english_title": item.get("english_title") or item.get("englishTitle"),
        "watched_at": item.get("watched_at") or item.get("watchedAt"),
    }
    item.update(alias_values)
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
        "backdrop_image",
        "tmdb_id",
        "wikipedia_extract",
        "local_name",
        "local_path",
        "notes",
        "review",
        "curation_updated_at",
    }
    for field in string_fields:
        item[field] = str(item.get(field) or "")
    for field in LIST_FIELDS:
        item[field] = normalize_tags(item.get(field))

    if looks_like_external_id(item["title"]):
        replacement_title = next(
            (
                value
                for value in [
                    item["wikipedia_title"],
                    item["spanish_title"],
                    item["original_title"],
                    item["english_title"],
                    *item["alternative_titles"],
                    item["local_name"],
                ]
                if value and not looks_like_external_id(value)
            ),
            "",
        )
        if replacement_title:
            item["title"] = replacement_title
    for field in ("original_title", "spanish_title", "english_title"):
        if looks_like_external_id(item[field]):
            item[field] = ""

    item["kind"] = normalize_kind(item.get("kind"))
    inferred_kind = infer_kind_from_text(
        item["title"],
        item["description"],
        item["wikipedia_extract"],
    )
    if (
        item["kind"] == "pelicula"
        and inferred_kind in {"serie", "anime", "documental"}
        and "kind" not in item["locked_fields"]
    ):
        item["kind"] = inferred_kind
    item["status"] = normalize_status(item.get("status"))
    item["watched_at"] = normalize_date(item.get("watched_at"))
    item["rating"] = normalize_rating(item.get("rating"))
    item["en_catalogo"] = normalize_bool(item.get("en_catalogo"))
    item["link_curation_status"] = normalize_link_curation_status(
        item.get("link_curation_status"),
        linked=has_external_link(item),
    )
    item["duplicate_decisions"] = normalize_duplicate_decisions(item.get("duplicate_decisions"))
    if not item["id"]:
        seed = (
            item["url"]
            or item["local_path"]
            or item["local_name"]
            or f"{item['title']} {item['year']}".strip()
        )
        item["id"] = stable_id(seed) if seed else ""
    item["metadata_sources"] = ensure_metadata_sources(item)
    for alias in (
        "addedAt",
        "originalTitle",
        "spanishTitle",
        "englishTitle",
        "alternativeTitles",
        "watchedAt",
        "genre",
        "director",
        "writer",
        "screenwriters",
        "actors",
        "actor",
        "releaseDates",
    ):
        item.pop(alias, None)
    return CatalogItem.from_mapping(item)


def normalize_date(value: Any) -> str:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value or "").strip())
    return match.group(1) if match else ""


def today_date() -> str:
    return datetime.now().date().isoformat()


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


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def canonical_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        hostname = _normalized_hostname(parsed)
    except (UnicodeError, ValueError):
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        return ""
    if parsed.username or parsed.password:
        return ""
    try:
        port = parsed.port
    except ValueError:
        return ""
    host = hostname.removeprefix("www.")
    default_port = 443 if parsed.scheme.lower() == "https" else 80
    authority = f"[{host}]" if ":" in host else host
    if port and port != default_port:
        authority = f"{authority}:{port}"
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{authority}{path}"


def trusted_external_url(url: str) -> str:
    canonical = canonical_url(url)
    return canonical if external_source_name(canonical) else ""


def external_source_name(url: str) -> str:
    try:
        parsed = urlparse(str(url or ""))
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"} or parsed.username or parsed.password:
            return ""
        port = parsed.port
        default_port = 443 if scheme == "https" else 80
        if port and port != default_port:
            return ""
        hostname = _normalized_hostname(parsed).removeprefix("www.")
    except (UnicodeError, ValueError):
        return ""
    for source, expected_host in KNOWN_LINK_HOSTS.items():
        if hostname == expected_host or hostname.endswith(f".{expected_host}"):
            return source
    return ""


def _normalized_hostname(parsed: Any) -> str:
    hostname = parsed.hostname or ""
    if ":" in hostname:
        return hostname.lower().rstrip(".")
    return hostname.encode("idna").decode("ascii").lower().rstrip(".")


def source_url_field(source: str, url: str = "") -> str:
    source_name = str(source or "").strip().lower()
    if source_name not in KNOWN_LINK_HOSTS:
        source_name = external_source_name(url)
    if source_name:
        return f"{source_name}_url"
    return ""


def external_urls(item: Mapping[str, Any]) -> set[str]:
    urls = {
        trusted_external_url(str(item.get("url") or "")),
        trusted_external_url(str(item.get("wikipedia_url") or "")),
        trusted_external_url(str(item.get("imdb_url") or "")),
        trusted_external_url(str(item.get("filmaffinity_url") or "")),
    }
    return {url for url in urls if url}


def has_external_link(item: Mapping[str, Any]) -> bool:
    return bool(external_urls(item))


def linked_sources(item: Mapping[str, Any]) -> set[str]:
    """Which of the named sources (not the generic `url` field) have a trusted link."""
    return {
        source
        for source in KNOWN_LINK_HOSTS
        if trusted_external_url(str(item.get(source_url_field(source)) or ""))
    }


def external_link_coverage(item: Mapping[str, Any]) -> int:
    return len(linked_sources(item))


def title_match_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", html.unescape(value).lower())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = value.split()
    # A leading year-shaped token can be the title itself (1917, 1984 or
    # 2001: A Space Odyssey). Release years elsewhere remain filename noise.
    tokens = [
        token
        for index, token in enumerate(tokens)
        if index == 0 or not re.fullmatch(r"(?:19|20)\d{2}", token)
    ]
    return " ".join(tokens)


def normalize_path_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", html.unescape(value).lower())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"[\\/]+", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def title_values_for_item(item: Mapping[str, Any]) -> list[str]:
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


def title_match_keys_for_item(item: Mapping[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            key for key in (title_match_key(value) for value in title_values_for_item(item)) if key
        )
    )


def title_similarity(left: str, right: str) -> float:
    left_terms = set(left.split())
    right_terms = set(right.split())
    if not left_terms or not right_terms:
        return 0.0
    return len(left_terms & right_terms) / max(len(left_terms), len(right_terms))


def same_catalog_item(
    item: Mapping[str, Any], item_id: str, item_url: str, title: str, year: str, local_name: str
) -> bool:
    if item_id and str(item.get("id") or "") == item_id:
        return True
    target_url = canonical_url(item_url)
    if target_url and canonical_url(str(item.get("url") or "")) == target_url:
        return True
    target_title = title_match_key(title or local_name)
    item_year = str(item.get("year") or "")
    if (
        target_title
        and target_title in title_match_keys_for_item(item)
        and (not year or not item_year or item_year == year)
    ):
        return True
    item_local = normalize_path_text(str(item.get("local_name") or item.get("local_path") or ""))
    target_local = normalize_path_text(local_name)
    return bool(item_local and target_local and item_local == target_local)


def possible_duplicate_candidates(
    items: list[Mapping[str, Any]], item: Mapping[str, Any]
) -> list[dict[str, Any]]:
    item_titles = title_match_keys_for_item(item)
    item_year = str(item.get("year") or "")
    candidates: list[dict[str, Any]] = []
    for existing in items:
        existing_titles = title_match_keys_for_item(existing)
        existing_year = str(existing.get("year") or "")
        exact = bool(set(existing_titles) & set(item_titles))
        similarity = max(
            (title_similarity(left, right) for left in existing_titles for right in item_titles),
            default=0.0,
        )
        similar = similarity >= 0.75
        if not item_titles or not existing_titles or (not exact and not similar):
            continue
        year_mismatch = bool(item_year and existing_year and item_year != existing_year)
        if year_mismatch and not exact:
            continue
        if exact and year_mismatch:
            reason = "exact_title_year_mismatch"
        elif exact and (not item_year or not existing_year):
            reason = "exact_title_missing_year"
        elif exact:
            reason = "exact_title_year"
        else:
            reason = "similar_title_requires_review"
        candidates.append(
            {
                "id": existing.get("id", ""),
                "title": existing.get("title", ""),
                "original_title": existing.get("original_title", ""),
                "spanish_title": existing.get("spanish_title", ""),
                "english_title": existing.get("english_title", ""),
                "alternative_titles": existing.get("alternative_titles", []),
                "year": existing.get("year", ""),
                "kind": existing.get("kind", ""),
                "source": existing.get("source", ""),
                "url": existing.get("url", ""),
                "wikipedia_url": existing.get("wikipedia_url", ""),
                "imdb_url": existing.get("imdb_url", ""),
                "filmaffinity_url": existing.get("filmaffinity_url", ""),
                "wikidata_id": existing.get("wikidata_id", ""),
                "en_catalogo": existing.get("en_catalogo", False),
                "reason": reason,
                "score": round(similarity, 3),
            }
        )
    return sorted(
        candidates,
        key=lambda candidate: (
            str(candidate.get("reason") or "") == "exact_title_year",
            float(candidate.get("score") or 0),
        ),
        reverse=True,
    )


def catalog_membership(item: Mapping[str, Any], items: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify exact identity separately from conservative title candidates."""
    item_id = str(item.get("id") or "")
    urls = external_urls(item)
    for existing in items:
        same_id = bool(item_id and item_id == str(existing.get("id") or ""))
        same_url = bool(urls and urls & external_urls(existing))
        if same_id or same_url:
            return {
                "state": "present",
                "item_id": str(existing.get("id") or ""),
                "candidate_count": 0,
                "candidates": [],
            }
    candidates = possible_duplicate_candidates(items, item)
    if candidates:
        return {
            "state": "review",
            "item_id": "",
            "candidate_count": len(candidates),
            "candidates": candidates,
        }
    return {"state": "missing", "item_id": "", "candidate_count": 0, "candidates": []}


def annotate_duplicate_items(items: list[MutableMapping[str, Any]]) -> None:
    if not items:
        return
    parents = list(range(len(items)))
    owners: dict[str, int] = {}
    numeric_title_indexes: dict[str, list[int]] = {}

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
        for field in (
            "_curation_ref",
            "_duplicate_count",
            "_duplicate_ids",
            "_duplicate_refs",
            "_duplicate_deferred_count",
            "_duplicate_deferred_ids",
            "_duplicate_deferred_refs",
            "_duplicate_reason",
        ):
            item.pop(field, None)
        item["_curation_ref"] = curation_item_reference(item)
        keys = [f"url:{url}" for url in sorted(external_urls(item))]
        year = str(item.get("year") or "").strip()
        title_keys = title_match_keys_for_item(item)
        if year:
            keys.extend(f"title-year:{title}:{year}" for title in title_keys)
        for title in title_keys:
            if re.fullmatch(r"(?:19|20)\d{2}", title):
                numeric_title_indexes.setdefault(title, []).append(index)
        for key in keys:
            union(index, owners[key]) if key in owners else owners.setdefault(key, index)

    # Old scanner imports could mistake a numeric title (for example "1917")
    # for its release year. Surface only that narrow legacy pattern for review;
    # ordinary remakes with the same title and different years stay separate.
    for title, indexes in numeric_title_indexes.items():
        years = {str(items[index].get("year") or "").strip() for index in indexes}
        if len(indexes) > 1 and title in years and any(year and year != title for year in years):
            for index in indexes[1:]:
                union(indexes[0], index)

    groups: dict[int, list[int]] = {}
    for index in range(len(items)):
        groups.setdefault(root(index), []).append(index)
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            item = items[index]
            pending = [
                items[other_index]
                for other_index in indexes
                if other_index != index
                and duplicate_decision_status(item, items[other_index]) == "pending"
            ]
            deferred = [
                items[other_index]
                for other_index in indexes
                if other_index != index
                and duplicate_decision_status(item, items[other_index]) == "deferred"
            ]
            if pending:
                item["_duplicate_count"] = len(pending)
                item["_duplicate_ids"] = [str(other.get("id") or "") for other in pending]
                item["_duplicate_refs"] = [curation_item_reference(other) for other in pending]
            if deferred:
                item["_duplicate_deferred_count"] = len(deferred)
                item["_duplicate_deferred_ids"] = [str(other.get("id") or "") for other in deferred]
                item["_duplicate_deferred_refs"] = [
                    curation_item_reference(other) for other in deferred
                ]
            if pending or deferred:
                item["_duplicate_reason"] = "misma URL o titulo/ano"


def metadata_source_record(
    source: str, url: str, inferred: bool, updated_at: str = ""
) -> dict[str, Any]:
    return {
        "source": source or "unknown",
        "url": url,
        "updated_at": updated_at or datetime.now(UTC).isoformat(),
        "inferred": inferred,
    }


def metadata_origin(item: Mapping[str, Any]) -> tuple[str, str]:
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


def ensure_metadata_sources(item: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sources = normalize_metadata_sources(item.get("metadata_sources"))
    source, url = metadata_origin(item)
    for field in METADATA_FIELDS:
        value = item.get(field)
        if field not in sources and value not in (None, "", [], {}):
            sources[field] = metadata_source_record(
                source, url, True, str(item.get("added_at") or "")
            )
    return sources


def merge_metadata_field(
    existing: MutableMapping[str, Any], incoming: Mapping[str, Any], field: str
) -> None:
    if field in normalize_locked_fields(existing.get("locked_fields")):
        return
    before = existing.get(field)
    incoming_value = incoming.get(field)
    if field == "release_dates":
        after: Any = merge_release_dates(before, incoming_value)
    else:
        after = (
            merge_lists(normalize_tags(before), normalize_tags(incoming_value))
            if field in LIST_FIELDS
            else before or incoming_value
        )
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


def is_wikipedia_item(item: Mapping[str, Any]) -> bool:
    return (
        str(item.get("source") or "") == "wikipedia"
        or external_source_name(str(item.get("url") or "")) == "wikipedia"
        or external_source_name(str(item.get("wikipedia_url") or "")) == "wikipedia"
    )


def merge_into_existing(
    items: Sequence[MutableMapping[str, Any]], incoming: Mapping[str, Any], target_id: str
) -> bool:
    incoming_kind_explicit = bool(str(incoming.get("kind") or "").strip())
    incoming = normalize_item(incoming)
    for existing in items:
        if str(existing.get("id") or "") != target_id:
            continue
        incoming_url = str(incoming.get("url") or "")
        incoming_source_field = source_url_field(str(incoming.get("source") or ""), incoming_url)
        existing["url"] = existing.get("url") or incoming_url
        existing["source"] = (
            incoming.get("source")
            if existing.get("source") in {"", "local_files"}
            else existing.get("source")
        )
        for field in METADATA_FIELDS:
            if field != "kind":
                merge_metadata_field(existing, incoming, field)
        existing_kind = normalize_kind(existing.get("kind"))
        incoming_kind = normalize_kind(incoming.get("kind"))
        if (
            incoming_kind_explicit
            and "kind" not in normalize_locked_fields(existing.get("locked_fields"))
            and existing_kind == "pelicula"
            and incoming_kind in {"serie", "anime", "documental"}
        ):
            existing["kind"] = incoming_kind
            incoming_sources = ensure_metadata_sources(incoming)
            sources = ensure_metadata_sources(existing)
            if "kind" in incoming_sources:
                sources["kind"] = dict(incoming_sources["kind"])
            existing["metadata_sources"] = sources
        else:
            existing["kind"] = existing_kind
        statuses = {
            normalize_status(existing.get("status")),
            normalize_status(incoming.get("status")),
        }
        existing["status"] = "watched" if "watched" in statuses else "to_watch"
        existing["watched_at"] = existing.get("watched_at") or incoming.get("watched_at", "")
        existing["rating"] = normalize_rating(existing.get("rating")) or normalize_rating(
            incoming.get("rating")
        )
        if incoming_source_field and incoming_url:
            existing[incoming_source_field] = existing.get(incoming_source_field) or incoming_url
        for field in ("wikipedia_url", "imdb_url", "filmaffinity_url"):
            existing[field] = existing.get(field) or incoming.get(field, "")
        if not existing.get("wikipedia_url") and is_wikipedia_item(incoming):
            existing["wikipedia_url"] = incoming_url
        if not existing.get("wikipedia_title") and is_wikipedia_item(incoming):
            merge_metadata_field(
                existing,
                {**incoming, "wikipedia_title": incoming.get("title", "")},
                "wikipedia_title",
            )
        existing["en_catalogo"] = bool(existing.get("en_catalogo") or incoming.get("en_catalogo"))
        existing["local_files"] = merge_local_files(
            normalize_local_files(
                existing.get("local_files"),
                existing.get("local_name", ""),
                existing.get("local_path", ""),
            ),
            normalize_local_files(
                incoming.get("local_files"),
                incoming.get("local_name", ""),
                incoming.get("local_path", ""),
            ),
        )
        for field in ("local_name", "local_path", "notes", "review", "added_at"):
            existing[field] = existing.get(field) or incoming.get(field, "")
        existing["tags"] = sorted(
            set(normalize_tags(existing.get("tags")) + normalize_tags(incoming.get("tags")))
        )
        existing["locked_fields"] = normalize_locked_fields(existing.get("locked_fields"))
        existing["metadata_sources"] = ensure_metadata_sources(existing)
        existing["link_curation_status"] = normalize_link_curation_status(
            existing.get("link_curation_status"),
            linked=has_external_link(existing),
        )
        return True
    return False
