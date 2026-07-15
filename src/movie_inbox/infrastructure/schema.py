#!/usr/bin/env python3
"""Shared catalog schema and persistence helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from movie_inbox.domain.metadata import (
    METADATA_FIELDS,
    merge_local_files,
    normalize_local_files,
    normalize_locked_fields,
    normalize_metadata_sources,
    normalize_non_negative_int,
)
from movie_inbox.domain.normalization import VALID_KINDS, VALID_STATUSES, normalize_bool, normalize_kind, normalize_status


SCHEMA_VERSION = 4
BACKUP_LIMIT = 10
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

REQUIRED_ITEM_FIELDS = {
    "id", "title", "kind", "status", "en_catalogo", "local_files",
    "metadata_sources", "locked_fields",
}
LOCAL_FILE_FIELDS = {
    "path", "name", "size_bytes", "modified_at", "part", "library_id",
    "relative_path", "fingerprint", "last_seen_at", "available",
}
LIST_ITEM_FIELDS = {"alternative_titles", "genres", "directors", "writers", "cast", "tags", "locked_fields"}
STRING_ITEM_FIELDS = set(CATALOG_FIELDS) - LIST_ITEM_FIELDS - {
    "rating", "en_catalogo", "local_files", "metadata_sources",
}


class CatalogSchemaError(ValueError):
    """Raised when a catalog document does not satisfy a supported schema."""


class UnsupportedCatalogVersion(CatalogSchemaError):
    """Raised when a catalog is newer than this application can safely read."""


def catalog_document(items: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean_items = [
        {key: plain_value(value) for key, value in item.items() if not str(key).startswith("_")}
        for item in items
    ]
    document = {"schema_version": SCHEMA_VERSION, "items": clean_items}
    validate_catalog_document(document)
    return document


def extract_catalog_items(raw: Any) -> list[dict[str, Any]]:
    document = migrate_catalog_document(raw)
    return [dict(row) for row in document["items"]]


def migrate_catalog_document(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list):
        document: dict[str, Any] = {"schema_version": 1, "items": copy_item_rows(raw, "legacy list")}
    elif isinstance(raw, Mapping):
        if "schema_version" not in raw:
            if "items" not in raw:
                raise CatalogSchemaError("Legacy catalog object must contain an 'items' array")
            document = {"schema_version": 1, "items": copy_item_rows(raw.get("items"), "legacy object")}
        else:
            version = raw.get("schema_version")
            if not isinstance(version, int) or isinstance(version, bool):
                raise CatalogSchemaError("schema_version must be an integer")
            if version > SCHEMA_VERSION:
                raise UnsupportedCatalogVersion(
                    f"Catalog schema v{version} is newer than supported v{SCHEMA_VERSION}"
                )
            if version < 1:
                raise CatalogSchemaError(f"Unsupported catalog schema version: {version}")
            extra = set(raw) - {"schema_version", "items"}
            if extra:
                raise CatalogSchemaError(
                    f"Catalog v{version} contains unsupported root fields: {', '.join(sorted(extra))}"
                )
            document = {"schema_version": version, "items": copy_item_rows(raw.get("items"), f"v{version}")}
    else:
        raise CatalogSchemaError("Catalog root must be an object or a legacy array")

    migrations = {1: v1_to_v2, 2: v2_to_v3, 3: v3_to_v4}
    while document["schema_version"] < SCHEMA_VERSION:
        migration = migrations.get(document["schema_version"])
        if migration is None:
            raise CatalogSchemaError(f"Missing migration from schema v{document['schema_version']}")
        document = migration(document)
    validate_catalog_document(document)
    return document


def copy_item_rows(value: Any, source: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise CatalogSchemaError(f"Catalog {source} must contain an 'items' array")
    rows: list[dict[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise CatalogSchemaError(f"Catalog {source} item {index} must be an object")
        rows.append(dict(row))
    return rows


def v1_to_v2(document: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in copy_item_rows(document.get("items"), "v1"):
        item = normalize_legacy_item(row)
        rows.append(item)
    return {"schema_version": 2, "items": rows}


def v2_to_v3(document: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in copy_item_rows(document.get("items"), "v2"):
        item = normalize_legacy_item(row)
        item["local_files"] = normalize_local_files(
            item.get("local_files"), str(item.get("local_name") or ""), str(item.get("local_path") or "")
        )
        item["metadata_sources"] = normalize_metadata_sources(item.get("metadata_sources"))
        item["locked_fields"] = normalize_locked_fields(item.get("locked_fields"))
        rows.append(item)
    return {"schema_version": 3, "items": rows}


def v3_to_v4(document: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in copy_item_rows(document.get("items"), "v3"):
        item = normalize_legacy_item(row)
        item["local_files"] = normalize_local_files(
            item.get("local_files"), str(item.get("local_name") or ""), str(item.get("local_path") or "")
        )
        item["metadata_sources"] = normalize_metadata_sources(item.get("metadata_sources"))
        item["locked_fields"] = normalize_locked_fields(item.get("locked_fields"))
        rows.append(item)
    return {"schema_version": 4, "items": rows}


def validate_catalog_document(document: Mapping[str, Any]) -> None:
    extra = set(document) - {"schema_version", "items"}
    if extra:
        raise CatalogSchemaError(f"Catalog root contains unsupported fields: {', '.join(sorted(extra))}")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise CatalogSchemaError(f"Catalog must use schema_version {SCHEMA_VERSION}")
    rows = document.get("items")
    if not isinstance(rows, list):
        raise CatalogSchemaError("Catalog 'items' must be an array")
    for index, row in enumerate(rows):
        validate_catalog_item(row, index)


def validate_catalog_item(row: Any, index: int = 0) -> None:
    if not isinstance(row, Mapping):
        raise CatalogSchemaError(f"items[{index}] must be an object")
    missing = sorted(REQUIRED_ITEM_FIELDS - set(row))
    if missing:
        raise CatalogSchemaError(f"items[{index}] is missing required fields: {', '.join(missing)}")
    for field in STRING_ITEM_FIELDS:
        if field in row and not isinstance(row.get(field), str):
            raise CatalogSchemaError(f"items[{index}].{field} must be a string")
    if row.get("kind") not in VALID_KINDS:
        raise CatalogSchemaError(f"items[{index}].kind is invalid")
    if row.get("status") not in VALID_STATUSES:
        raise CatalogSchemaError(f"items[{index}].status is invalid")
    if not isinstance(row.get("en_catalogo"), bool):
        raise CatalogSchemaError(f"items[{index}].en_catalogo must be boolean")
    rating = row.get("rating", 0)
    if not isinstance(rating, int) or isinstance(rating, bool) or not 0 <= rating <= 10:
        raise CatalogSchemaError(f"items[{index}].rating must be an integer from 0 to 10")
    for field in LIST_ITEM_FIELDS:
        if field in row and not isinstance(row.get(field), list):
            raise CatalogSchemaError(f"items[{index}].{field} must be an array")
        if field in row and any(not isinstance(value, str) for value in row.get(field, [])):
            raise CatalogSchemaError(f"items[{index}].{field} must contain only strings")
    locked_fields = row.get("locked_fields", [])
    if len(locked_fields) != len(set(locked_fields)) or any(field not in METADATA_FIELDS for field in locked_fields):
        raise CatalogSchemaError(f"items[{index}].locked_fields contains invalid or duplicate values")
    validate_local_files(row.get("local_files"), index)
    validate_metadata_sources(row.get("metadata_sources"), index)


def validate_local_files(value: Any, item_index: int) -> None:
    if not isinstance(value, list):
        raise CatalogSchemaError(f"items[{item_index}].local_files must be an array")
    for file_index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise CatalogSchemaError(f"items[{item_index}].local_files[{file_index}] must be an object")
        extra = sorted(set(row) - LOCAL_FILE_FIELDS)
        if extra:
            raise CatalogSchemaError(
                f"items[{item_index}].local_files[{file_index}] contains unsupported fields: {', '.join(extra)}"
            )
        missing = sorted(LOCAL_FILE_FIELDS - set(row))
        if missing:
            raise CatalogSchemaError(
                f"items[{item_index}].local_files[{file_index}] is missing: {', '.join(missing)}"
            )
        if (
            not isinstance(row.get("size_bytes"), int)
            or isinstance(row.get("size_bytes"), bool)
            or row.get("size_bytes", 0) < 0
        ):
            raise CatalogSchemaError(
                f"items[{item_index}].local_files[{file_index}].size_bytes must be a non-negative integer"
            )
        if not isinstance(row.get("available"), bool):
            raise CatalogSchemaError(f"items[{item_index}].local_files[{file_index}].available must be boolean")
        for field in LOCAL_FILE_FIELDS - {"size_bytes", "available"}:
            if not isinstance(row.get(field), str):
                raise CatalogSchemaError(f"items[{item_index}].local_files[{file_index}].{field} must be string")


def validate_metadata_sources(value: Any, item_index: int) -> None:
    if not isinstance(value, Mapping):
        raise CatalogSchemaError(f"items[{item_index}].metadata_sources must be an object")
    for field, row in value.items():
        if field not in METADATA_FIELDS or not isinstance(row, Mapping):
            raise CatalogSchemaError(f"items[{item_index}].metadata_sources.{field} is invalid")
        required = {"source", "url", "updated_at", "inferred"}
        if set(row) != required:
            raise CatalogSchemaError(
                f"items[{item_index}].metadata_sources.{field} must contain source, url, updated_at and inferred"
            )
        if not isinstance(row.get("source"), str) or not row.get("source"):
            raise CatalogSchemaError(f"items[{item_index}].metadata_sources.{field}.source is required")
        for string_field in ("url", "updated_at"):
            if not isinstance(row.get(string_field), str):
                raise CatalogSchemaError(
                    f"items[{item_index}].metadata_sources.{field}.{string_field} must be string"
                )
        if not isinstance(row.get("inferred"), bool):
            raise CatalogSchemaError(f"items[{item_index}].metadata_sources.{field}.inferred must be boolean")


def plain_value(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): plain_value(row) for key, row in value.items()}
    if isinstance(value, list):
        return [plain_value(row) for row in value]
    return value


def normalize_legacy_item(row: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["id"] = str(item.get("id") or "")
    item["title"] = str(item.get("title") or item.get("local_name") or "")
    item["kind"] = normalize_kind(item.get("kind"))
    item["status"] = normalize_status(item.get("status"))
    item["en_catalogo"] = normalize_bool(item.get("en_catalogo"), default=False)
    item["rating"] = min(10, normalize_non_negative_int(item.get("rating")))
    for field in ("watched_at", "review", "original_title", "spanish_title", "english_title"):
        item[field] = str(item.get(field) or "")
    for field in ("alternative_titles", "genres", "directors", "writers", "cast", "tags"):
        value = item.get(field)
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",") if part.strip()]
        item[field] = list(value) if isinstance(value, list) else []
    return item


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

