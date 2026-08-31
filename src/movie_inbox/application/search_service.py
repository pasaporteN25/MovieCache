"""Catalog search and comparison ranking shared by HTTP clients."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from movie_inbox.domain.catalog import canonical_url, normalize_tags
from movie_inbox.domain.matching import decide_match
from movie_inbox.domain.metadata import normalize_local_files
from movie_inbox.domain.search import (
    SearchIntent,
    parse_search_query,
    search_key,
    text_match_score,
)
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE, SearchStrategy

SEARCH_RESULT_LIMIT = 60
_CATALOG_PREFILTER_MIN_ITEMS = 200
_CATALOG_PREFILTER_MAX_SHARE = 0.2

# Fields _search_values() also reports metadata/URL/file evidence under --
# a rescue for an ambiguous year-shaped token only makes sense against actual
# title text.
_TITLE_FIELDS = frozenset(
    {
        "title",
        "original_title",
        "spanish_title",
        "english_title",
        "wikipedia_title",
        "alternative_titles",
    }
)

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
    strategy: SearchStrategy = PRODUCTION_BASELINE,
) -> list[dict[str, Any]]:
    """Rank a personal catalog without applying the viewer's active filters."""
    intent = parse_search_query(query)
    if intent.director_query_key:
        return _search_by_director(items, intent, limit, strategy)
    if len(intent.title_key or intent.external_id or intent.key) < 2:
        return []
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for position in _catalog_search_positions(items, intent):
        item = items[position]
        score, matched_field, matched_value = _catalog_search_score(item, intent, strategy)
        if score < strategy.catalog_admission_threshold:
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


def _search_by_director(
    items: Sequence[Mapping[str, Any]],
    intent: SearchIntent,
    limit: int,
    strategy: SearchStrategy,
) -> list[dict[str, Any]]:
    """[Q4] tareas.md: explicit discovery by director, never blended into
    the title-scoring path above -- a separate function, not a branch inside
    _catalog_search_score/_search_values, so "nunca mezclarse con el score
    de titulo" holds structurally. Never read by decide_match, so it can
    never produce identity evidence or an automatic merge."""
    query_terms = tuple(intent.director_query_key.split())
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for item in items:
        directors = [str(value or "").strip() for value in (item.get("directors") or [])]
        best_score = 0.0
        best_value = ""
        for director in directors:
            if not director:
                continue
            score = text_match_score(search_key(director), intent.director_query_key, query_terms)
            if score > best_score:
                best_score, best_value = score, director
        if best_score < strategy.catalog_admission_threshold:
            continue
        payload = dict(item)
        payload["_search"] = {
            "score": round(best_score, 1),
            "matched_field": "director",
            "matched_value": best_value,
            "reason": "director_match",
        }
        ranked.append((best_score, str(item.get("id") or ""), payload))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in ranked[: max(1, limit)]]


def rank_catalog_candidates(
    items: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    limit: int = SEARCH_RESULT_LIMIT,
    strategy: SearchStrategy = PRODUCTION_BASELINE,
) -> list[dict[str, Any]]:
    """Rank local candidates using the same conservative merge evidence."""
    query = _candidate_query(candidate)
    broad_candidates = search_catalog_items(
        items, query, limit=max(limit * 3, limit), strategy=strategy
    )
    by_id = {str(row.get("id") or ""): row for row in broad_candidates}
    for item in items:
        match_decision = decide_match(item, candidate, strategy)
        if match_decision.score <= 0:
            continue
        item_id = str(item.get("id") or "")
        payload = by_id.setdefault(item_id, dict(item))
        payload["_match"] = match_decision.to_dict()

    ranked: list[tuple[int, float, float, str, dict[str, Any]]] = []
    for item_id, payload in by_id.items():
        raw_decision = payload.get("_match")
        if isinstance(raw_decision, Mapping):
            decision_payload = dict(raw_decision)
        else:
            decision_payload = decide_match(payload, candidate, strategy).to_dict()
            payload["_match"] = decision_payload
        raw_search = payload.get("_search")
        search_payload = raw_search if isinstance(raw_search, Mapping) else {}
        search_score = float(search_payload.get("score") or 0)
        match_score = float(decision_payload.get("score") or 0)
        if str(decision_payload.get("reason") or "") in _HARD_MISMATCH_REASONS:
            match_score = 0.0
        if search_score < strategy.catalog_admission_threshold and match_score <= 0:
            continue
        payload["_search"] = {
            **search_payload,
            "score": round(max(search_score, match_score * 100), 1),
            "reason": str(decision_payload.get("reason") or "insufficient_evidence"),
            "accepted": bool(decision_payload.get("accepted")),
            "evidence": decision_payload.get("evidence")
            if isinstance(decision_payload.get("evidence"), Mapping)
            else {},
        }
        ranked.append(
            (
                1 if decision_payload.get("accepted") else 0,
                match_score,
                search_score,
                item_id,
                payload,
            )
        )
    ranked.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3]))
    return [row[4] for row in ranked[: max(1, limit)]]


def group_external_results(results: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "wikipedia": [],
        "imdb": [],
        "filmaffinity": [],
    }
    for result in results:
        source = str(result.get("source") or "").casefold()
        if source in groups:
            groups[source].append(dict(result))
    return groups


def _catalog_search_positions(
    items: Sequence[Mapping[str, Any]], intent: SearchIntent
) -> range | list[int]:
    """Use a rare exact query token as a conservative large-catalog prefilter.

    Fuzzy scoring remains the authority for small catalogs and typo-only
    queries.  On a large catalog, an exact uncommon token (usually the title's
    distinctive word, number or external id) prevents thousands of generic
    partial matches from reaching ``SequenceMatcher``.
    """
    all_positions = range(len(items))
    if len(items) < _CATALOG_PREFILTER_MIN_ITEMS:
        return all_positions
    query = intent.title_key or search_key(intent.external_id) or intent.key
    query_terms = tuple(dict.fromkeys(query.split()))
    alternate_terms = (
        tuple(dict.fromkeys(intent.alternate_title_key.split()))
        if intent.alternate_title_key
        else ()
    )
    all_terms = tuple(dict.fromkeys((*query_terms, *alternate_terms)))
    if not all_terms:
        return all_positions

    positions_by_term: dict[str, list[int]] = {term: [] for term in all_terms}
    for position, item in enumerate(items):
        value_terms: set[str] = set()
        for field, value, _weight in _search_values(item):
            for normalized_value in _field_values(field, value):
                value_terms.update(normalized_value.split())
        for term in all_terms:
            if term in value_terms:
                positions_by_term[term].append(position)

    # Rarity is picked independently per interpretation, never by comparing a
    # primary term's rarity against an alternate term's: mixing the two into
    # one pool could let a rare alternate-only token (e.g. "1993" in "Verano
    # 1993") win the single-rarest-term selection and silently exclude every
    # primary-interpretation match that doesn't happen to share it.
    candidates = _rarest_term_positions(positions_by_term, query_terms)
    if alternate_terms:
        alternate_candidates = _rarest_term_positions(positions_by_term, alternate_terms)
        if alternate_candidates is not None:
            candidates = (
                alternate_candidates
                if candidates is None
                else sorted(set(candidates) | set(alternate_candidates))
            )
    if candidates is None:
        return all_positions
    maximum = max(SEARCH_RESULT_LIMIT * 3, round(len(items) * _CATALOG_PREFILTER_MAX_SHARE))
    return candidates if len(candidates) <= maximum else all_positions


def _rarest_term_positions(
    positions_by_term: Mapping[str, list[int]], terms: tuple[str, ...]
) -> list[int] | None:
    nonempty = [positions_by_term[term] for term in terms if positions_by_term[term]]
    return min(nonempty, key=len) if nonempty else None


def _catalog_search_score(
    item: Mapping[str, Any],
    intent: SearchIntent,
    strategy: SearchStrategy = PRODUCTION_BASELINE,
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
            best_score += strategy.year_match_bonus
        elif item_year:
            best_score -= strategy.year_mismatch_penalty
    best_score = max(0.0, min(best_score, 100.0))

    if intent.alternate_title_key:
        alt_score, alt_field, alt_value = _best_title_field_match(item, intent.alternate_title_key)
        if alt_score >= strategy.ambiguous_year_alternate_floor and alt_score > best_score:
            return min(alt_score, 100.0), alt_field, alt_value

    return best_score, best_field, best_value


def _best_title_field_match(
    item: Mapping[str, Any], alternate_title_key: str
) -> tuple[float, str, str]:
    """Score an ambiguous query's unsplit reading against title text only --
    never external_id/external_link/local_file, where a bare alternate title
    key like "verano 1993" has no meaning. Weighted the same way the primary
    per-field loop above is, so a merely-"contains"-tier match on a lower
    weighted field (alternative_titles, wikipedia_title) can't clear the
    strategy floor when the same raw match on the primary title field
    wouldn't have either."""
    best_score = 0.0
    best_field = ""
    best_value = ""
    query_terms = tuple(alternate_title_key.split())
    for field, value, weight in _search_values(item):
        if field not in _TITLE_FIELDS:
            continue
        normalized_value = search_key(value)
        if not normalized_value:
            continue
        score = text_match_score(normalized_value, alternate_title_key, query_terms) * weight
        if score > best_score:
            best_score, best_field, best_value = score, field, value
    return best_score, best_field, best_value


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
        ("external_id", item.get("mal_id"), 1.0),
        ("external_link", item.get("url"), 0.92),
        ("external_link", item.get("wikipedia_url"), 0.92),
        ("external_link", item.get("imdb_url"), 0.92),
        ("external_link", item.get("filmaffinity_url"), 0.92),
        ("external_link", item.get("myanimelist_url"), 0.92),
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
