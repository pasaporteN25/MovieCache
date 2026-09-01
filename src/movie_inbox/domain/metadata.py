"""Domain rules for local files and field-level metadata provenance."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from movie_inbox.domain.normalization import normalize_bool

METADATA_FIELDS = (
    "title",
    "original_title",
    "spanish_title",
    "english_title",
    "alternative_titles",
    "kind",
    "year",
    "release_dates",
    "description",
    "wikipedia_url",
    "imdb_url",
    "filmaffinity_url",
    "myanimelist_url",
    "tmdb_url",
    "wikipedia_title",
    "wikidata_id",
    "duration_minutes",
    "countries",
    "original_languages",
    "producers",
    "composers",
    "genres",
    "directors",
    "writers",
    "cast",
    "page_image",
    "backdrop_image",
    "tmdb_id",
    "mal_id",
    "wikipedia_extract",
)


def normalize_local_files(
    value: Any, legacy_name: str = "", legacy_path: str = ""
) -> list[dict[str, Any]]:
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = []

    rows = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_row in rows:
        row: Any = raw_row
        if isinstance(row, str):
            row = {"path": row, "name": Path(row).name}
        if not isinstance(row, Mapping):
            continue
        path = str(row.get("path") or row.get("local_path") or "").strip()
        name = str(
            row.get("name") or row.get("local_name") or (Path(path).name if path else "")
        ).strip()
        library_id = str(row.get("library_id") or "").strip()
        relative_path = str(row.get("relative_path") or path).strip().replace("\\", "/")
        if not path and not name:
            continue
        key = f"{library_id}:{relative_path or path or name}".casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "path": path,
                "name": name,
                "size_bytes": normalize_non_negative_int(row.get("size_bytes")),
                "modified_at": str(row.get("modified_at") or "").strip(),
                "part": str(row.get("part") or "").strip(),
                "library_id": library_id,
                "relative_path": relative_path,
                "fingerprint": str(row.get("fingerprint") or "").strip(),
                "last_seen_at": str(row.get("last_seen_at") or "").strip(),
                "available": normalize_bool(row.get("available", True), default=True),
            }
        )

    legacy_path = str(legacy_path or "").strip()
    legacy_name = str(legacy_name or (Path(legacy_path).name if legacy_path else "")).strip()
    if legacy_path:
        legacy_key = legacy_path.replace("\\", "/").casefold()
        legacy_exists = any(
            str(row.get("path") or "").replace("\\", "/").casefold() == legacy_key
            for row in normalized
        )
    else:
        legacy_key = legacy_name.casefold()
        legacy_exists = any(
            str(row.get("name") or "").casefold() == legacy_key for row in normalized
        )
    if legacy_key and not legacy_exists:
        normalized.append(
            {
                "path": legacy_path,
                "name": legacy_name,
                "size_bytes": 0,
                "modified_at": "",
                "part": "",
                "library_id": "",
                "relative_path": legacy_path.replace("\\", "/"),
                "fingerprint": "",
                "last_seen_at": "",
                "available": True,
            }
        )
    return normalized


def merge_local_files(primary: Any, secondary: Any) -> list[dict[str, Any]]:
    return normalize_local_files(normalize_local_files(primary) + normalize_local_files(secondary))


def normalize_metadata_sources(value: Any) -> dict[str, dict[str, Any]]:
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for field, row in value.items():
        if field not in METADATA_FIELDS or not isinstance(row, Mapping):
            continue
        source = str(row.get("source") or "").strip()
        if not source:
            continue
        normalized[str(field)] = {
            "source": source,
            "url": str(row.get("url") or "").strip(),
            "updated_at": str(row.get("updated_at") or "").strip(),
            "inferred": normalize_bool(row.get("inferred", False)),
        }
    return normalized


def metadata_source_names(value: Any) -> tuple[str, ...]:
    """Return the ordered contributors encoded in a provenance record.

    Provenance remains backward compatible with the existing compact `source`
    string. A `+` joins independent contributors (for example
    `jikan+anime_offline_database`) and is deliberately not an authority order.
    """
    source = str(value.get("source") if isinstance(value, Mapping) else value or "")
    return tuple(dict.fromkeys(part.strip() for part in source.split("+") if part.strip()))


def compose_metadata_sources(*values: Any) -> str:
    names: list[str] = []
    for value in values:
        for source in metadata_source_names(value):
            if source not in names:
                names.append(source)
    return "+".join(names)


def normalize_locked_fields(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    rows = value if isinstance(value, list) else []
    return sorted({str(field) for field in rows if str(field) in METADATA_FIELDS})


def normalize_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_optional_positive_int(value: Any) -> int | None:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def normalize_external_positive_id(value: Any) -> str:
    """Canonical string form for numeric IDs owned by an external source."""
    try:
        normalized = int(str(value or "").strip())
    except (TypeError, ValueError):
        return ""
    return str(normalized) if normalized > 0 else ""
