"""Rules for removing one external source without touching personal catalog data."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from movie_inbox.domain.catalog import (
    external_source_name,
    metadata_source_record,
    normalize_item,
    source_url_field,
)
from movie_inbox.domain.metadata import (
    METADATA_FIELDS,
    compose_metadata_sources,
    metadata_source_names,
    normalize_locked_fields,
    normalize_metadata_sources,
)
from movie_inbox.domain.releases import normalize_release_dates

TMDB_SOURCE = "tmdb"
_LIST_FIELDS = {
    "alternative_titles",
    "countries",
    "original_languages",
    "producers",
    "composers",
    "genres",
    "directors",
    "writers",
    "cast",
}
_REMAINING_LINK_SOURCES = ("wikipedia", "imdb", "filmaffinity", "jikan")


def retire_tmdb_metadata(item: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a purged copy and an audit-safe per-item report.

    A field is removed only when TMDb is its sole recorded contributor. Composite
    provenance keeps the value and drops TMDb from the contributor label. Locked
    fields always win. Release dates have row-level provenance, so their TMDb rows
    can be removed without discarding dates supplied by another source.
    """
    original = normalize_item(item).to_dict()
    updated = normalize_item(item).to_dict()
    sources = normalize_metadata_sources(updated.get("metadata_sources"))
    locked = set(normalize_locked_fields(updated.get("locked_fields")))
    removed: list[str] = []
    preserved_locked: list[str] = []
    preserved_shared: list[str] = []
    removed_release_dates = 0

    for field in METADATA_FIELDS:
        record = sources.get(field)
        contributors = metadata_source_names(record)
        value = updated.get(field)
        tmdb_release_rows = (
            [
                row
                for row in normalize_release_dates(value)
                if str(row.get("source") or "").casefold() == TMDB_SOURCE
            ]
            if field == "release_dates"
            else []
        )
        if TMDB_SOURCE not in contributors and not tmdb_release_rows:
            continue
        if field in locked:
            preserved_locked.append(field)
            continue

        other_contributors = [source for source in contributors if source != TMDB_SOURCE]
        if field == "release_dates":
            releases = normalize_release_dates(value)
            remaining = [
                row for row in releases if str(row.get("source") or "").casefold() != TMDB_SOURCE
            ]
            removed_release_dates += len(releases) - len(remaining)
            if other_contributors or remaining:
                updated[field] = remaining
                remaining_sources = [
                    str(row.get("source") or "") for row in remaining if row.get("source")
                ]
                source = compose_metadata_sources(
                    "+".join(other_contributors), "+".join(remaining_sources)
                )
                if source:
                    sources[field] = _without_tmdb(record, source)
                else:
                    sources.pop(field, None)
                preserved_shared.append(field)
            else:
                updated[field] = []
                sources.pop(field, None)
                removed.append(field)
            continue

        if other_contributors:
            sources[field] = _without_tmdb(record, "+".join(other_contributors))
            preserved_shared.append(field)
            continue

        updated[field] = _empty_metadata_value(field)
        sources.pop(field, None)
        removed.append(field)

    primary_reference_removed = False
    if (
        not updated.get("tmdb_url")
        and external_source_name(str(updated.get("url") or "")) == TMDB_SOURCE
    ):
        primary_reference_removed = True
        updated["url"] = ""
        updated["source"] = ""
        for source in _REMAINING_LINK_SOURCES:
            field = source_url_field(source)
            url = str(updated.get(field) or "")
            if url:
                updated["source"] = source
                updated["url"] = url
                break
        if not updated["source"]:
            updated["source"] = "local_files" if updated.get("local_files") else "retired"

    if not str(updated.get("title") or "").strip():
        updated["title"] = _replacement_title(updated)
        sources["title"] = metadata_source_record("system", "", False)
    if not str(updated.get("kind") or "").strip():
        updated["kind"] = "pelicula"
        sources["kind"] = metadata_source_record("system", "", False)
    updated["metadata_sources"] = sources
    normalized = normalize_item(updated).to_dict()
    changed = normalized != original
    return normalized, {
        "changed": changed,
        "removed_fields": sorted(set(removed)),
        "preserved_locked_fields": sorted(set(preserved_locked)),
        "preserved_shared_fields": sorted(set(preserved_shared)),
        "removed_release_dates": removed_release_dates,
        "primary_reference_removed": primary_reference_removed,
    }


def _without_tmdb(record: Mapping[str, Any] | None, source: str) -> dict[str, Any]:
    row = dict(record or {})
    row["source"] = source
    if external_source_name(str(row.get("url") or "")) == TMDB_SOURCE:
        row["url"] = ""
    return row


def _empty_metadata_value(field: str) -> Any:
    if field in _LIST_FIELDS or field == "release_dates":
        return []
    if field == "duration_minutes":
        return None
    return ""


def _replacement_title(item: Mapping[str, Any]) -> str:
    local_name = str(item.get("local_name") or "").strip()
    return local_name or "Obra sin metadata"


__all__ = ["TMDB_SOURCE", "retire_tmdb_metadata"]
