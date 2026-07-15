"""External catalog use cases expressed against an injected gateway."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from movie_inbox.domain.catalog import canonical_url, external_source_name, merge_lists, normalize_tags
from movie_inbox.domain.models import ExternalSearchResult


class ExternalSourceGateway(Protocol):
    def search(self, query: str, source: str = "all") -> tuple[list[dict[str, Any]], dict[str, Any]]: ...

    def selected_metadata(
        self,
        url: str,
        loader: Callable[[str], dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]: ...

    def snapshot(self, cache_hit: bool | None = None) -> dict[str, Any]: ...


class ExternalCatalogService:
    def __init__(
        self,
        gateway: ExternalSourceGateway,
        metadata_loader: Callable[[str], dict[str, Any]],
    ) -> None:
        self.gateway = gateway
        self.metadata_loader = metadata_loader

    def search(self, query: str, source: str = "all") -> tuple[list[ExternalSearchResult], dict[str, Any]]:
        results, state = self.gateway.search(query, source)
        return results, state

    def enrich(self, result: ExternalSearchResult | dict[str, Any]) -> ExternalSearchResult:
        enriched: ExternalSearchResult = dict(result)
        result_url = str(enriched.get("url") or "")
        detected_source = external_source_name(result_url)
        source = str(enriched.get("source") or detected_source)
        if source not in {"wikipedia", "imdb", "filmaffinity"} or source != detected_source:
            return enriched
        cache_key = canonical_url(result_url) or result_url
        metadata, _ = self.gateway.selected_metadata(cache_key, lambda _: self.metadata_loader(result_url))
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

    def snapshot(self) -> dict[str, Any]:
        return self.gateway.snapshot()
