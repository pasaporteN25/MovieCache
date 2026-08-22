"""Persistence contract for reversible scanner review operations."""

from __future__ import annotations

from typing import Any, Protocol

from movie_inbox.application.curation_history import HISTORY_MODES, normalize_history_mode

__all__ = [
    "HISTORY_MODES",
    "SCANNER_HISTORY_LIMIT",
    "ScannerHistoryError",
    "ScannerHistoryRepository",
    "normalize_history_mode",
]

SCANNER_HISTORY_LIMIT = 50


class ScannerHistoryError(RuntimeError):
    """Raised when the scanner operational history cannot be read or written."""


class ScannerHistoryRepository(Protocol):
    def list(self, namespace: str = "") -> list[dict[str, Any]]: ...

    def append(self, operation: dict[str, Any], namespace: str = "") -> None: ...

    def replace(self, operation: dict[str, Any], namespace: str = "") -> None: ...

    def clear(self, namespace: str = "") -> int: ...
