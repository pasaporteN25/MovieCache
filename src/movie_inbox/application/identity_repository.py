"""Persistence contract for local accounts and sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from movie_inbox.domain.identity import (
    ArchivedMember,
    AuthenticatedIdentity,
    PersonalCatalog,
    UserAccount,
)
from movie_inbox.domain.privacy import ItemPrivacyOverride, PrivacyPreferences


class IdentityRepositoryError(RuntimeError):
    """Base error for instance identity persistence."""


class IdentityAlreadyInitialized(IdentityRepositoryError):
    """Raised when an owner already exists."""


class IdentityCatalogMismatch(IdentityRepositoryError):
    """Raised when the configured catalog differs from the owner's catalog."""


class IdentityConflict(IdentityRepositoryError):
    """Raised when an account conflicts with an existing identity."""


class IdentityNotFound(IdentityRepositoryError):
    """Raised when an account does not exist."""


class IdentityOwnerProtected(IdentityRepositoryError):
    """Raised when a member-only operation targets the owner."""


class IdentityMemberActive(IdentityRepositoryError):
    """Raised when an active member is targeted by an archival operation."""


class IdentityRepository(Protocol):
    path: Path

    def initialize(self) -> None: ...

    def has_users(self) -> bool: ...

    def create_owner(
        self,
        username: str,
        password_hash: str,
        catalog_name: str,
        source_paths: list[str],
        write_path: str,
    ) -> tuple[UserAccount, PersonalCatalog]: ...

    def create_member(
        self,
        username: str,
        password_hash: str,
        catalog_name: str,
        source_paths: list[str],
        write_path: str,
    ) -> tuple[UserAccount, PersonalCatalog]: ...

    def list_accounts(self) -> list[tuple[UserAccount, PersonalCatalog]]: ...

    def account(self, user_id: str) -> UserAccount | None: ...

    def set_user_active(self, user_id: str, active: bool) -> UserAccount: ...

    def update_member(
        self,
        user_id: str,
        username: str,
        catalog_name: str,
    ) -> tuple[UserAccount, PersonalCatalog]: ...

    def archive_member(self, user_id: str) -> ArchivedMember: ...

    def list_archived_members(self) -> list[ArchivedMember]: ...

    def restore_archived_member(
        self,
        archive_id: str,
        username: str,
        password_hash: str,
    ) -> tuple[UserAccount, PersonalCatalog]: ...

    def replace_password(
        self,
        user_id: str,
        password_hash: str,
        *,
        must_change_password: bool,
    ) -> UserAccount: ...

    def credentials_for(self, username: str) -> tuple[UserAccount, str] | None: ...

    def default_catalog_for(self, user_id: str) -> PersonalCatalog | None: ...

    def privacy_for(self, user_id: str) -> PrivacyPreferences: ...

    def update_privacy(
        self, user_id: str, preferences: PrivacyPreferences
    ) -> PrivacyPreferences: ...

    def item_privacy_overrides(
        self,
        user_id: str,
        catalog_id: str,
    ) -> dict[str, ItemPrivacyOverride]: ...

    def set_item_privacy(
        self,
        user_id: str,
        catalog_id: str,
        item_id: str,
        override: ItemPrivacyOverride,
    ) -> ItemPrivacyOverride: ...

    def save_session(
        self,
        token_hash: str,
        user_id: str,
        created_at: int,
        expires_at: int,
    ) -> None: ...

    def session_identity(self, token_hash: str, now: int) -> AuthenticatedIdentity | None: ...

    def touch_session(self, token_hash: str, seen_at: int) -> None: ...

    def delete_session(self, token_hash: str) -> None: ...

    def delete_user_sessions(self, user_id: str) -> int: ...

    def save_device_session(
        self,
        access_token_hash: str,
        refresh_token_hash: str,
        user_id: str,
        device_name: str,
        created_at: int,
        access_expires_at: int,
        refresh_expires_at: int,
    ) -> None: ...

    def device_session_identity(
        self, access_token_hash: str, now: int
    ) -> AuthenticatedIdentity | None: ...

    def rotate_device_session(
        self,
        refresh_token_hash: str,
        access_token_hash: str,
        next_refresh_token_hash: str,
        now: int,
        access_expires_at: int,
        refresh_expires_at: int,
    ) -> AuthenticatedIdentity | None: ...

    def touch_device_session(self, access_token_hash: str, seen_at: int) -> None: ...

    def delete_device_session(self, access_token_hash: str) -> None: ...

    def owner(self) -> UserAccount | None: ...

    def validate_owner_catalog(
        self, source_paths: list[str], write_path: str
    ) -> PersonalCatalog: ...
