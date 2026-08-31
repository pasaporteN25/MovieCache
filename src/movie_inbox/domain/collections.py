"""Curated collection models and catalog-copy boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.privacy import SHARED_CATALOG_FIELDS

COLLECTION_VISIBILITIES = {"private", "published"}
COLLECTION_SOURCE_KINDS = {"builtin", "import", "user"}
# _availability is excluded even though SHARED_CATALOG_FIELDS carries it for a
# different, already-safe caller (privacy.py's shared_catalog_item(), which
# reconstructs a clean sub-dict field-by-field). normalize_collection_item()
# below only allowlists top-level keys, so a personal catalog item's full
# _availability blob -- including nested library_id/library_name -- would
# otherwise pass through untouched. Collections never legitimately need it.
COLLECTION_ITEM_FIELDS = (SHARED_CATALOG_FIELDS - {"en_catalogo", "_availability"}) | {
    "metadata_sources",
    "file_count",
}


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
    # Set only for a [P2] collection auto-generated from a scanned library's
    # confirmed availability. source_kind stays "user" for these (changing the
    # curated_collections.source_kind CHECK constraint would need SQLite's
    # unsupported recreate-table migration) -- this field, not source_kind, is
    # the real discriminator for "this collection is library-derived."
    derived_library_id: str = ""

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
    item = {key: normalized[key] for key in COLLECTION_ITEM_FIELDS if key in normalized}
    if not str(item.get("id") or "") or not str(item.get("title") or "").strip():
        raise ValueError("Collection items require an id and title")
    return item


def collection_item_from_availability_record(
    record: Mapping[str, Any], position: int
) -> CollectionItem:
    """Build a [P2] collection item from one `availability_records()` row.

    Deliberately never reads `record["library_id"]`/`record["library_name"]` --
    only `identity` (already `work_identity()`-shaped: title/year/kind/external
    urls, never a path or filename) and `work_key` (a stable dedup id) feed the
    item, so the per-item leak surface does not exist by construction."""
    identity = dict(record.get("identity") or {})
    work_key = str(record.get("work_key") or "")
    if not work_key:
        raise ValueError("Availability record requires a work_key")
    item = normalize_collection_item(
        {**identity, "id": work_key, "file_count": int(record.get("file_count") or 0)}
    )
    return CollectionItem(id=work_key, position=position, item=item)


def normalize_club_collection_title(value: Any) -> str:
    title = str(value or "").strip()
    if not 2 <= len(title) <= 120:
        raise ValueError("Collection title must contain 2-120 characters")
    return title


def normalize_club_collection_description(value: Any) -> str:
    description = str(value or "").strip()
    if len(description) > 2000:
        raise ValueError("Collection description must be 2000 characters or fewer")
    return description


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
