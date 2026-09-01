"""Build and expose the deliberately small public presentation snapshot."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from movie_inbox.application.collection_repository import CollectionRepository
from movie_inbox.application.public_presentation_repository import PublicPresentationRepository
from movie_inbox.domain.public_presentations import (
    MAX_PUBLIC_PRESENTATION_ITEMS,
    PUBLIC_PRESENTATION_SCHEMA_VERSION,
    PublicPresentation,
)


class PublicPresentationNotFound(LookupError):
    """A public presentation is absent, inactive, or not owned by this caller."""


class PublicPresentationValidationError(ValueError):
    """Owner input or its selected collection cannot form a safe snapshot."""


class PublicPresentationService:
    def __init__(
        self,
        repository: PublicPresentationRepository,
        collections: CollectionRepository,
    ) -> None:
        self.repository = repository
        self.collections = collections

    def list_for_owner(self, owner_user_id: str) -> list[dict[str, Any]]:
        values = self.repository.list_for_owner(owner_user_id)
        return [self._owner_summary(value) for value in values]

    def create(self, owner_user_id: str, payload: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
        collection, title, description, snapshot = self._candidate_snapshot(owner_user_id, payload)
        capability = secrets.token_urlsafe(32)
        now = _utc_now()
        presentation = PublicPresentation(
            id=f"public-{uuid.uuid4().hex}",
            owner_user_id=owner_user_id,
            collection_id=collection.id,
            capability_hash=_capability_hash(capability),
            title=title,
            description=description,
            snapshot=snapshot,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.repository.create(presentation)
        return self._owner_summary(presentation), capability

    def preview(self, owner_user_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        _, _, _, snapshot = self._candidate_snapshot(owner_user_id, payload)
        return snapshot

    def refresh(self, owner_user_id: str, presentation_id: str) -> dict[str, Any]:
        current = self.repository.get_for_owner(owner_user_id, presentation_id)
        if current is None or current.status != "active":
            raise PublicPresentationNotFound("Public presentation was not found")
        _, title, description, snapshot = self._candidate_snapshot(
            owner_user_id,
            {
                "collection_id": current.collection_id,
                "title": current.title,
                "description": current.description,
            },
        )
        updated = self.repository.replace_snapshot(
            owner_user_id,
            presentation_id,
            title=title,
            description=description,
            snapshot=snapshot,
            updated_at=_utc_now(),
        )
        if updated is None:
            raise PublicPresentationNotFound("Public presentation was not found")
        return self._owner_summary(updated)

    def revoke(self, owner_user_id: str, presentation_id: str) -> dict[str, Any]:
        revoked = self.repository.revoke(owner_user_id, presentation_id, revoked_at=_utc_now())
        if revoked is None:
            raise PublicPresentationNotFound("Public presentation was not found")
        return self._owner_summary(revoked)

    def public_payload(self, capability: str) -> dict[str, Any]:
        normalized = str(capability or "").strip()
        if not is_public_capability(normalized):
            raise PublicPresentationNotFound("Public presentation was not found")
        value = self.repository.get_active_by_capability_hash(_capability_hash(normalized))
        if value is None:
            raise PublicPresentationNotFound("Public presentation was not found")
        return value.snapshot

    def _candidate_snapshot(
        self, owner_user_id: str, payload: Mapping[str, Any]
    ) -> tuple[Any, str, str, dict[str, Any]]:
        collection_id = str(payload.get("collection_id") or "").strip()
        collection = self.collections.get_accessible(owner_user_id, collection_id)
        if collection is None or collection.owner_user_id != owner_user_id:
            raise PublicPresentationValidationError("Select one of your own collections")
        title = _text(payload.get("title"), minimum=2, maximum=120, field="title")
        description = _text(
            payload.get("description"), minimum=0, maximum=2000, field="description"
        )
        if len(collection.items) > MAX_PUBLIC_PRESENTATION_ITEMS:
            raise PublicPresentationValidationError("A public presentation is limited to 200 items")
        items = [_public_item(entry.item, entry.position) for entry in collection.items]
        return (
            collection,
            title,
            description,
            {
                "schema_version": PUBLIC_PRESENTATION_SCHEMA_VERSION,
                "presentation": {"title": title, "description": description},
                "items": items,
            },
        )

    @staticmethod
    def _owner_summary(value: PublicPresentation) -> dict[str, Any]:
        return {
            "id": value.id,
            "collection_id": value.collection_id,
            "title": value.title,
            "description": value.description,
            "status": value.status,
            "item_count": len(value.snapshot.get("items", [])),
            "created_at": value.created_at,
            "updated_at": value.updated_at,
            "revoked_at": value.revoked_at,
        }


def _public_item(item: Mapping[str, Any], position: int) -> dict[str, Any]:
    value: dict[str, Any] = {
        "position": max(1, int(position) + 1),
        "title": _text(item.get("title"), minimum=1, maximum=500, field="item title"),
        "kind": _text(item.get("kind"), minimum=1, maximum=40, field="item kind"),
    }
    original_title = _optional_text(item.get("original_title"), maximum=500)
    if original_title:
        value["original_title"] = original_title
    year = _optional_int(item.get("year"), minimum=1800, maximum=3000)
    if year is not None:
        value["year"] = year
    genres = _genres(item.get("genres"))
    if genres:
        value["genres"] = genres
    duration = _optional_int(item.get("duration_minutes"), minimum=1, maximum=1440)
    if duration is not None:
        value["duration_minutes"] = duration
    return value


def _text(value: object, *, minimum: int, maximum: int, field: str) -> str:
    text = str(value or "").strip()
    if not minimum <= len(text) <= maximum:
        raise PublicPresentationValidationError(
            f"Public presentation {field} must contain {minimum}-{maximum} characters"
        )
    return text


def _optional_text(value: object, *, maximum: int) -> str:
    text = str(value or "").strip()
    return text[:maximum]


def _optional_int(value: object, *, minimum: int, maximum: int) -> int | None:
    try:
        if not isinstance(value, (str, int, float)):
            return None
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if minimum <= number <= maximum else None


def _genres(value: object) -> list[str]:
    raw = value if isinstance(value, list) else []
    values: list[str] = []
    for candidate in raw:
        text = str(candidate or "").strip()
        if text and text not in values:
            values.append(text[:80])
    return values[:8]


def _capability_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_public_capability(value: str) -> bool:
    """Accept only the fixed-format opaque capability before rate-limit state is made."""
    return len(value) >= 43 and all(character.isalnum() or character in "-_" for character in value)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
