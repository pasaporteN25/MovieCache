"""SQLite persistence for minimal public presentation snapshots."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

from movie_inbox.application.public_presentation_repository import PublicPresentationRepositoryError
from movie_inbox.domain.public_presentations import PublicPresentation


class SqlitePublicPresentationRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def create(self, presentation: PublicPresentation) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        """INSERT INTO public_presentations(
                            id, owner_user_id, collection_id, capability_hash, title, description,
                            snapshot_json, status, created_at, updated_at, revoked_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            presentation.id,
                            presentation.owner_user_id,
                            presentation.collection_id,
                            presentation.capability_hash,
                            presentation.title,
                            presentation.description,
                            _json_dump(presentation.snapshot),
                            presentation.status,
                            presentation.created_at,
                            presentation.updated_at,
                            presentation.revoked_at,
                        ),
                    )
                    connection.commit()
            except sqlite3.Error as error:
                raise PublicPresentationRepositoryError(
                    f"Cannot create public presentation in: {self.path}"
                ) from error

    def list_for_owner(self, owner_user_id: str) -> list[PublicPresentation]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT * FROM public_presentations
                        WHERE owner_user_id = ? ORDER BY updated_at DESC, id""",
                        (owner_user_id,),
                    ).fetchall()
                    return [_presentation(row) for row in rows]
            except sqlite3.Error as error:
                raise PublicPresentationRepositoryError(
                    f"Cannot list public presentations from: {self.path}"
                ) from error

    def get_for_owner(self, owner_user_id: str, presentation_id: str) -> PublicPresentation | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        """SELECT * FROM public_presentations
                        WHERE id = ? AND owner_user_id = ?""",
                        (presentation_id, owner_user_id),
                    ).fetchone()
                    return _presentation(row) if row else None
            except sqlite3.Error as error:
                raise PublicPresentationRepositoryError(
                    f"Cannot read public presentation from: {self.path}"
                ) from error

    def get_active_by_capability_hash(self, capability_hash: str) -> PublicPresentation | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        """SELECT p.* FROM public_presentations p
                        JOIN users u ON u.id = p.owner_user_id
                        JOIN curated_collections c ON c.id = p.collection_id
                        WHERE p.capability_hash = ? AND p.status = 'active' AND u.active = 1""",
                        (capability_hash,),
                    ).fetchone()
                    return _presentation(row) if row else None
            except sqlite3.Error as error:
                raise PublicPresentationRepositoryError(
                    f"Cannot read public presentation from: {self.path}"
                ) from error

    def replace_snapshot(
        self,
        owner_user_id: str,
        presentation_id: str,
        *,
        title: str,
        description: str,
        snapshot: dict[str, object],
        updated_at: str,
    ) -> PublicPresentation | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    cursor = connection.execute(
                        """UPDATE public_presentations SET title = ?, description = ?,
                        snapshot_json = ?, updated_at = ?
                        WHERE id = ? AND owner_user_id = ? AND status = 'active'""",
                        (
                            title,
                            description,
                            _json_dump(snapshot),
                            updated_at,
                            presentation_id,
                            owner_user_id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        connection.rollback()
                        return None
                    row = connection.execute(
                        "SELECT * FROM public_presentations WHERE id = ?", (presentation_id,)
                    ).fetchone()
                    connection.commit()
                    return _presentation(row) if row else None
            except sqlite3.Error as error:
                raise PublicPresentationRepositoryError(
                    f"Cannot refresh public presentation in: {self.path}"
                ) from error

    def revoke(
        self, owner_user_id: str, presentation_id: str, *, revoked_at: str
    ) -> PublicPresentation | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    cursor = connection.execute(
                        """UPDATE public_presentations SET status = 'revoked', revoked_at = ?,
                        updated_at = ? WHERE id = ? AND owner_user_id = ? AND status = 'active'""",
                        (revoked_at, revoked_at, presentation_id, owner_user_id),
                    )
                    if cursor.rowcount != 1:
                        connection.rollback()
                        return None
                    row = connection.execute(
                        "SELECT * FROM public_presentations WHERE id = ?", (presentation_id,)
                    ).fetchone()
                    connection.commit()
                    return _presentation(row) if row else None
            except sqlite3.Error as error:
                raise PublicPresentationRepositoryError(
                    f"Cannot revoke public presentation in: {self.path}"
                ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection


def _presentation(row: sqlite3.Row) -> PublicPresentation:
    return PublicPresentation(
        id=str(row["id"]),
        owner_user_id=str(row["owner_user_id"]),
        collection_id=str(row["collection_id"]),
        capability_hash=str(row["capability_hash"]),
        title=str(row["title"]),
        description=str(row["description"]),
        snapshot=_json_object(row["snapshot_json"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        revoked_at=str(row["revoked_at"]),
    )


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _json_object(value: object) -> dict[str, Any]:
    try:
        decoded = json.loads(str(value or "{}"))
    except json.JSONDecodeError as error:
        raise PublicPresentationRepositoryError(
            "Stored public presentation is invalid JSON"
        ) from error
    if not isinstance(decoded, dict):
        raise PublicPresentationRepositoryError("Stored public presentation must be an object")
    return decoded
