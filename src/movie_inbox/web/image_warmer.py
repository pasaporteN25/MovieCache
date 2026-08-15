"""Gradually warm poster images after authenticated catalogs are opened."""

from __future__ import annotations

import heapq
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.image_proxy import (
    ImageCacheInfo,
    cached_image,
    cached_image_keys,
    image_cache_info,
    image_cache_url_keys,
    image_is_cached,
)
from movie_inbox.web.security import UnsafeRemoteUrl, validate_http_url

ImageFetcher = Callable[[ViewerConfig, str], tuple[bytes, str]]
FETCH_ERRORS = (UnsafeRemoteUrl, ValueError, HTTPError, URLError, TimeoutError, OSError)


@dataclass(frozen=True)
class _ScopeSnapshot:
    poster_urls: frozenset[str]
    asset_urls: frozenset[str]
    missing_posters: int
    rejected_posters: int


class ImageCacheWarmer:
    def __init__(
        self,
        config: ViewerConfig,
        *,
        interval_seconds: float | None = None,
        max_attempts: int = 3,
        fetcher: ImageFetcher | None = None,
    ) -> None:
        self.config = config
        self.enabled = bool(config.image_cache and config.image_cache_warm)
        self.interval_seconds = max(
            0.0,
            float(
                config.image_cache_warm_interval_seconds
                if interval_seconds is None
                else interval_seconds
            ),
        )
        self.max_attempts = max(1, int(max_attempts))
        self._fetcher = fetcher or cached_image
        self._condition = threading.Condition(threading.RLock())
        self._ready: deque[str] = deque()
        self._delayed: list[tuple[float, int, str]] = []
        self._queued: set[str] = set()
        self._attempts: dict[str, int] = {}
        self._failed: set[str] = set()
        self._foreground: dict[str, int] = {}
        self._scopes: dict[str, _ScopeSnapshot] = {}
        self._current_url = ""
        self._last_error = ""
        self._last_error_at = ""
        self._last_success_at = ""
        self._sequence = 0
        self._stopping = False
        self._thread: threading.Thread | None = None

    def register_items(self, scope_id: str, items: Iterable[Mapping[str, Any]]) -> None:
        normalized_scope = str(scope_id or "").strip()
        if not normalized_scope:
            raise ValueError("Image cache scope is required")

        poster_order: list[str] = []
        backdrop_order: list[str] = []
        missing_posters = 0
        rejected_posters = 0
        for item in items:
            poster = str(item.get("page_image") or "").strip()
            if poster:
                validated = self._validated_url(poster)
                if validated:
                    poster_order.append(validated)
                else:
                    rejected_posters += 1
            else:
                missing_posters += 1
            backdrop = str(item.get("backdrop_image") or "").strip()
            if backdrop and (validated_backdrop := self._validated_url(backdrop)):
                backdrop_order.append(validated_backdrop)

        poster_urls = frozenset(poster_order)
        asset_order = list(dict.fromkeys([*poster_order, *backdrop_order]))
        snapshot = _ScopeSnapshot(
            poster_urls,
            frozenset(asset_order),
            missing_posters,
            rejected_posters,
        )
        with self._condition:
            if self._stopping:
                return
            self._scopes[normalized_scope] = snapshot
            if self.enabled:
                for image_url in asset_order:
                    if image_url in self._queued:
                        continue
                    self._failed.discard(image_url)
                    self._attempts.pop(image_url, None)
                    self._queued.add(image_url)
                    self._ready.append(image_url)
                if asset_order:
                    self._ensure_thread_locked()
            self._condition.notify_all()

    @contextmanager
    def foreground(self, image_url: str) -> Iterator[None]:
        validated = self._validated_url(image_url)
        if not validated:
            yield
            return
        with self._condition:
            self._foreground[validated] = self._foreground.get(validated, 0) + 1
            self._condition.notify_all()
        try:
            yield
        finally:
            with self._condition:
                remaining = self._foreground.get(validated, 1) - 1
                if remaining > 0:
                    self._foreground[validated] = remaining
                else:
                    self._foreground.pop(validated, None)
                self._condition.notify_all()

    def status(self, scope_id: str, *, include_global: bool = False) -> dict[str, Any]:
        normalized_scope = str(scope_id or "").strip()
        with self._condition:
            scope = self._scopes.get(normalized_scope)
            scopes = dict(self._scopes)
            queued = set(self._queued)
            attempts = dict(self._attempts)
            failed = set(self._failed)
            current_url = self._current_url
            thread_alive = bool(self._thread and self._thread.is_alive())
            last_error = self._last_error
            last_error_at = self._last_error_at
            last_success_at = self._last_success_at

        cache_dir = Path(self.config.image_cache_dir)
        cache_error = ""
        try:
            cache_keys = cached_image_keys(cache_dir)
            cache_info = image_cache_info(cache_dir, self.config.image_cache_total_bytes)
        except OSError:
            cache_keys = set()
            cache_info = ImageCacheInfo(
                cache_dir,
                files=0,
                total_bytes=0,
                max_bytes=self.config.image_cache_total_bytes,
            )
            cache_error = "cache_unavailable"
        personal = self._scope_status(
            scope,
            cache_keys,
            queued,
            attempts,
            failed,
            current_url,
            registered=scope is not None,
            cache_is_full=cache_info.total_bytes >= self.config.image_cache_total_bytes,
        )
        if cache_error and self.enabled and scope is not None:
            personal["state"] = "error"
        payload: dict[str, Any] = {
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "personal": personal,
            "cache": {
                "files": cache_info.files,
                "total_bytes": cache_info.total_bytes,
                "max_bytes": self.config.image_cache_total_bytes,
            },
            "worker": {
                "running": thread_alive,
                "in_progress": bool(current_url),
                "last_error": last_error,
                "last_error_at": last_error_at,
                "last_success_at": last_success_at,
                "cache_error": cache_error,
            },
        }
        if include_global:
            global_assets = frozenset(
                image_url
                for registered_scope in scopes.values()
                for image_url in registered_scope.asset_urls
            )
            payload["global"] = {
                **self._url_status(
                    global_assets,
                    cache_keys,
                    queued,
                    attempts,
                    failed,
                    current_url,
                    registered=bool(scopes),
                    cache_is_full=cache_info.total_bytes >= self.config.image_cache_total_bytes,
                ),
                "registered_scopes": len(scopes),
                "queue_size": len(queued),
            }
        return payload

    def stop(self, timeout: float = 12.0) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(max(0.0, timeout))

    def _validated_url(self, image_url: str) -> str:
        try:
            return validate_http_url(image_url, self.config.image_allowed_hosts)
        except (UnsafeRemoteUrl, ValueError):
            return ""

    def _ensure_thread_locked(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="movie-inbox-image-warmer",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while True:
            image_url = self._take_next()
            if not image_url:
                return
            attempted_download = False
            try:
                if image_is_cached(self.config, image_url):
                    self._finish_success(image_url)
                    continue
                with self._condition:
                    if self._foreground.get(image_url, 0):
                        self._defer_locked(image_url, 0.25)
                        continue
                attempted_download = True
                self._fetcher(self.config, image_url)
            except FETCH_ERRORS:
                self._finish_failure(image_url)
            else:
                self._finish_success(image_url)
            if attempted_download and self.interval_seconds:
                with self._condition:
                    if self._condition.wait_for(lambda: self._stopping, self.interval_seconds):
                        return

    def _take_next(self) -> str:
        with self._condition:
            while not self._stopping:
                now = time.monotonic()
                while self._delayed and self._delayed[0][0] <= now:
                    _, _, image_url = heapq.heappop(self._delayed)
                    if image_url in self._queued:
                        self._ready.append(image_url)
                while self._ready:
                    image_url = self._ready.popleft()
                    if image_url not in self._queued:
                        continue
                    if not self._is_registered_locked(image_url):
                        self._queued.discard(image_url)
                        self._attempts.pop(image_url, None)
                        continue
                    self._current_url = image_url
                    return image_url
                wait_seconds = None
                if self._delayed:
                    wait_seconds = max(0.0, self._delayed[0][0] - now)
                self._condition.wait(wait_seconds)
            return ""

    def _finish_success(self, image_url: str) -> None:
        with self._condition:
            self._queued.discard(image_url)
            self._attempts.pop(image_url, None)
            self._failed.discard(image_url)
            self._current_url = ""
            self._last_success_at = _utc_now()
            self._condition.notify_all()

    def _finish_failure(self, image_url: str) -> None:
        with self._condition:
            attempt = self._attempts.get(image_url, 0) + 1
            self._attempts[image_url] = attempt
            self._current_url = ""
            self._last_error = "image_fetch_failed"
            self._last_error_at = _utc_now()
            if attempt >= self.max_attempts:
                self._queued.discard(image_url)
                self._failed.add(image_url)
            else:
                backoff = max(0.25, self.interval_seconds) * (2 ** (attempt - 1))
                self._defer_locked(image_url, backoff)
            self._condition.notify_all()

    def _defer_locked(self, image_url: str, delay_seconds: float) -> None:
        self._current_url = ""
        self._sequence += 1
        heapq.heappush(
            self._delayed,
            (time.monotonic() + max(0.01, delay_seconds), self._sequence, image_url),
        )
        self._condition.notify_all()

    def _is_registered_locked(self, image_url: str) -> bool:
        return any(image_url in scope.asset_urls for scope in self._scopes.values())

    def _scope_status(
        self,
        scope: _ScopeSnapshot | None,
        cache_keys: set[str],
        queued: set[str],
        attempts: dict[str, int],
        failed: set[str],
        current_url: str,
        *,
        registered: bool,
        cache_is_full: bool,
    ) -> dict[str, Any]:
        poster_urls = scope.poster_urls if scope else frozenset()
        status = self._url_status(
            poster_urls,
            cache_keys,
            queued,
            attempts,
            failed,
            current_url,
            registered=registered,
            cache_is_full=cache_is_full,
        )
        rejected = scope.rejected_posters if scope else 0
        if self.enabled and rejected and status["state"] in {"complete", "idle"}:
            status["state"] = "error"
        return {
            **status,
            "without_url": scope.missing_posters if scope else 0,
            "rejected": rejected,
        }

    def _url_status(
        self,
        urls: frozenset[str],
        cache_keys: set[str],
        queued: set[str],
        attempts: dict[str, int],
        failed: set[str],
        current_url: str,
        *,
        registered: bool,
        cache_is_full: bool,
    ) -> dict[str, Any]:
        available = sum(
            1
            for image_url in urls
            if any(key in cache_keys for key in image_cache_url_keys(image_url))
        )
        failed_count = len(urls & failed)
        pending = max(0, len(urls) - available - failed_count)
        retrying = sum(1 for image_url in urls & queued if attempts.get(image_url, 0) > 0)
        in_progress = bool(current_url and current_url in urls)
        queued_count = len(urls & queued)
        if not self.enabled:
            state = "disabled"
        elif not registered:
            state = "inactive"
        elif in_progress or queued_count:
            state = "retrying" if retrying and not in_progress else "working"
        elif failed_count:
            state = "error"
        elif pending and cache_is_full:
            state = "limit_reached"
        elif pending:
            state = "idle"
        else:
            state = "complete"
        return {
            "state": state,
            "eligible": len(urls),
            "available": available,
            "pending": pending,
            "failed": failed_count,
            "retrying": retrying,
            "queued": queued_count,
            "in_progress": in_progress,
        }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
