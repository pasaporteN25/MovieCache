"""Persistence contract for local accounts and sessions."""

from __future__ import annotations

from typing import Protocol

from movie_inbox.domain.identity import AuthenticatedIdentity, PersonalCatalog, UserAccount


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


class IdentityRepository(Protocol):
    path: object

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

    def replace_password(
        self,
        user_id: str,
        password_hash: str,
        *,
        must_change_password: bool,
    ) -> UserAccount: ...

    def credentials_for(self, username: str) -> tuple[UserAccount, str] | None: ...

    def default_catalog_for(self, user_id: str) -> PersonalCatalog | None: ...

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

    def owner(self) -> UserAccount | None: ...

    def validate_owner_catalog(self, source_paths: list[str], write_path: str) -> PersonalCatalog: ...
