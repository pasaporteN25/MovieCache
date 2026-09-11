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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from movie_inbox.domain.catalog import merge_lists
from movie_inbox.domain.search import (
    EXTERNAL_RELEVANCE_THRESHOLD,
    external_result_score,
    parse_search_query,
    search_key,
)
from movie_inbox.external.common import string_list
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


# Fields the alias carries onto the row it found. Titles only: nothing here
# decides identity, and nothing here comes from anywhere but the entity that
# already matched the query above EXTERNAL_RELEVANCE_THRESHOLD.
ALIAS_IDENTITY_FIELDS = ("original_title", "spanish_title", "english_title")


def needs_alias_retry(query: str | Any, results: Sequence[Mapping[str, Any]]) -> bool:
    """Whether a source's own answer is worth retrying under a confirmed alias.

    Not "did it answer" but "did it answer anything usable". A source that
    comes back with a page of rows none of which clears the relevance floor has
    told us as little as one that came back empty, and until now only the empty
    case triggered the retry: a FilmAffinity listing for "Der Untergang" scores
    17.4 on "El hundimiento", under the 28.0 floor, and the retry that would
    have recovered it never ran because the listing was not empty.

    IMDb's own bridge has fired on this condition since [Q3] (`imdb.py`,
    `is_empty or all(...)`). This is the same rule, for the two sources that
    only got half of it.
    """

    return not any(
        external_result_score(query, result) >= EXTERNAL_RELEVANCE_THRESHOLD
        for result in results
    )


@dataclass(frozen=True)
class AliasVariant:
    """A title to retry a search with, and the entity that vouched for it.

    The two travel together because a row found under a translated title
    otherwise arrives with no trace of what was actually being looked for.
    "Der Untergang" retried as "El hundimiento" finds the right film and then
    scores 13.9 against the query that found it -- below the relevance floor,
    so the retry buys nothing exactly when it was needed most. Carrying the
    alias across turns that into 100.
    """

    title: str
    identity: Mapping[str, Any] = field(default_factory=dict)


def alias_variants(source_name: str, query: str) -> list[AliasVariant]:
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
    variants: list[AliasVariant] = []
    for candidate in _priority_order(source_name, metadata):
        candidate = str(candidate or "").strip()
        key = search_key(candidate)
        if not candidate or not key or key in seen:
            continue
        seen.add(key)
        variants.append(AliasVariant(title=candidate, identity=metadata))
        if len(variants) >= MAX_ALIAS_VARIANTS:
            break
    return variants


def with_alias_identity(
    results: Sequence[Mapping[str, Any]], variant: AliasVariant
) -> list[dict[str, Any]]:
    """Carry the alias's confirmed titles onto the row it actually found.

    Only onto that row. A search for the alias title can come back with a
    whole page of films, and stamping a confirmed identity on all of them
    would be inventing one -- so a row is only annotated when its own title
    *is* the title we retried with. Every other row is returned untouched, to
    be scored on what it says about itself.

    Both sides are parsed the same way before comparing, because a year is
    written into the title on both: FilmAffinity appends it ("El hundimiento
    (2004)") and a title can simply contain one ("Estiu 1993"). Comparing a
    parsed key against a raw one silently never matches. When both sides do
    name a year they have to agree, so a series told apart only by its year
    cannot borrow its sibling's identity.

    Fields already filled by the source win: this fills gaps, it does not
    overwrite what the source stated. What it does not do is drop the alias's
    value for a field the source already claimed -- that goes to
    `alternative_titles`, where the scorer reads it too. FilmAffinity labels
    every title it returns as the Spanish one, so without that the confirmed
    Spanish title of a work whose FilmAffinity row is titled in Catalan or
    Basque would have nowhere to land, and the row the alias found would still
    be unreachable from the query that found it.
    """

    expected = parse_search_query(variant.title)
    annotated: list[dict[str, Any]] = []
    for result in results:
        row = dict(result)
        if _is_the_alias(str(row.get("title") or ""), expected):
            spare: list[str] = []
            for field_name in ALIAS_IDENTITY_FIELDS:
                confirmed = str(variant.identity.get(field_name) or "").strip()
                if not str(row.get(field_name) or "").strip():
                    row[field_name] = confirmed
                elif confirmed:
                    spare.append(confirmed)
            row["alternative_titles"] = merge_lists(
                string_list(row.get("alternative_titles")),
                [*string_list(variant.identity.get("alternative_titles")), *spare],
            )
        annotated.append(row)
    return annotated


def _is_the_alias(title: str, expected: Any) -> bool:
    found = parse_search_query(title)
    key = expected.title_key or search_key(expected.raw)
    if not key or (found.title_key or search_key(title)) != key:
        return False
    return not (expected.year and found.year) or expected.year == found.year


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
    "ALIAS_IDENTITY_FIELDS",
    "MAX_ALIAS_VARIANTS",
    "PREFERRED_ALIAS_LANGUAGES",
    "VARIANT_RETRY_TIMEOUT_SECONDS",
    "AliasVariant",
    "alias_variants",
    "needs_alias_retry",
    "with_alias_identity",
]
