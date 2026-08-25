"""Application-facing catalog operations used by the HTTP handlers."""

from __future__ import annotations

import copy
import glob
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.curation_service import (
    build_curation_payload as build_curation_payload,
)
from movie_inbox.application.curation_service import (
    curation_counts as curation_counts,
)
from movie_inbox.application.curation_workflow import CurationWorkflowService
from movie_inbox.application.library_service import AvailabilityService
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.domain import catalog as domain
from movie_inbox.domain.metadata import METADATA_FIELDS, normalize_optional_positive_int
from movie_inbox.domain.models import CatalogItem
from movie_inbox.domain.normalization import normalize_kind, normalize_rating
from movie_inbox.infrastructure.curation_history import (
    JsonCurationHistoryRepository,
    MemoryCurationHistoryRepository,
    curation_history_path,
)
from movie_inbox.infrastructure.external_catalog import (
    enrich_external_result,
    external_metadata_by_title,
    search_external_sources,
)
from movie_inbox.infrastructure.repositories import CATALOG_SUFFIXES, open_catalog_repository
from movie_inbox.web.config import ViewerConfig

_CATALOG_SERVICES: dict[str, CatalogService] = {}
_CURATION_WORKFLOWS: dict[str, CurationWorkflowService] = {}
_LOAD_ITEMS_CACHE_MAX_ENTRIES = 16
_LOAD_ITEMS_CACHE: OrderedDict[
    tuple[str, ...], tuple[tuple[tuple[int, int], ...], list[dict[str, Any]]]
] = OrderedDict()
_LOAD_ITEMS_CACHE_LOCK = threading.Lock()


def first_catalog_file(patterns: list[str]) -> str:
    files = resolved_files(patterns)
    if not files:
        raise SystemExit("No supported catalog file found to write additions.")
    return files[0]


# Compatibility for callers written before SQLite catalogs were supported.
first_json_file = first_catalog_file


def write_path_for(config: ViewerConfig, source_file: str) -> Path:
    if source_file:
        try:
            source_path = Path(source_file).resolve()
            for file in resolved_files(config.patterns):
                if Path(file).resolve() == source_path:
                    return Path(file)
        except OSError:
            pass
    return Path(config.write_json)


def resolved_files(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            files.extend(matches)
        else:
            files.append(pattern)
    return sorted(
        str(Path(file)) for file in files if Path(file).suffix.lower() in CATALOG_SUFFIXES
    )


def load_items(patterns: list[str]) -> list[dict[str, Any]]:
    files = resolved_files(patterns)
    cache_key = tuple(files)
    signature = tuple(_catalog_file_signature(Path(file)) for file in files)
    with _LOAD_ITEMS_CACHE_LOCK:
        cached = _LOAD_ITEMS_CACHE.get(cache_key)
        if cached is not None and cached[0] == signature:
            _LOAD_ITEMS_CACHE.move_to_end(cache_key)
            return copy.deepcopy(cached[1])

    items: list[dict[str, Any]] = []
    for file in files:
        try:
            rows = read_json_items(Path(file))
        except CatalogRepositoryError as error:
            print(f"[catalog-viewer] catalog read error file={file} error={error}", flush=True)
            raise
        for item in rows:
            row = item.to_dict()
            row["_source_file"] = str(file)
            items.append(row)
    annotate_duplicate_items(items)
    result = sorted(
        items, key=lambda item: str(item.get("added_at") or item.get("addedAt") or ""), reverse=True
    )
    with _LOAD_ITEMS_CACHE_LOCK:
        _LOAD_ITEMS_CACHE[cache_key] = (signature, copy.deepcopy(result))
        _LOAD_ITEMS_CACHE.move_to_end(cache_key)
        while len(_LOAD_ITEMS_CACHE) > _LOAD_ITEMS_CACHE_MAX_ENTRIES:
            _LOAD_ITEMS_CACHE.popitem(last=False)
    return result


def _catalog_file_signature(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
    except OSError:
        return (-1, -1)
    return stat.st_mtime_ns, stat.st_size


def read_json_items(path: Path) -> list[CatalogItem]:
    return catalog_service(path).list_items()


def write_json_items(path: Path, items: list[CatalogItem]) -> None:
    catalog_service(path).repository.write(items)


def catalog_service(path: Path) -> CatalogService:
    try:
        key = str(path.resolve())
    except OSError:
        key = str(path.absolute())
    if key not in _CATALOG_SERVICES:
        _CATALOG_SERVICES[key] = CatalogService(
            open_catalog_repository(Path(key), domain.normalize_item)
        )
    return _CATALOG_SERVICES[key]


def curation_workflow(
    config: ViewerConfig, availability_service: AvailabilityService
) -> CurationWorkflowService:
    primary_path = Path(config.write_json)
    try:
        key = str(primary_path.resolve())
    except OSError:
        key = str(primary_path.absolute())
    if key not in _CURATION_WORKFLOWS:
        _CURATION_WORKFLOWS[key] = CurationWorkflowService(
            lambda path: catalog_service(path).repository,
            JsonCurationHistoryRepository(curation_history_path(primary_path)),
            MemoryCurationHistoryRepository(),
            availability_service,
        )
    return _CURATION_WORKFLOWS[key]


annotate_duplicate_items = domain.annotate_duplicate_items
canonical_url = domain.canonical_url
external_urls = domain.external_urls
has_external_link = domain.has_external_link
merge_lists = domain.merge_lists
metadata_source_record = domain.metadata_source_record
normalize_date = domain.normalize_date
normalize_item = domain.normalize_item
normalize_tags = domain.normalize_tags
source_url_field = domain.source_url_field
stable_id = domain.stable_id
title_match_key = domain.title_match_key
title_match_keys_for_item = domain.title_match_keys_for_item


def append_item(
    path: Path,
    item: dict[str, Any],
    action: str = "check",
    target_id: str = "",
    expected_source: str = "",
) -> tuple[bool, str, dict[str, Any]]:
    added, reason, extra = catalog_service(path).append_item(item, action, target_id)
    if added and reason == "merged":
        print(
            f"[catalog-viewer] merge ok path={path} target_id={target_id} "
            f"incoming_source={item.get('source', '')} incoming_url={item.get('url', '')}",
            flush=True,
        )
    return added, reason, extra


def needs_background_title_enrichment(item: dict[str, Any]) -> bool:
    return not str(item.get("wikidata_id") or "").strip()


def background_enrich_catalog_item(path: Path, item_id: str, seed: dict[str, Any]) -> None:
    year = str(seed.get("year") or "").strip()
    titles = normalize_tags(
        [
            str(seed.get("original_title") or ""),
            str(seed.get("title") or ""),
            str(seed.get("english_title") or ""),
            str(seed.get("spanish_title") or ""),
            *normalize_tags(seed.get("alternative_titles")),
        ]
    )[:3]
    print(
        f"[catalog-viewer] background enrichment start item_id={item_id} "
        f"titles={titles!r} year={year}",
        flush=True,
    )
    try:
        metadata: dict[str, Any] = {}
        for title in titles:
            metadata = external_metadata_by_title(title, year)
            if metadata:
                break
        if not metadata:
            print(f"[catalog-viewer] background enrichment no_match item_id={item_id}", flush=True)
            return
        wikipedia_url = str(metadata.get("wikipedia_url") or metadata.get("url") or "")
        incoming = {
            **metadata,
            "url": wikipedia_url,
            "source": "wikipedia",
            "wikipedia_url": wikipedia_url,
        }
        updated, reason = catalog_service(path).merge_external_metadata(item_id, incoming)
        print(
            f"[catalog-viewer] background enrichment {reason} item_id={item_id} "
            f"aliases={len(normalize_tags(metadata.get('alternative_titles')))} "
            f"wikidata={metadata.get('wikidata_id', '')}",
            flush=True,
        )
        if not updated:
            return
    except (CatalogRepositoryError, ValueError, OSError) as error:
        print(
            f"[catalog-viewer] background enrichment error item_id={item_id} error={error}",
            flush=True,
        )


def delete_item_anywhere(
    config: ViewerConfig,
    source_file: str,
    item_id: str,
    item_url: str,
    title: str,
    year: str,
    local_name: str,
    confirmed: bool,
) -> tuple[bool, str]:
    paths = [write_path_for(config, source_file)]
    for file in resolved_files(config.patterns):
        path = Path(file)
        if all(path.resolve() != existing.resolve() for existing in paths):
            paths.append(path)
    last_reason = "not_found"
    for path in paths:
        deleted, reason = delete_item(path, item_id, item_url, title, year, local_name, confirmed)
        if deleted:
            return True, reason
        last_reason = reason
    return False, last_reason


def delete_item(
    path: Path,
    item_id: str,
    item_url: str,
    title: str,
    year: str,
    local_name: str,
    confirmed: bool,
) -> tuple[bool, str]:
    return catalog_service(path).delete_item(item_id, item_url, title, year, local_name, confirmed)


def update_item_status(
    path: Path, item_id: str, status: str, watched_at: str = ""
) -> tuple[bool, str]:
    return catalog_service(path).update_status(item_id, status, watched_at)


def update_item_kind(path: Path, item_id: str, kind: str) -> tuple[bool, str]:
    return catalog_service(path).update_kind(item_id, kind)


def update_item_catalog_status(path: Path, item_id: str, en_catalogo: Any) -> tuple[bool, str]:
    return catalog_service(path).update_catalog_status(item_id, en_catalogo)


def update_item_personal(
    path: Path, item_id: str, watched_at: str, rating: Any, review: str
) -> tuple[bool, str]:
    return catalog_service(path).update_personal(item_id, watched_at, rating, review)


def update_link_curation(path: Path, item_id: str, status: str) -> tuple[bool, str]:
    return catalog_service(path).update_link_curation(item_id, status)


def update_duplicate_curation(
    path: Path,
    item_id: str,
    other_reference: str,
    status: str,
) -> tuple[bool, str]:
    return catalog_service(path).update_duplicate_curation(item_id, other_reference, status)


def update_item_metadata(
    path: Path,
    item_id: str,
    values: dict[str, Any],
    locked_fields: Any,
) -> tuple[bool, str]:
    return catalog_service(path).update_metadata(item_id, values, locked_fields)


def search_sources(query: str, source: str = "all") -> list[dict[str, Any]]:
    started = time.monotonic()
    results, external_state = search_external_sources(query, source)
    cache_hit = external_state.get("cache", {}).get("last_request_hit")
    print(
        f"[catalog-viewer] external search completed query={query!r} source={source} "
        f"seconds={time.monotonic() - started:.2f} count={len(results)} cache_hit={cache_hit}",
        flush=True,
    )
    return [dict(result) for result in results]


def enrich_selected_result(result: dict[str, Any]) -> dict[str, Any]:
    return dict(enrich_external_result(result))


def item_from_search_result(result: dict[str, Any]) -> dict[str, Any]:
    url = str(result.get("url") or "").strip()
    title = str(result.get("title") or "").strip()
    if not url or not title:
        raise ValueError("Result must include title and url")
    source = str(result.get("source") or source_from_url(url))
    link_field = source_url_field(source, url)
    source_links = {
        "wikipedia_url": str(result.get("wikipedia_url") or ""),
        "imdb_url": str(result.get("imdb_url") or ""),
        "filmaffinity_url": str(result.get("filmaffinity_url") or ""),
    }
    if link_field:
        source_links[link_field] = source_links.get(link_field) or url
    item: dict[str, Any] = {
        "id": stable_id(url),
        "url": url,
        "source": source,
        "title": title,
        "original_title": str(result.get("original_title") or ""),
        "spanish_title": str(result.get("spanish_title") or ""),
        "english_title": str(result.get("english_title") or ""),
        "alternative_titles": normalize_tags(result.get("alternative_titles")),
        "kind": normalize_kind(result.get("kind")),
        "status": str(result.get("status") or "to_watch"),
        "watched_at": normalize_date(result.get("watched_at")),
        "rating": normalize_rating(result.get("rating")),
        "year": str(result.get("year") or ""),
        "release_dates": result.get("release_dates")
        if isinstance(result.get("release_dates"), list)
        else [],
        "description": str(result.get("description") or ""),
        **source_links,
        "wikipedia_title": str(
            result.get("wikipedia_title") or (title if source == "wikipedia" else "")
        ),
        "wikidata_id": str(result.get("wikidata_id") or ""),
        "duration_minutes": normalize_optional_positive_int(result.get("duration_minutes")),
        "countries": normalize_tags(result.get("countries")),
        "original_languages": normalize_tags(result.get("original_languages")),
        "producers": normalize_tags(result.get("producers")),
        "composers": normalize_tags(result.get("composers")),
        "genres": normalize_tags(result.get("genres")),
        "directors": normalize_tags(result.get("directors")),
        "writers": normalize_tags(result.get("writers")),
        "cast": normalize_tags(result.get("cast")),
        "page_image": str(result.get("page_image") or ""),
        "backdrop_image": str(result.get("backdrop_image") or ""),
        "tmdb_id": str(result.get("tmdb_id") or ""),
        "wikipedia_extract": str(result.get("wikipedia_extract") or ""),
        "en_catalogo": False,
        "local_files": [],
        "local_name": "",
        "local_path": "",
        "tags": [],
        "notes": "",
        "review": "",
        "metadata_sources": {},
        "locked_fields": [],
        "added_at": datetime.now(UTC).isoformat(),
    }
    item["metadata_sources"] = {
        field: metadata_source_record(source, url, inferred=False)
        for field in METADATA_FIELDS
        if item.get(field) not in (None, "", [], {})
    }
    return item


def source_from_url(url: str) -> str:
    source = domain.external_source_name(url)
    if source:
        return source
    return (urlparse(url).hostname or "").lower().removeprefix("www.")
