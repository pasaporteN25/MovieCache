"""Configured external-source gateway for application entrypoints."""

from __future__ import annotations

from typing import Any

from movie_inbox.application.external_service import ExternalCatalogService
from movie_inbox.domain.models import ExternalSearchResult
from movie_inbox.external.metadata import fetch_metadata
from movie_inbox.external.registry import EXTERNAL_SOURCES


EXTERNAL_CATALOG = ExternalCatalogService(EXTERNAL_SOURCES, fetch_metadata)


def search_external_sources(query: str, source: str = "all") -> tuple[list[ExternalSearchResult], dict[str, Any]]:
    return EXTERNAL_CATALOG.search(query, source)


def enrich_external_result(result: ExternalSearchResult | dict[str, Any]) -> ExternalSearchResult:
    return EXTERNAL_CATALOG.enrich(result)


def external_sources_snapshot() -> dict[str, Any]:
    return EXTERNAL_CATALOG.snapshot()
