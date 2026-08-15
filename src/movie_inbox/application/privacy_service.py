"""Application service for opt-in catalog sharing and item privacy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from movie_inbox.application.identity_repository import IdentityRepository
from movie_inbox.domain.identity import AuthenticatedIdentity, PersonalCatalog, UserAccount
from movie_inbox.domain.privacy import (
    ItemPrivacyOverride,
    PrivacyPreferences,
    item_privacy_override,
    privacy_preferences,
    shared_catalog_item,
    shared_watch_history,
)

CatalogLoader = Callable[[list[str]], list[dict[str, Any]]]


class SharedCatalogUnavailable(LookupError):
    """Raised when a personal catalog is inactive, private or missing."""


class PrivacyService:
    def __init__(self, repository: IdentityRepository, catalog_loader: CatalogLoader) -> None:
        self.repository = repository
        self.catalog_loader = catalog_loader

    def preferences(self, identity: AuthenticatedIdentity) -> PrivacyPreferences:
        return self.repository.privacy_for(identity.user.id)

    def update_preferences(
        self,
        identity: AuthenticatedIdentity,
        payload: dict[str, Any],
    ) -> PrivacyPreferences:
        preferences = privacy_preferences(payload)
        return self.repository.update_privacy(identity.user.id, preferences)

    def item_overrides(self, identity: AuthenticatedIdentity) -> dict[str, ItemPrivacyOverride]:
        return self.repository.item_privacy_overrides(identity.user.id, identity.catalog.id)

    def update_item_override(
        self,
        identity: AuthenticatedIdentity,
        item_id: str,
        payload: dict[str, Any],
    ) -> ItemPrivacyOverride:
        normalized_item_id = str(item_id or "").strip()
        if not normalized_item_id:
            raise ValueError("Missing item id")
        override = item_privacy_override(payload)
        return self.repository.set_item_privacy(
            identity.user.id,
            identity.catalog.id,
            normalized_item_id,
            override,
        )

    def shared_catalogs(self, viewer: AuthenticatedIdentity) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for user, catalog in self.repository.list_accounts():
            if not user.active:
                continue
            preferences = self.repository.privacy_for(user.id)
            if not preferences.catalog_shared:
                continue
            rows = self.catalog_loader([source.path for source in catalog.sources])
            summaries.append(
                {
                    "user": _shared_user(user, viewer.user.id),
                    "catalog": {"id": catalog.id, "name": catalog.name},
                    "counts": {
                        "total": len(rows),
                        "in_catalog": sum(1 for row in rows if bool(row.get("en_catalogo"))),
                    },
                    "visibility": preferences.to_dict(),
                }
            )
        return summaries

    def shared_catalog(
        self,
        viewer: AuthenticatedIdentity,
        target_user_id: str,
    ) -> dict[str, Any]:
        user, catalog = self._shared_account(str(target_user_id or ""))
        preferences = self.repository.privacy_for(user.id)
        if not preferences.catalog_shared:
            raise SharedCatalogUnavailable("Shared catalog was not found")
        rows = self.catalog_loader([source.path for source in catalog.sources])
        overrides = self.repository.item_privacy_overrides(user.id, catalog.id)
        public_items = [
            shared_catalog_item(row, preferences, overrides.get(str(row.get("id") or "")))
            for row in rows
        ]
        return {
            "user": _shared_user(user, viewer.user.id),
            "catalog": {"id": catalog.id, "name": catalog.name},
            "visibility": preferences.to_dict(),
            "items": public_items,
            "history": shared_watch_history(rows, preferences),
        }

    def _shared_account(self, user_id: str) -> tuple[UserAccount, PersonalCatalog]:
        target = self.repository.account(user_id)
        if target is None or not target.active:
            raise SharedCatalogUnavailable("Shared catalog was not found")
        catalog = self.repository.default_catalog_for(target.id)
        if catalog is None:
            raise SharedCatalogUnavailable("Shared catalog was not found")
        return target, catalog


def _shared_user(user: UserAccount, viewer_id: str) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_self": user.id == viewer_id,
    }
