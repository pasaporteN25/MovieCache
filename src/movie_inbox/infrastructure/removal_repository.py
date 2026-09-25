"""SQLite persistence for the record of works removed from a catalogue."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from movie_inbox.application.removal_repository import RemovalRepositoryError
from movie_inbox.domain.removals import DeviceRemoval

# SQLite bounds the number of bound parameters, so id lists go in chunks.
_CHUNK = 200


class SqliteRemovalRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def save(self, catalog_id: str, removals: Sequence[DeviceRemoval], now: int) -> None:
        if not removals:
            return
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    for removal in removals:
                        # A later removal of the same id replaces the earlier one:
                        # a work that came back through an undo and left again is
                        # answered by how it left the second time.
                        connection.execute(
                            """INSERT INTO device_removals(
                                catalog_id, device_id, reason, merged_into, removed_at
                            ) VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(catalog_id, device_id) DO UPDATE SET
                                reason = excluded.reason,
                                merged_into = excluded.merged_into,
                                removed_at = excluded.removed_at""",
                            (
                                catalog_id,
                                removal.device_id,
                                removal.reason,
                                removal.merged_into,
                                now,
                            ),
                        )
                    connection.commit()
            except sqlite3.Error as error:
                raise RemovalRepositoryError(f"Cannot save removals in: {self.path}") from error

    def get_many(self, catalog_id: str, device_ids: Sequence[str]) -> dict[str, DeviceRemoval]:
        wanted = list(dict.fromkeys(device_ids))
        if not wanted:
            return {}
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    found: dict[str, DeviceRemoval] = {}
                    for start in range(0, len(wanted), _CHUNK):
                        chunk = wanted[start : start + _CHUNK]
                        marks = ", ".join("?" for _ in chunk)
                        rows = connection.execute(
                            "SELECT device_id, reason, merged_into, removed_at "
                            f"FROM device_removals WHERE catalog_id = ? AND device_id IN ({marks})",
                            (catalog_id, *chunk),
                        ).fetchall()
                        for row in rows:
                            found[str(row["device_id"])] = DeviceRemoval(
                                device_id=str(row["device_id"]),
                                reason=str(row["reason"]),
                                merged_into=str(row["merged_into"]),
                                removed_at=int(row["removed_at"]),
                            )
                    return found
            except sqlite3.Error as error:
                raise RemovalRepositoryError(f"Cannot read removals from: {self.path}") from error

    def forget(self, catalog_id: str, device_ids: Sequence[str]) -> int:
        wanted = list(dict.fromkeys(device_ids))
        if not wanted:
            return 0
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    removed = 0
                    for start in range(0, len(wanted), _CHUNK):
                        chunk = wanted[start : start + _CHUNK]
                        marks = ", ".join("?" for _ in chunk)
                        removed += connection.execute(
                            "DELETE FROM device_removals "
                            f"WHERE catalog_id = ? AND device_id IN ({marks})",
                            (catalog_id, *chunk),
                        ).rowcount
                    connection.commit()
                    return removed
            except sqlite3.Error as error:
                raise RemovalRepositoryError(f"Cannot forget removals in: {self.path}") from error

    def purge(self, removed_before: int) -> int:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    cursor = connection.execute(
                        "DELETE FROM device_removals WHERE removed_at < ?", (removed_before,)
                    )
                    return cursor.rowcount
            except sqlite3.Error as error:
                raise RemovalRepositoryError(f"Cannot purge removals from: {self.path}") from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection
