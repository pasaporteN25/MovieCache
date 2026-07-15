"""Repository selection for supported catalog storage formats."""

from __future__ import annotations

from pathlib import Path

from movie_inbox.application.repository import CatalogNormalizer, CatalogRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.sqlite_repository import SqliteCatalogRepository


JSON_SUFFIXES = {".json"}
SQLITE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
CATALOG_SUFFIXES = JSON_SUFFIXES | SQLITE_SUFFIXES


def open_catalog_repository(path: Path, normalizer: CatalogNormalizer) -> CatalogRepository:
    path = Path(path)
    suffix = path.suffix.casefold()
    if suffix in JSON_SUFFIXES:
        return JsonCatalogRepository(path, normalizer)
    if suffix in SQLITE_SUFFIXES:
        return SqliteCatalogRepository(path, normalizer)
    supported = ", ".join(sorted(CATALOG_SUFFIXES))
    raise ValueError(f"Unsupported catalog extension '{suffix or '<none>'}'. Use one of: {supported}")
