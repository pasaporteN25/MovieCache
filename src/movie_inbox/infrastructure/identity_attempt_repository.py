"""SQLite record of Wikipedia articles that answered without a Wikidata id."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from movie_inbox.application.identity_resolution_service import IdentityAttemptStoreError

_CHUNK = 200


class SqliteIdentityAttemptRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def recent_misses(self, keys: Sequence[str], since: int) -> set[str]:
        wanted = list(dict.fromkeys(keys))
        if not wanted:
            return set()
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    found: set[str] = set()
                    for start in range(0, len(wanted), _CHUNK):
                        chunk = wanted[start : start + _CHUNK]
                        marks = ", ".join("?" for _ in chunk)
                        rows = connection.execute(
                            "SELECT article_key FROM identity_resolution_misses "
                            f"WHERE attempted_at >= ? AND article_key IN ({marks})",
                            (since, *chunk),
                        ).fetchall()
                        found.update(str(row[0]) for row in rows)
                    return found
            except sqlite3.Error as error:
                raise IdentityAttemptStoreError(
                    f"Cannot read identity attempts from: {self.path}"
                ) from error

    def record_misses(self, keys: Sequence[str], at: int) -> None:
        wanted = list(dict.fromkeys(keys))
        if not wanted:
            return
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.executemany(
                        """INSERT INTO identity_resolution_misses(article_key, attempted_at)
                        VALUES (?, ?)
                        ON CONFLICT(article_key)
                        DO UPDATE SET attempted_at = excluded.attempted_at""",
                        [(key, int(at)) for key in wanted],
                    )
                    connection.commit()
            except sqlite3.Error as error:
                raise IdentityAttemptStoreError(
                    f"Cannot record identity attempts in: {self.path}"
                ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection
