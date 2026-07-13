#!/usr/bin/env python3
"""Application-facing orchestration for external catalog sources."""

from __future__ import annotations

from typing import Any

from catalog_domain import canonical_url, external_source_name, merge_lists, normalize_tags
from catalog_metadata import fetch_metadata
from catalog_models import ExternalSearchResult
from catalog_sources import EXTERNAL_SOURCES


def search_external_sources(query: str, source: str = "all") -> tuple[list[ExternalSearchResult], dict[str, Any]]:
    results, state = EXTERNAL_SOURCES.search(query, source)
    return results, state


def enrich_external_result(result: ExternalSearchResult | dict[str, Any]) -> ExternalSearchResult:
    enriched: ExternalSearchResult = dict(result)
    result_url = str(enriched.get("url") or "")
    detected_source = external_source_name(result_url)
    source = str(enriched.get("source") or detected_source)
    if source not in {"wikipedia", "imdb", "filmaffinity"} or source != detected_source:
        return enriched
    cache_key = canonical_url(result_url) or result_url
    metadata, _ = EXTERNAL_SOURCES.selected_metadata(cache_key, lambda _: fetch_metadata(result_url))
    if not metadata:
        return enriched
    for field in (
        "title", "original_title", "spanish_title", "english_title", "year",
        "description", "wikipedia_title", "wikidata_id", "page_image", "wikipedia_extract",
    ):
        if metadata.get(field):
            enriched[field] = str(metadata[field])
    for field in ("alternative_titles", "genres", "directors", "writers", "cast"):
        values = normalize_tags(metadata.get(field))
        if values:
            enriched[field] = merge_lists(normalize_tags(enriched.get(field)), values)
    for field in ("wikipedia_url", "imdb_url", "filmaffinity_url"):
        if metadata.get(field):
            enriched[field] = str(metadata[field])
    metadata_url = str(metadata.get("url") or "")
    if source == "wikipedia" and metadata_url:
        enriched["url"] = metadata_url
        enriched["wikipedia_url"] = metadata_url
    elif source == "imdb":
        enriched["imdb_url"] = result_url
    elif source == "filmaffinity":
        enriched["filmaffinity_url"] = result_url
    return enriched


def external_sources_snapshot() -> dict[str, Any]:
    return EXTERNAL_SOURCES.snapshot()
