"""Opt-in adapter for the local anime-offline-database index."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from movie_inbox.domain.catalog import merge_lists
from movie_inbox.domain.search import parse_search_query
from movie_inbox.external.jikan import jikan_anime_id
from movie_inbox.infrastructure.anime_offline_index import (
    ANIME_OFFLINE_ATTRIBUTION,
    ANIME_OFFLINE_REPOSITORY_URL,
    ANIME_OFFLINE_SOURCE,
    AnimeLookupResult,
    anime_index_stats,
    lookup_anime_by_mal_id,
    lookup_anime_by_title,
)


class AnimeOfflineAdapter:
    name = ANIME_OFFLINE_SOURCE
    label = "anime-offline-database"

    def __init__(self, index_path: Path) -> None:
        self.index_path = Path(index_path)

    def search(self, query: str) -> list[dict[str, Any]]:
        intent = parse_search_query(query)
        if intent.director_query:
            return []
        mal_id = jikan_anime_id(intent.canonical_url or query)
        if mal_id:
            found = lookup_anime_by_mal_id(self.index_path, mal_id)
            matches = [found] if found is not None else []
        else:
            lookup = intent.title or query.strip()
            matches = lookup_anime_by_title(
                self.index_path,
                lookup,
                int(intent.year) if intent.year else None,
            )
        return [_search_result(result) for result in matches]

    def complete_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        completed: list[dict[str, Any]] = []
        for raw_result in results:
            result = dict(raw_result)
            mal_id = str(result.get("mal_id") or "").strip()
            offline = lookup_anime_by_mal_id(self.index_path, mal_id) if mal_id else None
            if offline is None:
                completed.append(result)
                continue
            current_aliases = _string_list(result.get("alternative_titles"))
            merged_aliases = merge_lists(current_aliases, list(offline.aliases))[:40]
            external_ids = {row.provider: row.external_id for row in offline.external_ids}
            enriched_fields: list[str] = []
            if merged_aliases != current_aliases:
                result["alternative_titles"] = merged_aliases
                enriched_fields.append("alternative_titles")
                metadata_sources = _metadata_sources(result.get("metadata_sources"))
                metadata_sources["alternative_titles"] = {
                    "source": "jikan+anime_offline_database",
                    "url": ANIME_OFFLINE_REPOSITORY_URL,
                    "updated_at": offline.snapshot_date,
                    "inferred": False,
                }
                result["metadata_sources"] = metadata_sources
            if external_ids:
                result["external_ids"] = {
                    **_string_mapping(result.get("external_ids")),
                    **external_ids,
                }
                enriched_fields.append("external_ids")
            if enriched_fields:
                result["offline_completion"] = {
                    "source": ANIME_OFFLINE_SOURCE,
                    "snapshot_date": offline.snapshot_date,
                    "fields": enriched_fields,
                    "attribution": ANIME_OFFLINE_ATTRIBUTION,
                }
            completed.append(result)
        return completed

    def health_metadata(self) -> dict[str, Any]:
        stats = anime_index_stats(self.index_path)
        return {
            "snapshot_date": stats.snapshot_date,
            "index_size_bytes": stats.index_size_bytes,
            "attribution": ANIME_OFFLINE_ATTRIBUTION,
        }


def _search_result(result: AnimeLookupResult) -> dict[str, Any]:
    external_ids = {row.provider: row.external_id for row in result.external_ids}
    myanimelist_url = f"https://myanimelist.net/anime/{result.mal_id}" if result.mal_id else ""
    return {
        "source": ANIME_OFFLINE_SOURCE,
        "title": result.title,
        "original_title": "",
        "spanish_title": "",
        "english_title": "",
        "alternative_titles": list(result.aliases),
        "kind": "anime",
        "year": str(result.release_year or ""),
        "url": myanimelist_url or result.primary_url,
        "myanimelist_url": myanimelist_url,
        "mal_id": result.mal_id,
        "external_ids": external_ids,
        "snapshot_date": result.snapshot_date,
        "offline": True,
        "attribution": ANIME_OFFLINE_ATTRIBUTION,
    }


def _string_list(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else []
    return [str(row).strip() for row in rows if str(row).strip()]


def _string_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): str(row) for key, row in value.items() if str(key).strip() and str(row).strip()
    }


def _metadata_sources(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): dict(row) for key, row in value.items() if isinstance(row, Mapping)}


__all__ = ["AnimeOfflineAdapter"]
