"""SQLite persistence for the two most recent featured recommendation lineups."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

HOME_SNAPSHOT_LIMIT = 2


class HomeSnapshotRepositoryError(RuntimeError):
    """Raised when daily recommendation history cannot be read or stored."""


class SqliteHomeSnapshotRepository:
    def __init__(self, path: Path | str, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def get(self, user_id: str, local_date: str) -> list[dict[str, Any]] | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        """SELECT entries_json FROM home_featured_snapshots
                        WHERE user_id = ? AND local_date = ?""",
                        (user_id, local_date),
                    ).fetchone()
            except sqlite3.Error as error:
                raise HomeSnapshotRepositoryError(
                    f"Cannot read home history from: {self.path}"
                ) from error
        if row is None:
            return None
        return _decode_entries(str(row["entries_json"] or "[]"))

    def save(
        self,
        user_id: str,
        local_date: str,
        entries: Sequence[Mapping[str, Any]],
    ) -> None:
        payload = _encode_entries(entries)
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    active = connection.execute(
                        "SELECT 1 FROM users WHERE id = ? AND active = 1",
                        (user_id,),
                    ).fetchone()
                    if active is None:
                        connection.rollback()
                        raise HomeSnapshotRepositoryError("Recommendation owner is unavailable")
                    connection.execute(
                        """INSERT INTO home_featured_snapshots(
                            user_id, local_date, entries_json, updated_at
                        ) VALUES (?, ?, ?, ?)
                        ON CONFLICT(user_id, local_date) DO NOTHING""",
                        (user_id, local_date, payload, int(time.time())),
                    )
                    connection.execute(
                        """DELETE FROM home_featured_snapshots
                        WHERE user_id = ? AND local_date NOT IN (
                            SELECT local_date FROM home_featured_snapshots
                            WHERE user_id = ?
                            ORDER BY local_date DESC
                            LIMIT ?
                        )""",
                        (user_id, user_id, HOME_SNAPSHOT_LIMIT),
                    )
                    connection.commit()
            except HomeSnapshotRepositoryError:
                raise
            except sqlite3.Error as error:
                raise HomeSnapshotRepositoryError(
                    f"Cannot save home history to: {self.path}"
                ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection


def _encode_entries(entries: Sequence[Mapping[str, Any]]) -> str:
    clean: list[dict[str, Any]] = []
    for entry in entries:
        item_id = str(entry.get("item_id") or "").strip()
        if not item_id:
            continue
        reason = entry.get("reason") if isinstance(entry.get("reason"), Mapping) else {}
        clean.append(
            {
                "item_id": item_id,
                "reason": {key: str(reason.get(key) or "") for key in ("code", "label", "detail")},
            }
        )
    return json.dumps(clean, ensure_ascii=False, separators=(",", ":"))


def _decode_entries(value: str) -> list[dict[str, Any]]:
    try:
        raw = json.loads(value)
    except (TypeError, ValueError) as error:
        raise HomeSnapshotRepositoryError("Stored home history is invalid") from error
    if not isinstance(raw, list):
        raise HomeSnapshotRepositoryError("Stored home history is invalid")
    entries: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise HomeSnapshotRepositoryError("Stored home history is invalid")
        item_id = str(row.get("item_id") or "").strip()
        reason = row.get("reason")
        if not item_id or not isinstance(reason, Mapping):
            raise HomeSnapshotRepositoryError("Stored home history is invalid")
        entries.append(
            {
                "item_id": item_id,
                "reason": {key: str(reason.get(key) or "") for key in ("code", "label", "detail")},
            }
        )
    return entries


__all__ = [
    "HOME_SNAPSHOT_LIMIT",
    "HomeSnapshotRepositoryError",
    "SqliteHomeSnapshotRepository",
]
