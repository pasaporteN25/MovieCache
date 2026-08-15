"""Operational history stores for persistent and session-only undo."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from movie_inbox.application.curation_history import (
    HISTORY_LIMIT,
    CurationHistoryError,
)

HISTORY_DOCUMENT_VERSION = 1


class JsonCurationHistoryRepository:
    def __init__(self, path: Path, limit: int = HISTORY_LIMIT) -> None:
        self.path = Path(path)
        self.limit = max(1, int(limit))
        self._lock = threading.RLock()

    def list(self, namespace: str = "") -> list[dict[str, Any]]:
        del namespace
        with self._lock:
            return self._read()

    def append(self, operation: dict[str, Any], namespace: str = "") -> None:
        del namespace
        with self._lock:
            operations = [
                dict(operation),
                *(row for row in self._read() if row.get("id") != operation.get("id")),
            ][: self.limit]
            self._write(operations)

    def replace(self, operation: dict[str, Any], namespace: str = "") -> None:
        del namespace
        with self._lock:
            operations = self._read()
            for index, row in enumerate(operations):
                if row.get("id") == operation.get("id"):
                    operations[index] = dict(operation)
                    self._write(operations)
                    return
            raise CurationHistoryError("Curation operation was not found")

    def clear(self, namespace: str = "") -> int:
        del namespace
        with self._lock:
            count = len(self._read())
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            except OSError as error:
                raise CurationHistoryError(f"Cannot clear curation history: {self.path}") from error
            return count

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CurationHistoryError(f"Cannot read curation history: {self.path}") from error
        if not isinstance(raw, dict) or raw.get("version") != HISTORY_DOCUMENT_VERSION:
            raise CurationHistoryError(f"Unsupported curation history document: {self.path}")
        operations = raw.get("operations")
        if not isinstance(operations, list) or any(not isinstance(row, dict) for row in operations):
            raise CurationHistoryError(f"Invalid curation history document: {self.path}")
        return [dict(row) for row in operations[: self.limit]]

    def _write(self, operations: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "version": HISTORY_DOCUMENT_VERSION,
            "operations": operations[: self.limit],
        }
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            os.replace(temporary_path, self.path)
        except OSError as error:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
            raise CurationHistoryError(f"Cannot write curation history: {self.path}") from error


class MemoryCurationHistoryRepository:
    def __init__(self, limit: int = HISTORY_LIMIT) -> None:
        self.limit = max(1, int(limit))
        self._operations: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def list(self, namespace: str = "") -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._operations.get(namespace, [])]

    def append(self, operation: dict[str, Any], namespace: str = "") -> None:
        with self._lock:
            current = self._operations.get(namespace, [])
            self._operations[namespace] = [
                dict(operation),
                *(row for row in current if row.get("id") != operation.get("id")),
            ][: self.limit]

    def replace(self, operation: dict[str, Any], namespace: str = "") -> None:
        with self._lock:
            current = self._operations.get(namespace, [])
            for index, row in enumerate(current):
                if row.get("id") == operation.get("id"):
                    current[index] = dict(operation)
                    return
            raise CurationHistoryError("Curation operation was not found")

    def clear(self, namespace: str = "") -> int:
        with self._lock:
            count = len(self._operations.get(namespace, []))
            self._operations.pop(namespace, None)
            return count


def curation_history_path(catalog_path: Path) -> Path:
    path = Path(catalog_path)
    return path.with_name(f".{path.name}.curation-history.json")
