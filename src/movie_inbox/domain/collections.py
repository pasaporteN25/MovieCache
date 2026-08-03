"""Curated collection models and catalog-copy boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.privacy import SHARED_CATALOG_FIELDS


COLLECTION_VISIBILITIES = {"private", "published"}
COLLECTION_SOURCE_KINDS = {"builtin", "import", "user"}
COLLECTION_ITEM_FIELDS = (SHARED_CATALOG_FIELDS - {"en_catalogo"}) | {"metadata_sources"}


@dataclass(frozen=True)
class CollectionItem:
    id: str
    position: int
    item: dict[str, Any]


@dataclass(frozen=True)
class CuratedCollection:
    id: str
    slug: str
    title: str
    description: str
    owner_user_id: str
    visibility: str = "private"
    source_kind: str = "user"
    source_url: str = ""
    source_label: str = ""
    built_in: bool = False
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    owner_username: str = ""
    followed: bool = False
    items: tuple[CollectionItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.visibility not in COLLECTION_VISIBILITIES:
            raise ValueError(f"Invalid collection visibility: {self.visibility}")
        if self.source_kind not in COLLECTION_SOURCE_KINDS:
            raise ValueError(f"Invalid collection source: {self.source_kind}")
        if not self.id or not self.slug or not self.title.strip():
            raise ValueError("A collection requires an id, slug and title")


def normalize_collection_item(value: Mapping[str, Any]) -> dict[str, Any]:
    """Keep shareable work identity and metadata, never personal state."""
    normalized = normalize_item(value).to_dict()
    item = {
        key: normalized[key]
        for key in COLLECTION_ITEM_FIELDS
        if key in normalized
    }
    if not str(item.get("id") or "") or not str(item.get("title") or "").strip():
        raise ValueError("Collection items require an id and title")
    return item


def catalog_item_from_collection(
    entry: CollectionItem,
    collection: CuratedCollection,
    *,
    added_at: str,
) -> dict[str, Any]:
    """Create a neutral personal-catalog item while retaining collection provenance."""
    item = dict(normalize_collection_item(entry.item))
    item.update(
        {
            "status": "to_watch",
            "watched_at": "",
            "rating": 0,
            "review": "",
            "notes": "",
            "en_catalogo": False,
            "local_files": [],
            "local_name": "",
            "local_path": "",
            "locked_fields": [],
            "duplicate_decisions": {},
            "curation_updated_at": "",
            "added_at": added_at,
            "collection_sources": [
                {
                    "collection_id": collection.id,
                    "collection_title": collection.title,
                    "collection_item_id": entry.id,
                    "added_at": added_at,
                }
            ],
        }
    )
    return normalize_item(item).to_dict()
