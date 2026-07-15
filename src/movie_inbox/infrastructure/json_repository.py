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
from typing import Iterator

from movie_inbox.application.repository import (
    CatalogBusyError,
    CatalogFormatError,
    CatalogMutation,
    CatalogNormalizer,
    CatalogRepositoryError,
    T,
)
from movie_inbox.domain.models import CatalogItem
from movie_inbox.infrastructure.schema import CatalogSchemaError, atomic_write_json, catalog_document, extract_catalog_items


class JsonCatalogRepository:
    def __init__(
        self,
        path: Path,
        normalizer: CatalogNormalizer,
        lock_timeout: float = 10.0,
        stale_lock_seconds: float = 300.0,
    ) -> None:
        self.path = Path(path)
        self.normalizer = normalizer
        self.lock_timeout = max(0.1, lock_timeout)
        self.stale_lock_seconds = max(30.0, stale_lock_seconds)
        self._thread_lock = threading.RLock()
        self._local = threading.local()

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f".{self.path.name}.lock")

    def read(self) -> list[CatalogItem]:
        with self.locked():
            return self._read_unlocked()

    def write(self, items: list[CatalogItem]) -> None:
        with self.locked():
            self._write_unlocked(items)

    def mutate(self, mutation: CatalogMutation[T]) -> T:
        with self.locked():
            items = self._read_unlocked()
            changed, result = mutation(items)
            if changed:
                self._write_unlocked(items)
            return result

    @contextmanager
    def locked(self) -> Iterator[None]:
        with self._thread_lock:
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
