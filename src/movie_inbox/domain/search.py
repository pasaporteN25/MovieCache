"""Search-query parsing and relevance scoring shared across catalog sources."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import unquote, urlparse

from movie_inbox.domain.catalog import FUNCTION_WORDS, canonical_url, external_source_name
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
_DIRECTOR_QUERY_PATTERN = re.compile(r"^director:\s*(.+)$", flags=re.IGNORECASE)


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
    # [Q4] tareas.md: "director:Jacopetti" is explicit discovery, not a title
    # query that happens to be empty. Populated only by the early-return
    # branch in parse_search_query() below; every other field stays at its
    # normal empty/"" default for a director query (no title, no year).
    director_query: str = ""
    director_query_key: str = ""


def parse_search_query(value: Any) -> SearchIntent:
    raw = " ".join(str(value or "").strip().split())
    director_match = _DIRECTOR_QUERY_PATTERN.match(raw)
    if director_match:
        director_query = director_match.group(1).strip()
        director_query_key = search_key(director_query)
        return SearchIntent(
            raw=raw,
            key=director_query_key,
            title="",
            title_key="",
            terms=tuple(director_query_key.split()),
            year="",
            source="",
            external_id="",
            canonical_url="",
            director_query=director_query,
            director_query_key=director_query_key,
        )
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
        # Anchored at the start of a word, for the same reason _term_matches is:
        # what this rule is for is finding a word inside a phrase -- "Fly" in
        # "The Fly", an external id inside a URL -- not a fragment inside a
        # word. Unanchored it scored "Man" 82 against "Spiderman" and "Age" 82
        # against "Carnage", and searching the catalogue for "Fly" put "M.
        # Butterfly" above both films actually called "The Fly".
        #
        # Typing the beginning of a word is still a match: the prefix test above
        # covers "Moon" finding "Moonlight", and " fly" covers "Fly" finding
        # "The Flying Dutchman". What is gone is arriving at the middle of a
        # word from nowhere.
        if f" {query}" in value:
            return 82.0
    value_terms = value.split()
    covered_terms = [term for term in query_terms if _term_matches(term, value_terms)]
    coverage = len(covered_terms) / max(1, len(query_terms))
    if coverage == 1:
        return 70.0 + (12.0 * min(1.0, len(query) / max(1, len(value))))
    if covered_terms and all(term in FUNCTION_WORDS for term in covered_terms):
        # The only words these two titles have in common are articles, which is
        # not evidence of anything. Scored on what is left instead, so a near
        # miss still surfaces and an unrelated film does not.
        return _content_word_score(query, value)
    if len(query) < _MIN_FUZZY_QUERY_LENGTH:
        return coverage * 62.0
    # Nothing whole matched, so all that is left is character similarity -- but
    # over the words that carry meaning, not over the raw strings. Comparing
    # the raw strings scored "The Fly" against "M. Butterfly" at 32.2, above
    # the 29.0 it gave "The Flies", on the strength of letters shared between
    # "the" and "butterfly".
    return max(coverage * 62.0, _content_word_score(query, value))


def _content_word_score(query: str, value: str) -> float:
    """Character similarity with the articles taken out of both sides.

    Two branches reach it and for the same reason: what is left of a title once
    the articles are gone is what the person was actually looking for. It is
    the answer when articles were the only words in common, and the fallback
    when no whole word matched at all.

    A title that is nothing but an article is a real thing -- Bunuel's "El" --
    so when either side has no content left, the original comparison stands
    rather than being replaced by an invented one.
    """

    query_content = " ".join(term for term in query.split() if term not in FUNCTION_WORDS)
    value_content = " ".join(term for term in value.split() if term not in FUNCTION_WORDS)
    if not query_content or not value_content:
        return SequenceMatcher(None, query, value).ratio() * 58.0
    return SequenceMatcher(None, query_content, value_content).ratio() * 58.0


def external_result_score(
    query: str | SearchIntent,
    result: Mapping[str, Any],
    strategy: SearchStrategy = PRODUCTION_BASELINE,
) -> float:
    intent = query if isinstance(query, SearchIntent) else parse_search_query(query)
    if intent.director_query_key:
        # [Q4]: director search is explicit discovery, not title identity --
        # a surname has nothing sensible to compare against title text, so
        # trust the source's own relevance ranking (why it returned this
        # candidate at all) instead of re-scoring locally. 0.0 only filters
        # genuinely empty/garbage rows, never "less relevant" ones -- that
        # call already belongs to the source. Never identity evidence:
        # domain/matching.py doesn't read this field at all.
        has_title = any(
            str(result.get(field) or "").strip()
            for field in ("title", "original_title", "spanish_title", "english_title")
        )
        return 100.0 if has_title else 0.0
    result_url = canonical_url(str(result.get("url") or ""))
    if intent.canonical_url and result_url == intent.canonical_url:
        return 140.0
    if intent.external_id and any(
        intent.external_id in str(result.get(field) or "").casefold()
        for field in ("url", "imdb_url", "wikidata_id", "tmdb_id", "mal_id")
    ):
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
    split_title = re.sub(r"\(\s*\)", " ", split_title)
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
    """Whether one query term is present among a title's terms.

    The equality test is not redundant with the substring tests below it: those
    are gated on three characters, so without it a two-letter term never
    matched even an identical one. "Ed" found nothing at all in a catalogue
    holding "Ed Wood", and "Up" could not see "Up in the Air".

    Equality does not count for an article, though. Term coverage of 1 takes a
    fast path well above the admission floor, so letting "la" match "la" would
    make a two-letter query pull in every title that merely starts with it --
    the same noise `title_similarity` was just cleared of, arriving by another
    door.

    The substring tests are anchored at the start of a word. A short word
    buried inside a longer one is a coincidence of spelling, not a shared word:
    "Fly" is not "Butterfly", which the golden corpus now states outright --
    without the anchor, searching the catalogue for "The Fly" ranked "M.
    Butterfly" (32.2) above "The Flies" (29.0). The anchored form keeps what
    the test was for, which is compounds and plurals reaching their root, and
    terms of five characters or more still have the fuzzy test underneath, so
    "terminator" still finds "exterminator".
    """

    return any(
        (term == value and term not in FUNCTION_WORDS)
        or (len(term) >= _MIN_SUBSTRING_LENGTH and value.startswith(term))
        or (len(value) >= _MIN_SUBSTRING_LENGTH and term.startswith(value))
        or (len(term) >= 5 and SequenceMatcher(None, term, value).ratio() >= 0.82)
        for value in values
    )
