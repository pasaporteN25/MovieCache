"""Persistence contract for curated collections and local follows."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from movie_inbox.domain.collections import CuratedCollection


class CollectionRepositoryError(RuntimeError):
    """Raised when collection persistence is unavailable."""


class CollectionRepository(Protocol):
    path: Path

    def install_once(
        self,
        seed_key: str,
        collection: CuratedCollection,
    ) -> bool: ...

    def create_private(self, collection: CuratedCollection) -> bool: ...

    def list_accessible(self, user_id: str) -> list[CuratedCollection]: ...

    def get_accessible(self, user_id: str, collection_id: str) -> CuratedCollection | None: ...

    def set_following(self, user_id: str, collection_id: str, following: bool) -> bool: ...
