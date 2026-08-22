"""Reversible scanner review decisions."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.curation_workflow import (
    CatalogPointer,
    capture_catalog_state,
    transition_catalog_states,
)
from movie_inbox.application.library_repository import (
    LibraryNotFound,
    LibraryRepository,
    ReviewedFileState,
)
from movie_inbox.application.library_service import ManagedLibraryService, ReviewPlan
from movie_inbox.application.scanner_history import ScannerHistoryRepository, normalize_history_mode
from movie_inbox.domain.curation import curation_timestamp
from movie_inbox.domain.libraries import work_identity

ACTION_LABELS = {
    "confirm": "Vinculado a identidad existente",
    "ignore": "Archivo omitido",
    "create": "Creado y vinculado",
}


class ScannerWorkflowError(RuntimeError):
    """Base error for reviewed scanner operations."""


class ScannerOperationNotFound(ScannerWorkflowError):
    """Raised when a history operation cannot be found."""


class ScannerOperationNotApplied(ScannerWorkflowError):
    """Raised when trying to undo an operation that is not currently applied."""


class ScannerWorkflowService:
    def __init__(
        self,
        library_service: ManagedLibraryService,
        library_repository: LibraryRepository,
        persistent_history: ScannerHistoryRepository,
        session_history: ScannerHistoryRepository,
        catalog_service_factory: Callable[[Path], CatalogService] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.library_service = library_service
        self.library_repository = library_repository
        self.persistent_history = persistent_history
        self.session_history = session_history
        self.catalog_service_factory = catalog_service_factory
        self.clock = clock

    def review(
        self,
        file_id: str,
        payload: Mapping[str, Any],
        *,
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        plan = self.library_service.resolve_review(file_id, payload)
        return self._commit(plan, history_mode=history_mode, session_id=session_id)

    def create_and_link(
        self,
        file_id: str,
        payload: Mapping[str, Any],
        *,
        catalog_path: Path,
        comparison_items: list[Mapping[str, Any]],
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        if self.catalog_service_factory is None:
            raise ScannerWorkflowError("Scanner workflow has no catalog service configured")
        if not any(file.id == file_id for file in self.library_service.repository.review_queue()):
            raise LibraryNotFound("Scanner queue item was not found")
        catalog_service = self.catalog_service_factory(catalog_path)
        created, catalog_reason, catalog_result = catalog_service.ensure_scanner_item(
            payload, comparison_items=comparison_items
        )
        if catalog_reason == "possible_duplicate":
            return {"ok": False, "reason": catalog_reason, "catalog_result": catalog_result}
        catalog_item = catalog_result.get("item")
        if not isinstance(catalog_item, dict):
            raise ScannerWorkflowError("catalog_item_unavailable")
        catalog_item_id = str(catalog_item.get("id") or "")

        def catalog_repository_factory(_: Path) -> Any:
            return catalog_service.repository

        catalog_after = capture_catalog_state(
            catalog_repository_factory, CatalogPointer(catalog_path, catalog_item_id)
        )
        catalog_before = (
            {
                "source_file": catalog_after["source_file"],
                "item_id": catalog_item_id,
                "position": 0,
                "item": None,
            }
            if created
            else catalog_after
        )

        plan = self.library_service.resolve_review(
            file_id, {"action": "confirm", "identity": work_identity(catalog_item)}
        )
        file_before = {file.id: ReviewedFileState.from_file(file) for file in plan.siblings}
        result = self.library_service.apply_review(plan)
        file_after = {file.id: ReviewedFileState.from_file(file) for file in result.files}

        _, repository, namespace = self._history_repository(history_mode, session_id)
        operation = {
            "id": uuid.uuid4().hex,
            "action": "scanner_create",
            "label": f"{ACTION_LABELS['create']}: {catalog_item.get('title') or ''}".rstrip(": "),
            "status": "applied",
            "mode": normalize_history_mode(history_mode),
            "created_at": curation_timestamp(),
            "undone_at": "",
            "summary": {
                "action": "create",
                "file_count": len(plan.siblings),
                "primary_title": str(catalog_item.get("title") or ""),
                "catalog_created": created,
            },
            "before": _encode_states(file_before),
            "after": _encode_states(file_after),
            "catalog_before": catalog_before,
            "catalog_after": catalog_after,
            "catalog_path": str(catalog_path),
        }
        try:
            repository.append(operation, namespace)
        except Exception:
            self.library_repository.restore_reviewed_files(file_after, file_before, self._now())
            transition_catalog_states(catalog_repository_factory, [catalog_after], [catalog_before])
            raise
        return {
            "ok": True,
            "item": result.payload,
            "operation": public_scanner_operation(operation),
            "catalog_action": catalog_reason,
            "catalog_item": catalog_item,
            "created": created,
            "writable": bool(catalog_result.get("writable")),
        }

    def history(self, history_mode: str, session_id: str) -> dict[str, Any]:
        mode, repository, namespace = self._history_repository(history_mode, session_id)
        operations = [public_scanner_operation(row) for row in repository.list(namespace)]
        return {"mode": mode, "count": len(operations), "operations": operations}

    def clear_history(self, history_mode: str, session_id: str, *, confirmed: bool) -> int:
        if not confirmed:
            raise ValueError("History deletion requires confirmation")
        _, repository, namespace = self._history_repository(history_mode, session_id)
        return repository.clear(namespace)

    def undo(self, operation_id: str, *, history_mode: str, session_id: str) -> dict[str, Any]:
        _, repository, namespace = self._history_repository(history_mode, session_id)
        operation = next(
            (row for row in repository.list(namespace) if row.get("id") == operation_id),
            None,
        )
        if operation is None:
            raise ScannerOperationNotFound("history_operation_not_found")
        if operation.get("status") != "applied":
            raise ScannerOperationNotApplied("history_operation_not_applied")
        before = _decode_states(operation.get("before"))
        after = _decode_states(operation.get("after"))
        catalog_before = operation.get("catalog_before")
        catalog_after = operation.get("catalog_after")
        catalog_path = str(operation.get("catalog_path") or "")

        def restore_catalog(expected: Any, target: Any) -> None:
            if not (catalog_path and isinstance(expected, Mapping) and isinstance(target, Mapping)):
                return
            if self.catalog_service_factory is None:
                raise ScannerWorkflowError("Scanner workflow has no catalog service configured")
            catalog_service = self.catalog_service_factory(Path(catalog_path))

            def factory(_: Path) -> Any:
                return catalog_service.repository

            transition_catalog_states(factory, [dict(expected)], [dict(target)])

        restore_catalog(catalog_after, catalog_before)
        try:
            self.library_repository.restore_reviewed_files(after, before, self._now())
        except Exception:
            restore_catalog(catalog_before, catalog_after)
            raise
        updated = {**operation, "status": "undone", "undone_at": curation_timestamp()}
        try:
            repository.replace(updated, namespace)
        except Exception:
            self.library_repository.restore_reviewed_files(before, after, self._now())
            restore_catalog(catalog_before, catalog_after)
            raise
        return public_scanner_operation(updated)

    def _commit(
        self,
        plan: ReviewPlan,
        *,
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        before = {file.id: ReviewedFileState.from_file(file) for file in plan.siblings}
        result = self.library_service.apply_review(plan)
        after = {file.id: ReviewedFileState.from_file(file) for file in result.files}
        _, repository, namespace = self._history_repository(history_mode, session_id)
        operation = {
            "id": uuid.uuid4().hex,
            "action": f"scanner_{plan.action}",
            "label": _label(plan),
            "status": "applied",
            "mode": normalize_history_mode(history_mode),
            "created_at": curation_timestamp(),
            "undone_at": "",
            "summary": _summary(plan),
            "before": _encode_states(before),
            "after": _encode_states(after),
        }
        try:
            repository.append(operation, namespace)
        except Exception:
            self.library_repository.restore_reviewed_files(after, before, self._now())
            raise
        return {"item": result.payload, "operation": public_scanner_operation(operation)}

    def _history_repository(
        self,
        history_mode: str,
        session_id: str,
    ) -> tuple[str, ScannerHistoryRepository, str]:
        mode = normalize_history_mode(history_mode)
        if mode == "session":
            return mode, self.session_history, str(session_id or "anonymous")
        return mode, self.persistent_history, ""

    def _now(self) -> int:
        return int(self.clock())


def public_scanner_operation(operation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(operation.get("id") or ""),
        "action": str(operation.get("action") or ""),
        "label": str(operation.get("label") or ""),
        "status": str(operation.get("status") or ""),
        "mode": str(operation.get("mode") or "persistent"),
        "created_at": str(operation.get("created_at") or ""),
        "undone_at": str(operation.get("undone_at") or ""),
        "can_undo": operation.get("status") == "applied",
        "summary": dict(operation.get("summary") or {}),
    }


def _label(plan: ReviewPlan) -> str:
    action_label = ACTION_LABELS.get(plan.action, "Revision de Scanner")
    title = plan.siblings[0].detected_title if plan.siblings else ""
    return f"{action_label}: {title}" if title else action_label


def _summary(plan: ReviewPlan) -> dict[str, Any]:
    return {
        "action": plan.action,
        "file_count": len(plan.siblings),
        "primary_title": plan.siblings[0].detected_title if plan.siblings else "",
    }


def _encode_states(states: Mapping[str, ReviewedFileState]) -> dict[str, dict[str, Any]]:
    return {
        file_id: {
            "state": state.state,
            "work_key": state.work_key,
            "identity": dict(state.identity),
            "candidates": [dict(candidate) for candidate in state.candidates],
        }
        for file_id, state in states.items()
    }


def _decode_states(data: Any) -> dict[str, ReviewedFileState]:
    if not isinstance(data, Mapping):
        return {}
    return {
        str(file_id): ReviewedFileState(
            state=str(row.get("state") or ""),
            work_key=str(row.get("work_key") or ""),
            identity=dict(row.get("identity") or {}),
            candidates=tuple(
                dict(candidate)
                for candidate in row.get("candidates") or []
                if isinstance(candidate, Mapping)
            ),
        )
        for file_id, row in data.items()
        if isinstance(row, Mapping)
    }
