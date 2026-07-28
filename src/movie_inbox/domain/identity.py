"""Identity and personal catalog models."""

from __future__ import annotations

import re
from dataclasses import dataclass


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
VALID_ROLES = {"owner", "member"}


class IdentityValidationError(ValueError):
    """Raised when account data is not valid."""


def normalize_username(value: str) -> str:
    username = str(value or "").strip()
    if not USERNAME_PATTERN.fullmatch(username):
        raise IdentityValidationError(
            "Username must contain 3-64 letters, numbers, dots, underscores or hyphens"
        )
    return username


def username_key(value: str) -> str:
    return normalize_username(value).casefold()


@dataclass(frozen=True)
class UserAccount:
    id: str
    username: str
    role: str
    active: bool
    must_change_password: bool
    created_at: str

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


@dataclass(frozen=True)
class CatalogSource:
    path: str
    writable: bool = False


@dataclass(frozen=True)
class PersonalCatalog:
    id: str
    owner_user_id: str
    name: str
    sources: tuple[CatalogSource, ...]
    created_at: str

    @property
    def write_path(self) -> str:
        writable = next((source.path for source in self.sources if source.writable), "")
        return writable or (self.sources[0].path if self.sources else "")


@dataclass(frozen=True)
class AuthenticatedIdentity:
    user: UserAccount
    catalog: PersonalCatalog
    expires_at: int
