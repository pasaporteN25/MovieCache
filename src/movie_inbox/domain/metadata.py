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
    "description",
    "wikipedia_title",
    "wikidata_id",
    "genres",
    "directors",
    "writers",
    "cast",
    "page_image",
    "wikipedia_extract",
)


def normalize_local_files(value: Any, legacy_name: str = "", legacy_path: str = "") -> list[dict[str, Any]]:
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
        name = str(row.get("name") or row.get("local_name") or (Path(path).name if path else "")).strip()
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
    legacy_key = (legacy_path or legacy_name).replace("\\", "/").casefold()
    if legacy_key and legacy_key not in seen:
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
