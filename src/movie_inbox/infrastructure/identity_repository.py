"""SQLite persistence for self-hosted users, sessions and personal catalogs."""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from movie_inbox.application.identity_repository import (
    IdentityAlreadyInitialized,
    IdentityCatalogMismatch,
    IdentityConflict,
    IdentityMemberActive,
    IdentityNotFound,
    IdentityOwnerProtected,
    IdentityRepositoryError,
)
from movie_inbox.domain.identity import (
    ArchivedMember,
    AuthenticatedIdentity,
    CatalogSource,
    PersonalCatalog,
    UserAccount,
    username_key,
)
from movie_inbox.domain.privacy import ItemPrivacyOverride, PrivacyPreferences

INSTANCE_SCHEMA_VERSION = 7
INSTANCE_SCHEMA_V1 = """
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

INSTANCE_SCHEMA_V2 = """
CREATE TABLE user_privacy_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    catalog_shared INTEGER NOT NULL DEFAULT 0 CHECK (catalog_shared IN (0, 1)),
    share_status INTEGER NOT NULL DEFAULT 0 CHECK (share_status IN (0, 1)),
    share_watched_at INTEGER NOT NULL DEFAULT 0 CHECK (share_watched_at IN (0, 1)),
    share_history INTEGER NOT NULL DEFAULT 0 CHECK (share_history IN (0, 1)),
    share_rating INTEGER NOT NULL DEFAULT 0 CHECK (share_rating IN (0, 1)),
    share_review INTEGER NOT NULL DEFAULT 0 CHECK (share_review IN (0, 1)),
    updated_at TEXT NOT NULL
);

CREATE TABLE item_privacy_overrides (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    catalog_id TEXT NOT NULL REFERENCES catalogs(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    field TEXT NOT NULL CHECK (field IN ('rating', 'review')),
    visibility TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, catalog_id, item_id, field)
);
CREATE INDEX ix_item_privacy_catalog ON item_privacy_overrides(catalog_id, item_id);

CREATE TABLE archived_members (
    id TEXT PRIMARY KEY,
    former_user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    catalog_name TEXT NOT NULL,
    archived_at TEXT NOT NULL
);

CREATE TABLE archived_catalog_sources (
    archive_id TEXT NOT NULL REFERENCES archived_members(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    writable INTEGER NOT NULL DEFAULT 0 CHECK (writable IN (0, 1)),
    PRIMARY KEY (archive_id, position),
    UNIQUE (archive_id, storage_path)
);
"""

INSTANCE_SCHEMA_V3 = """
CREATE TABLE curated_collections (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    owner_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    visibility TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'published')),
    source_kind TEXT NOT NULL DEFAULT 'user' CHECK (source_kind IN ('builtin', 'import', 'user')),
    source_url TEXT NOT NULL DEFAULT '',
    source_label TEXT NOT NULL DEFAULT '',
    built_in INTEGER NOT NULL DEFAULT 0 CHECK (built_in IN (0, 1)),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX ix_curated_collections_visibility
ON curated_collections(visibility, title);

CREATE TABLE curated_collection_items (
    collection_id TEXT NOT NULL REFERENCES curated_collections(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    payload_json TEXT NOT NULL,
    PRIMARY KEY (collection_id, item_id),
    UNIQUE (collection_id, position)
);
CREATE INDEX ix_curated_collection_items_position
ON curated_collection_items(collection_id, position);

CREATE TABLE collection_follows (
    collection_id TEXT NOT NULL REFERENCES curated_collections(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followed_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, user_id)
);
CREATE INDEX ix_collection_follows_user
ON collection_follows(user_id, followed_at);

CREATE TABLE collection_seed_records (
    seed_key TEXT PRIMARY KEY,
    installed_at TEXT NOT NULL
);
"""

INSTANCE_SCHEMA_V4 = """
CREATE TABLE import_drafts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    source_format TEXT NOT NULL CHECK (source_format IN ('txt', 'csv', 'json')),
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ready', 'applying', 'applied', 'failed')),
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    applied_at INTEGER NOT NULL DEFAULT 0,
    result_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX ix_import_drafts_user_updated
ON import_drafts(user_id, updated_at DESC);
CREATE INDEX ix_import_drafts_expiry
ON import_drafts(expires_at);

CREATE TABLE import_draft_items (
    draft_id TEXT NOT NULL REFERENCES import_drafts(id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    state TEXT NOT NULL CHECK (state IN ('new', 'present', 'review', 'invalid')),
    reason TEXT NOT NULL DEFAULT '',
    label TEXT NOT NULL,
    item_json TEXT NOT NULL DEFAULT '{}',
    candidates_json TEXT NOT NULL DEFAULT '[]',
    collection_eligible INTEGER NOT NULL DEFAULT 0 CHECK (collection_eligible IN (0, 1)),
    PRIMARY KEY (draft_id, item_id),
    UNIQUE (draft_id, position)
);
CREATE INDEX ix_import_draft_items_state
ON import_draft_items(draft_id, state, position);
"""

INSTANCE_SCHEMA_V5 = """
CREATE TABLE media_libraries (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    root_key TEXT NOT NULL UNIQUE,
    schedule TEXT NOT NULL DEFAULT 'manual' CHECK (schedule IN ('manual', 'hourly', 'daily')),
    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'unverified'
        CHECK (status IN (
            'unverified', 'ready', 'scanning', 'paused', 'offline', 'warning', 'error'
        )),
    max_missing_ratio REAL NOT NULL DEFAULT 0.5
        CHECK (max_missing_ratio >= 0 AND max_missing_ratio <= 1),
    verified_at INTEGER NOT NULL DEFAULT 0,
    last_scan_at INTEGER NOT NULL DEFAULT 0,
    next_scan_at INTEGER NOT NULL DEFAULT 0,
    created_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX ix_media_libraries_due
ON media_libraries(active, schedule, next_scan_at);

CREATE TABLE library_scan_runs (
    id TEXT PRIMARY KEY,
    library_id TEXT NOT NULL REFERENCES media_libraries(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('dry_run', 'apply')),
    trigger TEXT NOT NULL CHECK (trigger IN ('manual', 'scheduled')),
    status TEXT NOT NULL
        CHECK (status IN ('queued', 'running', 'completed', 'partial', 'blocked', 'failed')),
    created_at INTEGER NOT NULL,
    started_at INTEGER NOT NULL DEFAULT 0,
    finished_at INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT NOT NULL DEFAULT '{}',
    errors_json TEXT NOT NULL DEFAULT '[]',
    preview_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX ix_library_scan_runs_library
ON library_scan_runs(library_id, created_at DESC);
CREATE UNIQUE INDEX ux_library_active_run
ON library_scan_runs(library_id) WHERE status IN ('queued', 'running');

CREATE TABLE library_files (
    id TEXT PRIMARY KEY,
    library_id TEXT NOT NULL REFERENCES media_libraries(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    relative_key TEXT NOT NULL,
    name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    modified_ns INTEGER NOT NULL DEFAULT 0,
    modified_at TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    detected_title TEXT NOT NULL DEFAULT '',
    detected_year TEXT NOT NULL DEFAULT '',
    detected_kind TEXT NOT NULL DEFAULT 'pelicula',
    state TEXT NOT NULL DEFAULT 'new' CHECK (state IN ('new', 'matched', 'review', 'ignored')),
    work_key TEXT NOT NULL DEFAULT '',
    identity_json TEXT NOT NULL DEFAULT '{}',
    candidates_json TEXT NOT NULL DEFAULT '[]',
    available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    first_seen_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    last_run_id TEXT NOT NULL DEFAULT '',
    UNIQUE (library_id, relative_key)
);
CREATE INDEX ix_library_files_fingerprint
ON library_files(library_id, fingerprint);
CREATE INDEX ix_library_files_review
ON library_files(state, available, updated_at DESC);
CREATE INDEX ix_library_files_availability
ON library_files(available, state, work_key);
"""

INSTANCE_SCHEMA_V6 = """
CREATE TABLE home_featured_snapshots (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    local_date TEXT NOT NULL,
    entries_json TEXT NOT NULL DEFAULT '[]',
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, local_date)
);
CREATE INDEX ix_home_featured_snapshots_user_date
ON home_featured_snapshots(user_id, local_date DESC);
"""

INSTANCE_SCHEMA_V7 = """
CREATE TABLE scanner_history (
    id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'applied' CHECK (status IN ('applied', 'undone')),
    mode TEXT NOT NULL DEFAULT 'persistent',
    created_at TEXT NOT NULL,
    undone_at TEXT NOT NULL DEFAULT '',
    summary_json TEXT NOT NULL DEFAULT '{}',
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    catalog_before_json TEXT NOT NULL DEFAULT 'null',
    catalog_after_json TEXT NOT NULL DEFAULT 'null',
    catalog_path TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_scanner_history_created
ON scanner_history(created_at DESC);
"""

INSTANCE_MIGRATIONS = {
    2: ("privacy preferences and reversible member archives", INSTANCE_SCHEMA_V2),
    3: ("curated collections and local follows", INSTANCE_SCHEMA_V3),
    4: ("bounded user import drafts", INSTANCE_SCHEMA_V4),
    5: ("managed media libraries and shared availability", INSTANCE_SCHEMA_V5),
    6: ("daily featured recommendation snapshots", INSTANCE_SCHEMA_V6),
    7: ("reversible scanner review history", INSTANCE_SCHEMA_V7),
}


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
                raise IdentityRepositoryError(
                    f"Cannot initialize instance database: {self.path}"
                ) from error

    def has_users(self) -> bool:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    return connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot inspect instance database: {self.path}"
                ) from error

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
                        raise IdentityAlreadyInitialized(
                            "The instance already has an owner account"
                        )
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
                            """INSERT INTO catalog_sources
                            (catalog_id, position, storage_path, writable)
                            VALUES (?, ?, ?, ?)""",
                            (catalog_id, position, path, int(path == writable_path)),
                        )
                    connection.commit()
            except IdentityAlreadyInitialized:
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot create owner account in: {self.path}"
                ) from error
        user = UserAccount(user_id, username, "owner", True, False, now)
        catalog = PersonalCatalog(
            catalog_id,
            user_id,
            str(catalog_name or "Mi catalogo").strip(),
            tuple(CatalogSource(path, path == writable_path) for path in sources),
            now,
        )
        return user, catalog

    def create_member(
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
                    connection.execute(
                        """INSERT INTO users(
                            id, username, username_key, password_hash, role, active,
                            must_change_password, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'member', 1, 1, ?, ?)""",
                        (user_id, username, username_key(username), password_hash, now, now),
                    )
                    connection.execute(
                        """INSERT INTO catalogs(id, owner_user_id, name, is_default, created_at)
                        VALUES (?, ?, ?, 1, ?)""",
                        (catalog_id, user_id, str(catalog_name or "Mi catalogo").strip(), now),
                    )
                    for position, path in enumerate(sources):
                        connection.execute(
                            """INSERT INTO catalog_sources
                            (catalog_id, position, storage_path, writable)
                            VALUES (?, ?, ?, ?)""",
                            (catalog_id, position, path, int(path == writable_path)),
                        )
                    connection.commit()
            except sqlite3.IntegrityError as error:
                raise IdentityConflict("Username is already in use") from error
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot create member account in: {self.path}"
                ) from error
        user = UserAccount(user_id, username, "member", True, True, now)
        catalog = PersonalCatalog(
            catalog_id,
            user_id,
            str(catalog_name or "Mi catalogo").strip(),
            tuple(CatalogSource(path, path == writable_path) for path in sources),
            now,
        )
        return user, catalog

    def list_accounts(self) -> list[tuple[UserAccount, PersonalCatalog]]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    rows = connection.execute(
                        """SELECT * FROM users
                        ORDER BY CASE role WHEN 'owner' THEN 0 ELSE 1 END, username_key"""
                    ).fetchall()
                    accounts: list[tuple[UserAccount, PersonalCatalog]] = []
                    for row in rows:
                        user = _user(row)
                        catalog = self._catalog(connection, user.id)
                        if catalog is None:
                            raise IdentityRepositoryError(
                                f"Account {user.id} does not have a default personal catalog"
                            )
                        accounts.append((user, catalog))
                    return accounts
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot list accounts from: {self.path}") from error

    def account(self, user_id: str) -> UserAccount | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    row = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                    return _user(row) if row else None
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot read account from: {self.path}") from error

    def set_user_active(self, user_id: str, active: bool) -> UserAccount:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                    if row is None:
                        connection.rollback()
                        raise IdentityNotFound("Member account was not found")
                    if str(row["role"]) == "owner":
                        connection.rollback()
                        raise IdentityOwnerProtected("The owner account cannot be deactivated")
                    connection.execute(
                        "UPDATE users SET active = ?, updated_at = ? WHERE id = ?",
                        (int(active), _utc_now(), user_id),
                    )
                    if not active:
                        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                    updated = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                    connection.commit()
                    return _user(updated)
            except (IdentityNotFound, IdentityOwnerProtected):
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot update account in: {self.path}") from error

    def update_member(
        self,
        user_id: str,
        username: str,
        catalog_name: str,
    ) -> tuple[UserAccount, PersonalCatalog]:
        now = _utc_now()
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                    if row is None:
                        connection.rollback()
                        raise IdentityNotFound("Member account was not found")
                    if str(row["role"]) == "owner":
                        connection.rollback()
                        raise IdentityOwnerProtected(
                            "The owner account cannot be edited as a member"
                        )
                    connection.execute(
                        "UPDATE users SET username = ?, username_key = ?, updated_at = ? "
                        "WHERE id = ?",
                        (username, username_key(username), now, user_id),
                    )
                    cursor = connection.execute(
                        "UPDATE catalogs SET name = ? WHERE owner_user_id = ? AND is_default = 1",
                        (catalog_name, user_id),
                    )
                    if cursor.rowcount != 1:
                        connection.rollback()
                        raise IdentityNotFound("Member personal catalog was not found")
                    updated = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                    catalog = self._catalog(connection, user_id)
                    connection.commit()
                    if catalog is None:
                        raise IdentityNotFound("Member personal catalog was not found")
                    return _user(updated), catalog
            except (IdentityNotFound, IdentityOwnerProtected):
                raise
            except sqlite3.IntegrityError as error:
                raise IdentityConflict("Username is already in use") from error
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot update member in: {self.path}") from error

    def archive_member(self, user_id: str) -> ArchivedMember:
        archive_id = uuid.uuid4().hex
        archived_at = _utc_now()
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    user_row = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                    if user_row is None:
                        connection.rollback()
                        raise IdentityNotFound("Member account was not found")
                    if str(user_row["role"]) == "owner":
                        connection.rollback()
                        raise IdentityOwnerProtected("The owner account cannot be archived")
                    if bool(user_row["active"]):
                        connection.rollback()
                        raise IdentityMemberActive(
                            "Deactivate the member before archiving the account"
                        )
                    catalog_row = connection.execute(
                        "SELECT * FROM catalogs WHERE owner_user_id = ? AND is_default = 1",
                        (user_id,),
                    ).fetchone()
                    if catalog_row is None:
                        connection.rollback()
                        raise IdentityNotFound("Member personal catalog was not found")
                    source_rows = connection.execute(
                        "SELECT * FROM catalog_sources WHERE catalog_id = ? ORDER BY position",
                        (catalog_row["id"],),
                    ).fetchall()
                    if not source_rows:
                        connection.rollback()
                        raise IdentityNotFound("Member personal catalog has no sources")
                    connection.execute(
                        """INSERT INTO archived_members(
                            id, former_user_id, username, catalog_name, archived_at
                        ) VALUES (?, ?, ?, ?, ?)""",
                        (
                            archive_id,
                            user_id,
                            str(user_row["username"]),
                            str(catalog_row["name"]),
                            archived_at,
                        ),
                    )
                    for source in source_rows:
                        connection.execute(
                            """INSERT INTO archived_catalog_sources(
                                archive_id, position, storage_path, writable
                            ) VALUES (?, ?, ?, ?)""",
                            (
                                archive_id,
                                int(source["position"]),
                                str(source["storage_path"]),
                                int(source["writable"]),
                            ),
                        )
                    connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    connection.commit()
                    return ArchivedMember(
                        archive_id,
                        user_id,
                        str(user_row["username"]),
                        str(catalog_row["name"]),
                        tuple(
                            CatalogSource(str(source["storage_path"]), bool(source["writable"]))
                            for source in source_rows
                        ),
                        archived_at,
                    )
            except (IdentityMemberActive, IdentityNotFound, IdentityOwnerProtected):
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot archive member in: {self.path}") from error

    def list_archived_members(self) -> list[ArchivedMember]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    rows = connection.execute(
                        "SELECT * FROM archived_members ORDER BY archived_at DESC"
                    ).fetchall()
                    return [self._archived_member(connection, row) for row in rows]
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot list archived members from: {self.path}"
                ) from error

    def restore_archived_member(
        self,
        archive_id: str,
        username: str,
        password_hash: str,
    ) -> tuple[UserAccount, PersonalCatalog]:
        now = _utc_now()
        user_id = uuid.uuid4().hex
        catalog_id = uuid.uuid4().hex
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    archive_row = connection.execute(
                        "SELECT * FROM archived_members WHERE id = ?",
                        (archive_id,),
                    ).fetchone()
                    if archive_row is None:
                        connection.rollback()
                        raise IdentityNotFound("Archived member was not found")
                    source_rows = connection.execute(
                        "SELECT * FROM archived_catalog_sources "
                        "WHERE archive_id = ? ORDER BY position",
                        (archive_id,),
                    ).fetchall()
                    if not source_rows:
                        connection.rollback()
                        raise IdentityNotFound("Archived personal catalog has no sources")
                    connection.execute(
                        """INSERT INTO users(
                            id, username, username_key, password_hash, role, active,
                            must_change_password, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'member', 1, 1, ?, ?)""",
                        (user_id, username, username_key(username), password_hash, now, now),
                    )
                    connection.execute(
                        """INSERT INTO catalogs(id, owner_user_id, name, is_default, created_at)
                        VALUES (?, ?, ?, 1, ?)""",
                        (catalog_id, user_id, str(archive_row["catalog_name"]), now),
                    )
                    for source in source_rows:
                        connection.execute(
                            """INSERT INTO catalog_sources
                            (catalog_id, position, storage_path, writable)
                            VALUES (?, ?, ?, ?)""",
                            (
                                catalog_id,
                                int(source["position"]),
                                str(source["storage_path"]),
                                int(source["writable"]),
                            ),
                        )
                    connection.execute("DELETE FROM archived_members WHERE id = ?", (archive_id,))
                    connection.commit()
                    user = UserAccount(user_id, username, "member", True, True, now)
                    catalog = PersonalCatalog(
                        catalog_id,
                        user_id,
                        str(archive_row["catalog_name"]),
                        tuple(
                            CatalogSource(str(source["storage_path"]), bool(source["writable"]))
                            for source in source_rows
                        ),
                        now,
                    )
                    return user, catalog
            except IdentityNotFound:
                raise
            except sqlite3.IntegrityError as error:
                raise IdentityConflict("Username is already in use") from error
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot restore member in: {self.path}") from error

    def replace_password(
        self,
        user_id: str,
        password_hash: str,
        *,
        must_change_password: bool,
    ) -> UserAccount:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    cursor = connection.execute(
                        """UPDATE users
                        SET password_hash = ?, must_change_password = ?, updated_at = ?
                        WHERE id = ?""",
                        (password_hash, int(must_change_password), _utc_now(), user_id),
                    )
                    if cursor.rowcount != 1:
                        connection.rollback()
                        raise IdentityNotFound("Account was not found")
                    connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
                    updated = connection.execute(
                        "SELECT * FROM users WHERE id = ?", (user_id,)
                    ).fetchone()
                    connection.commit()
                    return _user(updated)
            except IdentityNotFound:
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(f"Cannot replace password in: {self.path}") from error

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
                raise IdentityRepositoryError(
                    f"Cannot read personal catalog from: {self.path}"
                ) from error

    def privacy_for(self, user_id: str) -> PrivacyPreferences:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    row = connection.execute(
                        "SELECT * FROM user_privacy_preferences WHERE user_id = ?",
                        (user_id,),
                    ).fetchone()
                    return _privacy(row)
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot read privacy preferences from: {self.path}"
                ) from error

    def update_privacy(self, user_id: str, preferences: PrivacyPreferences) -> PrivacyPreferences:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    if (
                        connection.execute(
                            "SELECT 1 FROM users WHERE id = ?", (user_id,)
                        ).fetchone()
                        is None
                    ):
                        connection.rollback()
                        raise IdentityNotFound("Account was not found")
                    connection.execute(
                        """INSERT INTO user_privacy_preferences(
                            user_id, catalog_shared, share_status, share_watched_at,
                            share_history, share_rating, share_review, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            catalog_shared = excluded.catalog_shared,
                            share_status = excluded.share_status,
                            share_watched_at = excluded.share_watched_at,
                            share_history = excluded.share_history,
                            share_rating = excluded.share_rating,
                            share_review = excluded.share_review,
                            updated_at = excluded.updated_at""",
                        (
                            user_id,
                            int(preferences.catalog_shared),
                            int(preferences.share_status),
                            int(preferences.share_watched_at),
                            int(preferences.share_history),
                            int(preferences.share_rating),
                            int(preferences.share_review),
                            _utc_now(),
                        ),
                    )
                    connection.commit()
                    return preferences
            except IdentityNotFound:
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot update privacy preferences in: {self.path}"
                ) from error

    def item_privacy_overrides(
        self,
        user_id: str,
        catalog_id: str,
    ) -> dict[str, ItemPrivacyOverride]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    self._require_owned_catalog(connection, user_id, catalog_id)
                    rows = connection.execute(
                        """SELECT item_id, field, visibility FROM item_privacy_overrides
                        WHERE user_id = ? AND catalog_id = ? ORDER BY item_id, field""",
                        (user_id, catalog_id),
                    ).fetchall()
                    values: dict[str, dict[str, str]] = {}
                    for row in rows:
                        values.setdefault(str(row["item_id"]), {})[str(row["field"])] = str(
                            row["visibility"]
                        )
                    return {
                        item_id: ItemPrivacyOverride(
                            rating=fields.get("rating", "inherit"),
                            review=fields.get("review", "inherit"),
                        )
                        for item_id, fields in values.items()
                    }
            except IdentityNotFound:
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot read item privacy from: {self.path}"
                ) from error

    def set_item_privacy(
        self,
        user_id: str,
        catalog_id: str,
        item_id: str,
        override: ItemPrivacyOverride,
    ) -> ItemPrivacyOverride:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    self._require_owned_catalog(connection, user_id, catalog_id)
                    for field in ("rating", "review"):
                        visibility = getattr(override, field)
                        if visibility == "inherit":
                            connection.execute(
                                """DELETE FROM item_privacy_overrides
                                WHERE user_id = ? AND catalog_id = ? AND item_id = ?
                                    AND field = ?""",
                                (user_id, catalog_id, item_id, field),
                            )
                        else:
                            connection.execute(
                                """INSERT INTO item_privacy_overrides(
                                    user_id, catalog_id, item_id, field, visibility, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?)
                                ON CONFLICT(user_id, catalog_id, item_id, field) DO UPDATE SET
                                    visibility = excluded.visibility,
                                    updated_at = excluded.updated_at""",
                                (user_id, catalog_id, item_id, field, visibility, _utc_now()),
                            )
                    connection.commit()
                    return override
            except IdentityNotFound:
                raise
            except sqlite3.Error as error:
                raise IdentityRepositoryError(
                    f"Cannot update item privacy in: {self.path}"
                ) from error

    def save_session(self, token_hash: str, user_id: str, created_at: int, expires_at: int) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (created_at,))
                    connection.execute(
                        """INSERT INTO sessions
                        (token_hash, user_id, created_at, expires_at, last_seen_at)
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
                        WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                            AND users.active = 1""",
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
                    cursor = connection.execute(
                        "DELETE FROM sessions WHERE user_id = ?", (user_id,)
                    )
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
        if (
            configured_sources != stored_sources
            or _normalized_path(catalog.write_path) != configured_write
        ):
            raise IdentityCatalogMismatch(
                "Configured catalog files do not match the personal catalog "
                "registered for the owner"
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
                connection.executescript("BEGIN IMMEDIATE;\n" + INSTANCE_SCHEMA_V1)
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
        if version < 1 or version > INSTANCE_SCHEMA_VERSION:
            raise IdentityRepositoryError(
                f"Unsupported instance schema v{version}; "
                f"latest is v{INSTANCE_SCHEMA_VERSION}: {self.path}"
            )
        for target_version in range(version + 1, INSTANCE_SCHEMA_VERSION + 1):
            migration = INSTANCE_MIGRATIONS.get(target_version)
            if migration is None:
                raise IdentityRepositoryError(f"Missing instance migration v{target_version}")
            name, script = migration
            try:
                connection.executescript("BEGIN IMMEDIATE;\n" + script)
                connection.execute(
                    "INSERT INTO instance_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (target_version, name, _utc_now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

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
            tuple(
                CatalogSource(str(source["storage_path"]), bool(source["writable"]))
                for source in sources
            ),
            str(row["created_at"]),
        )

    @staticmethod
    def _archived_member(connection: sqlite3.Connection, row: sqlite3.Row) -> ArchivedMember:
        sources = connection.execute(
            """SELECT storage_path, writable FROM archived_catalog_sources
            WHERE archive_id = ? ORDER BY position""",
            (row["id"],),
        ).fetchall()
        return ArchivedMember(
            str(row["id"]),
            str(row["former_user_id"]),
            str(row["username"]),
            str(row["catalog_name"]),
            tuple(
                CatalogSource(str(source["storage_path"]), bool(source["writable"]))
                for source in sources
            ),
            str(row["archived_at"]),
        )

    @staticmethod
    def _require_owned_catalog(
        connection: sqlite3.Connection,
        user_id: str,
        catalog_id: str,
    ) -> None:
        row = connection.execute(
            "SELECT 1 FROM catalogs WHERE id = ? AND owner_user_id = ?",
            (catalog_id, user_id),
        ).fetchone()
        if row is None:
            raise IdentityNotFound("Personal catalog was not found")


def _user(row: sqlite3.Row) -> UserAccount:
    return UserAccount(
        id=str(row["id"]),
        username=str(row["username"]),
        role=str(row["role"]),
        active=bool(row["active"]),
        must_change_password=bool(row["must_change_password"]),
        created_at=str(row["created_at"]),
    )


def _privacy(row: sqlite3.Row | None) -> PrivacyPreferences:
    if row is None:
        return PrivacyPreferences()
    return PrivacyPreferences(
        catalog_shared=bool(row["catalog_shared"]),
        share_status=bool(row["share_status"]),
        share_watched_at=bool(row["share_watched_at"]),
        share_history=bool(row["share_history"]),
        share_rating=bool(row["share_rating"]),
        share_review=bool(row["share_review"]),
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
    return datetime.now(UTC).isoformat()
