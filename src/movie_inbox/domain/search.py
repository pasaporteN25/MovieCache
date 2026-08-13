"""Search-query parsing and relevance scoring shared across catalog sources."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Mapping
from urllib.parse import unquote, urlparse

from movie_inbox.domain.catalog import canonical_url, external_source_name


_YEAR_PATTERN = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b")
_MEDIA_QUALIFIER_PATTERN = re.compile(
    r"\s*\((?:\d{4}\s+)?(?:film|movie|pelicula|tv series|series|miniseries|anime|documentary)[^)]*\)\s*$",
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


def parse_search_query(value: Any) -> SearchIntent:
    raw = " ".join(str(value or "").strip().split())
    source = external_source_name(raw)
    canonical = canonical_url(raw) if source else ""
    title = _title_from_url(raw, source) if source else raw
    year_match = _YEAR_PATTERN.search(title or raw)
    year = year_match.group(1) if year_match else ""
    title = _MEDIA_QUALIFIER_PATTERN.sub(" ", title)
    title = _YEAR_PATTERN.sub(" ", title)
    title = " ".join(title.replace("_", " ").split()).strip(" -")
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
    )


def search_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def text_match_score(value: str, query: str, query_terms: tuple[str, ...] | list[str]) -> float:
    if not value or not query:
        return 0.0
    if value == query:
        return 100.0
    if value.startswith(query):
        return 88.0
    if query in value:
        return 82.0
    value_terms = value.split()
    covered = sum(1 for term in query_terms if _term_matches(term, value_terms))
    coverage = covered / max(1, len(query_terms))
    if coverage == 1:
        return 70.0 + (12.0 * min(1.0, len(query) / max(1, len(value))))
    ratio = SequenceMatcher(None, query, value).ratio()
    return max(coverage * 62.0, ratio * 58.0)


def external_result_score(query: str | SearchIntent, result: Mapping[str, Any]) -> float:
    intent = query if isinstance(query, SearchIntent) else parse_search_query(query)
    result_url = canonical_url(str(result.get("url") or ""))
    if intent.canonical_url and result_url == intent.canonical_url:
        return 140.0

    title_query = intent.title_key or search_key(intent.external_id) or intent.key
    title_terms = tuple(title_query.split())
    titles = [
        result.get("title"),
        result.get("original_title"),
        result.get("spanish_title"),
        result.get("english_title"),
        result.get("wikipedia_title"),
        *(result.get("alternative_titles") if isinstance(result.get("alternative_titles"), list) else []),
    ]
    score = max(
        (text_match_score(search_key(value), title_query, title_terms) for value in titles if str(value or "").strip()),
        default=0.0,
    )
    result_year = str(result.get("year") or "").strip()
    if intent.year:
        if result_year == intent.year:
            score += 12
        elif result_year:
            score -= 18
    return max(0.0, score)


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
        term in value
        or value in term
        or (len(term) >= 5 and SequenceMatcher(None, term, value).ratio() >= 0.82)
        for value in values
    )
