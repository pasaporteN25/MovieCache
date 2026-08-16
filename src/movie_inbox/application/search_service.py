"""Catalog search and comparison ranking shared by HTTP clients."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from movie_inbox.domain.catalog import canonical_url, normalize_local_files, normalize_tags
from movie_inbox.domain.matching import decide_match
from movie_inbox.domain.search import (
    YEAR_MATCH_BONUS,
    YEAR_MISMATCH_PENALTY,
    SearchIntent,
    parse_search_query,
    search_key,
    text_match_score,
)

SEARCH_RESULT_LIMIT = 60

# decide_match still reports these with a nonzero, auditable score -- Scanner's
# manual "confirm" review relies on that score to keep a year/kind mismatch
# selectable for human review (see tests/test_libraries.py's "1917" legacy-year
# case). "Comparar" is a different context: a title match the algorithm already
# knows is contradicted by year or kind shouldn't rank alongside genuine
# candidates, so it doesn't count as match evidence here.
_HARD_MISMATCH_REASONS = frozenset({"exact_title_year_mismatch", "exact_title_kind_mismatch"})


def search_catalog_items(
    items: Sequence[Mapping[str, Any]],
    query: str,
    limit: int = SEARCH_RESULT_LIMIT,
) -> list[dict[str, Any]]:
    """Rank a personal catalog without applying the viewer's active filters."""
    intent = parse_search_query(query)
    if len(intent.title_key or intent.external_id or intent.key) < 2:
        return []
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for item in items:
        score, matched_field, matched_value = _catalog_search_score(item, intent)
        if score < 28:
            continue
        payload = dict(item)
        payload["_search"] = {
            "score": round(score, 1),
            "matched_field": matched_field,
            "matched_value": matched_value,
            "reason": _search_reason(score, matched_field),
        }
        ranked.append((score, str(item.get("id") or ""), payload))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in ranked[: max(1, limit)]]


def rank_catalog_candidates(
    items: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    limit: int = SEARCH_RESULT_LIMIT,
) -> list[dict[str, Any]]:
    """Rank local candidates using the same conservative merge evidence."""
    query = _candidate_query(candidate)
    broad_candidates = search_catalog_items(items, query, limit=max(limit * 3, limit))
    by_id = {str(row.get("id") or ""): row for row in broad_candidates}
    for item in items:
        decision = decide_match(item, candidate)
        if decision.score <= 0:
            continue
        item_id = str(item.get("id") or "")
        payload = by_id.setdefault(item_id, dict(item))
        payload["_match"] = decision.to_dict()

    ranked: list[tuple[int, float, float, str, dict[str, Any]]] = []
    for item_id, payload in by_id.items():
        decision = payload.get("_match")
        if not isinstance(decision, dict):
            decision = decide_match(payload, candidate).to_dict()
            payload["_match"] = decision
        search_score = float((payload.get("_search") or {}).get("score") or 0)
        match_score = float(decision.get("score") or 0)
        if str(decision.get("reason") or "") in _HARD_MISMATCH_REASONS:
            match_score = 0.0
        if search_score < 28 and match_score <= 0:
            continue
        payload["_search"] = {
            **(payload.get("_search") if isinstance(payload.get("_search"), dict) else {}),
            "score": round(max(search_score, match_score * 100), 1),
            "reason": str(decision.get("reason") or "insufficient_evidence"),
            "accepted": bool(decision.get("accepted")),
            "evidence": decision.get("evidence")
            if isinstance(decision.get("evidence"), dict)
            else {},
        }
        ranked.append(
            (
                1 if decision.get("accepted") else 0,
                match_score,
                search_score,
                item_id,
                payload,
            )
        )
    ranked.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))
    return [row[4] for row in ranked[: max(1, limit)]]


def group_external_results(results: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {"wikipedia": [], "imdb": [], "filmaffinity": []}
    for result in results:
        source = str(result.get("source") or "").casefold()
        if source in groups:
            groups[source].append(dict(result))
    return groups


def _catalog_search_score(
    item: Mapping[str, Any],
    intent: SearchIntent,
) -> tuple[float, str, str]:
    best_score = 0.0
    best_field = ""
    best_value = ""
    for field, value, weight in _search_values(item):
        queries = _field_queries(field, intent)
        values = _field_values(field, value)
        score = max(
            (
                text_match_score(normalized_value, query, tuple(query.split())) * weight
                for normalized_value in values
                for query in queries
                if normalized_value and query
            ),
            default=0.0,
        )
        if score > best_score:
            best_score, best_field, best_value = score, field, value

    item_year = str(item.get("year") or "").strip()
    if intent.year:
        if item_year == intent.year:
            best_score += YEAR_MATCH_BONUS
        elif item_year:
            best_score -= YEAR_MISMATCH_PENALTY
    return max(0.0, min(best_score, 100.0)), best_field, best_value


def _search_values(item: Mapping[str, Any]) -> list[tuple[str, str, float]]:
    local_values = [
        str(value or "").strip()
        for local_file in normalize_local_files(item.get("local_files"))
        for value in (
            local_file.get("name"),
            local_file.get("path"),
            local_file.get("relative_path"),
        )
        if str(value or "").strip()
    ]
    local_values.extend(
        str(item.get(field) or "").strip()
        for field in ("local_name", "local_path")
        if str(item.get(field) or "").strip()
    )
    fields = (
        ("title", item.get("title"), 1.0),
        ("original_title", item.get("original_title"), 1.0),
        ("spanish_title", item.get("spanish_title"), 1.0),
        ("english_title", item.get("english_title"), 1.0),
        ("wikipedia_title", item.get("wikipedia_title"), 0.98),
        ("alternative_titles", item.get("alternative_titles"), 0.96),
        ("local_file", local_values, 0.9),
        ("external_id", item.get("wikidata_id"), 1.0),
        ("external_id", item.get("tmdb_id"), 1.0),
        ("external_link", item.get("url"), 0.92),
        ("external_link", item.get("wikipedia_url"), 0.92),
        ("external_link", item.get("imdb_url"), 0.92),
        ("external_link", item.get("filmaffinity_url"), 0.92),
        # Secondary metadata (director/genre/writer/cast/tags/description/notes/review)
        # is deliberately excluded: docs/search-quality.md's "Catálogo" and
        # "Comparar/merge" contracts only permit title/alias/ID/file evidence here,
        # so this metadata can't masquerade as a title match. It stays visible on
        # the item detail view; it just isn't searchable from the main search box.
    )
    values: list[tuple[str, str, float]] = []
    seen: set[tuple[str, str]] = set()
    for field, raw_value, weight in fields:
        if isinstance(raw_value, (list, tuple, set)):
            rows = [str(value).strip() for value in raw_value]
        else:
            rows = [str(raw_value or "").strip()]
        for value in rows:
            key = (field, value.casefold())
            if value and key not in seen:
                seen.add(key)
                values.append((field, value, weight))
    return values


def _field_queries(field: str, intent: SearchIntent) -> list[str]:
    if field in {"external_id", "external_link"}:
        return list(
            dict.fromkeys(
                value
                for value in (
                    search_key(intent.external_id),
                    search_key(intent.canonical_url),
                    intent.key,
                )
                if value
            )
        )
    return [intent.title_key or intent.key]


def _field_values(field: str, value: str) -> list[str]:
    if field == "external_link":
        return list(dict.fromkeys([search_key(canonical_url(value)), search_key(value)]))
    return [search_key(value)]


def _candidate_query(candidate: Mapping[str, Any]) -> str:
    titles = [
        str(candidate.get(field) or "").strip()
        for field in ("title", "original_title", "spanish_title", "english_title")
    ]
    titles.extend(normalize_tags(candidate.get("alternative_titles")))
    title = next((value for value in titles if value), "")
    return " ".join(value for value in (title, str(candidate.get("year") or "").strip()) if value)


def _search_reason(score: float, field: str) -> str:
    if score >= 95:
        return f"exact_{field or 'text'}"
    if score >= 70:
        return f"strong_{field or 'text'}"
    return f"similar_{field or 'text'}"
