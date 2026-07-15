"""Concurrent external-source registry with health and short-lived caches."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from movie_inbox.external.base import SourceAdapter
from movie_inbox.external.common import clean_text, dedupe_results, interleave_batches, utc_now
from movie_inbox.external.filmaffinity import FilmAffinityAdapter
from movie_inbox.external.imdb import ImdbAdapter
from movie_inbox.external.wikipedia import WikipediaAdapter


SEARCH_CACHE_TTL_SECONDS = 15 * 60
SEARCH_CACHE_MAX_ENTRIES = 128


class ExternalSourceService:
    def __init__(self, adapters: list[SourceAdapter] | None = None) -> None:
        selected = adapters or [WikipediaAdapter(), ImdbAdapter(), FilmAffinityAdapter()]
        self.adapters = {adapter.name: adapter for adapter in selected}
        self._search_cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
        self._metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        self._health = {adapter.name: self._initial_health(adapter) for adapter in selected}

    def search(self, query: str, source: str = "all") -> tuple[list[dict[str, Any]], dict[str, Any]]:
        query = query.strip()
        if len(query) < 2:
            return [], self.snapshot()
        selected = list(self.adapters) if source == "all" else [source] if source in self.adapters else list(self.adapters)
        cache_key = (" ".join(query.casefold().split()), source if source in self.adapters else "all")
        cached = self._get_search_cache(cache_key)
        if cached is not None:
            return cached, self.snapshot(cache_hit=True)

        with self._lock:
            self._cache_misses += 1
        batches: dict[str, list[dict[str, Any]]] = {name: [] for name in selected}
        with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="catalog-search") as executor:
            futures = {executor.submit(self._run_adapter, name, query): name for name in selected}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    batches[name] = future.result()
                except Exception as error:
                    self._record_error(name, error)
        results = dedupe_results(interleave_batches([batches[name] for name in selected]))[:18]
        self._set_search_cache(cache_key, results)
        return [dict(result) for result in results], self.snapshot(cache_hit=False)

    def selected_metadata(self, url: str, loader: Callable[[str], dict[str, Any]]) -> tuple[dict[str, Any], bool]:
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
            return {
                "sources": {name: dict(state) for name, state in self._health.items()},
                "cache": {
                    "ttl_seconds": SEARCH_CACHE_TTL_SECONDS,
                    "search_entries": len(self._search_cache),
                    "metadata_entries": len(self._metadata_cache),
                    "hits": self._cache_hits,
                    "misses": self._cache_misses,
                    "last_request_hit": cache_hit,
                },
            }

    def _run_adapter(self, name: str, query: str) -> list[dict[str, Any]]:
        started = time.monotonic()
        try:
            results = self.adapters[name].search(query)
        except Exception as error:
            self._record_error(name, error, started)
            return []
        latency_ms = round((time.monotonic() - started) * 1000)
        with self._lock:
            self._health[name].update(
                {
                    "status": "ok" if results else "empty",
                    "last_attempt_at": utc_now(),
                    "last_success_at": utc_now(),
                    "latency_ms": latency_ms,
                    "result_count": len(results),
                    "error": "",
                }
            )
        return results

    def _record_error(self, name: str, error: Exception, started: float | None = None) -> None:
        latency_ms = round((time.monotonic() - started) * 1000) if started is not None else 0
        with self._lock:
            self._health[name].update(
                {
                    "status": "error",
                    "last_attempt_at": utc_now(),
                    "latency_ms": latency_ms,
                    "result_count": 0,
                    "error": clean_text(str(error))[:160] or error.__class__.__name__,
                }
            )

    def _get_search_cache(self, key: tuple[str, str]) -> list[dict[str, Any]] | None:
        now = time.monotonic()
        with self._lock:
            cached = self._search_cache.get(key)
            if not cached:
                return None
            if now - cached[0] > SEARCH_CACHE_TTL_SECONDS:
                del self._search_cache[key]
                return None
            self._cache_hits += 1
            return [dict(result) for result in cached[1]]

    def _set_search_cache(self, key: tuple[str, str], results: list[dict[str, Any]]) -> None:
        with self._lock:
            self._search_cache[key] = (time.monotonic(), [dict(result) for result in results])
            self._prune_cache(self._search_cache)

    @staticmethod
    def _prune_cache(cache: dict[Any, tuple[float, Any]]) -> None:
        now = time.monotonic()
        for key in [key for key, (created_at, _) in cache.items() if now - created_at > SEARCH_CACHE_TTL_SECONDS]:
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
        }


EXTERNAL_SOURCES = ExternalSourceService()
