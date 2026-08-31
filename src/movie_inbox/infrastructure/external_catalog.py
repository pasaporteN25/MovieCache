"""Configured external-source gateway for application entrypoints."""

from __future__ import annotations

from typing import Any

from movie_inbox.application.external_service import ExternalCatalogService
from movie_inbox.domain.models import ExternalSearchResult
from movie_inbox.external.metadata import fetch_metadata, fetch_metadata_by_title
from movie_inbox.external.registry import ExternalSourceService, default_source_adapters

EXTERNAL_SOURCES = ExternalSourceService()
EXTERNAL_CATALOG = ExternalCatalogService(EXTERNAL_SOURCES, fetch_metadata)


def configure_external_catalog(tmdb_read_access_token: str = "") -> None:
    """Configure the process-wide gateway once for this single-worker app."""

    global EXTERNAL_CATALOG, EXTERNAL_SOURCES
    EXTERNAL_SOURCES = ExternalSourceService(default_source_adapters(tmdb_read_access_token))
    EXTERNAL_CATALOG = ExternalCatalogService(
        EXTERNAL_SOURCES,
        lambda url: fetch_metadata(
            url,
            tmdb_read_access_token=tmdb_read_access_token,
        ),
    )


def search_external_sources(
    query: str, source: str = "all"
) -> tuple[list[ExternalSearchResult], dict[str, Any]]:
    return EXTERNAL_CATALOG.search(query, source)


def enrich_external_result(result: ExternalSearchResult | dict[str, Any]) -> ExternalSearchResult:
    return EXTERNAL_CATALOG.enrich(result)


def external_metadata_by_title(title: str, year: str = "") -> dict[str, Any]:
    cache_key = f"title:{title.strip().casefold()}:{str(year or '').strip()}"
    metadata, _ = EXTERNAL_SOURCES.selected_metadata(
        cache_key,
        lambda _: fetch_metadata_by_title(title, year),
    )
    return metadata


def external_sources_snapshot() -> dict[str, Any]:
    return EXTERNAL_CATALOG.snapshot()
