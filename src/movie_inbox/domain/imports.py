"""Import draft models shared by parsers, services and persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

IMPORT_FORMATS = {"txt", "csv", "json"}
IMPORT_DRAFT_STATUSES = {"ready", "applying", "applied", "failed"}
IMPORT_ITEM_STATES = {"new", "present", "review", "invalid"}

# Where a draft came from. A file someone uploaded through the browser is
# `web`; works added on a phone with no connection are `device`.
WEB_ORIGIN = "web"
DEVICE_ORIGIN = "device"
IMPORT_DRAFT_ORIGINS = {WEB_ORIGIN, DEVICE_ORIGIN}

# `expires_at = 0` means the draft never expires, and only a device draft is
# allowed to use it. ADR-0005 decided why: a draft written offline may wait days
# for a network, so expiring it would be exactly the loss the decision existed to
# prevent. An upload sitting in a browser has no such excuse and keeps its 48
# hours.
NEVER_EXPIRES = 0


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
    origin: str = WEB_ORIGIN

    def __post_init__(self) -> None:
        if not self.id or not self.user_id or not self.source_hash:
            raise ValueError("An import draft requires id, user and source hash")
        if self.source_format not in IMPORT_FORMATS:
            raise ValueError(f"Invalid import format: {self.source_format}")
        if self.status not in IMPORT_DRAFT_STATUSES:
            raise ValueError(f"Invalid import draft status: {self.status}")
        if self.origin not in IMPORT_DRAFT_ORIGINS:
            raise ValueError(f"Invalid import draft origin: {self.origin}")
        if self.never_expires and self.origin != DEVICE_ORIGIN:
            # Kept narrow deliberately: without this, a web upload could be made
            # immortal by passing a zero, and the 48-hour bound that keeps
            # untrusted uploads from accumulating would quietly stop applying.
            raise ValueError("Only a device draft may be kept without an expiry")
        if not self.never_expires and self.expires_at <= self.created_at:
            raise ValueError("An import draft must expire after it is created")

    @property
    def never_expires(self) -> bool:
        return self.expires_at == NEVER_EXPIRES

    def expired(self, now: int) -> bool:
        return not self.never_expires and self.expires_at <= now

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
