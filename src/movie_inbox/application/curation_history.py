"""Persistence contract for reversible curation operations."""

from __future__ import annotations

from typing import Any, Protocol

HISTORY_MODES = {"persistent", "session"}
HISTORY_LIMIT = 50


class CurationHistoryError(RuntimeError):
    """Raised when the operational history cannot be read or written."""


class CurationHistoryRepository(Protocol):
    def list(self, namespace: str = "") -> list[dict[str, Any]]: ...

    def append(self, operation: dict[str, Any], namespace: str = "") -> None: ...

    def replace(self, operation: dict[str, Any], namespace: str = "") -> None: ...

    def clear(self, namespace: str = "") -> int: ...


def normalize_history_mode(value: object) -> str:
    mode = str(value or "persistent").strip().casefold()
    if mode not in HISTORY_MODES:
        raise ValueError("Invalid history mode")
    return mode
