"""Import draft models shared by parsers, services and persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


IMPORT_FORMATS = {"txt", "csv", "json"}
IMPORT_DRAFT_STATUSES = {"ready", "applying", "applied", "failed"}
IMPORT_ITEM_STATES = {"new", "present", "review", "invalid"}


@dataclass(frozen=True)
class ParsedImportItem:
    id: str
    position: int
    label: str
    item: dict[str, Any] | None = None
    error: str = ""


@dataclass(frozen=True)
class ParsedImport:
    source_name: str
    source_format: str
    items: tuple[ParsedImportItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.source_format not in IMPORT_FORMATS:
            raise ValueError(f"Invalid import format: {self.source_format}")


@dataclass(frozen=True)
class ImportDraftItem:
    id: str
    position: int
    state: str
    reason: str
    label: str
    item: dict[str, Any] | None = None
    candidates: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    collection_eligible: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("An import draft item requires an id")
        if self.state not in IMPORT_ITEM_STATES:
            raise ValueError(f"Invalid import item state: {self.state}")
        if self.state != "invalid" and not isinstance(self.item, Mapping):
            raise ValueError("A valid import draft item requires normalized data")


@dataclass(frozen=True)
class ImportDraft:
    id: str
    user_id: str
    source_name: str
    source_format: str
    source_hash: str
    status: str
    created_at: int
    updated_at: int
    expires_at: int
    applied_at: int = 0
    result: dict[str, Any] = field(default_factory=dict)
    items: tuple[ImportDraftItem, ...] = field(default_factory=tuple)
    count_snapshot: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.user_id or not self.source_hash:
            raise ValueError("An import draft requires id, user and source hash")
        if self.source_format not in IMPORT_FORMATS:
            raise ValueError(f"Invalid import format: {self.source_format}")
        if self.status not in IMPORT_DRAFT_STATUSES:
            raise ValueError(f"Invalid import draft status: {self.status}")
        if self.expires_at <= self.created_at:
            raise ValueError("An import draft must expire after it is created")

    def expired(self, now: int) -> bool:
        return self.expires_at <= now

    def counts(self) -> dict[str, int]:
        if self.count_snapshot:
            return {
                "total": max(0, int(self.count_snapshot.get("total", 0))),
                "new": max(0, int(self.count_snapshot.get("new", 0))),
                "present": max(0, int(self.count_snapshot.get("present", 0))),
                "review": max(0, int(self.count_snapshot.get("review", 0))),
                "invalid": max(0, int(self.count_snapshot.get("invalid", 0))),
                "collection_eligible": max(
                    0,
                    int(self.count_snapshot.get("collection_eligible", 0)),
                ),
            }
        counts = {"total": len(self.items), "new": 0, "present": 0, "review": 0, "invalid": 0}
        for entry in self.items:
            counts[entry.state] += 1
        counts["collection_eligible"] = sum(1 for entry in self.items if entry.collection_eligible)
        return counts
