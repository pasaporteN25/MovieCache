"""Bounded, source-aware query-variant selection ([Q3], tareas.md).

Wikipedia and FilmAffinity have no alias/ID bridge of their own -- unlike
IMDb's (imdb.py:71-91), which this module deliberately leaves untouched.
When one of those two sources' own search comes back empty, its adapter
calls `alias_variants()` here to get up to a handful of Wikidata-confirmed
alternate titles for the same work to retry with. This never translates
free text and never touches director/cast data -- only alias titles a
Wikidata entity match has already confirmed belong to the same work as the
query, via the same `fetch_wikidata_title_matches()` IMDb's own bridge uses.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from movie_inbox.domain.search import (
    EXTERNAL_RELEVANCE_THRESHOLD,
    external_result_score,
    search_key,
)
from movie_inbox.external.wikidata import fetch_wikidata_title_matches

MAX_ALIAS_VARIANTS = 2

# Half the usual 8s default: a variant retry is a best-effort improvement on
# a search that already failed, not the primary path, so it gets a shorter
# leash. See docs/search-quality.md's [Q3] note for the worst-case latency
# arithmetic this bounds.
VARIANT_RETRY_TIMEOUT_SECONDS = 4.0

# Movie Inbox instances are Spanish-first today (docs, UI copy, FilmAffinity
# is a Spanish-only source) -- no per-instance setting exists yet to make
# this configurable (tareas.md [Q3] decided against adding one), so this
# stays a fixed, documented default instead of new settings infrastructure.
PREFERRED_ALIAS_LANGUAGES: tuple[str, ...] = ("es", "en")


def alias_variants(source_name: str, query: str) -> list[str]:
    """Up to MAX_ALIAS_VARIANTS Wikidata-confirmed alias titles for
    `source_name` to retry `query` with, when its own search came back
    empty. [] if no confident Wikidata match exists for `query`."""
    matches = fetch_wikidata_title_matches(query)
    if not matches:
        return []
    metadata = _best_matching_entity(query, matches)
    if metadata is None:
        return []

    seen = {search_key(query)}
    variants: list[str] = []
    for candidate in _priority_order(source_name, metadata):
        candidate = str(candidate or "").strip()
        key = search_key(candidate)
        if not candidate or not key or key in seen:
            continue
        seen.add(key)
        variants.append(candidate)
        if len(variants) >= MAX_ALIAS_VARIANTS:
            break
    return variants


def _best_matching_entity(
    query: str, matches: Mapping[str, dict[str, Any]]
) -> dict[str, Any] | None:
    scored = sorted(
        ((external_result_score(query, metadata), metadata) for metadata in matches.values()),
        key=lambda entry: -entry[0],
    )
    if not scored or scored[0][0] < EXTERNAL_RELEVANCE_THRESHOLD:
        return None
    return scored[0][1]


def _priority_order(source_name: str, metadata: Mapping[str, Any]) -> list[str]:
    original = str(metadata.get("original_title") or "")
    spanish = str(metadata.get("spanish_title") or "")
    english = str(metadata.get("english_title") or "")
    if source_name == "filmaffinity":
        # Spanish-only site: its own market title is the best bet, ahead of
        # the work's original-language title.
        base = [spanish, original, english]
    elif source_name == "wikipedia":
        # Already covers en/es itself every call (see WikipediaAdapter.search);
        # what it's actually missing is a title outside those two editions.
        base = [original, spanish, english]
    else:
        base = [spanish, english, original]  # PREFERRED_ALIAS_LANGUAGES order
    alternatives = [str(value or "") for value in (metadata.get("alternative_titles") or [])]
    return [*base, *alternatives]


__all__ = [
    "MAX_ALIAS_VARIANTS",
    "PREFERRED_ALIAS_LANGUAGES",
    "VARIANT_RETRY_TIMEOUT_SECONDS",
    "alias_variants",
]
