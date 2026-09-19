"""Application service for safe previews and explicit import writes."""

from __future__ import annotations

import hashlib
import re
import time
import unicodedata
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.collection_repository import CollectionRepository
from movie_inbox.application.import_repository import ImportDraftRepository
from movie_inbox.domain.catalog import CatalogComparisonIndex, catalog_membership, normalize_item
from movie_inbox.domain.collections import (
    CollectionItem,
    CuratedCollection,
    normalize_collection_item,
)
from movie_inbox.domain.imports import (
    DEVICE_ORIGIN,
    NEVER_EXPIRES,
    DeviceReceipt,
    ImportDraft,
    ImportDraftItem,
    ParsedImport,
    ParsedImportItem,
)
from movie_inbox.domain.titles import clean_whitespace

IMPORT_DRAFT_TTL_SECONDS = 48 * 60 * 60

# Everything a phone adds while offline lands in one draft per account rather
# than one draft per work. Two reasons: it matches how it reads -- "things I
# added from my phone" is one pending pile, not twenty -- and one work per draft
# would hit MAX_IMPORT_DRAFTS_PER_USER after twenty bus rides.
DEVICE_DRAFT_NAME = "Agregado desde el telefono"
MAX_DEVICE_ITEMS_PER_REQUEST = 100
# One draft cannot grow without limit either, or a phone that loops on a failing
# sync would fill the instance. Well above any realistic offline backlog.
MAX_DEVICE_DRAFT_ITEMS = 2_000
# [X6]: how long a resolved receipt is remembered. A pending one is never
# forgotten -- its work is still waiting in a draft. After this, a retry of the
# same client id would be taken for a new work; a phone that was offline for a
# year has bigger problems than that.
DEVICE_RECEIPT_RETENTION_SECONDS = 365 * 24 * 60 * 60
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


class DeviceDraftFull(ValueError):
    """Raised when the device draft cannot hold more pending works."""


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

    def append_device_items(
        self,
        user_id: str,
        entries: Sequence[Mapping[str, Any]],
        catalog_items: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Add works a phone recorded with no connection to that account's pending pile.

        This is the server half of [A2.3], and the distinction it rests on is
        the one the Android client's brief v3 makes explicit: editing a work
        that exists on both sides has a shared base and merges, while **adding**
        one has no base at all. That is not a merge, it is an import -- so it
        goes down the path imports already take, and lands in review rather than
        in the catalogue.

        The phone never decides identity. Each entry is classified against the
        catalogue by the same rules a file import uses: an obvious match reads
        `present`, an uncertain one `review`, and only a clear miss reads `new`.
        Nothing is written to the catalogue here.

        Idempotent by the client's own id. A sync that succeeds on the server and
        fails on the way back will be retried, and a retry must not duplicate
        the film -- so an entry whose id is already in the draft is reported
        back, not added again.

        Enrichment is deliberately **not** done here. It is a network call, and
        making a phone wait on it -- or fail because a third party is down --
        would defeat the point of an offline addition. The draft carries what
        the person typed; the existing enrichment path fills the rest in when
        someone reviews it.
        """

        if len(entries) > MAX_DEVICE_ITEMS_PER_REQUEST:
            raise ValueError(
                f"At most {MAX_DEVICE_ITEMS_PER_REQUEST} works can be sent in one request"
            )
        now = self._now()
        self.repository.purge_expired(now)
        self.repository.purge_receipts(now - DEVICE_RECEIPT_RETENTION_SECONDS)
        draft = self._device_draft(user_id)
        known = {entry.id for entry in draft.items} if draft is not None else set()
        position = max((entry.position for entry in draft.items), default=-1) if draft else -1

        client_ids = [str(raw.get("id") or "").strip()[:64] for raw in entries]
        if not all(client_ids):
            raise ValueError("Every work needs a client id, so a retry cannot duplicate it")
        # [X6]: a work the server already has an answer for is a duplicate whether or
        # not its draft still exists. It used to be judged only against the draft
        # still `ready`, so a retry after the draft was applied or deleted in the
        # browser added the same works again.
        answered = self.repository.receipts_for(user_id, client_ids)

        parsed_items: list[ParsedImportItem] = []
        duplicates: list[str] = []
        for raw, entry_id in zip(entries, client_ids, strict=True):
            if (
                entry_id in known
                or entry_id in answered
                or entry_id in {row.id for row in parsed_items}
            ):
                duplicates.append(entry_id)
                continue
            position += 1
            parsed_items.append(self._device_entry(entry_id, position, raw))

        if draft is not None and len(draft.items) + len(parsed_items) > MAX_DEVICE_DRAFT_ITEMS:
            raise DeviceDraftFull(
                f"The device draft already holds {len(draft.items)} works; "
                "review it before adding more"
            )

        added: tuple[ImportDraftItem, ...] = ()
        if parsed_items:
            parsed = ParsedImport(DEVICE_DRAFT_NAME, "json", tuple(parsed_items))
            # Classified against the catalogue plus what the draft already holds,
            # so a work added twice on two different days is caught as well.
            seen = list(catalog_items) + [
                entry.item for entry in (draft.items if draft else ()) if entry.item
            ]
            added = self._classify(parsed, seen)
            draft = self._store_device_items(user_id, draft, added, now)

        if draft is not None:
            self.repository.save_receipts(
                user_id, self._new_receipts(draft.id, added, duplicates, known, answered), now
            )

        return {
            "draft_id": draft.id if draft is not None else "",
            "accepted": [
                {"id": entry.id, "state": entry.state, "reason": entry.reason} for entry in added
            ],
            "duplicates": duplicates,
            "counts": draft.counts() if draft is not None else {},
        }

    @staticmethod
    def _new_receipts(
        draft_id: str,
        added: Sequence[ImportDraftItem],
        duplicates: Sequence[str],
        known: set[str],
        answered: Mapping[str, DeviceReceipt],
    ) -> list[DeviceReceipt]:
        """The receipts a request leaves behind, written after its works are stored.

        Written after, not before: a receipt without its work would tell a retry
        the work was safe when it was not. The reverse is harmless -- a work
        without a receipt is still in the draft, so a retry finds it there and
        the duplicate branch backfills the receipt it is missing.
        """

        receipts = {
            entry.id: DeviceReceipt(
                entry.id,
                "discarded" if entry.state == "invalid" else "pending",
                "invalid" if entry.state == "invalid" else "",
                draft_id=draft_id,
            )
            for entry in added
        }
        for entry_id in duplicates:
            if entry_id in known and entry_id not in answered and entry_id not in receipts:
                receipts[entry_id] = DeviceReceipt(entry_id, "pending", draft_id=draft_id)
        return list(receipts.values())

    def _device_draft(self, user_id: str) -> ImportDraft | None:
        for summary in self.repository.list_for_user(user_id):
            if summary.origin == DEVICE_ORIGIN and summary.status == "ready":
                return self.repository.get_for_user(user_id, summary.id)
        return None

    def _device_entry(
        self,
        entry_id: str,
        position: int,
        raw: Mapping[str, Any],
    ) -> ParsedImportItem:
        title = clean_whitespace(str(raw.get("title") or ""))[:400]
        if not title:
            return ParsedImportItem(entry_id, position, "(sin titulo)", None, "missing_title")
        year = str(raw.get("year") or "").strip()[:8]
        label = f"{title} ({year})" if year else title
        item = normalize_item(
            {
                "title": title,
                "year": year,
                "kind": str(raw.get("kind") or "pelicula"),
                "notes": clean_whitespace(str(raw.get("notes") or ""))[:2000],
            }
        ).to_dict()
        return ParsedImportItem(entry_id, position, label, item)

    def _store_device_items(
        self,
        user_id: str,
        draft: ImportDraft | None,
        added: tuple[ImportDraftItem, ...],
        now: int,
    ) -> ImportDraft:
        if draft is None:
            if self.repository.count_for_user(user_id) >= self.max_drafts:
                raise ImportDraftLimit(
                    f"Import draft limit reached ({self.max_drafts}); "
                    "delete a draft before adding from a phone"
                )
            created = ImportDraft(
                id=self.id_factory(),
                user_id=user_id,
                source_name=DEVICE_DRAFT_NAME,
                source_format="json",
                source_hash=hashlib.sha256(f"device:{user_id}".encode()).hexdigest(),
                status="ready",
                created_at=now,
                updated_at=now,
                expires_at=NEVER_EXPIRES,
                origin=DEVICE_ORIGIN,
                items=added,
            )
            self.repository.create(created)
            return created
        if not self.repository.append_items(user_id, draft.id, added, now):
            # Someone is applying the draft in the browser right now, or it was
            # just deleted. Saying so beats writing into a draft about to
            # disappear: the phone keeps the works and offers them again.
            raise ImportDraftBusy("The device draft is being applied; try again")
        return replace(draft, updated_at=now, items=draft.items + added)

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
                id=str((entry.item or {}).get("id") or ""),
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
        # Both comparisons below run once per parsed row against the same two
        # lists, so both lists are prepared once. The source one grows as rows
        # are accepted, which is what add() is for.
        source_items = CatalogComparisonIndex()
        prepared_catalog = CatalogComparisonIndex(catalog_items)
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
            source_items.add(parsed_entry.item)
            membership = catalog_membership(parsed_entry.item, prepared_catalog)
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
        prepared = CatalogComparisonIndex(catalog_items)
        for entry in draft.items:
            if entry.state == "invalid" or not entry.collection_eligible:
                refreshed.append(entry)
                continue
            membership = catalog_membership(entry.item or {}, prepared)
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
        raw_provenance = item.get("import_sources")
        provenance = list(raw_provenance) if isinstance(raw_provenance, list) else []
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
            "origin": draft.origin,
            "created_at": _iso_time(draft.created_at),
            "updated_at": _iso_time(draft.updated_at),
            # A device draft has no expiry to report, and inventing one would
            # put a countdown on a surface that must not show one.
            "expires_at": "" if draft.never_expires else _iso_time(draft.expires_at),
            "remaining_seconds": None if draft.never_expires else max(0, draft.expires_at - now),
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
