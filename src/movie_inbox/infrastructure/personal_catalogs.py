"""Provision isolated SQLite catalogs for local members."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.repositories import open_catalog_repository


class SqlitePersonalCatalogProvisioner:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def create(self) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.directory, 0o700)
        except OSError:
            pass
        path = self.directory / f"member-{uuid.uuid4().hex}.db"
        open_catalog_repository(path, normalize_item).write([])
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return path.resolve()

    def discard(self, path: Path) -> None:
        candidate = Path(path).resolve()
        directory = self.directory.resolve()
        if candidate.parent != directory or not candidate.name.startswith("member-"):
            raise ValueError("Refusing to discard a catalog outside the managed member directory")
        for suffix in ("", "-wal", "-shm", "-journal"):
            managed_file = Path(str(candidate) + suffix)
            try:
                managed_file.unlink()
            except FileNotFoundError:
                pass
