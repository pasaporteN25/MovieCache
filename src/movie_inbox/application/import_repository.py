"""Persistence contract for user-scoped import drafts."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from movie_inbox.domain.imports import ImportDraft, ImportDraftItem


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

    def append_items(
        self,
        user_id: str,
        draft_id: str,
        items: Sequence[ImportDraftItem],
        now: int,
    ) -> bool:
        """Add items to a draft that is still `ready`; False if it is not.

        Appending rather than rewriting: a phone syncs more than once, and
        rewriting the whole draft each time would race with someone reviewing it
        in the browser.
        """
        ...

    def purge_expired(self, now: int) -> int: ...
