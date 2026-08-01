"""Owner-managed lifecycle for local members and their personal catalogs."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from movie_inbox.application.auth_service import PasswordHasher
from movie_inbox.application.identity_repository import IdentityRepository
from movie_inbox.domain.identity import PersonalCatalog, UserAccount, normalize_username


CATALOG_NAME_MAX_LENGTH = 120


class MemberAuthorizationError(PermissionError):
    """Raised when a non-owner attempts to administer members."""


class PersonalCatalogProvisioner(Protocol):
    def create(self) -> Path: ...

    def discard(self, path: Path) -> None: ...


@dataclass(frozen=True)
class ManagedMember:
    user: UserAccount
    catalog: PersonalCatalog


@dataclass(frozen=True)
class ProvisionedMember:
    member: ManagedMember
    temporary_password: str


class MemberService:
    def __init__(
        self,
        repository: IdentityRepository,
        provisioner: PersonalCatalogProvisioner,
        *,
        hasher: PasswordHasher | None = None,
    ) -> None:
        self.repository = repository
        self.provisioner = provisioner
        self.hasher = hasher or PasswordHasher()

    def list_members(self, actor: UserAccount) -> list[ManagedMember]:
        _require_owner(actor)
        return [
            ManagedMember(user, catalog)
            for user, catalog in self.repository.list_accounts()
            if user.role == "member"
        ]

    def create_member(
        self,
        actor: UserAccount,
        username: str,
        *,
        temporary_password: str = "",
        catalog_name: str = "",
    ) -> ProvisionedMember:
        _require_owner(actor)
        normalized_username = normalize_username(username)
        password = str(temporary_password or "") or generate_temporary_password()
        password_hash = self.hasher.hash(password)
        resolved_catalog_name = _catalog_name(catalog_name, normalized_username)
        catalog_path = self.provisioner.create()
        try:
            user, catalog = self.repository.create_member(
                normalized_username,
                password_hash,
                resolved_catalog_name,
                [str(catalog_path)],
                str(catalog_path),
            )
        except Exception:
            try:
                self.provisioner.discard(catalog_path)
            except (OSError, ValueError):
                pass
            raise
        return ProvisionedMember(ManagedMember(user, catalog), password)

    def set_active(self, actor: UserAccount, user_id: str, active: bool) -> ManagedMember:
        _require_owner(actor)
        user = self.repository.set_user_active(str(user_id or ""), bool(active))
        catalog = self.repository.default_catalog_for(user.id)
        if catalog is None:
            raise ValueError("Member does not have a personal catalog")
        return ManagedMember(user, catalog)

    def reset_password(
        self,
        actor: UserAccount,
        user_id: str,
        *,
        temporary_password: str = "",
    ) -> ProvisionedMember:
        _require_owner(actor)
        target = self.repository.account(str(user_id or ""))
        if target is None or target.role != "member":
            raise ValueError("Member account was not found")
        password = str(temporary_password or "") or generate_temporary_password()
        updated = self.repository.replace_password(
            target.id,
            self.hasher.hash(password),
            must_change_password=True,
        )
        catalog = self.repository.default_catalog_for(updated.id)
        if catalog is None:
            raise ValueError("Member does not have a personal catalog")
        return ProvisionedMember(ManagedMember(updated, catalog), password)


def generate_temporary_password() -> str:
    return secrets.token_urlsafe(18)


def _catalog_name(value: str, username: str) -> str:
    name = str(value or "").strip() or f"Catalogo de {username}"
    if len(name) > CATALOG_NAME_MAX_LENGTH:
        raise ValueError(f"Catalog name cannot exceed {CATALOG_NAME_MAX_LENGTH} characters")
    return name


def _require_owner(actor: UserAccount) -> None:
    if not actor.active or not actor.is_owner:
        raise MemberAuthorizationError("Owner privileges are required")
