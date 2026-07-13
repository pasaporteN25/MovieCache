#!/usr/bin/env python3
"""Shared catalog schema and persistence helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 3
BACKUP_LIMIT = 10
VALID_KINDS = ("pelicula", "serie", "anime", "documental")
VALID_STATUSES = ("to_watch", "watched")
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

CATALOG_FIELDS = [
    "id",
    "url",
    "source",
    "title",
    "original_title",
    "spanish_title",
    "english_title",
    "alternative_titles",
    "kind",
    "status",
    "watched_at",
    "rating",
    "year",
    "description",
    "wikipedia_url",
    "imdb_url",
    "filmaffinity_url",
    "wikipedia_title",
    "wikidata_id",
    "genres",
    "directors",
    "writers",
    "cast",
    "page_image",
    "wikipedia_extract",
    "en_catalogo",
    "local_files",
    "local_name",
    "local_path",
    "tags",
    "notes",
    "review",
    "metadata_sources",
    "locked_fields",
    "added_at",
]


def catalog_document(items: list[dict[str, Any]]) -> dict[str, Any]:
    clean_items = [
        {key: value for key, value in item.items() if not str(key).startswith("_")}
        for item in items
    ]
    return {"schema_version": SCHEMA_VERSION, "items": clean_items}


def extract_catalog_items(raw: Any) -> list[dict[str, Any]]:
    rows = raw if isinstance(raw, list) else raw.get("items", []) if isinstance(raw, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def normalize_local_files(value: Any, legacy_name: str = "", legacy_path: str = "") -> list[dict[str, Any]]:
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = []

    rows = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if isinstance(row, str):
            row = {"path": row, "name": Path(row).name}
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or row.get("local_path") or "").strip()
        name = str(row.get("name") or row.get("local_name") or (Path(path).name if path else "")).strip()
        if not path and not name:
            continue
        key = (path or name).replace("\\", "/").casefold()
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
            }
        )
    return normalized


def merge_local_files(primary: Any, secondary: Any) -> list[dict[str, Any]]:
    return normalize_local_files(normalize_local_files(primary) + normalize_local_files(secondary))


def normalize_metadata_sources(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for field, row in value.items():
        if field not in METADATA_FIELDS or not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip()
        if not source:
            continue
        normalized[field] = {
            "source": source,
            "url": str(row.get("url") or "").strip(),
            "updated_at": str(row.get("updated_at") or "").strip(),
            "inferred": bool(row.get("inferred", False)),
        }
    return normalized


def normalize_locked_fields(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    rows = value if isinstance(value, list) else []
    return sorted({str(field) for field in rows if str(field) in METADATA_FIELDS})


def atomic_write_json(path: Path, payload: Any, backup_limit: int = BACKUP_LIMIT) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        backup_json_file(path, backup_limit)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def backup_json_file(path: Path, limit: int = BACKUP_LIMIT) -> Path | None:
    path = Path(path)
    if not path.exists() or path.suffix.lower() != ".json":
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = path.with_name(f"{path.stem}.{stamp}.bak{path.suffix}")
    shutil.copy2(path, backup_path)
    backups = sorted(
        path.parent.glob(f"{path.stem}.*.bak{path.suffix}"),
        key=lambda candidate: candidate.stat().st_mtime_ns,
        reverse=True,
    )
    for old_backup in backups[max(1, limit) :]:
        try:
            old_backup.unlink()
        except OSError:
            pass
    return backup_path


def normalize_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
