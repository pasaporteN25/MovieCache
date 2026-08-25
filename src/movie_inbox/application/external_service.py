"""External catalog use cases expressed against an injected gateway."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

from movie_inbox.domain.catalog import (
    canonical_url,
    external_source_name,
    merge_lists,
    normalize_tags,
)
from movie_inbox.domain.models import ExternalSearchResult
from movie_inbox.domain.releases import merge_release_dates, normalize_release_dates
from movie_inbox.domain.titles import looks_like_external_id


class ExternalSourceGateway(Protocol):
    def search(
        self, query: str, source: str = "all"
    ) -> tuple[list[ExternalSearchResult], dict[str, Any]]: ...

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

    def search(
        self, query: str, source: str = "all"
    ) -> tuple[list[ExternalSearchResult], dict[str, Any]]:
        results, state = self.gateway.search(query, source)
        return results, state

    def enrich(self, result: Mapping[str, Any]) -> ExternalSearchResult:
        enriched: dict[str, Any] = dict(result)
        preserved_titles = [
            *(
                str(enriched.get(field) or "").strip()
                for field in ("title", "original_title", "spanish_title", "english_title")
            ),
            *normalize_tags(enriched.get("alternative_titles")),
        ]
        result_url = str(enriched.get("url") or "")
        detected_source = external_source_name(result_url)
        source = str(enriched.get("source") or detected_source)
        if source not in {"wikipedia", "imdb", "filmaffinity"} or source != detected_source:
            return cast(ExternalSearchResult, enriched)
        cache_key = canonical_url(result_url) or result_url
        metadata, _ = self.gateway.selected_metadata(
            cache_key, lambda _: self.metadata_loader(result_url)
        )
        if not metadata:
            return cast(ExternalSearchResult, enriched)
        for field in (
            "title",
            "original_title",
            "spanish_title",
            "english_title",
            "kind",
            "year",
            "description",
            "wikipedia_title",
            "wikidata_id",
            "page_image",
            "backdrop_image",
            "tmdb_id",
            "wikipedia_extract",
        ):
            if metadata.get(field):
                value = str(metadata[field])
                if field in {
                    "title",
                    "original_title",
                    "spanish_title",
                    "english_title",
                } and looks_like_external_id(value):
                    continue
                enriched[field] = value
        duration_minutes = metadata.get("duration_minutes")
        if isinstance(duration_minutes, int) and not isinstance(duration_minutes, bool):
            if duration_minutes > 0:
                enriched["duration_minutes"] = duration_minutes
        for field in (
            "alternative_titles",
            "countries",
            "original_languages",
            "producers",
            "composers",
            "genres",
            "directors",
            "writers",
            "cast",
        ):
            values = normalize_tags(metadata.get(field))
            if values:
                enriched[field] = merge_lists(normalize_tags(enriched.get(field)), values)
        release_dates = normalize_release_dates(metadata.get("release_dates"))
        if release_dates:
            enriched["release_dates"] = merge_release_dates(
                enriched.get("release_dates"), release_dates
            )
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
        enriched["alternative_titles"] = _alternative_titles(enriched, preserved_titles)
        return cast(ExternalSearchResult, enriched)

    def snapshot(self) -> dict[str, Any]:
        return self.gateway.snapshot()


def _alternative_titles(result: Mapping[str, Any], preserved_titles: list[str]) -> list[str]:
    primary = {
        str(result.get(field) or "").strip().casefold()
        for field in ("title", "original_title", "spanish_title", "english_title")
        if str(result.get(field) or "").strip()
    }
    aliases: list[str] = []
    seen: set[str] = set()
    for value in [*normalize_tags(result.get("alternative_titles")), *preserved_titles]:
        title = str(value or "").strip()
        key = title.casefold()
        if not title or key in primary or key in seen:
            continue
        seen.add(key)
        aliases.append(title)
    return aliases[:40]
