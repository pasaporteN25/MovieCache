"""Use cases for browsing, following and copying curated collections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.collection_repository import CollectionRepository
from movie_inbox.domain.catalog import external_urls, possible_duplicate_candidates
from movie_inbox.domain.collections import (
    CuratedCollection,
    catalog_item_from_collection,
)


class CollectionNotFound(ValueError):
    """Raised when a collection is unavailable to the current user."""


class CollectionItemNotFound(ValueError):
    """Raised when a requested collection item does not exist."""


class CollectionService:
    def __init__(self, repository: CollectionRepository) -> None:
        self.repository = repository

    def list_collections(self, user_id: str) -> list[dict[str, Any]]:
        return [self._summary(collection) for collection in self.repository.list_accessible(user_id)]

    def collection_detail(
        self,
        user_id: str,
        collection_id: str,
        catalog_items: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        collection = self._require_collection(user_id, collection_id)
        rows = []
        counts = {"total": len(collection.items), "missing": 0, "present": 0, "review": 0}
        for entry in collection.items:
            membership = _catalog_membership(entry.item, catalog_items)
            counts[membership["state"]] += 1
            rows.append({**entry.item, "collection_item_id": entry.id, "catalog": membership})
        return {**self._summary(collection), "counts": counts, "items": rows}

    def set_following(self, user_id: str, collection_id: str, following: bool) -> dict[str, Any]:
        self._require_collection(user_id, collection_id)
        changed = self.repository.set_following(user_id, collection_id, following)
        collection = self._require_collection(user_id, collection_id)
        return {
            "ok": True,
            "reason": "followed" if following else "unfollowed",
            "changed": changed,
            "collection": self._summary(collection),
        }

    def add_to_catalog(
        self,
        user_id: str,
        collection_id: str,
        item_ids: list[str],
        catalog: CatalogService,
        catalog_items: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        collection = self._require_collection(user_id, collection_id)
        requested = list(
            dict.fromkeys(
                str(value or "").strip()
                for value in item_ids
                if str(value or "").strip()
            )
        )
        if not requested:
            raise ValueError("Select at least one collection item")
        if len(requested) > 500:
            raise ValueError("A collection copy is limited to 500 items")
        entries = {entry.id: entry for entry in collection.items}
        missing = [item_id for item_id in requested if item_id not in entries]
        if missing:
            raise CollectionItemNotFound(f"Collection item was not found: {missing[0]}")

        results: list[dict[str, Any]] = []
        summary = {"requested": len(requested), "added": 0, "present": 0, "review": 0}
        known_items = list(catalog_items)
        for item_id in requested:
            entry = entries[item_id]
            item = catalog_item_from_collection(entry, collection, added_at=_utc_now())
            membership = _catalog_membership(item, known_items)
            if membership["state"] == "present":
                added, reason, extra = False, "duplicate", {}
            elif membership["state"] == "review":
                added, reason, extra = False, "possible_duplicate", {
                    "candidates": possible_duplicate_candidates(known_items, item)[:5]
                }
            else:
                added, reason, extra = catalog.append_item(item, action="check")
            outcome = "added" if added else "present" if reason == "duplicate" else "review"
            if added:
                known_items.append(item)
            summary[outcome] += 1
            results.append(
                {
                    "collection_item_id": item_id,
                    "item_id": str(item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "outcome": outcome,
                    "reason": reason,
                    "candidates": extra.get("candidates", []) if outcome == "review" else [],
                }
            )
        return {
            "ok": True,
            "reason": "collection_items_processed",
            "summary": summary,
            "results": results,
        }

    def _require_collection(self, user_id: str, collection_id: str) -> CuratedCollection:
        collection = self.repository.get_accessible(user_id, str(collection_id or ""))
        if collection is None:
            raise CollectionNotFound("Collection was not found")
        return collection

    @staticmethod
    def _summary(collection: CuratedCollection) -> dict[str, Any]:
        return {
            "id": collection.id,
            "slug": collection.slug,
            "title": collection.title,
            "description": collection.description,
            "visibility": collection.visibility,
            "source_kind": collection.source_kind,
            "source_url": collection.source_url,
            "source_label": collection.source_label,
            "built_in": collection.built_in,
            "version": collection.version,
            "created_at": collection.created_at,
            "updated_at": collection.updated_at,
            "followed": collection.followed,
            "owner": {
                "id": collection.owner_user_id,
                "username": collection.owner_username,
            },
            "counts": {"total": len(collection.items)},
            "preview": [entry.item for entry in collection.items[:4]],
        }


def _catalog_membership(
    item: Mapping[str, Any],
    catalog_items: list[Mapping[str, Any]],
) -> dict[str, Any]:
    item_id = str(item.get("id") or "")
    urls = external_urls(item)
    for existing in catalog_items:
        same_id = item_id and item_id == str(existing.get("id") or "")
        same_url = urls and urls & external_urls(existing)
        if same_id or same_url:
            return {
                "state": "present",
                "item_id": str(existing.get("id") or ""),
                "candidate_count": 0,
            }
    candidates = possible_duplicate_candidates(catalog_items, item)
    if candidates:
        return {
            "state": "review",
            "item_id": "",
            "candidate_count": len(candidates),
        }
    return {"state": "missing", "item_id": "", "candidate_count": 0}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
