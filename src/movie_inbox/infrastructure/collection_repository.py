"""SQLite repository for instance-local curated collections."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.domain.collections import (
    CollectionItem,
    CuratedCollection,
    normalize_collection_item,
)


class SqliteCollectionRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def install_once(self, seed_key: str, collection: CuratedCollection) -> bool:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if connection.execute(
                        "SELECT 1 FROM collection_seed_records WHERE seed_key = ?",
                        (seed_key,),
                    ).fetchone():
                        connection.rollback()
                        return False
                    if (
                        connection.execute(
                            "SELECT 1 FROM users WHERE id = ? AND active = 1",
                            (collection.owner_user_id,),
                        ).fetchone()
                        is None
                    ):
                        connection.rollback()
                        raise CollectionRepositoryError("Collection seed owner is unavailable")
                    self._insert_collection(connection, collection)
                    connection.execute(
                        "INSERT INTO collection_seed_records(seed_key, installed_at) VALUES (?, ?)",
                        (seed_key, collection.created_at),
                    )
                    connection.commit()
                    return True
            except CollectionRepositoryError:
                raise
            except sqlite3.Error as error:
                raise CollectionRepositoryError(
                    f"Cannot install collection seed in: {self.path}"
                ) from error

    def create_private(self, collection: CuratedCollection) -> bool:
        if (
            collection.visibility != "private"
            or collection.built_in
            or collection.source_kind != "import"
        ):
            raise ValueError("Imported collections must be private, non-built-in collections")
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    existing = connection.execute(
                        "SELECT owner_user_id, source_kind FROM curated_collections WHERE id = ?",
                        (collection.id,),
                    ).fetchone()
                    if existing:
                        connection.rollback()
                        if (
                            str(existing["owner_user_id"] or "") == collection.owner_user_id
                            and str(existing["source_kind"]) == "import"
                        ):
                            return False
                        raise CollectionRepositoryError("Collection id is already in use")
                    active = connection.execute(
                        "SELECT 1 FROM users WHERE id = ? AND active = 1",
                        (collection.owner_user_id,),
                    ).fetchone()
                    if active is None:
                        connection.rollback()
                        raise CollectionRepositoryError("Collection owner is unavailable")
                    self._insert_collection(connection, collection)
                    connection.commit()
                    return True
            except CollectionRepositoryError:
                raise
            except sqlite3.Error as error:
                raise CollectionRepositoryError(
                    f"Cannot create collection in: {self.path}"
                ) from error

    def list_accessible(self, user_id: str) -> list[CuratedCollection]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT c.*, u.username AS owner_username,
                            EXISTS(
                                SELECT 1 FROM collection_follows f
                                WHERE f.collection_id = c.id AND f.user_id = ?
                            ) AS followed
                        FROM curated_collections c
                        LEFT JOIN users u ON u.id = c.owner_user_id
                        WHERE c.visibility = 'published' OR c.owner_user_id = ?
                        ORDER BY followed DESC, c.built_in DESC, c.title COLLATE NOCASE""",
                        (user_id, user_id),
                    ).fetchall()
                    return [self._collection(connection, row) for row in rows]
            except sqlite3.Error as error:
                raise CollectionRepositoryError(
                    f"Cannot list collections from: {self.path}"
                ) from error

    def get_accessible(self, user_id: str, collection_id: str) -> CuratedCollection | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        """SELECT c.*, u.username AS owner_username,
                            EXISTS(
                                SELECT 1 FROM collection_follows f
                                WHERE f.collection_id = c.id AND f.user_id = ?
                            ) AS followed
                        FROM curated_collections c
                        LEFT JOIN users u ON u.id = c.owner_user_id
                        WHERE c.id = ? AND (c.visibility = 'published' OR c.owner_user_id = ?)""",
                        (user_id, collection_id, user_id),
                    ).fetchone()
                    return self._collection(connection, row) if row else None
            except sqlite3.Error as error:
                raise CollectionRepositoryError(
                    f"Cannot read collection from: {self.path}"
                ) from error

    def set_following(self, user_id: str, collection_id: str, following: bool) -> bool:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    available = connection.execute(
                        """SELECT 1 FROM curated_collections
                        WHERE id = ? AND (visibility = 'published' OR owner_user_id = ?)""",
                        (collection_id, user_id),
                    ).fetchone()
                    if available is None:
                        connection.rollback()
                        return False
                    if following:
                        cursor = connection.execute(
                            """INSERT OR IGNORE INTO collection_follows
                            (collection_id, user_id, followed_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)""",
                            (collection_id, user_id),
                        )
                    else:
                        cursor = connection.execute(
                            "DELETE FROM collection_follows "
                            "WHERE collection_id = ? AND user_id = ?",
                            (collection_id, user_id),
                        )
                    connection.commit()
                    return cursor.rowcount > 0
            except sqlite3.Error as error:
                raise CollectionRepositoryError(
                    f"Cannot update collection follow in: {self.path}"
                ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection

    @staticmethod
    def _insert_collection(connection: sqlite3.Connection, collection: CuratedCollection) -> None:
        connection.execute(
            """INSERT INTO curated_collections(
                id, slug, title, description, owner_user_id, visibility,
                source_kind, source_url, source_label, built_in, version,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                collection.id,
                collection.slug,
                collection.title,
                collection.description,
                collection.owner_user_id,
                collection.visibility,
                collection.source_kind,
                collection.source_url,
                collection.source_label,
                int(collection.built_in),
                collection.version,
                collection.created_at,
                collection.updated_at,
            ),
        )
        for entry in collection.items:
            connection.execute(
                """INSERT INTO curated_collection_items(
                    collection_id, item_id, position, payload_json
                ) VALUES (?, ?, ?, ?)""",
                (
                    collection.id,
                    entry.id,
                    entry.position,
                    _json_dump(normalize_collection_item(entry.item)),
                ),
            )

    @staticmethod
    def _collection(connection: sqlite3.Connection, row: sqlite3.Row) -> CuratedCollection:
        item_rows = connection.execute(
            """SELECT item_id, position, payload_json FROM curated_collection_items
            WHERE collection_id = ? ORDER BY position, item_id""",
            (row["id"],),
        ).fetchall()
        items = tuple(
            CollectionItem(
                id=str(item["item_id"]),
                position=int(item["position"]),
                item=normalize_collection_item(_json_object(item["payload_json"])),
            )
            for item in item_rows
        )
        return CuratedCollection(
            id=str(row["id"]),
            slug=str(row["slug"]),
            title=str(row["title"]),
            description=str(row["description"]),
            owner_user_id=str(row["owner_user_id"] or ""),
            visibility=str(row["visibility"]),
            source_kind=str(row["source_kind"]),
            source_url=str(row["source_url"]),
            source_label=str(row["source_label"]),
            built_in=bool(row["built_in"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            owner_username=str(row["owner_username"] or ""),
            followed=bool(row["followed"]),
            items=items,
        )


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _json_object(value: object) -> dict[str, object]:
    try:
        decoded = json.loads(str(value or "{}"))
    except json.JSONDecodeError as error:
        raise CollectionRepositoryError("Stored collection item is invalid JSON") from error
    if not isinstance(decoded, dict):
        raise CollectionRepositoryError("Stored collection item must be an object")
    return decoded
