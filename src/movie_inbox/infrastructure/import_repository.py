"""SQLite persistence for bounded, user-scoped import drafts."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

from movie_inbox.application.import_repository import ImportRepositoryError
from movie_inbox.domain.imports import ImportDraft, ImportDraftItem

STALE_APPLY_GRACE_SECONDS = 15 * 60


class SqliteImportDraftRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def create(self, draft: ImportDraft) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    active = connection.execute(
                        "SELECT 1 FROM users WHERE id = ? AND active = 1",
                        (draft.user_id,),
                    ).fetchone()
                    if active is None:
                        connection.rollback()
                        raise ImportRepositoryError("Import draft owner is unavailable")
                    connection.execute(
                        """INSERT INTO import_drafts(
                            id, user_id, source_name, source_format, source_hash, status,
                            created_at, updated_at, expires_at, applied_at, result_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            draft.id,
                            draft.user_id,
                            draft.source_name,
                            draft.source_format,
                            draft.source_hash,
                            draft.status,
                            draft.created_at,
                            draft.updated_at,
                            draft.expires_at,
                            draft.applied_at,
                            _json_dump(draft.result),
                        ),
                    )
                    for entry in draft.items:
                        connection.execute(
                            """INSERT INTO import_draft_items(
                                draft_id, item_id, position, state, reason, label,
                                item_json, candidates_json, collection_eligible
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                draft.id,
                                entry.id,
                                entry.position,
                                entry.state,
                                entry.reason,
                                entry.label,
                                _json_dump(entry.item or {}),
                                _json_dump(list(entry.candidates)),
                                int(entry.collection_eligible),
                            ),
                        )
                    connection.commit()
            except ImportRepositoryError:
                raise
            except sqlite3.Error as error:
                raise ImportRepositoryError(
                    f"Cannot create import draft in: {self.path}"
                ) from error

    def list_for_user(self, user_id: str) -> list[ImportDraft]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        "SELECT * FROM import_drafts WHERE user_id = ? "
                        "ORDER BY updated_at DESC, id",
                        (user_id,),
                    ).fetchall()
                    return [self._draft(connection, row, include_items=False) for row in rows]
            except sqlite3.Error as error:
                raise ImportRepositoryError(
                    f"Cannot list import drafts from: {self.path}"
                ) from error

    def count_for_user(self, user_id: str) -> int:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        "SELECT COUNT(*) AS total FROM import_drafts WHERE user_id = ?",
                        (user_id,),
                    ).fetchone()
                    return int(row["total"] if row else 0)
            except sqlite3.Error as error:
                raise ImportRepositoryError(
                    f"Cannot count import drafts from: {self.path}"
                ) from error

    def get_for_user(self, user_id: str, draft_id: str) -> ImportDraft | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        "SELECT * FROM import_drafts WHERE id = ? AND user_id = ?",
                        (draft_id, user_id),
                    ).fetchone()
                    return self._draft(connection, row) if row else None
            except sqlite3.Error as error:
                raise ImportRepositoryError(
                    f"Cannot read import draft from: {self.path}"
                ) from error

    def claim_for_apply(
        self, user_id: str, draft_id: str, now: int, stale_before: int
    ) -> ImportDraft | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute(
                        "SELECT * FROM import_drafts WHERE id = ? AND user_id = ?",
                        (draft_id, user_id),
                    ).fetchone()
                    if row is None:
                        connection.rollback()
                        return None
                    if str(row["status"]) == "applied" or int(row["expires_at"]) <= now:
                        connection.rollback()
                        return self._draft(connection, row)
                    can_claim = str(row["status"]) in {"ready", "failed"} or (
                        str(row["status"]) == "applying" and int(row["updated_at"]) <= stale_before
                    )
                    if can_claim:
                        connection.execute(
                            "UPDATE import_drafts SET status = 'applying', updated_at = ? "
                            "WHERE id = ?",
                            (now, draft_id),
                        )
                        connection.commit()
                        updated = connection.execute(
                            "SELECT * FROM import_drafts WHERE id = ?",
                            (draft_id,),
                        ).fetchone()
                        return self._draft(connection, updated)
                    connection.rollback()
                    return self._draft(connection, row)
            except sqlite3.Error as error:
                raise ImportRepositoryError(f"Cannot claim import draft in: {self.path}") from error

    def complete(
        self,
        user_id: str,
        draft_id: str,
        now: int,
        expires_at: int,
        result: dict[str, object],
    ) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    cursor = connection.execute(
                        """UPDATE import_drafts
                        SET status = 'applied', updated_at = ?, applied_at = ?,
                            expires_at = ?, result_json = ?
                        WHERE id = ? AND user_id = ? AND status = 'applying'""",
                        (now, now, expires_at, _json_dump(result), draft_id, user_id),
                    )
                    connection.commit()
                    if cursor.rowcount != 1:
                        raise ImportRepositoryError("Import draft completion lost its apply claim")
            except ImportRepositoryError:
                raise
            except sqlite3.Error as error:
                raise ImportRepositoryError(
                    f"Cannot complete import draft in: {self.path}"
                ) from error

    def fail(self, user_id: str, draft_id: str, now: int) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute(
                        """UPDATE import_drafts SET status = 'failed', updated_at = ?
                        WHERE id = ? AND user_id = ? AND status = 'applying'""",
                        (now, draft_id, user_id),
                    )
                    connection.commit()
            except sqlite3.Error as error:
                raise ImportRepositoryError(f"Cannot fail import draft in: {self.path}") from error

    def delete(self, user_id: str, draft_id: str) -> bool:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    cursor = connection.execute(
                        "DELETE FROM import_drafts "
                        "WHERE id = ? AND user_id = ? AND status != 'applying'",
                        (draft_id, user_id),
                    )
                    connection.commit()
                    return cursor.rowcount > 0
            except sqlite3.Error as error:
                raise ImportRepositoryError(
                    f"Cannot delete import draft from: {self.path}"
                ) from error

    def purge_expired(self, now: int) -> int:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    cursor = connection.execute(
                        """DELETE FROM import_drafts
                        WHERE expires_at <= ?
                          AND (status != 'applying' OR updated_at <= ?)""",
                        (now, now - STALE_APPLY_GRACE_SECONDS),
                    )
                    connection.commit()
                    return max(0, cursor.rowcount)
            except sqlite3.Error as error:
                raise ImportRepositoryError(
                    f"Cannot purge import drafts from: {self.path}"
                ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection

    @staticmethod
    def _draft(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        include_items: bool = True,
    ) -> ImportDraft:
        entries: tuple[ImportDraftItem, ...] = ()
        count_snapshot: dict[str, int] = {}
        if include_items:
            item_rows = connection.execute(
                "SELECT * FROM import_draft_items WHERE draft_id = ? ORDER BY position, item_id",
                (row["id"],),
            ).fetchall()
            entries = tuple(
                ImportDraftItem(
                    id=str(item["item_id"]),
                    position=int(item["position"]),
                    state=str(item["state"]),
                    reason=str(item["reason"]),
                    label=str(item["label"]),
                    item=_json_object(item["item_json"]) or None,
                    candidates=tuple(_json_array(item["candidates_json"])),
                    collection_eligible=bool(item["collection_eligible"]),
                )
                for item in item_rows
            )
        else:
            counts = connection.execute(
                """SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN state = 'new' THEN 1 ELSE 0 END) AS new_count,
                    SUM(CASE WHEN state = 'present' THEN 1 ELSE 0 END) AS present_count,
                    SUM(CASE WHEN state = 'review' THEN 1 ELSE 0 END) AS review_count,
                    SUM(CASE WHEN state = 'invalid' THEN 1 ELSE 0 END) AS invalid_count,
                    SUM(collection_eligible) AS collection_eligible_count
                FROM import_draft_items WHERE draft_id = ?""",
                (row["id"],),
            ).fetchone()
            count_snapshot = {
                "total": int(counts["total"] or 0),
                "new": int(counts["new_count"] or 0),
                "present": int(counts["present_count"] or 0),
                "review": int(counts["review_count"] or 0),
                "invalid": int(counts["invalid_count"] or 0),
                "collection_eligible": int(counts["collection_eligible_count"] or 0),
            }
        return ImportDraft(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            source_name=str(row["source_name"]),
            source_format=str(row["source_format"]),
            source_hash=str(row["source_hash"]),
            status=str(row["status"]),
            created_at=int(row["created_at"]),
            updated_at=int(row["updated_at"]),
            expires_at=int(row["expires_at"]),
            applied_at=int(row["applied_at"]),
            result=_json_object(row["result_json"]),
            items=entries,
            count_snapshot=count_snapshot,
        )


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _json_object(value: object) -> dict[str, Any]:
    try:
        decoded = json.loads(str(value or "{}"))
    except json.JSONDecodeError as error:
        raise ImportRepositoryError("Stored import draft contains invalid JSON") from error
    if not isinstance(decoded, dict):
        raise ImportRepositoryError("Stored import draft object is invalid")
    return decoded


def _json_array(value: object) -> list[dict[str, Any]]:
    try:
        decoded = json.loads(str(value or "[]"))
    except json.JSONDecodeError as error:
        raise ImportRepositoryError(
            "Stored import draft candidates contain invalid JSON"
        ) from error
    if not isinstance(decoded, list) or any(not isinstance(row, dict) for row in decoded):
        raise ImportRepositoryError("Stored import draft candidates are invalid")
    return decoded
