"""Concurrent external-source registry with health and short-lived caches."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from math import ceil
from typing import Any
from urllib.error import HTTPError, URLError

from movie_inbox.domain.search import (
    EXTERNAL_RELEVANCE_THRESHOLD,
    external_result_score,
    parse_search_query,
)
from movie_inbox.external.base import SourceAdapter
from movie_inbox.external.common import clean_text, dedupe_results, utc_now
from movie_inbox.external.filmaffinity import FilmAffinityAdapter
from movie_inbox.external.imdb import ImdbAdapter
from movie_inbox.external.jikan import JikanAdapter
from movie_inbox.external.tmdb import TmdbAdapter
from movie_inbox.external.wikipedia import WikipediaAdapter

SEARCH_CACHE_TTL_SECONDS = 15 * 60
EMPTY_SEARCH_CACHE_TTL_SECONDS = 30
SEARCH_CACHE_MAX_ENTRIES = 128
DEFAULT_TIMEOUT_COOLDOWN_SECONDS = 30
DEFAULT_UPSTREAM_COOLDOWN_SECONDS = 45


class ExternalSourceService:
    def __init__(
        self,
        adapters: list[SourceAdapter] | None = None,
        fallback_adapters: Mapping[str, SourceAdapter] | None = None,
    ) -> None:
        selected = default_source_adapters() if adapters is None else adapters
        self.adapters = {adapter.name: adapter for adapter in selected}
        self.fallback_adapters = dict(fallback_adapters or {})
        self._search_cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
        self._metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._cooldowns: dict[str, float] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._health = {adapter.name: self._initial_health(adapter) for adapter in selected}
        for live_source, adapter in self.fallback_adapters.items():
            fallback_health = {
                **self._initial_health(adapter),
                "role": "offline_fallback",
                "fallback_for": live_source,
            }
            metadata_loader: Any = getattr(adapter, "health_metadata", None)
            if callable(metadata_loader):
                try:
                    fallback_health.update(metadata_loader())
                except Exception as error:
                    fallback_health.update(
                        {
                            "status": "error",
                            "error": clean_text(str(error))[:160] or error.__class__.__name__,
                            "error_code": "index_unavailable",
                        }
                    )
            self._health[adapter.name] = fallback_health

    def search(
        self, query: str, source: str = "all"
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        query = query.strip()
        if len(query) < 2:
            return [], self.snapshot()
        intent = parse_search_query(query)
        if source == "all":
            selected = [intent.source] if intent.source in self.adapters else list(self.adapters)
        elif source in self.adapters:
            selected = [source]
        else:
            selected = list(self.adapters)
        cache_key = (
            " ".join(query.casefold().split()),
            source if source in self.adapters else "all",
        )
        cached = self._get_search_cache(cache_key)
        if cached is not None:
            return cached, self.snapshot(cache_hit=True)

        with self._lock:
            self._cache_misses += 1
        batches: dict[str, list[dict[str, Any]]] = {name: [] for name in selected}
        succeeded: dict[str, bool] = {name: False for name in selected}
        with ThreadPoolExecutor(
            max_workers=len(selected), thread_name_prefix="catalog-search"
        ) as executor:
            futures = {executor.submit(self._run_adapter, name, query): name for name in selected}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    batches[name], succeeded[name] = future.result()
                except Exception as error:
                    self._record_error(name, error)
        for name in selected:
            fallback = self.fallback_adapters.get(name)
            if fallback is None:
                continue
            if succeeded[name] and batches[name]:
                batches[name] = self._complete_with_fallback(fallback, batches[name])
                continue
            fallback_rows, _ = self._run_source(fallback.name, fallback, query)
            reason = self._fallback_reason(name, succeeded[name])
            batches[name].extend(
                {
                    **row,
                    "source": str(row.get("source") or fallback.name),
                    "_search_shelf": name,
                    "fallback_reason": reason,
                }
                for row in fallback_rows
            )
        # Keep each source together and preserve up to eight alternatives per adapter.
        # Consumers can render independent shelves without losing later-source results.
        results = dedupe_results(
            [result for name in selected for result in self._rank_batch(query, batches[name])[:8]]
        )[: 8 * len(selected)]
        if all(succeeded.values()):
            self._set_search_cache(cache_key, results)
        return [dict(result) for result in results], self.snapshot(cache_hit=False)

    def selected_metadata(
        self, url: str, loader: Callable[[str], dict[str, Any]]
    ) -> tuple[dict[str, Any], bool]:
        now = time.monotonic()
        with self._lock:
            cached = self._metadata_cache.get(url)
            if cached and now - cached[0] <= SEARCH_CACHE_TTL_SECONDS:
                self._cache_hits += 1
                return dict(cached[1]), True
        metadata = loader(url)
        with self._lock:
            self._cache_misses += 1
            self._metadata_cache[url] = (now, dict(metadata))
            self._prune_cache(self._metadata_cache)
        return metadata, False

    def snapshot(self, cache_hit: bool | None = None) -> dict[str, Any]:
        with self._lock:
            sources = {
                name: self._health_snapshot(name, state) for name, state in self._health.items()
            }
            return {
                "sources": sources,
                "cache": {
                    "ttl_seconds": SEARCH_CACHE_TTL_SECONDS,
                    "empty_ttl_seconds": EMPTY_SEARCH_CACHE_TTL_SECONDS,
                    "search_entries": len(self._search_cache),
                    "metadata_entries": len(self._metadata_cache),
                    "hits": self._cache_hits,
                    "misses": self._cache_misses,
                    "last_request_hit": cache_hit,
                },
            }

    def _run_adapter(self, name: str, query: str) -> tuple[list[dict[str, Any]], bool]:
        if self._cooldown_remaining(name) > 0:
            return [], False
        return self._run_source(name, self.adapters[name], query)

    def _run_source(
        self, name: str, adapter: SourceAdapter, query: str
    ) -> tuple[list[dict[str, Any]], bool]:
        started = time.monotonic()
        try:
            results = adapter.search(query)
        except Exception as error:
            self._record_error(name, error, started)
            return [], False
        latency_ms = round((time.monotonic() - started) * 1000)
        with self._lock:
            snapshot_date = str(results[0].get("snapshot_date") or "") if results else ""
            self._health[name].update(
                {
                    "status": "ok" if results else "empty",
                    "last_attempt_at": utc_now(),
                    "last_success_at": utc_now(),
                    "latency_ms": latency_ms,
                    "result_count": len(results),
                    "error": "",
                    "error_code": "",
                    "cooldown_until": "",
                    "retry_after_seconds": 0,
                    **({"snapshot_date": snapshot_date} if snapshot_date else {}),
                }
            )
            self._cooldowns.pop(name, None)
        return results, True

    def _complete_with_fallback(
        self,
        fallback: SourceAdapter,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        completion: Any = getattr(fallback, "complete_results", None)
        if not callable(completion):
            return results
        started = time.monotonic()
        try:
            raw_completed = completion([dict(row) for row in results])
        except Exception as error:
            self._record_error(fallback.name, error, started)
            return results
        if not isinstance(raw_completed, list):
            self._record_error(
                fallback.name,
                TypeError("Fallback completion returned an invalid result list"),
                started,
            )
            return results
        completed = [dict(row) for row in raw_completed if isinstance(row, Mapping)]
        if len(completed) != len(results):
            self._record_error(
                fallback.name,
                TypeError("Fallback completion dropped invalid result rows"),
                started,
            )
            return results
        completion_count = sum(bool(row.get("offline_completion")) for row in completed)
        with self._lock:
            self._health[fallback.name].update(
                {
                    "status": "ok" if completion_count else "empty",
                    "last_attempt_at": utc_now(),
                    "last_success_at": utc_now(),
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "result_count": completion_count,
                    "error": "",
                    "error_code": "",
                }
            )
        return completed

    def _record_error(self, name: str, error: Exception, started: float | None = None) -> None:
        latency_ms = round((time.monotonic() - started) * 1000) if started is not None else 0
        error_code, cooldown_seconds = _source_error_state(error)
        cooldown_until = ""
        if cooldown_seconds > 0:
            cooldown_until = (datetime.now(UTC) + timedelta(seconds=cooldown_seconds)).isoformat()
        with self._lock:
            if cooldown_seconds > 0:
                self._cooldowns[name] = time.monotonic() + cooldown_seconds
            self._health[name].update(
                {
                    "status": "cooldown" if cooldown_seconds > 0 else "error",
                    "last_attempt_at": utc_now(),
                    "latency_ms": latency_ms,
                    "result_count": 0,
                    "error": clean_text(str(error))[:160] or error.__class__.__name__,
                    "error_code": error_code,
                    "cooldown_until": cooldown_until,
                    "retry_after_seconds": cooldown_seconds,
                }
            )

    def _cooldown_remaining(self, name: str) -> int:
        with self._lock:
            expires_at = self._cooldowns.get(name, 0)
            remaining = max(0, ceil(expires_at - time.monotonic()))
            if not remaining and expires_at:
                self._cooldowns.pop(name, None)
                state = self._health[name]
                if state.get("status") == "cooldown":
                    state.update(
                        {
                            "status": "ready",
                            "error": "",
                            "error_code": "",
                            "cooldown_until": "",
                            "retry_after_seconds": 0,
                        }
                    )
            return remaining

    def _health_snapshot(self, name: str, state: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(state)
        expires_at = self._cooldowns.get(name, 0)
        remaining = max(0, ceil(expires_at - time.monotonic()))
        snapshot["retry_after_seconds"] = remaining
        if remaining:
            snapshot["status"] = "cooldown"
        elif snapshot.get("status") == "cooldown":
            snapshot.update(
                {
                    "status": "ready",
                    "error": "",
                    "error_code": "",
                    "cooldown_until": "",
                }
            )
        return snapshot

    def _fallback_reason(self, name: str, succeeded: bool) -> str:
        if succeeded:
            return "empty"
        with self._lock:
            return str(self._health.get(name, {}).get("error_code") or "unavailable")

    def _get_search_cache(self, key: tuple[str, str]) -> list[dict[str, Any]] | None:
        now = time.monotonic()
        with self._lock:
            cached = self._search_cache.get(key)
            if not cached:
                return None
            ttl = SEARCH_CACHE_TTL_SECONDS if cached[1] else EMPTY_SEARCH_CACHE_TTL_SECONDS
            if now - cached[0] > ttl:
                del self._search_cache[key]
                return None
            self._cache_hits += 1
            return [dict(result) for result in cached[1]]

    def _set_search_cache(self, key: tuple[str, str], results: list[dict[str, Any]]) -> None:
        with self._lock:
            self._search_cache[key] = (time.monotonic(), [dict(result) for result in results])
            self._prune_search_cache()

    def _prune_search_cache(self) -> None:
        now = time.monotonic()
        for key, (created_at, results) in list(self._search_cache.items()):
            ttl = SEARCH_CACHE_TTL_SECONDS if results else EMPTY_SEARCH_CACHE_TTL_SECONDS
            if now - created_at > ttl:
                del self._search_cache[key]
        while len(self._search_cache) > SEARCH_CACHE_MAX_ENTRIES:
            del self._search_cache[
                min(self._search_cache, key=lambda key: self._search_cache[key][0])
            ]

    @staticmethod
    def _rank_batch(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = dedupe_results(results)
        scored = sorted(
            ((external_result_score(query, row), index, row) for index, row in enumerate(rows)),
            key=lambda entry: (-entry[0], entry[1]),
        )
        return [row for score, _, row in scored if score >= EXTERNAL_RELEVANCE_THRESHOLD]

    @staticmethod
    def _prune_cache(cache: dict[Any, tuple[float, Any]]) -> None:
        now = time.monotonic()
        for key in [
            key
            for key, (created_at, _) in cache.items()
            if now - created_at > SEARCH_CACHE_TTL_SECONDS
        ]:
            del cache[key]
        while len(cache) > SEARCH_CACHE_MAX_ENTRIES:
            del cache[min(cache, key=lambda key: cache[key][0])]

    @staticmethod
    def _initial_health(adapter: SourceAdapter) -> dict[str, Any]:
        return {
            "name": adapter.name,
            "label": adapter.label,
            "status": "ready",
            "last_attempt_at": "",
            "last_success_at": "",
            "latency_ms": 0,
            "result_count": 0,
            "error": "",
            "error_code": "",
            "cooldown_until": "",
            "retry_after_seconds": 0,
        }


def _source_error_state(error: Exception) -> tuple[str, int]:
    if isinstance(error, HTTPError):
        if error.code == 429:
            return "rate_limited", _retry_after_seconds(error)
        if 500 <= error.code <= 599:
            return "upstream_error", DEFAULT_UPSTREAM_COOLDOWN_SECONDS
        return f"http_{error.code}", 0
    if isinstance(error, TimeoutError) or (
        isinstance(error, URLError) and isinstance(error.reason, TimeoutError)
    ):
        return "timeout", DEFAULT_TIMEOUT_COOLDOWN_SECONDS
    return "source_error", 0


def _retry_after_seconds(error: HTTPError) -> int:
    raw_value = str(error.headers.get("Retry-After") or "").strip() if error.headers else ""
    try:
        return max(1, ceil(float(raw_value)))
    except (TypeError, ValueError):
        pass
    try:
        parsed = parsedate_to_datetime(raw_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(1, ceil((parsed.astimezone(UTC) - datetime.now(UTC)).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return DEFAULT_UPSTREAM_COOLDOWN_SECONDS


def default_source_adapters(tmdb_read_access_token: str = "") -> list[SourceAdapter]:
    adapters: list[SourceAdapter] = [
        WikipediaAdapter(),
        ImdbAdapter(),
        FilmAffinityAdapter(),
        JikanAdapter(),
    ]
    if tmdb_read_access_token:
        adapters.append(TmdbAdapter(tmdb_read_access_token))
    return adapters


EXTERNAL_SOURCES = ExternalSourceService()
