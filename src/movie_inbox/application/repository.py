"""Persistence contract consumed by catalog application services."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol, TypeVar

from movie_inbox.domain.models import CatalogItem


T = TypeVar("T")
CatalogNormalizer = Callable[[dict[str, object]], CatalogItem]
CatalogMutation = Callable[[list[CatalogItem]], tuple[bool, T]]


class CatalogRepositoryError(RuntimeError):
    """Base error for catalog persistence failures."""


class CatalogBusyError(CatalogRepositoryError):
    """Raised when another process keeps the catalog locked."""


class CatalogFormatError(CatalogRepositoryError):
    """Raised when a catalog cannot be parsed safely."""


class CatalogRepository(Protocol):
    path: Path

    def read(self) -> list[CatalogItem]: ...

    def write(self, items: list[CatalogItem]) -> None: ...

    def mutate(self, mutation: CatalogMutation[T]) -> T: ...
