"""SQLite repository for instance-scoped media libraries."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

from movie_inbox.application.library_repository import (
    LibraryConflict,
    LibraryNotFound,
    LibraryRepositoryError,
    LibraryRunBusy,
    ReviewedFileState,
)
from movie_inbox.domain.libraries import (
    LibraryFile,
    LibraryScanRun,
    ManagedLibrary,
    work_identity_key,
)

RUN_HISTORY_LIMIT = 100


class SqliteLibraryRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def create_library(self, library: ManagedLibrary) -> ManagedLibrary:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute(
                        """INSERT INTO media_libraries(
                            id, name, root_path, root_key, schedule, active, status,
                            max_missing_ratio, verified_at, last_scan_at, next_scan_at,
                            created_by_user_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            library.id,
                            library.name,
                            library.root_path,
                            _path_key(library.root_path),
                            library.schedule,
                            int(library.active),
                            library.status,
                            library.max_missing_ratio,
                            library.verified_at,
                            library.last_scan_at,
                            library.next_scan_at,
                            library.created_by_user_id,
                            library.created_at,
                            library.updated_at,
                        ),
                    )
                    connection.commit()
                    return library
            except sqlite3.IntegrityError as error:
                raise LibraryRepositoryError("A managed library already uses that path") from error
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot create managed library in: {self.path}"
                ) from error

    def list_libraries(self) -> list[ManagedLibrary]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        "SELECT * FROM media_libraries ORDER BY name COLLATE NOCASE, created_at"
                    ).fetchall()
                    return [_library(row) for row in rows]
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot list managed libraries from: {self.path}"
                ) from error

    def get_library(self, library_id: str) -> ManagedLibrary | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        "SELECT * FROM media_libraries WHERE id = ?",
                        (library_id,),
                    ).fetchone()
                    return _library(row) if row else None
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot read managed library from: {self.path}"
                ) from error

    def update_library(self, library: ManagedLibrary) -> ManagedLibrary:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    running = connection.execute(
                        """SELECT 1 FROM library_scan_runs
                        WHERE library_id = ? AND status IN ('queued', 'running')""",
                        (library.id,),
                    ).fetchone()
                    if running:
                        connection.rollback()
                        raise LibraryRunBusy("The library is currently being scanned")
                    cursor = connection.execute(
                        """UPDATE media_libraries SET
                            name = ?, root_path = ?, root_key = ?, schedule = ?, active = ?,
                            status = ?, max_missing_ratio = ?, verified_at = ?, last_scan_at = ?,
                            next_scan_at = ?, updated_at = ?
                        WHERE id = ?""",
                        (
                            library.name,
                            library.root_path,
                            _path_key(library.root_path),
                            library.schedule,
                            int(library.active),
                            library.status,
                            library.max_missing_ratio,
                            library.verified_at,
                            library.last_scan_at,
                            library.next_scan_at,
                            library.updated_at,
                            library.id,
                        ),
                    )
                    connection.commit()
                    if cursor.rowcount != 1:
                        raise LibraryNotFound("Managed library was not found")
                    return library
            except (LibraryNotFound, LibraryRepositoryError, LibraryRunBusy):
                raise
            except sqlite3.IntegrityError as error:
                raise LibraryRepositoryError("A managed library already uses that path") from error
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot update managed library in: {self.path}"
                ) from error

    def delete_library(self, library_id: str) -> bool:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    running = connection.execute(
                        """SELECT 1 FROM library_scan_runs
                        WHERE library_id = ? AND status IN ('queued', 'running')""",
                        (library_id,),
                    ).fetchone()
                    if running:
                        connection.rollback()
                        raise LibraryRunBusy("The library is currently being scanned")
                    cursor = connection.execute(
                        "DELETE FROM media_libraries WHERE id = ?", (library_id,)
                    )
                    connection.commit()
                    return cursor.rowcount > 0
            except LibraryRunBusy:
                raise
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot delete managed library from: {self.path}"
                ) from error

    def create_run(self, run: LibraryScanRun) -> LibraryScanRun:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute(
                        """INSERT INTO library_scan_runs(
                            id, library_id, mode, trigger, status, created_at, started_at,
                            finished_at, summary_json, errors_json, preview_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            run.id,
                            run.library_id,
                            run.mode,
                            run.trigger,
                            run.status,
                            run.created_at,
                            run.started_at,
                            run.finished_at,
                            _json_dump(run.summary),
                            _json_dump(list(run.errors)),
                            _json_dump(list(run.preview)),
                        ),
                    )
                    connection.execute(
                        "UPDATE media_libraries SET status = 'scanning', updated_at = ? "
                        "WHERE id = ?",
                        (run.created_at, run.library_id),
                    )
                    connection.commit()
                    return run
            except sqlite3.IntegrityError as error:
                if "ux_library_active_run" in str(error) or "UNIQUE constraint" in str(error):
                    raise LibraryRunBusy("A scan is already queued or running") from error
                raise LibraryRepositoryError("Cannot queue scan for the managed library") from error
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot queue library scan in: {self.path}"
                ) from error

    def claim_run(self, run_id: str, started_at: int) -> LibraryScanRun | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute(
                        "SELECT * FROM library_scan_runs WHERE id = ?",
                        (run_id,),
                    ).fetchone()
                    if row is None or str(row["status"]) != "queued":
                        connection.rollback()
                        return None
                    connection.execute(
                        "UPDATE library_scan_runs SET status = 'running', started_at = ? "
                        "WHERE id = ?",
                        (started_at, run_id),
                    )
                    connection.execute(
                        "UPDATE media_libraries SET status = 'scanning', updated_at = ? "
                        "WHERE id = ?",
                        (started_at, str(row["library_id"])),
                    )
                    connection.commit()
                    claimed = connection.execute(
                        "SELECT * FROM library_scan_runs WHERE id = ?",
                        (run_id,),
                    ).fetchone()
                    return _run(claimed)
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot claim library scan in: {self.path}"
                ) from error

    def get_run(self, run_id: str) -> LibraryScanRun | None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    row = connection.execute(
                        "SELECT * FROM library_scan_runs WHERE id = ?",
                        (run_id,),
                    ).fetchone()
                    return _run(row) if row else None
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot read library scan from: {self.path}"
                ) from error

    def list_runs(self, library_id: str, limit: int = 20) -> list[LibraryScanRun]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT * FROM library_scan_runs WHERE library_id = ?
                        ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                        (library_id, max(1, min(100, int(limit)))),
                    ).fetchall()
                    return [_run(row) for row in rows]
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot list library scans from: {self.path}"
                ) from error

    def previous_files(self, library_id: str) -> list[LibraryFile]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        "SELECT * FROM library_files WHERE library_id = ? ORDER BY relative_key",
                        (library_id,),
                    ).fetchall()
                    return [_file(row) for row in rows]
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot read library inventory from: {self.path}"
                ) from error

    def complete_run(
        self,
        run: LibraryScanRun,
        library: ManagedLibrary,
        files: list[LibraryFile],
        *,
        commit_inventory: bool,
        mark_missing: bool,
    ) -> None:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    if commit_inventory:
                        for item in files:
                            self._upsert_file(connection, item)
                        if mark_missing:
                            connection.execute(
                                """UPDATE library_files SET available = 0, updated_at = ?
                                WHERE library_id = ? AND available = 1 AND last_run_id != ?""",
                                (run.finished_at, library.id, run.id),
                            )
                    connection.execute(
                        """UPDATE library_scan_runs SET status = ?, started_at = ?, finished_at = ?,
                            summary_json = ?, errors_json = ?, preview_json = ?
                        WHERE id = ? AND status = 'running'""",
                        (
                            run.status,
                            run.started_at,
                            run.finished_at,
                            _json_dump(run.summary),
                            _json_dump(list(run.errors)),
                            _json_dump(list(run.preview)),
                            run.id,
                        ),
                    )
                    connection.execute(
                        """UPDATE media_libraries SET active = ?, status = ?, verified_at = ?,
                            last_scan_at = ?, next_scan_at = ?, updated_at = ? WHERE id = ?""",
                        (
                            int(library.active),
                            library.status,
                            library.verified_at,
                            library.last_scan_at,
                            library.next_scan_at,
                            library.updated_at,
                            library.id,
                        ),
                    )
                    connection.execute(
                        """DELETE FROM library_scan_runs
                        WHERE library_id = ? AND status NOT IN ('queued', 'running')
                          AND id NOT IN (
                              SELECT id FROM library_scan_runs
                              WHERE library_id = ?
                              ORDER BY created_at DESC, rowid DESC
                              LIMIT ?
                          )""",
                        (library.id, library.id, RUN_HISTORY_LIMIT),
                    )
                    connection.commit()
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot complete library scan in: {self.path}"
                ) from error

    def recover_interrupted_runs(self, finished_at: int) -> int:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    rows = connection.execute(
                        "SELECT id, library_id FROM library_scan_runs "
                        "WHERE status IN ('queued', 'running')"
                    ).fetchall()
                    if rows:
                        connection.execute(
                            """UPDATE library_scan_runs SET status = 'failed', finished_at = ?,
                                errors_json = '[\"Server restarted before the scan completed\"]'
                            WHERE status IN ('queued', 'running')""",
                            (finished_at,),
                        )
                        library_ids = list(dict.fromkeys(str(row["library_id"]) for row in rows))
                        connection.executemany(
                            """UPDATE media_libraries SET status = 'warning', updated_at = ?
                            WHERE id = ? AND status = 'scanning'""",
                            [(finished_at, library_id) for library_id in library_ids],
                        )
                    connection.commit()
                    return len(rows)
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot recover interrupted scans in: {self.path}"
                ) from error

    def due_libraries(self, now: int) -> list[ManagedLibrary]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT * FROM media_libraries
                        WHERE active = 1 AND verified_at > 0 AND schedule != 'manual'
                          AND next_scan_at > 0 AND next_scan_at <= ?
                        ORDER BY next_scan_at, id""",
                        (now,),
                    ).fetchall()
                    return [_library(row) for row in rows]
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot read due library scans from: {self.path}"
                ) from error

    def review_queue(self) -> list[LibraryFile]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT * FROM library_files
                        WHERE available = 1 AND state IN ('new', 'review')
                        ORDER BY updated_at DESC, relative_key"""
                    ).fetchall()
                    return [_file(row) for row in rows]
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot read scanner review queue from: {self.path}"
                ) from error

    def review_file(
        self,
        file_id: str,
        action: str,
        identity: dict[str, Any] | None,
        updated_at: int,
    ) -> LibraryFile:
        return self.review_files([file_id], action, identity, updated_at)[0]

    def review_files(
        self,
        file_ids: list[str],
        action: str,
        identity: dict[str, Any] | None,
        updated_at: int,
    ) -> list[LibraryFile]:
        unique_ids = list(
            dict.fromkeys(str(file_id or "") for file_id in file_ids if str(file_id or ""))
        )
        if not unique_ids:
            raise LibraryNotFound("Scanner queue item was not found")
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    placeholders = ",".join("?" for _ in unique_ids)
                    rows = connection.execute(
                        f"SELECT * FROM library_files WHERE id IN ({placeholders})",
                        unique_ids,
                    ).fetchall()
                    if len(rows) != len(unique_ids):
                        connection.rollback()
                        raise LibraryNotFound("Scanner queue item was not found")
                    if action == "ignore":
                        state, work_key, payload = "ignored", "", {}
                    elif action == "confirm":
                        payload = dict(identity or {})
                        work_key = work_identity_key(payload)
                        if not work_key:
                            connection.rollback()
                            raise ValueError(
                                "A confirmed scanner item requires a recognizable identity"
                            )
                        state = "matched"
                    else:
                        connection.rollback()
                        raise ValueError("Scanner review action must be confirm or ignore")
                    connection.execute(
                        """UPDATE library_files SET state = ?, work_key = ?, identity_json = ?,
                            candidates_json = '[]', updated_at = ?
                            WHERE id IN ("""
                        + placeholders
                        + ")",
                        (state, work_key, _json_dump(payload), updated_at, *unique_ids),
                    )
                    connection.commit()
                    updated_rows = connection.execute(
                        f"SELECT * FROM library_files WHERE id IN ({placeholders}) "
                        "ORDER BY relative_key",
                        unique_ids,
                    ).fetchall()
                    return [_file(row) for row in updated_rows]
            except (LibraryNotFound, ValueError):
                raise
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot update scanner review queue in: {self.path}"
                ) from error

    def restore_reviewed_files(
        self,
        expected: dict[str, ReviewedFileState],
        target: dict[str, ReviewedFileState],
        updated_at: int,
    ) -> list[LibraryFile]:
        unique_ids = list(dict.fromkeys(expected))
        if not unique_ids or set(target) != set(expected):
            raise LibraryNotFound("Scanner queue item was not found")
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    placeholders = ",".join("?" for _ in unique_ids)
                    rows = connection.execute(
                        f"SELECT * FROM library_files WHERE id IN ({placeholders})",
                        unique_ids,
                    ).fetchall()
                    if len(rows) != len(unique_ids):
                        connection.rollback()
                        raise LibraryConflict("scanner_item_changed_since_operation")
                    for row in rows:
                        current = ReviewedFileState.from_file(_file(row))
                        if current != expected[str(row["id"])]:
                            connection.rollback()
                            raise LibraryConflict("scanner_item_changed_since_operation")
                    for file_id in unique_ids:
                        state = target[file_id]
                        connection.execute(
                            """UPDATE library_files SET state = ?, work_key = ?, identity_json = ?,
                                candidates_json = ?, updated_at = ? WHERE id = ?""",
                            (
                                state.state,
                                state.work_key,
                                _json_dump(dict(state.identity)),
                                _json_dump(list(state.candidates)),
                                updated_at,
                                file_id,
                            ),
                        )
                    connection.commit()
                    updated_rows = connection.execute(
                        f"SELECT * FROM library_files WHERE id IN ({placeholders}) "
                        "ORDER BY relative_key",
                        unique_ids,
                    ).fetchall()
                    return [_file(row) for row in updated_rows]
            except (LibraryNotFound, LibraryConflict):
                raise
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot restore scanner review queue in: {self.path}"
                ) from error

    def availability_records(self) -> list[dict[str, Any]]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT f.work_key, f.identity_json, f.library_id, l.name AS library_name,
                                  COUNT(*) AS file_count
                        FROM library_files f
                        JOIN media_libraries l ON l.id = f.library_id
                        WHERE f.available = 1 AND f.state = 'matched' AND f.work_key != ''
                        GROUP BY f.work_key, f.identity_json, f.library_id, l.name
                        ORDER BY l.name COLLATE NOCASE, f.work_key"""
                    ).fetchall()
                    return [
                        {
                            "work_key": str(row["work_key"]),
                            "identity": _json_object(row["identity_json"]),
                            "library_id": str(row["library_id"]),
                            "library_name": str(row["library_name"]),
                            "file_count": int(row["file_count"]),
                        }
                        for row in rows
                    ]
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot read shared availability from: {self.path}"
                ) from error

    def counts(self, library_id: str) -> dict[str, int]:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT state, COUNT(*) AS total FROM library_files
                        WHERE library_id = ? AND available = 1 GROUP BY state""",
                        (library_id,),
                    ).fetchall()
                    counts = {"files": 0, "matched": 0, "new": 0, "review": 0, "ignored": 0}
                    for row in rows:
                        state = str(row["state"])
                        total = int(row["total"])
                        counts[state] = total
                        counts["files"] += total
                    return counts
            except sqlite3.Error as error:
                raise LibraryRepositoryError(
                    f"Cannot count library inventory in: {self.path}"
                ) from error

    def _upsert_file(self, connection: sqlite3.Connection, item: LibraryFile) -> None:
        connection.execute(
            """INSERT INTO library_files(
                id, library_id, relative_path, relative_key, name, size_bytes, modified_ns,
                modified_at, fingerprint, detected_title, detected_year, detected_kind,
                state, work_key, identity_json, candidates_json, available, first_seen_at,
                last_seen_at, updated_at, last_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                relative_path = excluded.relative_path,
                relative_key = excluded.relative_key,
                name = excluded.name,
                size_bytes = excluded.size_bytes,
                modified_ns = excluded.modified_ns,
                modified_at = excluded.modified_at,
                fingerprint = excluded.fingerprint,
                detected_title = excluded.detected_title,
                detected_year = excluded.detected_year,
                detected_kind = excluded.detected_kind,
                state = excluded.state,
                work_key = excluded.work_key,
                identity_json = excluded.identity_json,
                candidates_json = excluded.candidates_json,
                available = excluded.available,
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at,
                last_run_id = excluded.last_run_id""",
            (
                item.id,
                item.library_id,
                item.relative_path,
                _relative_path_key(item.relative_path),
                item.name,
                item.size_bytes,
                item.modified_ns,
                item.modified_at,
                item.fingerprint,
                item.detected_title,
                item.detected_year,
                item.detected_kind,
                item.state,
                item.work_key,
                _json_dump(item.identity),
                _json_dump(list(item.candidates)),
                int(item.available),
                item.first_seen_at,
                item.last_seen_at,
                item.updated_at,
                item.last_run_id,
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection


def _library(row: sqlite3.Row) -> ManagedLibrary:
    return ManagedLibrary(
        id=str(row["id"]),
        name=str(row["name"]),
        root_path=str(row["root_path"]),
        created_by_user_id=str(row["created_by_user_id"]),
        schedule=str(row["schedule"]),
        active=bool(row["active"]),
        status=str(row["status"]),
        max_missing_ratio=float(row["max_missing_ratio"]),
        verified_at=int(row["verified_at"]),
        last_scan_at=int(row["last_scan_at"]),
        next_scan_at=int(row["next_scan_at"]),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


def _run(row: sqlite3.Row) -> LibraryScanRun:
    return LibraryScanRun(
        id=str(row["id"]),
        library_id=str(row["library_id"]),
        mode=str(row["mode"]),
        trigger=str(row["trigger"]),
        status=str(row["status"]),
        created_at=int(row["created_at"]),
        started_at=int(row["started_at"]),
        finished_at=int(row["finished_at"]),
        summary=_json_object(row["summary_json"]),
        errors=tuple(str(value) for value in _json_list(row["errors_json"])),
        preview=tuple(
            value for value in _json_list(row["preview_json"]) if isinstance(value, dict)
        ),
    )


def _file(row: sqlite3.Row) -> LibraryFile:
    return LibraryFile(
        id=str(row["id"]),
        library_id=str(row["library_id"]),
        relative_path=str(row["relative_path"]),
        name=str(row["name"]),
        size_bytes=int(row["size_bytes"]),
        modified_ns=int(row["modified_ns"]),
        modified_at=str(row["modified_at"]),
        fingerprint=str(row["fingerprint"]),
        detected_title=str(row["detected_title"]),
        detected_year=str(row["detected_year"]),
        detected_kind=str(row["detected_kind"]),
        state=str(row["state"]),
        work_key=str(row["work_key"]),
        identity=_json_object(row["identity_json"]),
        candidates=tuple(
            value for value in _json_list(row["candidates_json"]) if isinstance(value, dict)
        ),
        available=bool(row["available"]),
        first_seen_at=int(row["first_seen_at"]),
        last_seen_at=int(row["last_seen_at"]),
        updated_at=int(row["updated_at"]),
        last_run_id=str(row["last_run_id"]),
    )


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _path_key(value: str) -> str:
    return os.path.normcase(str(Path(value).resolve()))


def _relative_path_key(value: str) -> str:
    return os.path.normcase(str(value or "").replace("\\", "/"))
