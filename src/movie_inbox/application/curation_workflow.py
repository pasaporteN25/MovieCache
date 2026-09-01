"""Reversible curation decisions and reviewed catalog merges."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from movie_inbox.application.curation_history import (
    CurationHistoryRepository,
    normalize_history_mode,
)
from movie_inbox.application.curation_service import build_curation_payload
from movie_inbox.application.library_service import AvailabilityService
from movie_inbox.application.repository import CatalogRepository
from movie_inbox.domain.catalog import has_external_link, merge_into_existing, normalize_item
from movie_inbox.domain.curation import (
    apply_duplicate_curation_decision,
    apply_link_curation_decision,
    curation_item_reference,
    curation_timestamp,
)
from movie_inbox.domain.merge_review import (
    MergeReviewError,
    apply_group_reviewed_merge,
    apply_reviewed_merge,
    build_group_merge_review,
    build_merge_review,
)

RepositoryFactory = Callable[[Path], CatalogRepository]


class CurationWorkflowError(RuntimeError):
    """Base error for reviewed curation operations."""


class CurationItemNotFound(CurationWorkflowError):
    """Raised when a compared catalog entry no longer exists."""


class CurationConflict(CurationWorkflowError):
    """Raised when catalog data changed after a comparison or operation."""


@dataclass(frozen=True)
class CatalogPointer:
    path: Path
    item_id: str

    def __post_init__(self) -> None:
        if not str(self.item_id or "").strip():
            raise ValueError("Missing item id")

    def payload(self) -> dict[str, str]:
        return {
            "id": self.item_id,
            "source_file": str(self.path),
        }


class CurationWorkflowService:
    def __init__(
        self,
        repository_factory: RepositoryFactory,
        persistent_history: CurationHistoryRepository,
        session_history: CurationHistoryRepository,
        availability_service: AvailabilityService | None = None,
    ) -> None:
        self.repository_factory = repository_factory
        self.persistent_history = persistent_history
        self.session_history = session_history
        self.availability_service = availability_service

    def compare(
        self,
        left: CatalogPointer,
        *,
        right: CatalogPointer | None = None,
        incoming: Mapping[str, Any] | None = None,
        survivor_side: str = "left",
    ) -> dict[str, Any]:
        left_state = self._capture(left)
        right_state, right_item, external = self._right_state(right, incoming)
        if external and survivor_side != "left":
            raise MergeReviewError("External results cannot replace the catalog identity")
        review = build_merge_review(
            left_state["item"],
            right_item,
            survivor_side,
            external_side="right" if external else "",
        )
        review["left"]["reference"] = left.payload()
        review["left"]["external"] = False
        review["left"]["_availability"] = self._decorated_item(left_state["item"]).get(
            "_availability"
        )
        review["right"]["reference"] = right.payload() if right is not None else {}
        review["right"]["external"] = external
        review["right"]["_availability"] = self._decorated_item(right_item).get("_availability")
        review["can_select_survivor"] = not external
        return review

    def compare_group(
        self,
        members: Sequence[CatalogPointer],
        *,
        survivor: CatalogPointer | None = None,
    ) -> dict[str, Any]:
        states = self._capture_group(members)
        survivor_state = self._group_survivor_state(states, survivor)
        member_rows = [(_state_reference(state), state["item"]) for state in states]
        review = build_group_merge_review(member_rows, _state_reference(survivor_state))
        states_by_reference = {_state_reference(state): state for state in states}
        for member in review["members"]:
            state = states_by_reference[str(member["ref"])]
            member["reference"] = {
                "id": str(state.get("item_id") or ""),
                "source_file": str(state.get("source_file") or ""),
            }
            member["external"] = False
            member["_availability"] = self._decorated_item(state["item"]).get("_availability")
        return review

    def merge(
        self,
        left: CatalogPointer,
        *,
        right: CatalogPointer | None = None,
        incoming: Mapping[str, Any] | None = None,
        survivor_side: str = "left",
        choices: Mapping[str, Any] | None = None,
        expected_review_id: str = "",
        history_mode: str = "persistent",
        session_id: str = "",
    ) -> dict[str, Any]:
        left_state = self._capture(left)
        right_state, right_item, external = self._right_state(right, incoming)
        if external and survivor_side != "left":
            raise MergeReviewError("External results cannot replace the catalog identity")
        if right is not None and _pointer_key(left) == _pointer_key(right):
            raise MergeReviewError("Cannot merge an item with itself")

        review = build_merge_review(
            left_state["item"],
            right_item,
            survivor_side,
            external_side="right" if external else "",
        )
        if expected_review_id and review["review_id"] != expected_review_id:
            raise CurationConflict("comparison_stale")

        removed_references = tuple(
            reference
            for reference in (
                _state_reference(left_state),
                _state_reference(right_state) if right_state is not None else "",
            )
            if reference
        )
        merged_item = apply_reviewed_merge(
            left_state["item"],
            right_item,
            survivor_side,
            choices or {},
            removed_references=removed_references,
            external_side="right" if external else "",
        )

        if survivor_side == "left":
            survivor_state = left_state
            loser_state = right_state
        else:
            if right_state is None:
                raise MergeReviewError("Missing catalog survivor")
            survivor_state = right_state
            loser_state = left_state

        before = [left_state, *(row for row in [right_state] if row is not None)]
        after = [
            _state_with_item(
                survivor_state,
                merged_item,
                position=_after_merge_position(survivor_state, loser_state),
            )
        ]
        if loser_state is not None:
            after.append(_state_with_item(loser_state, None))

        changed_fields = [field["key"] for field in review["fields"] if field["different"]]
        operation = self._commit_operation(
            action="merge",
            label=f"Combinacion: {_state_title(left_state)} + {_item_title(right_item)}",
            before=before,
            after=after,
            history_mode=history_mode,
            session_id=session_id,
            summary={
                "primary_title": _state_title(left_state),
                "secondary_title": _item_title(right_item),
                "survivor_title": _item_title(merged_item),
                "survivor_id": str(merged_item.get("id") or ""),
                "changed_fields": changed_fields,
                "external": external,
            },
        )
        return {
            "item": self._decorated_item(merged_item),
            "operation": public_operation(operation),
        }

    def merge_group(
        self,
        members: Sequence[CatalogPointer],
        *,
        survivor: CatalogPointer | None = None,
        choices: Mapping[str, Any] | None = None,
        expected_review_id: str = "",
        reference_aliases: Sequence[str] = (),
        history_mode: str = "persistent",
        session_id: str = "",
    ) -> dict[str, Any]:
        states = self._capture_group(members)
        survivor_state = self._group_survivor_state(states, survivor)
        member_rows = [(_state_reference(state), state["item"]) for state in states]
        survivor_ref = _state_reference(survivor_state)
        review = build_group_merge_review(member_rows, survivor_ref)
        if expected_review_id and review["review_id"] != expected_review_id:
            raise CurationConflict("comparison_stale")

        removed_references = tuple(
            dict.fromkeys(
                [
                    *(reference for reference, _ in member_rows if reference),
                    *self._validated_group_references(states, reference_aliases),
                ]
            )
        )
        merged_item = apply_group_reviewed_merge(
            member_rows,
            survivor_ref,
            choices or {},
            removed_references=removed_references,
        )
        loser_states = [state for state in states if state is not survivor_state]
        before = list(states)
        after = [
            _state_with_item(
                survivor_state,
                merged_item,
                position=_after_group_merge_position(survivor_state, loser_states),
            ),
            *[_state_with_item(state, None) for state in loser_states],
        ]
        changed_fields = [field["key"] for field in review["fields"] if field["different"]]
        operation = self._commit_operation(
            action="merge_group",
            label=f"Combinacion de {len(states)} entradas: {_item_title(merged_item)}",
            before=before,
            after=after,
            history_mode=history_mode,
            session_id=session_id,
            summary={
                "member_count": len(states),
                "member_titles": [_state_title(state) for state in states],
                "survivor_title": _item_title(merged_item),
                "survivor_id": str(merged_item.get("id") or ""),
                "changed_fields": changed_fields,
                "external": False,
            },
        )
        return {
            "item": self._decorated_item(merged_item),
            "operation": public_operation(operation),
        }

    def auto_resolve_duplicates(
        self,
        items: list[dict[str, Any]],
        *,
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Resolve each safe duplicate component as one atomic N-to-1 operation."""
        cases = build_curation_payload(items)["cases"]
        resolved = 0
        needs_review = 0
        for case in cases:
            if case["type"] != "duplicate" or case["status"] != "pending":
                continue
            members = [
                CatalogPointer(Path(member["source_file"]), member["id"])
                for member in case.get("members", [])
            ]
            try:
                review = self.compare_group(members)
                if review["unresolved_count"]:
                    needs_review += 1
                    continue
                self.merge_group(
                    members,
                    choices={},
                    expected_review_id=review["review_id"],
                    history_mode=history_mode,
                    session_id=session_id,
                )
                resolved += 1
            except (MergeReviewError, CurationConflict, CurationItemNotFound):
                needs_review += 1
        return {"resolved": resolved, "needs_review": needs_review}

    def update_duplicate_group_decision(
        self,
        members: Sequence[CatalogPointer],
        status: str,
        *,
        member_references: Sequence[str] = (),
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        states = self._capture_group(members)
        references = self._validated_group_references(states, member_references)
        if not references:
            references = [_state_reference(state) for state in states]
        after: list[dict[str, Any]] = []
        for state, own_reference in zip(states, references, strict=True):
            updated = dict(state["item"])
            for other_reference in references:
                if other_reference != own_reference:
                    apply_duplicate_curation_decision(updated, other_reference, status)
            after.append(_state_with_item(state, normalize_item(updated).to_dict()))
        labels = {
            "pending": "Grupo devuelto a pendientes",
            "deferred": "Grupo de duplicados pospuesto",
            "not_duplicate": "Entradas del grupo marcadas como distintas",
        }
        operation = self._commit_operation(
            action="duplicate_group_curation",
            label=f"{labels.get(status, 'Decision de grupo')}: {len(states)} entradas",
            before=list(states),
            after=after,
            history_mode=history_mode,
            session_id=session_id,
            summary={
                "member_count": len(states),
                "member_titles": [_state_title(state) for state in states],
                "decision": status,
            },
        )
        return {"operation": public_operation(operation)}

    def update_link_decision(
        self,
        pointer: CatalogPointer,
        status: str,
        *,
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        before = self._capture(pointer)
        updated = dict(before["item"])
        apply_link_curation_decision(updated, status, linked=has_external_link(updated))
        after = _state_with_item(before, normalize_item(updated).to_dict())
        labels = {
            "pending": "Referencia devuelta a pendientes",
            "deferred": "Referencia pospuesta",
            "not_required": "Referencia marcada como no requerida",
        }
        operation = self._commit_operation(
            action="link_curation",
            label=f"{labels.get(status, 'Decision de referencia')}: {_state_title(before)}",
            before=[before],
            after=[after],
            history_mode=history_mode,
            session_id=session_id,
            summary={
                "primary_title": _state_title(before),
                "decision": status,
            },
        )
        return {"operation": public_operation(operation)}

    def update_duplicate_decision(
        self,
        pointer: CatalogPointer,
        other_reference: str,
        status: str,
        *,
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        before = self._capture(pointer)
        updated = dict(before["item"])
        apply_duplicate_curation_decision(updated, other_reference, status)
        after = _state_with_item(before, normalize_item(updated).to_dict())
        labels = {
            "pending": "Coincidencia devuelta a pendientes",
            "deferred": "Coincidencia pospuesta",
            "not_duplicate": "Entradas marcadas como distintas",
        }
        operation = self._commit_operation(
            action="duplicate_curation",
            label=f"{labels.get(status, 'Decision de duplicado')}: {_state_title(before)}",
            before=[before],
            after=[after],
            history_mode=history_mode,
            session_id=session_id,
            summary={
                "primary_title": _state_title(before),
                "other_reference": str(other_reference or ""),
                "decision": status,
            },
        )
        return {"operation": public_operation(operation)}

    def auto_merge_on_add(
        self,
        pointer: CatalogPointer,
        incoming: Mapping[str, Any],
        *,
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Fold a newly-added external result into an existing item [Q6] already
        matched by `decide_match` -- deliberately uses `merge_into_existing`
        (fill-only, `locked_fields`-safe, proven by [Q5]'s fixtures), never
        `apply_reviewed_merge`, which has its own separate, unrelated field-choice
        logic that can override a locked-but-empty field (tracked separately, not
        this method's concern)."""
        before = self._capture(pointer)
        merged_item = dict(before["item"])
        merge_into_existing([merged_item], incoming, pointer.item_id)
        after = _state_with_item(before, merged_item)
        operation = self._commit_operation(
            action="auto_merge_on_add",
            label=f"Combinacion automatica al agregar: {_state_title(before)}",
            before=[before],
            after=[after],
            history_mode=history_mode,
            session_id=session_id,
            summary={
                "primary_title": _state_title(before),
                "source": str(incoming.get("source") or ""),
            },
        )
        return {
            "item": self._decorated_item(merged_item),
            "operation": public_operation(operation),
        }

    def history(self, history_mode: str, session_id: str) -> dict[str, Any]:
        mode, repository, namespace = self._history_repository(history_mode, session_id)
        operations = [public_operation(row) for row in repository.list(namespace)]
        return {
            "mode": mode,
            "count": len(operations),
            "operations": operations,
        }

    def clear_history(
        self,
        history_mode: str,
        session_id: str,
        *,
        confirmed: bool,
    ) -> int:
        if not confirmed:
            raise ValueError("History deletion requires confirmation")
        _, repository, namespace = self._history_repository(history_mode, session_id)
        return repository.clear(namespace)

    def undo(
        self,
        operation_id: str,
        *,
        history_mode: str,
        session_id: str,
    ) -> dict[str, Any]:
        _, repository, namespace = self._history_repository(history_mode, session_id)
        operation = next(
            (row for row in repository.list(namespace) if row.get("id") == operation_id),
            None,
        )
        if operation is None:
            raise CurationItemNotFound("history_operation_not_found")
        if operation.get("status") != "applied":
            raise CurationConflict("history_operation_not_applied")
        before = _operation_states(operation, "before")
        after = _operation_states(operation, "after")
        self._transition(after, before)
        updated = {
            **operation,
            "status": "undone",
            "undone_at": curation_timestamp(),
        }
        try:
            repository.replace(updated, namespace)
        except Exception:
            self._transition(before, after)
            raise
        return public_operation(updated)

    def _right_state(
        self,
        right: CatalogPointer | None,
        incoming: Mapping[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any], bool]:
        if right is not None and incoming is not None:
            raise MergeReviewError("Choose a catalog item or an external result")
        if right is not None:
            state = self._capture(right)
            return state, dict(state["item"]), False
        if incoming is None:
            raise MergeReviewError("Missing comparison item")
        return None, normalize_item(incoming).to_dict(), True

    def _decorated_item(self, item: Mapping[str, Any]) -> dict[str, Any]:
        """Attach `_availability` for display only -- never fed back into
        apply_reviewed_merge or persistence, so `en_catalogo` there stays the raw
        manual flag."""
        if self.availability_service is None:
            return dict(item)
        return self.availability_service.decorate_items([dict(item)], include_sources=False)[0]

    def _capture(self, pointer: CatalogPointer) -> dict[str, Any]:
        return capture_catalog_state(self.repository_factory, pointer)

    def _capture_group(self, members: Sequence[CatalogPointer]) -> list[dict[str, Any]]:
        if len(members) < 2:
            raise MergeReviewError("A duplicate group needs at least two members")
        keys = [_pointer_key(pointer) for pointer in members]
        if len(set(keys)) != len(keys):
            raise MergeReviewError("Duplicate group contains the same item more than once")
        states = [self._capture(pointer) for pointer in members]
        references = [_state_reference(state) for state in states]
        if len(set(references)) != len(references):
            raise MergeReviewError("Duplicate group contains ambiguous references")
        return states

    @staticmethod
    def _validated_group_references(
        states: Sequence[Mapping[str, Any]], references: Sequence[str]
    ) -> list[str]:
        if not references:
            return []
        normalized = [str(reference or "").strip() for reference in references]
        if len(normalized) != len(states) or len(set(normalized)) != len(normalized):
            raise MergeReviewError("Duplicate group contains invalid public references")
        for state, reference in zip(states, normalized, strict=True):
            if not reference or reference.split("::", 1)[0] != str(state.get("item_id") or ""):
                raise MergeReviewError("Duplicate group reference does not match its member")
        return normalized

    @staticmethod
    def _group_survivor_state(
        states: Sequence[dict[str, Any]], survivor: CatalogPointer | None
    ) -> dict[str, Any]:
        if survivor is None:
            return states[0]
        survivor_key = _pointer_key(survivor)
        for state in states:
            state_pointer = CatalogPointer(
                Path(str(state.get("source_file") or "")), str(state.get("item_id") or "")
            )
            if _pointer_key(state_pointer) == survivor_key:
                return state
        raise MergeReviewError("Group survivor is not a member")

    def _commit_operation(
        self,
        *,
        action: str,
        label: str,
        before: list[dict[str, Any]],
        after: list[dict[str, Any]],
        history_mode: str,
        session_id: str,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        mode, repository, namespace = self._history_repository(history_mode, session_id)
        operation = {
            "id": uuid.uuid4().hex,
            "action": action,
            "label": label,
            "status": "applied",
            "mode": mode,
            "created_at": curation_timestamp(),
            "undone_at": "",
            "summary": summary,
            "before": before,
            "after": after,
        }
        self._transition(before, after)
        try:
            repository.append(operation, namespace)
        except Exception:
            self._transition(after, before)
            raise
        return operation

    def _history_repository(
        self,
        history_mode: str,
        session_id: str,
    ) -> tuple[str, CurationHistoryRepository, str]:
        mode = normalize_history_mode(history_mode)
        if mode == "session":
            return mode, self.session_history, str(session_id or "anonymous")
        return mode, self.persistent_history, ""

    def _transition(
        self,
        expected_states: list[dict[str, Any]],
        target_states: list[dict[str, Any]],
    ) -> None:
        transition_catalog_states(self.repository_factory, expected_states, target_states)


def capture_catalog_state(
    repository_factory: RepositoryFactory,
    pointer: CatalogPointer,
) -> dict[str, Any]:
    repository = repository_factory(pointer.path)
    items = repository.read()
    for position, item in enumerate(items):
        if str(item.get("id") or "") == pointer.item_id:
            return _catalog_state(pointer.path, pointer.item_id, item, position)
    raise CurationItemNotFound(f"Catalog item not found: {pointer.item_id}")


def transition_catalog_states(
    repository_factory: RepositoryFactory,
    expected_states: list[dict[str, Any]],
    target_states: list[dict[str, Any]],
) -> None:
    expected_by_path = _states_by_path(expected_states)
    target_by_path = _states_by_path(target_states)
    paths = list(dict.fromkeys([*expected_by_path, *target_by_path]))
    applied: list[str] = []
    try:
        for path in paths:
            _transition_catalog_path(
                repository_factory,
                Path(path),
                expected_by_path.get(path, []),
                target_by_path.get(path, []),
            )
            applied.append(path)
    except Exception:
        for path in reversed(applied):
            try:
                _transition_catalog_path(
                    repository_factory,
                    Path(path),
                    target_by_path.get(path, []),
                    expected_by_path.get(path, []),
                )
            except Exception:
                pass
        raise


def _transition_catalog_path(
    repository_factory: RepositoryFactory,
    path: Path,
    expected_states: list[dict[str, Any]],
    target_states: list[dict[str, Any]],
) -> None:
    repository = repository_factory(path)

    def mutation(items):  # type: ignore[no-untyped-def]
        by_id = {str(item.get("id") or ""): item for item in items}
        for state in expected_states:
            current = by_id.get(str(state.get("item_id") or ""))
            expected = state.get("item")
            if expected is None:
                if current is not None:
                    raise CurationConflict("catalog_changed_since_operation")
            elif current is None or _snapshot(current) != expected:
                raise CurationConflict("catalog_changed_since_operation")

        affected_ids = {
            str(state.get("item_id") or "") for state in [*expected_states, *target_states]
        }
        items[:] = [item for item in items if str(item.get("id") or "") not in affected_ids]
        inserts = [state for state in target_states if isinstance(state.get("item"), Mapping)]
        for state in sorted(inserts, key=lambda row: int(row.get("position") or 0)):
            position = max(0, min(int(state.get("position") or 0), len(items)))
            items.insert(position, normalize_item(state["item"]))
        return True, None

    repository.mutate(mutation)


def public_operation(operation: Mapping[str, Any]) -> dict[str, Any]:
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


def _catalog_state(
    path: Path,
    item_id: str,
    item: Mapping[str, Any] | None,
    position: int,
) -> dict[str, Any]:
    try:
        source_file = str(path.resolve())
    except OSError:
        source_file = str(path.absolute())
    return {
        "source_file": source_file,
        "item_id": str(item_id or ""),
        "position": max(0, int(position)),
        "item": _snapshot(item) if item is not None else None,
    }


def _state_with_item(
    state: Mapping[str, Any],
    item: Mapping[str, Any] | None,
    *,
    position: int | None = None,
) -> dict[str, Any]:
    position_value = state.get("position") if position is None else position
    return {
        "source_file": str(state.get("source_file") or ""),
        "item_id": str(state.get("item_id") or ""),
        "position": int(position_value or 0),
        "item": _snapshot(item) if item is not None else None,
    }


def _snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in normalize_item(item).to_dict().items()
        if not str(key).startswith("_")
    }


def _states_by_path(states: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for state in states:
        path = str(state.get("source_file") or "")
        if not path:
            raise CurationWorkflowError("Operation state is missing its catalog path")
        grouped.setdefault(path, []).append(state)
    return grouped


def _operation_states(operation: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    rows = operation.get(key)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise CurationWorkflowError("Invalid curation operation state")
    return [dict(row) for row in rows]


def _after_merge_position(
    survivor: Mapping[str, Any],
    loser: Mapping[str, Any] | None,
) -> int:
    position = int(survivor.get("position") or 0)
    if (
        loser is not None
        and loser.get("source_file") == survivor.get("source_file")
        and int(loser.get("position") or 0) < position
    ):
        return max(0, position - 1)
    return position


def _after_group_merge_position(
    survivor: Mapping[str, Any], losers: Sequence[Mapping[str, Any]]
) -> int:
    position = int(survivor.get("position") or 0)
    removed_before = sum(
        1
        for loser in losers
        if loser.get("source_file") == survivor.get("source_file")
        and int(loser.get("position") or 0) < position
    )
    return max(0, position - removed_before)


def _pointer_key(pointer: CatalogPointer) -> tuple[str, str]:
    try:
        path = str(pointer.path.resolve())
    except OSError:
        path = str(pointer.path.absolute())
    return path.casefold(), pointer.item_id


def _state_reference(state: Mapping[str, Any] | None) -> str:
    if state is None or not isinstance(state.get("item"), Mapping):
        return ""
    item = {
        **dict(state["item"]),
        "_source_file": str(state.get("source_file") or ""),
    }
    return curation_item_reference(item)


def _state_title(state: Mapping[str, Any]) -> str:
    item = state.get("item")
    return _item_title(item if isinstance(item, Mapping) else {})


def _item_title(item: Mapping[str, Any]) -> str:
    return str(item.get("title") or item.get("local_name") or "Sin titulo")
