"""Search-query parsing and relevance scoring shared across catalog sources."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import unquote, urlparse

from movie_inbox.domain.catalog import canonical_url, external_source_name
from movie_inbox.domain.normalization import normalize_search_text
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE, SearchStrategy

_MIN_SUBSTRING_LENGTH = 3
_MIN_FUZZY_QUERY_LENGTH = 5
# external/registry.py's live external search still filters on this directly
# (it never receives a SearchStrategy) -- kept as a module constant, derived
# from the same baseline external_result_score() defaults to, so there is one
# source of truth instead of two numbers that could quietly drift apart.
EXTERNAL_RELEVANCE_THRESHOLD = PRODUCTION_BASELINE.external_relevance_threshold
_YEAR_PATTERN = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b")
_MEDIA_QUALIFIER_PATTERN = re.compile(
    r"\s*\((?:\d{4}\s+)?(?:film|movie|pelicula|tv series|series|miniseries|anime|documentary)"
    r"[^)]*\)\s*$",
    flags=re.IGNORECASE,
)
_EXTERNAL_ID_PATTERN = re.compile(r"\b(?:tt\d{7,9}|q\d+|film\d+)\b", flags=re.IGNORECASE)


@dataclass(frozen=True)
class SearchIntent:
    raw: str
    key: str
    title: str
    title_key: str
    terms: tuple[str, ...]
    year: str
    source: str
    external_id: str
    canonical_url: str
    # Populated only when a single unqualified year-shaped token made the
    # title/year split ambiguous ("Verano 1993": disambiguating suffix, or
    # part of the title? see _split_disambiguating_year). Holds the reading
    # that keeps the year merged into the title, for scoring functions that
    # want to consider both without guessing which one is "the" title.
    alternate_title: str = ""
    alternate_title_key: str = ""


def parse_search_query(value: Any) -> SearchIntent:
    raw = " ".join(str(value or "").strip().split())
    source = external_source_name(raw)
    canonical = canonical_url(raw) if source else ""
    title = _title_from_url(raw, source) if source else raw
    title = title.replace("_", " ")
    qualifier_match = _MEDIA_QUALIFIER_PATTERN.search(title)
    qualifier_year = _YEAR_PATTERN.search(qualifier_match.group(0)) if qualifier_match else None
    title = _MEDIA_QUALIFIER_PATTERN.sub(" ", title)
    pre_split_title = title
    year, title, year_is_ambiguous = _split_disambiguating_year(title)
    if qualifier_year is not None:
        year = qualifier_year.group(1)
        year_is_ambiguous = False
    title = " ".join(title.split()).strip(" -")
    alternate_title = ""
    alternate_title_key = ""
    if year_is_ambiguous:
        alternate_title = " ".join(pre_split_title.split()).strip(" -")
        alternate_title_key = search_key(alternate_title)
    key = search_key(canonical or raw)
    title_key = search_key(title)
    external_id_match = _EXTERNAL_ID_PATTERN.search(raw)
    external_id = external_id_match.group(0).lower() if external_id_match else ""
    effective_key = title_key or search_key(external_id) or key
    return SearchIntent(
        raw=raw,
        key=key,
        title=title,
        title_key=title_key,
        terms=tuple(effective_key.split()),
        year=year,
        source=source,
        external_id=external_id,
        canonical_url=canonical,
        alternate_title=alternate_title,
        alternate_title_key=alternate_title_key,
    )


def search_key(value: Any) -> str:
    return normalize_search_text(value)


def text_match_score(value: str, query: str, query_terms: tuple[str, ...] | list[str]) -> float:
    if not value or not query:
        return 0.0
    if value == query:
        return 100.0
    if len(query) >= _MIN_SUBSTRING_LENGTH:
        if value.startswith(query):
            return 88.0
        if query in value:
            return 82.0
    value_terms = value.split()
    covered = sum(1 for term in query_terms if _term_matches(term, value_terms))
    coverage = covered / max(1, len(query_terms))
    if coverage == 1:
        return 70.0 + (12.0 * min(1.0, len(query) / max(1, len(value))))
    if len(query) < _MIN_FUZZY_QUERY_LENGTH:
        return coverage * 62.0
    ratio = SequenceMatcher(None, query, value).ratio()
    return max(coverage * 62.0, ratio * 58.0)


def external_result_score(
    query: str | SearchIntent,
    result: Mapping[str, Any],
    strategy: SearchStrategy = PRODUCTION_BASELINE,
) -> float:
    intent = query if isinstance(query, SearchIntent) else parse_search_query(query)
    result_url = canonical_url(str(result.get("url") or ""))
    if intent.canonical_url and result_url == intent.canonical_url:
        return 140.0

    title_query = intent.title_key or search_key(intent.external_id) or intent.key
    score = _score_title_and_year(title_query, intent.year, result, strategy)
    if intent.alternate_title_key:
        alternate_score = _score_title_and_year(intent.alternate_title_key, "", result, strategy)
        if alternate_score >= strategy.ambiguous_year_alternate_floor:
            score = max(score, alternate_score)
    return score


def _score_title_and_year(
    title_query: str,
    year: str,
    result: Mapping[str, Any],
    strategy: SearchStrategy,
) -> float:
    title_terms = tuple(title_query.split())
    alternative_titles = result.get("alternative_titles")
    extra_titles = alternative_titles if isinstance(alternative_titles, list) else []
    titles = [
        result.get("title"),
        result.get("original_title"),
        result.get("spanish_title"),
        result.get("english_title"),
        result.get("wikipedia_title"),
        *extra_titles,
    ]
    score = max(
        (
            text_match_score(search_key(value), title_query, title_terms)
            for value in titles
            if str(value or "").strip()
        ),
        default=0.0,
    )
    result_year = str(result.get("year") or "").strip()
    if year:
        if result_year == year:
            score += strategy.year_match_bonus
        elif result_year:
            score -= strategy.year_mismatch_penalty
    return max(0.0, score)


def _split_disambiguating_year(title: str) -> tuple[str, str, bool]:
    """Split a trailing release-year token from a title, unless it's the only
    meaningful content: a numeric title like "1917", "1984", or "2001: A Space
    Odyssey" keeps its year-shaped token instead of losing it as if it were a
    disambiguating suffix (mirrors the leading-token exception in
    movie_inbox.domain.catalog.title_match_key).

    The third element flags a genuinely ambiguous split: exactly one
    year-shaped token, with real title text before it. With two or more year
    tokens the last one is unambiguously the disambiguator (e.g. "Verano 1993
    (2017)"); with none, or with the numeric-title exception above, there is
    nothing to be ambiguous about."""
    matches = list(_YEAR_PATTERN.finditer(title))
    if not matches:
        return "", title, False
    candidate = matches[-1]
    if not any(character.isalnum() for character in title[: candidate.start()]):
        return "", title, False
    year = candidate.group(1)
    split_title = title[: candidate.start()] + title[candidate.end() :]
    return year, split_title, len(matches) == 1


def _title_from_url(value: str, source: str) -> str:
    if source != "wikipedia":
        return ""
    try:
        path = urlparse(value).path
    except ValueError:
        return ""
    if "/wiki/" not in path:
        return ""
    slug = path.split("/wiki/", 1)[1].split("/", 1)[0]
    return unquote(slug).replace("_", " ")


def _term_matches(term: str, values: list[str]) -> bool:
    return any(
        (len(term) >= _MIN_SUBSTRING_LENGTH and term in value)
        or (len(value) >= _MIN_SUBSTRING_LENGTH and value in term)
        or (len(term) >= 5 and SequenceMatcher(None, term, value).ratio() >= 0.82)
        for value in values
    )
