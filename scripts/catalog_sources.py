#!/usr/bin/env python3
"""External catalog source adapters with shared cache and health reporting."""

from __future__ import annotations

import html
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen


SEARCH_CACHE_TTL_SECONDS = 15 * 60
SEARCH_CACHE_MAX_ENTRIES = 128


class SourceAdapter:
    name = ""
    label = ""

    def search(self, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class WikipediaAdapter(SourceAdapter):
    name = "wikipedia"
    label = "Wikipedia"

    def search(self, query: str) -> list[dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="wikipedia-search") as executor:
            batches = list(executor.map(lambda language: self._search_language(query, language), ["en", "es"]))
        return interleave_batches(batches)

    def _search_language(self, query: str, language: str) -> list[dict[str, Any]]:
        url = (
            f"https://{language}.wikipedia.org/w/api.php"
            f"?action=query&generator=search&gsrsearch={quote(query + ' film')}&gsrlimit=5"
            "&prop=extracts%7Cpageimages%7Cpageprops&exintro=1&explaintext=1&pithumbsize=480"
            "&format=json&formatversion=2"
        )
        raw = fetch_json(url)
        query_data = raw.get("query") if isinstance(raw.get("query"), dict) else {}
        rows = query_data.get("pages") if isinstance(query_data, dict) else []
        if not isinstance(rows, list):
            return []
        rows.sort(key=result_index)
        results: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "")
            if not title:
                continue
            extract = str(row.get("extract") or "")
            thumbnail = row.get("thumbnail") if isinstance(row.get("thumbnail"), dict) else {}
            pageprops = row.get("pageprops") if isinstance(row.get("pageprops"), dict) else {}
            page_url = f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"
            results.append(
                {
                    "source": self.name,
                    "title": title,
                    "original_title": "",
                    "spanish_title": title if language == "es" else "",
                    "english_title": title if language == "en" else "",
                    "alternative_titles": [],
                    "year": infer_year(extract),
                    "url": page_url,
                    "description": extract[:360],
                    "wikipedia_url": page_url,
                    "wikipedia_title": title,
                    "wikidata_id": str(pageprops.get("wikibase_item") or ""),
                    "genres": [],
                    "directors": [],
                    "writers": [],
                    "cast": [],
                    "page_image": str(thumbnail.get("source") or ""),
                    "wikipedia_extract": extract,
                }
            )
        return results


class ImdbAdapter(SourceAdapter):
    name = "imdb"
    label = "IMDb"

    def search(self, query: str) -> list[dict[str, Any]]:
        key = re.sub(r"[^a-z0-9_ -]+", "", query.lower()).strip().replace(" ", "_")
        if not key:
            return []
        raw = fetch_json(f"https://v3.sg.media-imdb.com/suggestion/x/{quote(key)}.json")
        rows = raw.get("d") if isinstance(raw.get("d"), list) else []
        results: list[dict[str, Any]] = []
        for row in rows[:8]:
            if not isinstance(row, dict) or row.get("qid") not in {"movie", "tvSeries", "tvMiniSeries", "tvMovie"}:
                continue
            imdb_id = str(row.get("id") or "")
            title = str(row.get("l") or "")
            if not imdb_id or not title:
                continue
            image = row.get("i") if isinstance(row.get("i"), dict) else {}
            results.append(
                {
                    "source": self.name,
                    "title": title,
                    "original_title": "",
                    "spanish_title": "",
                    "english_title": title,
                    "alternative_titles": [],
                    "year": str(row.get("y") or ""),
                    "url": f"https://www.imdb.com/title/{imdb_id}/",
                    "description": str(row.get("s") or ""),
                    "page_image": str(image.get("imageUrl") or "") if isinstance(image, dict) else "",
                }
            )
        return results


class FilmAffinityAdapter(SourceAdapter):
    name = "filmaffinity"
    label = "FilmAffinity"

    def search(self, query: str) -> list[dict[str, Any]]:
        parser = FilmAffinityParser()
        parser.feed(fetch_text(f"https://www.filmaffinity.com/es/search.php?stext={quote(query)}"))
        return parser.results[:8]


class FilmAffinityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, Any]] = []
        self.current_href = ""
        self.capture_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        href = attributes.get("href", "")
        if tag == "a" and "/film" in href:
            self.current_href = href
            self.capture_title = True
        if tag in {"div", "span"} and "mc-title" in attributes.get("class", ""):
            self.capture_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.capture_title = False

    def handle_data(self, data: str) -> None:
        title = clean_text(data)
        url = self.absolute_url(self.current_href)
        if not self.capture_title or not self.current_href or len(title) < 2:
            return
        if any(existing["url"] == url for existing in self.results):
            return
        self.results.append(
            {
                "source": "filmaffinity",
                "title": title,
                "original_title": "",
                "spanish_title": title,
                "english_title": "",
                "alternative_titles": [],
                "year": infer_year(title),
                "url": url,
                "description": "",
            }
        )

    @staticmethod
    def absolute_url(href: str) -> str:
        return href if href.startswith("http") else "https://www.filmaffinity.com" + href


class ExternalSourceService:
    def __init__(self) -> None:
        adapters = [WikipediaAdapter(), ImdbAdapter(), FilmAffinityAdapter()]
        self.adapters = {adapter.name: adapter for adapter in adapters}
        self._search_cache: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
        self._metadata_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._cache_hits = 0
        self._cache_misses = 0
        self._health: dict[str, dict[str, Any]] = {
            adapter.name: self._initial_health(adapter) for adapter in adapters
        }

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
        ordered_batches = [batches[name] for name in selected]
        results = dedupe_results(interleave_batches(ordered_batches))[:18]
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
            sources = {name: dict(state) for name, state in self._health.items()}
            return {
                "sources": sources,
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


def fetch_json(url: str) -> dict[str, Any]:
    raw = json.loads(fetch_text(url, accept="application/json") or "{}")
    return raw if isinstance(raw, dict) else {}


def fetch_text(url: str, accept: str = "text/html,application/xhtml+xml") -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "MovieInboxViewer/0.2 (+local personal catalog)",
            "Accept": accept,
        },
    )
    with urlopen(request, timeout=8) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read(800_000).decode(charset, errors="replace")


def dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for result in results:
        url = str(result.get("url") or "").strip().rstrip("/").casefold()
        key = url or f"{result.get('source')}:{result.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def interleave_batches(batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        batch[index]
        for index in range(max((len(batch) for batch in batches), default=0))
        for batch in batches
        if index < len(batch)
    ]


def result_index(row: Any) -> int:
    try:
        return int(row.get("index") or 999) if isinstance(row, dict) else 999
    except (TypeError, ValueError):
        return 999


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def infer_year(value: str) -> str:
    match = re.search(r"\b(19\d{2}|20\d{2})\b", value or "")
    return match.group(1) if match else ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


EXTERNAL_SOURCES = ExternalSourceService()
