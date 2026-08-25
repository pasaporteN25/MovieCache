"""Persistence contract for user-scoped import drafts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from movie_inbox.domain.imports import ImportDraft


class ImportRepositoryError(RuntimeError):
    """Raised when import draft persistence is unavailable."""


class ImportDraftRepository(Protocol):
    path: Path

    def create(self, draft: ImportDraft) -> None: ...

    def list_for_user(self, user_id: str) -> list[ImportDraft]: ...

    def count_for_user(self, user_id: str) -> int: ...

    def get_for_user(self, user_id: str, draft_id: str) -> ImportDraft | None: ...

    def claim_for_apply(
        self, user_id: str, draft_id: str, now: int, stale_before: int
    ) -> ImportDraft | None: ...

    def complete(
        self,
        user_id: str,
        draft_id: str,
        now: int,
        expires_at: int,
        result: dict[str, object],
    ) -> None: ...

    def fail(self, user_id: str, draft_id: str, now: int) -> None: ...

    def delete(self, user_id: str, draft_id: str) -> bool: ...

    def purge_expired(self, now: int) -> int: ...
