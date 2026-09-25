"""SQLite persistence for human charades difficulty decisions.

Only decisions a person made are stored. Suggestions are recomputed and never
written, so a stored row always means somebody chose it -- which is what makes
"a person outranks any recomputation" enforceable rather than aspirational.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from movie_inbox.application.charades_repository import CharadesRepositoryError


class SqliteCharadesRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def difficulties_for(self, user_id: str) -> dict[str, str]:
        with self._thread_lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT work_key, difficulty FROM charades_difficulty WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {str(row["work_key"]): str(row["difficulty"]) for row in rows}

    def set_difficulty(self, user_id: str, work_key: str, difficulty: str) -> None:
        with self._thread_lock, closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """INSERT INTO charades_difficulty(user_id, work_key, difficulty, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, work_key) DO UPDATE SET
                        difficulty = excluded.difficulty,
                        updated_at = excluded.updated_at""",
                    (user_id, work_key, difficulty, _utc_now()),
                )
                connection.commit()
            except sqlite3.Error as error:
                connection.rollback()
                raise CharadesRepositoryError(
                    f"Cannot store charades difficulty in: {self.path}"
                ) from error

    def clear_difficulty(self, user_id: str, work_key: str) -> None:
        """Undo a decision, returning the work to the suggestion path."""

        with self._thread_lock, closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "DELETE FROM charades_difficulty WHERE user_id = ? AND work_key = ?",
                    (user_id, work_key),
                )
                connection.commit()
            except sqlite3.Error as error:
                connection.rollback()
                raise CharadesRepositoryError(
                    f"Cannot clear charades difficulty in: {self.path}"
                ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
