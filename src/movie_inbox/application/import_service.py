"""Application service for safe previews and explicit import writes."""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
import uuid
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.collection_repository import CollectionRepository
from movie_inbox.application.import_repository import ImportDraftRepository
from movie_inbox.domain.catalog import catalog_membership, normalize_item
from movie_inbox.domain.collections import (
    CollectionItem,
    CuratedCollection,
    normalize_collection_item,
)
from movie_inbox.domain.imports import ImportDraft, ImportDraftItem, ParsedImport

IMPORT_DRAFT_TTL_SECONDS = 48 * 60 * 60
IMPORT_APPLY_STALE_SECONDS = 5 * 60
MAX_IMPORT_SELECTION = 10_000
MAX_IMPORT_DRAFTS_PER_USER = 20
PERSONAL_IMPORT_OPTIONS = {
    "include_status",
    "include_watched_at",
    "include_rating",
    "include_review",
}


class ImportDraftNotFound(ValueError):
    """Raised when a draft does not belong to the current user."""


class ImportDraftExpired(ValueError):
    """Raised when a draft passed its retention window."""


class ImportDraftBusy(ValueError):
    """Raised when another request is applying the same draft."""


class ImportPermissionError(ValueError):
    """Raised when a destination is unavailable to this user."""


class ImportDraftLimit(ValueError):
    """Raised when a user must remove a draft before creating another."""


class ImportService:
    def __init__(
        self,
        repository: ImportDraftRepository,
        collection_repository: CollectionRepository,
        *,
        parser: Callable[..., ParsedImport],
        clock: Callable[[], float] = time.time,
        id_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
        ttl_seconds: int = IMPORT_DRAFT_TTL_SECONDS,
        max_drafts: int = MAX_IMPORT_DRAFTS_PER_USER,
    ) -> None:
        self.repository = repository
        self.collection_repository = collection_repository
        self.parser = parser
        self.clock = clock
        self.id_factory = id_factory
        self.ttl_seconds = max(60, int(ttl_seconds))
        self.max_drafts = max(1, int(max_drafts))

    def create_draft(
        self,
        user_id: str,
        source_name: str,
        source_format: str,
        content: str,
        column_map: Mapping[str, str] | None,
        catalog_items: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        now = self._now()
        self.repository.purge_expired(now)
        if self.repository.count_for_user(user_id) >= self.max_drafts:
            raise ImportDraftLimit(
                f"Import draft limit reached ({self.max_drafts}); "
                "delete a draft before creating another"
            )
        parsed = self.parser(source_name, source_format, content, column_map)
        draft = ImportDraft(
            id=self.id_factory(),
            user_id=user_id,
            source_name=parsed.source_name,
            source_format=parsed.source_format,
            source_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            status="ready",
            created_at=now,
            updated_at=now,
            expires_at=now + self.ttl_seconds,
            items=self._classify(parsed, catalog_items),
        )
        self.repository.create(draft)
        return self._payload(draft, include_items=True, now=now)

    def list_drafts(self, user_id: str) -> list[dict[str, Any]]:
        now = self._now()
        self.repository.purge_expired(now)
        return [
            self._payload(draft, include_items=False, now=now)
            for draft in self.repository.list_for_user(user_id)
        ]

    def draft_detail(
        self,
        user_id: str,
        draft_id: str,
        catalog_items: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        now = self._now()
        draft = self._require_draft(user_id, draft_id, now)
        refreshed = self._refresh_catalog_states(draft, catalog_items)
        return self._payload(refreshed, include_items=True, now=now)

    def delete_draft(self, user_id: str, draft_id: str, confirmed: bool) -> bool:
        if not confirmed:
            raise ValueError("Import draft deletion requires confirmation")
        draft = self.repository.get_for_user(user_id, draft_id)
        if draft is None:
            raise ImportDraftNotFound("Import draft was not found")
        if draft.status == "applying":
            raise ImportDraftBusy("Import draft is being applied")
        return self.repository.delete(user_id, draft_id)

    def apply_draft(
        self,
        user_id: str,
        draft_id: str,
        destination: str,
        item_ids: list[str],
        catalog: CatalogService,
        catalog_items: list[Mapping[str, Any]],
        *,
        personal_options: Mapping[str, Any] | None = None,
        collection_title: str = "",
        collection_description: str = "",
        can_create_collection: bool = False,
    ) -> dict[str, Any]:
        now = self._now()
        draft = self._require_draft(user_id, draft_id, now)
        if draft.status == "applied":
            return dict(draft.result)
        destination = str(destination or "").strip().casefold()
        if destination not in {"catalog", "collection"}:
            raise ValueError("Import destination must be catalog or collection")
        if destination == "collection" and not can_create_collection:
            raise ImportPermissionError("Only the owner can create imported collections")

        requested = list(
            dict.fromkeys(
                str(value or "").strip() for value in item_ids if str(value or "").strip()
            )
        )
        if not requested:
            raise ValueError("Select at least one import item")
        if len(requested) > MAX_IMPORT_SELECTION:
            raise ValueError(f"Import selection exceeds {MAX_IMPORT_SELECTION} items")
        refreshed = self._refresh_catalog_states(draft, catalog_items)
        entries = {entry.id: entry for entry in refreshed.items}
        missing = next((item_id for item_id in requested if item_id not in entries), "")
        if missing:
            raise ValueError("Import selection contains an unknown item")
        selected = [entries[item_id] for item_id in requested]
        if any(entry.item is None or not entry.collection_eligible for entry in selected):
            raise ValueError("Import selection contains invalid or repeated source entries")

        options = self._personal_options(personal_options or {})
        title = self._collection_title(collection_title) if destination == "collection" else ""
        description = (
            self._collection_description(collection_description)
            if destination == "collection"
            else ""
        )
        claimed = self.repository.claim_for_apply(
            user_id,
            draft_id,
            now,
            now - IMPORT_APPLY_STALE_SECONDS,
        )
        if claimed is None:
            raise ImportDraftNotFound("Import draft was not found")
        if claimed.expired(now):
            raise ImportDraftExpired("Import draft expired")
        if claimed.status == "applied":
            return dict(claimed.result)
        if claimed.status != "applying":
            raise ImportDraftBusy("Import draft is being applied")

        try:
            if destination == "catalog":
                result = self._apply_to_catalog(refreshed, selected, catalog, options, now)
            else:
                result = self._apply_to_collection(refreshed, selected, title, description, now)
            self.repository.complete(
                user_id,
                draft_id,
                now,
                claimed.expires_at,
                result,
            )
            return result
        except Exception:
            try:
                self.repository.fail(user_id, draft_id, self._now())
            except Exception:
                pass
            raise

    def _apply_to_catalog(
        self,
        draft: ImportDraft,
        selected: list[ImportDraftItem],
        catalog: CatalogService,
        options: dict[str, bool],
        now: int,
    ) -> dict[str, Any]:
        ready = [entry for entry in selected if entry.state == "new" and entry.item]
        incoming = [self._personal_item(entry, draft, options, now) for entry in ready]
        written = catalog.append_items(incoming) if incoming else []
        written_by_id = {row["item_id"]: row for row in written}
        results: list[dict[str, Any]] = []
        summary = {"requested": len(selected), "added": 0, "present": 0, "review": 0}
        for entry in selected:
            item = entry.item or {}
            if entry.state == "present":
                row = self._result_row(entry, item, "present", entry.reason, entry.candidates)
            elif entry.state == "review":
                row = self._result_row(entry, item, "review", entry.reason, entry.candidates)
            else:
                write_result = written_by_id.get(str(item.get("id") or ""), {})
                outcome = str(write_result.get("outcome") or "review")
                row = self._result_row(
                    entry,
                    item,
                    outcome,
                    str(write_result.get("reason") or "possible_duplicate"),
                    tuple(write_result.get("candidates") or []),
                )
            summary[row["outcome"]] += 1
            results.append(row)
        return {
            "ok": True,
            "reason": "import_applied",
            "draft_id": draft.id,
            "destination": "catalog",
            "summary": summary,
            "results": results,
        }

    def _apply_to_collection(
        self,
        draft: ImportDraft,
        selected: list[ImportDraftItem],
        title: str,
        description: str,
        now: int,
    ) -> dict[str, Any]:
        collection_id = f"import-{draft.id}"
        entries = tuple(
            CollectionItem(
                id=str(entry.item.get("id") or ""),
                position=position,
                item=normalize_collection_item(entry.item or {}),
            )
            for position, entry in enumerate(selected)
        )
        timestamp = _iso_time(now)
        collection = CuratedCollection(
            id=collection_id,
            slug=f"{_slug(title)}-{draft.id[:8]}",
            title=title,
            description=description,
            owner_user_id=draft.user_id,
            visibility="private",
            source_kind="import",
            source_label=draft.source_name,
            built_in=False,
            version=1,
            created_at=timestamp,
            updated_at=timestamp,
            items=entries,
        )
        self.collection_repository.create_private(collection)
        return {
            "ok": True,
            "reason": "private_collection_created",
            "draft_id": draft.id,
            "destination": "collection",
            "collection": {
                "id": collection.id,
                "title": collection.title,
                "visibility": collection.visibility,
                "count": len(collection.items),
            },
            "summary": {"requested": len(selected), "created": len(collection.items)},
            "results": [],
        }

    def _require_draft(self, user_id: str, draft_id: str, now: int) -> ImportDraft:
        draft = self.repository.get_for_user(user_id, str(draft_id or ""))
        if draft is None:
            raise ImportDraftNotFound("Import draft was not found")
        if draft.expired(now):
            self.repository.delete(user_id, draft.id)
            raise ImportDraftExpired("Import draft expired")
        return draft

    @staticmethod
    def _classify(
        parsed: ParsedImport,
        catalog_items: list[Mapping[str, Any]],
    ) -> tuple[ImportDraftItem, ...]:
        source_items: list[Mapping[str, Any]] = []
        classified: list[ImportDraftItem] = []
        for parsed_entry in parsed.items:
            if parsed_entry.item is None:
                classified.append(
                    ImportDraftItem(
                        parsed_entry.id,
                        parsed_entry.position,
                        "invalid",
                        parsed_entry.error or "invalid_item",
                        parsed_entry.label,
                    )
                )
                continue
            source_membership = catalog_membership(parsed_entry.item, source_items)
            if source_membership["state"] != "missing":
                state = "present" if source_membership["state"] == "present" else "review"
                classified.append(
                    ImportDraftItem(
                        parsed_entry.id,
                        parsed_entry.position,
                        state,
                        "duplicate_in_source"
                        if state == "present"
                        else "possible_duplicate_in_source",
                        parsed_entry.label,
                        parsed_entry.item,
                        _import_candidates(source_membership.get("candidates") or []),
                        False,
                    )
                )
                continue
            source_items.append(parsed_entry.item)
            membership = catalog_membership(parsed_entry.item, catalog_items)
            state = "new" if membership["state"] == "missing" else membership["state"]
            classified.append(
                ImportDraftItem(
                    parsed_entry.id,
                    parsed_entry.position,
                    state,
                    _catalog_reason(state),
                    parsed_entry.label,
                    parsed_entry.item,
                    _import_candidates(membership.get("candidates") or []),
                    True,
                )
            )
        return tuple(classified)

    @staticmethod
    def _refresh_catalog_states(
        draft: ImportDraft,
        catalog_items: list[Mapping[str, Any]],
    ) -> ImportDraft:
        refreshed: list[ImportDraftItem] = []
        for entry in draft.items:
            if entry.state == "invalid" or not entry.collection_eligible:
                refreshed.append(entry)
                continue
            membership = catalog_membership(entry.item or {}, catalog_items)
            state = "new" if membership["state"] == "missing" else membership["state"]
            refreshed.append(
                replace(
                    entry,
                    state=state,
                    reason=_catalog_reason(state),
                    candidates=_import_candidates(membership.get("candidates") or []),
                )
            )
        return replace(draft, items=tuple(refreshed))

    @staticmethod
    def _personal_item(
        entry: ImportDraftItem,
        draft: ImportDraft,
        options: dict[str, bool],
        now: int,
    ) -> dict[str, Any]:
        item = dict(entry.item or {})
        if not options["include_status"]:
            item["status"] = "to_watch"
        if not options["include_watched_at"]:
            item["watched_at"] = ""
        if not options["include_rating"]:
            item["rating"] = 0
        if not options["include_review"]:
            item["review"] = ""
        item["local_files"] = []
        item["local_name"] = ""
        item["local_path"] = ""
        item["added_at"] = str(item.get("added_at") or _iso_time(now))
        provenance = (
            item.get("import_sources") if isinstance(item.get("import_sources"), list) else []
        )
        item["import_sources"] = [
            *provenance,
            {
                "draft_id": draft.id,
                "source_name": draft.source_name,
                "source_format": draft.source_format,
                "source_hash": draft.source_hash,
                "imported_at": _iso_time(now),
            },
        ]
        return normalize_item(item).to_dict()

    @staticmethod
    def _personal_options(value: Mapping[str, Any]) -> dict[str, bool]:
        extra = set(value) - PERSONAL_IMPORT_OPTIONS
        if extra or any(not isinstance(row, bool) for row in value.values()):
            raise ValueError("Personal import options are invalid")
        return {field: bool(value.get(field, True)) for field in PERSONAL_IMPORT_OPTIONS}

    @staticmethod
    def _collection_title(value: str) -> str:
        title = " ".join(str(value or "").split())
        if not 1 <= len(title) <= 120:
            raise ValueError("Collection title must contain 1-120 characters")
        return title

    @staticmethod
    def _collection_description(value: str) -> str:
        description = " ".join(str(value or "").split())
        if len(description) > 1_000:
            raise ValueError("Collection description must contain at most 1000 characters")
        return description

    @staticmethod
    def _result_row(
        entry: ImportDraftItem,
        item: Mapping[str, Any],
        outcome: str,
        reason: str,
        candidates: tuple[dict[str, Any], ...],
    ) -> dict[str, Any]:
        return {
            "draft_item_id": entry.id,
            "item_id": str(item.get("id") or ""),
            "title": str(item.get("title") or entry.label),
            "outcome": outcome,
            "reason": reason,
            "candidates": list(candidates)[:5] if outcome == "review" else [],
        }

    def _payload(self, draft: ImportDraft, *, include_items: bool, now: int) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": draft.id,
            "source": {
                "name": draft.source_name,
                "format": draft.source_format,
                "fingerprint": draft.source_hash[:12],
            },
            "status": draft.status,
            "created_at": _iso_time(draft.created_at),
            "updated_at": _iso_time(draft.updated_at),
            "expires_at": _iso_time(draft.expires_at),
            "remaining_seconds": max(0, draft.expires_at - now),
            "counts": draft.counts(),
            "result": draft.result,
        }
        if include_items:
            payload["items"] = [
                {
                    "id": entry.id,
                    "position": entry.position,
                    "state": entry.state,
                    "reason": entry.reason,
                    "label": entry.label,
                    "item": entry.item or {},
                    "candidates": list(entry.candidates)[:5],
                    "catalog_eligible": bool(entry.collection_eligible and entry.state == "new"),
                    "collection_eligible": entry.collection_eligible,
                }
                for entry in draft.items
            ]
        return payload

    def _now(self) -> int:
        return int(self.clock())


def _catalog_reason(state: str) -> str:
    return {
        "new": "new_item",
        "present": "already_in_catalog",
        "review": "possible_catalog_match",
    }.get(state, "invalid_item")


def _import_candidates(values: list[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    fields = ("id", "title", "year", "source", "url", "en_catalogo")
    return tuple(
        {field: candidate.get(field) for field in fields if candidate.get(field) not in {None, ""}}
        for candidate in values[:5]
    )


def _slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:72] or "coleccion"


def _iso_time(value: int) -> str:
    return datetime.fromtimestamp(value, UTC).isoformat()
