"""Persistence contract for the record of works removed from a catalogue."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from movie_inbox.domain.removals import DeviceRemoval


class RemovalRepositoryError(RuntimeError):
    """Raised when the removal record is unavailable."""


class RemovalRepository(Protocol):
    path: Path

    def save(self, catalog_id: str, removals: Sequence[DeviceRemoval], now: int) -> None: ...

    def get_many(self, catalog_id: str, device_ids: Sequence[str]) -> dict[str, DeviceRemoval]: ...

    def forget(self, catalog_id: str, device_ids: Sequence[str]) -> int: ...

    def purge(self, removed_before: int) -> int: ...
