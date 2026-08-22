"""Reversible scanner review decisions."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from movie_inbox.application.library_repository import LibraryRepository, ReviewedFileState
from movie_inbox.application.library_service import ManagedLibraryService, ReviewPlan
from movie_inbox.application.scanner_history import ScannerHistoryRepository, normalize_history_mode
from movie_inbox.domain.curation import curation_timestamp

ACTION_LABELS = {
    "confirm": "Vinculado a identidad existente",
    "ignore": "Archivo omitido",
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
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.library_service = library_service
        self.library_repository = library_repository
        self.persistent_history = persistent_history
        self.session_history = session_history
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
        self.library_repository.restore_reviewed_files(after, before, self._now())
        updated = {**operation, "status": "undone", "undone_at": curation_timestamp()}
        try:
            repository.replace(updated, namespace)
        except Exception:
            self.library_repository.restore_reviewed_files(before, after, self._now())
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
