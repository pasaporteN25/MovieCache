#!/usr/bin/env python3
"""JSON catalog repository with atomic writes and cross-process locking."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from movie_inbox.application.repository import (
    CatalogBusyError,
    CatalogFormatError,
    CatalogItemMutation,
    CatalogMutation,
    CatalogNormalizer,
    CatalogRepositoryError,
    T,
)
from movie_inbox.domain.metadata import normalize_local_files
from movie_inbox.domain.models import CatalogItem
from movie_inbox.domain.catalog import possible_duplicate_candidates
from movie_inbox.infrastructure.schema import CatalogSchemaError, atomic_write_json, catalog_document, extract_catalog_items


class JsonCatalogRepository:
    def __init__(
        self,
        path: Path,
        normalizer: CatalogNormalizer,
        lock_timeout: float = 10.0,
        stale_lock_seconds: float = 300.0,
        *,
        read_only: bool = False,
    ) -> None:
        self.path = Path(path)
        self.normalizer = normalizer
        self.lock_timeout = max(0.1, lock_timeout)
        self.stale_lock_seconds = max(30.0, stale_lock_seconds)
        self.read_only = bool(read_only)
        self._thread_lock = threading.RLock()
        self._local = threading.local()

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f".{self.path.name}.lock")

    def read(self) -> list[CatalogItem]:
        with self.locked():
            return self._read_unlocked()

    def get(self, item_id: str) -> CatalogItem | None:
        with self.locked():
            return next((item for item in self._read_unlocked() if item.id == item_id), None)

    def write(self, items: list[CatalogItem]) -> None:
        self._require_writable()
        with self.locked():
            self._write_unlocked(items)

    def mutate(self, mutation: CatalogMutation[T]) -> T:
        self._require_writable()
        with self.locked():
            items = self._read_unlocked()
            changed, result = mutation(items)
            if changed:
                self._write_unlocked(items)
            return result

    def update_item(self, item_id: str, mutation: CatalogItemMutation) -> bool:
        def update(items: list[CatalogItem]) -> tuple[bool, bool]:
            item = next((row for row in items if row.id == item_id), None)
            if item is None:
                return False, False
            mutation(item)
            return True, True

        return self.mutate(update)

    def update_status(self, item_id: str, status: str, watched_at: str | None = None) -> bool:
        def update(item: CatalogItem) -> None:
            item["status"] = status
            if watched_at is not None:
                item["watched_at"] = watched_at

        return self.update_item(item_id, update)

    def update_metadata(self, item_id: str, mutation: CatalogItemMutation) -> bool:
        return self.update_item(item_id, mutation)

    def delete_by_id(self, item_id: str) -> bool:
        def delete(items: list[CatalogItem]) -> tuple[bool, bool]:
            for index, item in enumerate(items):
                if item.id == item_id:
                    del items[index]
                    return True, True
            return False, False

        return self.mutate(delete)

    def attach_local_file(self, item_id: str, local_file: dict[str, Any]) -> bool:
        normalized = normalize_local_files([local_file])
        if not normalized:
            raise ValueError("Invalid local file")

        def attach(item: CatalogItem) -> None:
            item["local_files"] = normalize_local_files([*item.local_files, normalized[0]])
            item["en_catalogo"] = True
            item["local_name"] = item.local_name or normalized[0]["name"]
            item["local_path"] = item.local_path or normalized[0]["path"]

        return self.update_item(item_id, attach)

    def find_candidates(self, candidate: CatalogItem) -> list[dict[str, Any]]:
        return possible_duplicate_candidates(self.read(), candidate)

    @contextmanager
    def locked(self) -> Iterator[None]:
        with self._thread_lock:
            if self.read_only:
                yield
                return
            depth = int(getattr(self._local, "depth", 0))
            if depth:
                self._local.depth = depth + 1
                try:
                    yield
                finally:
                    self._local.depth -= 1
                return

            token = uuid.uuid4().hex
            self._acquire_file_lock(token)
            self._local.depth = 1
            try:
                yield
            finally:
                self._local.depth = 0
                self._release_file_lock(token)

    def _require_writable(self) -> None:
        if self.read_only:
            raise CatalogRepositoryError(f"Catalog is read-only: {self.path}")

    def _read_unlocked(self) -> list[CatalogItem]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError as error:
            raise CatalogRepositoryError(f"Cannot read catalog: {self.path}") from error
        except json.JSONDecodeError as error:
            raise CatalogFormatError(f"Invalid catalog JSON: {self.path} ({error})") from error
        try:
            rows = extract_catalog_items(raw)
            items = [self.normalizer(row) for row in rows]
            catalog_document(items)
            return items
        except CatalogSchemaError as error:
            raise CatalogFormatError(f"Invalid catalog schema: {self.path} ({error})") from error

    def _write_unlocked(self, items: list[CatalogItem]) -> None:
        try:
            atomic_write_json(self.path, catalog_document(items))
        except CatalogSchemaError as error:
            raise CatalogFormatError(f"Cannot write invalid catalog: {self.path} ({error})") from error
        except OSError as error:
            raise CatalogRepositoryError(f"Cannot write catalog: {self.path}") from error

    def _acquire_file_lock(self, token: str) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        payload = json.dumps(
            {
                "token": token,
                "pid": os.getpid(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=True,
        ).encode("utf-8")
        while True:
            try:
                descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                self._remove_stale_lock()
                if time.monotonic() - started >= self.lock_timeout:
                    raise CatalogBusyError(f"Catalog is busy: {self.path}")
                time.sleep(0.05)
                continue
            try:
                os.write(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return

    def _remove_stale_lock(self) -> None:
        try:
            age = time.time() - self.lock_path.stat().st_mtime
            if age > self.stale_lock_seconds:
                self.lock_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _release_file_lock(self, token: str) -> None:
        try:
            raw = json.loads(self.lock_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("token") == token:
                self.lock_path.unlink()
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
