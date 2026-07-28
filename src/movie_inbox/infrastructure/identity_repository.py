"""SQLite persistence for self-hosted users, sessions and personal catalogs."""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from movie_inbox.application.identity_repository import (
    IdentityAlreadyInitialized,
    IdentityCatalogMismatch,
    IdentityRepositoryError,
)
from movie_inbox.domain.identity import (
    AuthenticatedIdentity,
    CatalogSource,
    PersonalCatalog,
    UserAccount,
    username_key,
)


INSTANCE_SCHEMA_VERSION = 1
INSTANCE_SCHEMA = """
CREATE TABLE instance_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    username_key TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE catalogs (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 1 CHECK (is_default IN (0, 1)),
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_catalogs_default_owner
ON catalogs(owner_user_id) WHERE is_default = 1;

CREATE TABLE catalog_sources (
    catalog_id TEXT NOT NULL REFERENCES catalogs(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    writable INTEGER NOT NULL DEFAULT 0 CHECK (writable IN (0, 1)),
    PRIMARY KEY (catalog_id, position),
    UNIQUE (catalog_id, storage_path)
);

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL
);
CREATE INDEX ix_sessions_user ON sessions(user_id);
CREATE INDEX ix_sessions_expiry ON sessions(expires_at);
"""


class SqliteIdentityRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def initialize(self) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot initialize instance database: {self.path}") from error

    def has_users(self) -> bool:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    return connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot inspect instance database: {self.path}") from error

    def create_owner(
        self,
        username: str,
        password_hash: str,
        catalog_name: str,
        source_paths: list[str],
        write_path: str,
    ) -> tuple[UserAccount, PersonalCatalog]:
        sources, writable_path = _catalog_paths(source_paths, write_path)
        now = _utc_now()
        user_id = uuid.uuid4().hex
        catalog_id = uuid.uuid4().hex
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    if connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
                        connection.rollback()
                        raise IdentityAlreadyInitialized("The instance already has an owner account")
                    connection.execute(
                        """INSERT INTO users(
                            id, username, username_key, password_hash, role, active,
                            must_change_password, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'owner', 1, 0, ?, ?)""",
                        (user_id, username, username_key(username), password_hash, now, now),
                    )
                    connection.execute(
                        """INSERT INTO catalogs(id, owner_user_id, name, is_default, created_at)
                        VALUES (?, ?, ?, 1, ?)""",
                        (catalog_id, user_id, str(catalog_name or "Mi catalogo").strip(), now),
                    )
                    for position, path in enumerate(sources):
                        connection.execute(
                            """INSERT INTO catalog_sources(catalog_id, position, storage_path, writable)
                            VALUES (?, ?, ?, ?)""",
                            (catalog_id, position, path, int(path == writable_path)),
                        )
                    connection.commit()
            except IdentityAlreadyInitialized:
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot create owner account in: {self.path}") from error
        user = UserAccount(user_id, username, "owner", True, False, now)
        catalog = PersonalCatalog(
            catalog_id,
            user_id,
            str(catalog_name or "Mi catalogo").strip(),
            tuple(CatalogSource(path, path == writable_path) for path in sources),
            now,
        )
        return user, catalog

    def credentials_for(self, username: str) -> tuple[UserAccount, str] | None:
        try:
            key = username_key(username)
        except ValueError:
            return None
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    row = connection.execute(
                        "SELECT * FROM users WHERE username_key = ?",
                        (key,),
                    ).fetchone()
                    if row is None:
                        return None
                    return _user(row), str(row["password_hash"])
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot read account from: {self.path}") from error

    def default_catalog_for(self, user_id: str) -> PersonalCatalog | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    return self._catalog(connection, user_id)
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot read personal catalog from: {self.path}") from error

    def save_session(self, token_hash: str, user_id: str, created_at: int, expires_at: int) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (created_at,))
                    connection.execute(
                        """INSERT INTO sessions(token_hash, user_id, created_at, expires_at, last_seen_at)
                        VALUES (?, ?, ?, ?, ?)""",
                        (token_hash, user_id, created_at, expires_at, created_at),
                    )
                    connection.commit()
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot create session in: {self.path}") from error

    def session_identity(self, token_hash: str, now: int) -> AuthenticatedIdentity | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    row = connection.execute(
                        """SELECT
                            users.*,
                            sessions.expires_at AS session_expires_at
                        FROM sessions
                        JOIN users ON users.id = sessions.user_id
                        WHERE sessions.token_hash = ? AND sessions.expires_at > ? AND users.active = 1""",
                        (token_hash, now),
                    ).fetchone()
                    if row is None:
                        connection.execute(
                            "DELETE FROM sessions WHERE token_hash = ? OR expires_at <= ?",
                            (token_hash, now),
                        )
                        connection.commit()
                        return None
                    user = _user(row)
                    catalog = self._catalog(connection, user.id)
                    if catalog is None:
                        return None
                    return AuthenticatedIdentity(user, catalog, int(row["session_expires_at"]))
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot validate session in: {self.path}") from error

    def touch_session(self, token_hash: str, seen_at: int) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute(
                        "UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?",
                        (seen_at, token_hash),
                    )
                    connection.commit()
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot update session in: {self.path}") from error

    def delete_session(self, token_hash: str) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
                    connection.commit()
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot delete session from: {self.path}") from error

    def delete_user_sessions(self, user_id: str) -> int:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    cursor = connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                    connection.commit()
                    return max(0, cursor.rowcount)
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot clear sessions from: {self.path}") from error

    def owner(self) -> UserAccount | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    row = connection.execute(
                        "SELECT * FROM users WHERE role = 'owner' ORDER BY created_at LIMIT 1"
                    ).fetchone()
                    return _user(row) if row else None
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot read owner from: {self.path}") from error

    def validate_owner_catalog(self, source_paths: list[str], write_path: str) -> PersonalCatalog:
        owner = self.owner()
        if owner is None:
            raise IdentityRepositoryError("The instance does not have an owner account")
        catalog = self.default_catalog_for(owner.id)
        if catalog is None:
            raise IdentityRepositoryError("The owner does not have a personal catalog")
        configured_sources, configured_write = _catalog_paths(source_paths, write_path)
        stored_sources = [source.path for source in catalog.sources]
        if configured_sources != stored_sources or _normalized_path(catalog.write_path) != configured_write:
            raise IdentityCatalogMismatch(
                "Configured catalog files do not match the personal catalog registered for the owner"
            )
        return catalog

    def _connect(self) -> sqlite3.Connection:
        created = not self.path.exists()
        parent_created = not self.path.parent.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if parent_created:
            try:
                os.chmod(self.path.parent, 0o700)
            except OSError:
                pass
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        if created:
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'instance_migrations'"
        ).fetchone()
        if not exists:
            has_tables = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()
            if has_tables:
                raise IdentityRepositoryError(
                    f"Instance database has tables but no migration history: {self.path}"
                )
            try:
                connection.executescript("BEGIN IMMEDIATE;\n" + INSTANCE_SCHEMA)
                connection.execute(
                    "INSERT INTO instance_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (1, "local accounts, sessions and personal catalogs", _utc_now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM instance_migrations"
        ).fetchone()
        version = int(row["version"] if row else 0)
        if version != INSTANCE_SCHEMA_VERSION:
            raise IdentityRepositoryError(
                f"Unsupported instance schema v{version}; expected v{INSTANCE_SCHEMA_VERSION}: {self.path}"
            )

    @staticmethod
    def _catalog(connection: sqlite3.Connection, user_id: str) -> PersonalCatalog | None:
        row = connection.execute(
            """SELECT * FROM catalogs
            WHERE owner_user_id = ? AND is_default = 1
            ORDER BY created_at LIMIT 1""",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        sources = connection.execute(
            """SELECT storage_path, writable FROM catalog_sources
            WHERE catalog_id = ? ORDER BY position""",
            (row["id"],),
        ).fetchall()
        return PersonalCatalog(
            str(row["id"]),
            str(row["owner_user_id"]),
            str(row["name"]),
            tuple(CatalogSource(str(source["storage_path"]), bool(source["writable"])) for source in sources),
            str(row["created_at"]),
        )


def _user(row: sqlite3.Row) -> UserAccount:
    return UserAccount(
        id=str(row["id"]),
        username=str(row["username"]),
        role=str(row["role"]),
        active=bool(row["active"]),
        must_change_password=bool(row["must_change_password"]),
        created_at=str(row["created_at"]),
    )


def _catalog_paths(source_paths: list[str], write_path: str) -> tuple[list[str], str]:
    writable = _normalized_path(write_path)
    sources: set[str] = set()
    for value in [*source_paths, writable]:
        path = _normalized_path(value)
        if path:
            sources.add(path)
    if not sources or not writable:
        raise ValueError("A personal catalog requires at least one source and a write path")
    return sorted(sources), writable


def _normalized_path(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
