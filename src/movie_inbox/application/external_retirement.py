"""Previewable and reversible removal of persisted external-source metadata."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from movie_inbox.application.curation_history import CurationHistoryRepository
from movie_inbox.application.curation_workflow import (
    CurationConflict,
    public_operation,
    transition_catalog_states,
)
from movie_inbox.application.repository import CatalogRepository
from movie_inbox.domain.curation import curation_timestamp
from movie_inbox.domain.external_retirement import retire_tmdb_metadata

RepositoryFactory = Callable[[Path], CatalogRepository]


class ExternalRetirementError(RuntimeError):
    """Base error for source-retirement operations."""


class ExternalRetirementConflict(ExternalRetirementError):
    """Raised when a preview is stale or a catalog cannot be changed safely."""


@dataclass(frozen=True)
class RetirementCatalog:
    reference: str
    path: Path
    writable: bool


class TmdbRetirementService:
    def __init__(
        self,
        repository_factory: RepositoryFactory,
        history: CurationHistoryRepository,
        catalogs: Callable[[], Sequence[RetirementCatalog]],
    ) -> None:
        self.repository_factory = repository_factory
        self.history_repository = history
        self.catalogs = catalogs

    def preview(self) -> dict[str, Any]:
        internal = self._preview_internal()
        return dict(internal["public"])

    def purge(self, expected_preview_id: str, *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("TMDb retirement requires confirmation")
        preview = self._preview_internal()
        public = preview["public"]
        if str(expected_preview_id or "") != public["preview_id"]:
            raise ExternalRetirementConflict("tmdb_retirement_preview_stale")
        if public["blocked_catalogs"]:
            raise ExternalRetirementConflict("tmdb_retirement_read_only_catalog")
        if not preview["before"]:
            raise ExternalRetirementConflict("tmdb_retirement_nothing_to_purge")

        operation = {
            "id": uuid.uuid4().hex,
            "action": "tmdb_retirement",
            "label": "Retirada de metadata TMDb",
            "status": "applied",
            "mode": "persistent",
            "created_at": curation_timestamp(),
            "undone_at": "",
            "summary": _operation_summary(public),
            "before": preview["before"],
            "after": preview["after"],
        }
        transition_catalog_states(
            self.repository_factory,
            preview["before"],
            preview["after"],
        )
        try:
            self.history_repository.append(operation)
        except Exception:
            transition_catalog_states(
                self.repository_factory,
                preview["after"],
                preview["before"],
            )
            raise
        return {"preview": public, "operation": public_operation(operation)}

    def history(self) -> dict[str, Any]:
        operations = [
            public_operation(row)
            for row in self.history_repository.list()
            if row.get("action") == "tmdb_retirement"
        ]
        return {"count": len(operations), "operations": operations}

    def undo(self, operation_id: str) -> dict[str, Any]:
        operation = next(
            (
                row
                for row in self.history_repository.list()
                if row.get("id") == operation_id and row.get("action") == "tmdb_retirement"
            ),
            None,
        )
        if operation is None:
            raise ExternalRetirementConflict("tmdb_retirement_operation_not_found")
        if operation.get("status") != "applied":
            raise ExternalRetirementConflict("tmdb_retirement_operation_not_applied")
        before = _operation_states(operation, "before")
        after = _operation_states(operation, "after")
        transition_catalog_states(self.repository_factory, after, before)
        updated = {
            **operation,
            "status": "undone",
            "undone_at": curation_timestamp(),
        }
        try:
            self.history_repository.replace(updated)
        except Exception:
            transition_catalog_states(self.repository_factory, before, after)
            raise
        return public_operation(updated)

    def _preview_internal(self) -> dict[str, Any]:
        before: list[dict[str, Any]] = []
        after: list[dict[str, Any]] = []
        catalog_reports: list[dict[str, Any]] = []
        blocked_catalogs: list[str] = []
        affected_items = 0
        removed_fields = 0
        preserved_locked = 0
        preserved_shared = 0
        removed_release_dates = 0

        for target in _unique_catalogs(self.catalogs()):
            items = self.repository_factory(target.path).read()
            item_reports: list[dict[str, Any]] = []
            target_affected = False
            for position, item in enumerate(items):
                current = _snapshot(item)
                retired, report = retire_tmdb_metadata(current)
                if not report["changed"]:
                    continue
                target_affected = True
                affected_items += 1
                removed_fields += len(report["removed_fields"])
                preserved_locked += len(report["preserved_locked_fields"])
                preserved_shared += len(report["preserved_shared_fields"])
                removed_release_dates += int(report["removed_release_dates"])
                item_reports.append(
                    {
                        "item_id": str(current.get("id") or ""),
                        "title": str(current.get("title") or "Sin titulo"),
                        **report,
                    }
                )
                if target.writable:
                    before.append(_state(target.path, current, position))
                    after.append(_state(target.path, retired, position))
            if target_affected and not target.writable:
                blocked_catalogs.append(target.reference)
            if item_reports:
                catalog_reports.append(
                    {
                        "reference": target.reference,
                        "writable": target.writable,
                        "affected_items": len(item_reports),
                        "items": item_reports,
                    }
                )

        preview_id = _preview_id(before, blocked_catalogs)
        public = {
            "source": "tmdb",
            "preview_id": preview_id,
            "affected_catalogs": len(catalog_reports),
            "affected_items": affected_items,
            "removed_fields": removed_fields,
            "removed_release_dates": removed_release_dates,
            "preserved_locked_fields": preserved_locked,
            "preserved_shared_fields": preserved_shared,
            "blocked_catalogs": blocked_catalogs,
            "can_purge": bool(affected_items) and not blocked_catalogs,
            "catalogs": catalog_reports,
        }
        return {"public": public, "before": before, "after": after}


def retirement_history_path(instance_path: Path) -> Path:
    path = Path(instance_path)
    return path.with_name(f".{path.name}.tmdb-retirement-history.json")


def _unique_catalogs(catalogs: Sequence[RetirementCatalog]) -> list[RetirementCatalog]:
    unique: dict[str, RetirementCatalog] = {}
    for catalog in catalogs:
        try:
            key = str(catalog.path.resolve()).casefold()
        except OSError:
            key = str(catalog.path.absolute()).casefold()
        previous = unique.get(key)
        if previous is None or (catalog.writable and not previous.writable):
            unique[key] = catalog
    return list(unique.values())


def _snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
    from movie_inbox.domain.catalog import normalize_item

    return {
        str(key): value
        for key, value in normalize_item(item).to_dict().items()
        if not str(key).startswith("_")
    }


def _state(path: Path, item: Mapping[str, Any], position: int) -> dict[str, Any]:
    try:
        source_file = str(path.resolve())
    except OSError:
        source_file = str(path.absolute())
    return {
        "source_file": source_file,
        "item_id": str(item.get("id") or ""),
        "position": max(0, int(position)),
        "item": _snapshot(item),
    }


def _preview_id(before: list[dict[str, Any]], blocked_catalogs: list[str]) -> str:
    payload = json.dumps(
        {"before": before, "blocked_catalogs": sorted(blocked_catalogs)},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _operation_summary(preview: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: preview[key]
        for key in (
            "source",
            "preview_id",
            "affected_catalogs",
            "affected_items",
            "removed_fields",
            "removed_release_dates",
            "preserved_locked_fields",
            "preserved_shared_fields",
        )
    }


def _operation_states(operation: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    rows = operation.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise CurationConflict("invalid_tmdb_retirement_operation")
    return [dict(row) for row in rows]


__all__ = [
    "ExternalRetirementConflict",
    "ExternalRetirementError",
    "RetirementCatalog",
    "TmdbRetirementService",
    "retirement_history_path",
]
