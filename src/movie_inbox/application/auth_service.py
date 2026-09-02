"""Local password authentication and opaque session management."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from movie_inbox.application.identity_repository import IdentityRepository
from movie_inbox.domain.identity import (
    AuthenticatedIdentity,
    PersonalCatalog,
    UserAccount,
    normalize_username,
)

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 1024
SESSION_TOKEN_BYTES = 48
DEFAULT_SESSION_TTL_SECONDS = 14 * 24 * 60 * 60
DEFAULT_DEVICE_ACCESS_TTL_SECONDS = 15 * 60
DEFAULT_DEVICE_REFRESH_TTL_SECONDS = 30 * 24 * 60 * 60
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


class AuthenticationError(ValueError):
    """Raised when credentials or a session are invalid."""


class PasswordPolicyError(ValueError):
    """Raised when a password does not meet the local policy."""


class PasswordChangeRequiredError(ValueError):
    """Raised when a device cannot bypass the mandatory web password change."""


@dataclass(frozen=True)
class DeviceSession:
    """Plain device credentials returned once; persistence only receives their hashes."""

    access_token: str
    refresh_token: str
    identity: AuthenticatedIdentity
    access_expires_at: int
    refresh_expires_at: int


class PasswordHasher:
    scheme = "scrypt"

    def hash(self, password: str) -> str:
        value = validate_password(password)
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(
            value.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )
        return "$".join(
            (
                self.scheme,
                str(SCRYPT_N),
                str(SCRYPT_R),
                str(SCRYPT_P),
                _encode(salt),
                _encode(digest),
            )
        )

    def verify(self, password: str, encoded: str) -> bool:
        try:
            scheme, n_value, r_value, p_value, salt_value, digest_value = encoded.split("$", 5)
            if scheme != self.scheme:
                return False
            salt = _decode(salt_value)
            expected = _decode(digest_value)
            candidate = hashlib.scrypt(
                str(password or "").encode("utf-8"),
                salt=salt,
                n=int(n_value),
                r=int(r_value),
                p=int(p_value),
                dklen=len(expected),
            )
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(candidate, expected)


class AuthService:
    def __init__(
        self,
        repository: IdentityRepository,
        *,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        device_access_ttl_seconds: int = DEFAULT_DEVICE_ACCESS_TTL_SECONDS,
        device_refresh_ttl_seconds: int = DEFAULT_DEVICE_REFRESH_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
        hasher: PasswordHasher | None = None,
    ) -> None:
        self.repository = repository
        self.session_ttl_seconds = max(60, int(session_ttl_seconds))
        self.device_access_ttl_seconds = max(60, int(device_access_ttl_seconds))
        self.device_refresh_ttl_seconds = max(
            self.device_access_ttl_seconds + 60,
            int(device_refresh_ttl_seconds),
        )
        self.clock = clock
        self.hasher = hasher or PasswordHasher()
        self._dummy_hash = self.hasher.hash("movie-inbox-dummy-password")

    def bootstrap_owner(
        self,
        username: str,
        password: str,
        *,
        catalog_name: str,
        source_paths: list[str],
        write_path: str,
    ) -> tuple[UserAccount, PersonalCatalog]:
        normalized_username = normalize_username(username)
        password_hash = self.hasher.hash(password)
        return self.repository.create_owner(
            normalized_username,
            password_hash,
            catalog_name,
            source_paths,
            write_path,
        )

    def login(self, username: str, password: str) -> tuple[str, AuthenticatedIdentity]:
        user, catalog = self._authenticated_user(username, password)
        return self._create_session(user, catalog)

    def login_device(self, username: str, password: str, device_name: str) -> DeviceSession:
        user, catalog = self._authenticated_user(username, password)
        if user.must_change_password:
            raise PasswordChangeRequiredError("password_change_required")
        return self._create_device_session(user, catalog, validate_device_name(device_name))

    def refresh_device_session(self, refresh_token: str) -> DeviceSession | None:
        if not refresh_token or len(refresh_token) > 512:
            return None
        now = int(self.clock())
        access_expires_at = now + self.device_access_ttl_seconds
        refresh_expires_at = now + self.device_refresh_ttl_seconds
        access_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        next_refresh_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        identity = self.repository.rotate_device_session(
            session_token_hash(refresh_token),
            session_token_hash(access_token),
            session_token_hash(next_refresh_token),
            now,
            access_expires_at,
            refresh_expires_at,
        )
        if identity is None or identity.user.must_change_password:
            return None
        return DeviceSession(
            access_token,
            next_refresh_token,
            identity,
            access_expires_at,
            refresh_expires_at,
        )

    def authenticate_device(self, access_token: str) -> AuthenticatedIdentity | None:
        if not access_token or len(access_token) > 512:
            return None
        now = int(self.clock())
        token_hash = session_token_hash(access_token)
        identity = self.repository.device_session_identity(token_hash, now)
        if identity is not None:
            self.repository.touch_device_session(token_hash, now)
        return identity

    def logout_device(self, access_token: str) -> None:
        if access_token and len(access_token) <= 512:
            self.repository.delete_device_session(session_token_hash(access_token))

    def _authenticated_user(
        self, username: str, password: str
    ) -> tuple[UserAccount, PersonalCatalog]:
        try:
            normalized_username = normalize_username(username)
        except ValueError:
            credentials = None
        else:
            credentials = self.repository.credentials_for(normalized_username)
        encoded = credentials[1] if credentials else self._dummy_hash
        password_value = str(password or "")
        password_in_bounds = len(password_value) <= PASSWORD_MAX_LENGTH
        valid = (
            self.hasher.verify(password_value if password_in_bounds else "", encoded)
            and password_in_bounds
        )
        if not credentials or not valid or not credentials[0].active:
            raise AuthenticationError("invalid_credentials")

        user = credentials[0]
        catalog = self.repository.default_catalog_for(user.id)
        if catalog is None:
            raise AuthenticationError("catalog_unavailable")
        return user, catalog

    def change_password(
        self,
        identity: AuthenticatedIdentity,
        current_password: str,
        new_password: str,
    ) -> tuple[str, AuthenticatedIdentity]:
        current_password_value = str(current_password or "")
        current_password_in_bounds = len(current_password_value) <= PASSWORD_MAX_LENGTH
        credentials = self.repository.credentials_for(identity.user.username)
        if (
            not credentials
            or credentials[0].id != identity.user.id
            or not credentials[0].active
            or not current_password_in_bounds
            or not self.hasher.verify(current_password_value, credentials[1])
        ):
            raise AuthenticationError("invalid_credentials")
        if hmac.compare_digest(current_password_value, str(new_password or "")):
            raise PasswordPolicyError("New password must be different from the current password")
        updated = self.repository.replace_password(
            identity.user.id,
            self.hasher.hash(new_password),
            must_change_password=False,
        )
        catalog = self.repository.default_catalog_for(updated.id)
        if catalog is None:
            raise AuthenticationError("catalog_unavailable")
        return self._create_session(updated, catalog)

    def _create_session(
        self,
        user: UserAccount,
        catalog: PersonalCatalog,
    ) -> tuple[str, AuthenticatedIdentity]:
        now = int(self.clock())
        expires_at = now + self.session_ttl_seconds
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        self.repository.save_session(session_token_hash(token), user.id, now, expires_at)
        return token, AuthenticatedIdentity(user=user, catalog=catalog, expires_at=expires_at)

    def _create_device_session(
        self,
        user: UserAccount,
        catalog: PersonalCatalog,
        device_name: str,
    ) -> DeviceSession:
        now = int(self.clock())
        access_expires_at = now + self.device_access_ttl_seconds
        refresh_expires_at = now + self.device_refresh_ttl_seconds
        access_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        refresh_token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        self.repository.save_device_session(
            session_token_hash(access_token),
            session_token_hash(refresh_token),
            user.id,
            device_name,
            now,
            access_expires_at,
            refresh_expires_at,
        )
        return DeviceSession(
            access_token,
            refresh_token,
            AuthenticatedIdentity(user=user, catalog=catalog, expires_at=access_expires_at),
            access_expires_at,
            refresh_expires_at,
        )

    def authenticate(self, token: str) -> AuthenticatedIdentity | None:
        if not token or len(token) > 512:
            return None
        now = int(self.clock())
        token_hash = session_token_hash(token)
        return self.repository.session_identity(token_hash, now)

    def logout(self, token: str) -> None:
        if token and len(token) <= 512:
            self.repository.delete_session(session_token_hash(token))

    def validate_owner_catalog(self, source_paths: list[str], write_path: str) -> PersonalCatalog:
        return self.repository.validate_owner_catalog(source_paths, write_path)


def validate_password(password: str) -> str:
    value = str(password or "")
    if len(value) < PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError(
            f"Password must contain at least {PASSWORD_MIN_LENGTH} characters"
        )
    if len(value) > PASSWORD_MAX_LENGTH:
        raise PasswordPolicyError("Password is too long")
    return value


def validate_device_name(device_name: str) -> str:
    value = str(device_name or "").strip()
    if not 1 <= len(value) <= 80 or any(ord(character) < 32 for character in value):
        raise ValueError("invalid_device_name")
    return value


def session_token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
