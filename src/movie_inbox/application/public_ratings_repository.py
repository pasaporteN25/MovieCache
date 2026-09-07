"""Persistence contract for dated public-score snapshots."""

from __future__ import annotations

from typing import Protocol

from movie_inbox.domain.public_ratings import PublicRatingSnapshot


class PublicRatingsRepositoryError(RuntimeError):
    """Raised when a public-score snapshot cannot be read or persisted."""


class PublicRatingsRepository(Protocol):
    def ratings(self, source: str, work_keys: list[str]) -> dict[str, PublicRatingSnapshot]: ...

    def save_rating(self, snapshot: PublicRatingSnapshot) -> PublicRatingSnapshot: ...

    def purge_ratings(self, *, source: str = "", before: str = "") -> int:
        """Drop snapshots, optionally only one source's or only older ones."""
        ...
