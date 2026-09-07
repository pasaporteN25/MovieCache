"""SQLite persistence for dated public-score snapshots.

Only TMDb rows ever land here. IMDb scores are read straight from the local
index the owner built, so snapshotting them would duplicate a file that is
already on disk and add an expiry rule their terms do not ask for.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from movie_inbox.application.public_ratings_repository import PublicRatingsRepositoryError
from movie_inbox.domain.public_ratings import PublicRatingSnapshot


class SqlitePublicRatingsRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def ratings(self, source: str, work_keys: list[str]) -> dict[str, PublicRatingSnapshot]:
        if not work_keys:
            return {}
        found: dict[str, PublicRatingSnapshot] = {}
        with self._thread_lock, closing(self._connect()) as connection:
            # Chunked to stay under SQLite's variable limit for a large catalogue.
            for start in range(0, len(work_keys), 400):
                chunk = work_keys[start : start + 400]
                placeholders = ",".join("?" for _ in chunk)
                rows = connection.execute(
                    f"""SELECT work_key, source, checked_at, average, votes
                    FROM public_rating_snapshots
                    WHERE source = ? AND work_key IN ({placeholders})""",
                    (source, *chunk),
                ).fetchall()
                for row in rows:
                    found[str(row["work_key"])] = PublicRatingSnapshot(
                        work_key=str(row["work_key"]),
                        source=str(row["source"]),
                        checked_at=str(row["checked_at"]),
                        average=float(row["average"]),
                        votes=int(row["votes"]),
                    )
        return found

    def save_rating(self, snapshot: PublicRatingSnapshot) -> PublicRatingSnapshot:
        with self._thread_lock, closing(self._connect()) as connection:
            self._write(
                connection,
                """INSERT INTO public_rating_snapshots(
                    work_key, source, checked_at, average, votes
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(work_key, source) DO UPDATE SET
                    checked_at = excluded.checked_at,
                    average = excluded.average,
                    votes = excluded.votes""",
                (
                    snapshot.work_key,
                    snapshot.source,
                    snapshot.checked_at,
                    float(snapshot.average),
                    int(snapshot.votes),
                ),
            )
        return snapshot

    def purge_ratings(self, *, source: str = "", before: str = "") -> int:
        clauses: list[str] = []
        parameters: list[object] = []
        if source:
            clauses.append("source = ?")
            parameters.append(source)
        if before:
            clauses.append("checked_at < ?")
            parameters.append(before)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._thread_lock, closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    f"DELETE FROM public_rating_snapshots{where}", tuple(parameters)
                )
                removed = int(cursor.rowcount or 0)
                connection.commit()
            except sqlite3.Error as error:
                connection.rollback()
                raise PublicRatingsRepositoryError(
                    f"Cannot purge public rating snapshots in: {self.path}"
                ) from error
        return removed

    def _write(
        self,
        connection: sqlite3.Connection,
        statement: str,
        parameters: tuple[object, ...],
    ) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(statement, parameters)
            connection.commit()
        except sqlite3.Error as error:
            connection.rollback()
            raise PublicRatingsRepositoryError(
                f"Cannot write public rating snapshots in: {self.path}"
            ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection
