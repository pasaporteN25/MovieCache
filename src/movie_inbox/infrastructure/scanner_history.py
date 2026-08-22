"""SQLite persistence for reversible scanner review operations."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any

from movie_inbox.application.scanner_history import SCANNER_HISTORY_LIMIT, ScannerHistoryError


class SqliteScannerHistoryRepository:
    def __init__(
        self,
        path: Path,
        busy_timeout: float = 10.0,
        limit: int = SCANNER_HISTORY_LIMIT,
    ) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self.limit = max(1, int(limit))
        self._thread_lock = threading.RLock()

    def list(self, namespace: str = "") -> list[dict[str, Any]]:
        del namespace
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    rows = connection.execute(
                        """SELECT * FROM scanner_history
                        ORDER BY created_at DESC, rowid DESC LIMIT ?""",
                        (self.limit,),
                    ).fetchall()
                    return [_operation(row) for row in rows]
            except sqlite3.Error as error:
                raise ScannerHistoryError(f"Cannot read scanner history: {self.path}") from error

    def append(self, operation: dict[str, Any], namespace: str = "") -> None:
        del namespace
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        """INSERT INTO scanner_history(
                            id, action, label, status, mode, created_at, undone_at,
                            summary_json, before_json, after_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        _operation_row(operation),
                    )
                    connection.execute(
                        """DELETE FROM scanner_history WHERE id NOT IN (
                            SELECT id FROM scanner_history
                            ORDER BY created_at DESC, rowid DESC LIMIT ?
                        )""",
                        (self.limit,),
                    )
                    connection.commit()
            except sqlite3.Error as error:
                raise ScannerHistoryError(f"Cannot write scanner history: {self.path}") from error

    def replace(self, operation: dict[str, Any], namespace: str = "") -> None:
        del namespace
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    row = _operation_row(operation)
                    cursor = connection.execute(
                        """UPDATE scanner_history SET action = ?, label = ?, status = ?, mode = ?,
                            created_at = ?, undone_at = ?, summary_json = ?, before_json = ?,
                            after_json = ? WHERE id = ?""",
                        (*row[1:], row[0]),
                    )
                    if cursor.rowcount == 0:
                        connection.rollback()
                        raise ScannerHistoryError("Scanner operation was not found")
                    connection.commit()
            except sqlite3.Error as error:
                raise ScannerHistoryError(f"Cannot write scanner history: {self.path}") from error

    def clear(self, namespace: str = "") -> int:
        del namespace
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    count = connection.execute("SELECT COUNT(*) FROM scanner_history").fetchone()[0]
                    connection.execute("DELETE FROM scanner_history")
                    connection.commit()
                    return int(count)
            except sqlite3.Error as error:
                raise ScannerHistoryError(f"Cannot clear scanner history: {self.path}") from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection


def _operation_row(operation: dict[str, Any]) -> tuple[Any, ...]:
    return (
        str(operation.get("id") or ""),
        str(operation.get("action") or ""),
        str(operation.get("label") or ""),
        str(operation.get("status") or "applied"),
        str(operation.get("mode") or "persistent"),
        str(operation.get("created_at") or ""),
        str(operation.get("undone_at") or ""),
        json.dumps(operation.get("summary") or {}, ensure_ascii=False),
        json.dumps(operation.get("before") or {}, ensure_ascii=False),
        json.dumps(operation.get("after") or {}, ensure_ascii=False),
    )


def _operation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "action": str(row["action"]),
        "label": str(row["label"]),
        "status": str(row["status"]),
        "mode": str(row["mode"]),
        "created_at": str(row["created_at"]),
        "undone_at": str(row["undone_at"]),
        "summary": _json_object(row["summary_json"]),
        "before": _json_object(row["before_json"]),
        "after": _json_object(row["after_json"]),
    }


def _json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
