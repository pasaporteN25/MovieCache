"""Closed public-presentation value objects.

This boundary intentionally has no dependency on catalog, Club, or account payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PUBLIC_PRESENTATION_SCHEMA_VERSION = 1
PUBLIC_PRESENTATION_STATUSES = {"active", "revoked"}
MAX_PUBLIC_PRESENTATION_ITEMS = 200


@dataclass(frozen=True)
class PublicPresentation:
    id: str
    owner_user_id: str
    collection_id: str
    capability_hash: str
    title: str
    description: str
    snapshot: dict[str, Any]
    status: str
    created_at: str
    updated_at: str
    revoked_at: str = ""

    def __post_init__(self) -> None:
        if self.status not in PUBLIC_PRESENTATION_STATUSES:
            raise ValueError(f"Invalid public presentation status: {self.status}")
        if not all((self.id, self.owner_user_id, self.collection_id, self.capability_hash)):
            raise ValueError(
                "A public presentation requires stable ownership and a capability hash"
            )
