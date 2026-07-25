"""Persistence contract consumed by catalog application services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Protocol, TypeVar

from movie_inbox.domain.models import CatalogItem


T = TypeVar("T")
CatalogNormalizer = Callable[[dict[str, object]], CatalogItem]
CatalogMutation = Callable[[list[CatalogItem]], tuple[bool, T]]
CatalogItemMutation = Callable[[CatalogItem], None]


class CatalogRepositoryError(RuntimeError):
    """Base error for catalog persistence failures."""


class CatalogBusyError(CatalogRepositoryError):
    """Raised when another process keeps the catalog locked."""


class CatalogFormatError(CatalogRepositoryError):
    """Raised when a catalog cannot be parsed safely."""


class CatalogRepository(Protocol):
    path: Path

    def read(self) -> list[CatalogItem]: ...

    def get(self, item_id: str) -> CatalogItem | None: ...

    def write(self, items: list[CatalogItem]) -> None: ...

    def mutate(self, mutation: CatalogMutation[T]) -> T: ...

    def update_item(self, item_id: str, mutation: CatalogItemMutation) -> bool: ...

    def update_metadata(self, item_id: str, mutation: CatalogItemMutation) -> bool: ...

    def update_status(self, item_id: str, status: str, watched_at: str | None = None) -> bool: ...

    def delete_by_id(self, item_id: str) -> bool: ...

    def attach_local_file(self, item_id: str, local_file: dict[str, Any]) -> bool: ...

    def find_candidates(self, candidate: CatalogItem) -> list[dict[str, Any]]: ...
