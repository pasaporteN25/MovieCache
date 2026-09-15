"""Persistence contract for human charades difficulty decisions."""

from __future__ import annotations

from typing import Protocol


class CharadesRepositoryError(RuntimeError):
    """Raised when a difficulty decision cannot be persisted."""


class CharadesRepository(Protocol):
    def difficulties_for(self, user_id: str) -> dict[str, str]: ...

    def set_difficulty(self, user_id: str, work_key: str, difficulty: str) -> None: ...

    def clear_difficulty(self, user_id: str, work_key: str) -> None: ...
