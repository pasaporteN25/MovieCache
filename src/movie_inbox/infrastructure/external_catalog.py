"""Configured external-source gateway for application entrypoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from movie_inbox.application.external_service import ExternalCatalogService
from movie_inbox.domain.models import ExternalSearchResult
from movie_inbox.external.anime_offline import AnimeOfflineAdapter
from movie_inbox.external.imdb import imdb_id_from_text
from movie_inbox.external.imdb_dataset_source import (
    ImdbDatasetSource,
    apply_dataset_authority,
)
from movie_inbox.external.metadata import fetch_metadata, fetch_metadata_by_title
from movie_inbox.external.registry import ExternalSourceService, default_source_adapters

EXTERNAL_SOURCES = ExternalSourceService()
EXTERNAL_CATALOG = ExternalCatalogService(EXTERNAL_SOURCES, fetch_metadata)


def configure_external_catalog(
    tmdb_read_access_token: str = "",
    anime_offline_index_path: str = "",
    imdb_dataset_index_path: str = "",
) -> None:
    """Configure the process-wide gateway once for this single-worker app."""

    global EXTERNAL_CATALOG, EXTERNAL_SOURCES
    fallback_adapters = (
        {"jikan": AnimeOfflineAdapter(Path(anime_offline_index_path))}
        if anime_offline_index_path
        else {}
    )
    EXTERNAL_SOURCES = ExternalSourceService(
        default_source_adapters(tmdb_read_access_token),
        fallback_adapters=fallback_adapters,
    )
    dataset_source = (
        ImdbDatasetSource(Path(imdb_dataset_index_path)) if imdb_dataset_index_path else None
    )

    def load_metadata(url: str) -> dict[str, Any]:
        metadata = fetch_metadata(url, tmdb_read_access_token=tmdb_read_access_token)
        # The id can come from the URL itself or from what the live source just
        # returned (TMDb, for one, hands back an imdb_url), so both are tried.
        imdb_id = imdb_id_from_text(url) or imdb_id_from_text(str(metadata.get("imdb_url") or ""))
        return apply_dataset_authority(metadata, dataset_source, imdb_id)

    EXTERNAL_CATALOG = ExternalCatalogService(EXTERNAL_SOURCES, load_metadata)


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
