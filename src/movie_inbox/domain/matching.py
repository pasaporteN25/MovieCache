#!/usr/bin/env python3
"""Conservative, auditable matching rules for catalog entries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, TypedDict

from movie_inbox.domain.catalog import (
    external_urls,
    themoviedb_media_reference,
    title_match_keys_for_item,
    title_similarity,
)
from movie_inbox.domain.metadata import normalize_external_positive_id
from movie_inbox.domain.normalization import normalize_kind
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE, SearchStrategy


@dataclass(frozen=True)
class MatchDecision:
    accepted: bool
    reason: str
    score: float
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RankedCandidate(TypedDict):
    score: float
    decision: dict[str, Any]
    result: dict[str, Any]


def decide_match(
    existing: Mapping[str, Any],
    incoming: Mapping[str, Any],
    strategy: SearchStrategy = PRODUCTION_BASELINE,
) -> MatchDecision:
    existing_tmdb_id = normalize_external_positive_id(existing.get("tmdb_id"))
    incoming_tmdb_id = normalize_external_positive_id(incoming.get("tmdb_id"))
    if existing_tmdb_id and incoming_tmdb_id:
        if existing_tmdb_id != incoming_tmdb_id:
            return MatchDecision(
                False,
                "tmdb_id_conflict",
                1.0,
                {
                    "existing_tmdb_id": existing_tmdb_id,
                    "incoming_tmdb_id": incoming_tmdb_id,
                },
            )
        existing_tmdb_type = _tmdb_media_type(existing)
        incoming_tmdb_type = _tmdb_media_type(incoming)
        if existing_tmdb_type and incoming_tmdb_type and existing_tmdb_type != incoming_tmdb_type:
            return MatchDecision(
                False,
                "tmdb_media_type_conflict",
                1.0,
                {
                    "tmdb_id": existing_tmdb_id,
                    "existing_media_type": existing_tmdb_type,
                    "incoming_media_type": incoming_tmdb_type,
                },
            )

    existing_mal_id = normalize_external_positive_id(existing.get("mal_id"))
    incoming_mal_id = normalize_external_positive_id(incoming.get("mal_id"))
    if existing_mal_id and incoming_mal_id and existing_mal_id != incoming_mal_id:
        return MatchDecision(
            False,
            "mal_id_conflict",
            1.0,
            {"existing_mal_id": existing_mal_id, "incoming_mal_id": incoming_mal_id},
        )

    if existing_tmdb_id and existing_tmdb_id == incoming_tmdb_id:
        return MatchDecision(
            True,
            "shared_tmdb_id",
            1.0,
            {"tmdb_id": existing_tmdb_id, "media_type": _tmdb_media_type(existing)},
        )

    shared_urls = sorted(external_urls(dict(existing)) & external_urls(dict(incoming)))
    if shared_urls:
        return MatchDecision(True, "shared_external_url", 1.0, {"urls": shared_urls})

    existing_wikidata = str(existing.get("wikidata_id") or "").strip().upper()
    incoming_wikidata = str(incoming.get("wikidata_id") or "").strip().upper()
    if existing_wikidata and existing_wikidata == incoming_wikidata:
        return MatchDecision(True, "shared_wikidata_id", 1.0, {"wikidata_id": existing_wikidata})

    if existing_mal_id and incoming_mal_id:
        return MatchDecision(True, "shared_mal_id", 1.0, {"mal_id": existing_mal_id})

    existing_titles = title_match_keys_for_item(dict(existing))
    incoming_titles = title_match_keys_for_item(dict(incoming))
    shared_titles = sorted(set(existing_titles) & set(incoming_titles))
    existing_year = str(existing.get("year") or "").strip()
    incoming_year = str(incoming.get("year") or "").strip()
    existing_kind = explicit_kind(existing)
    incoming_kind = explicit_kind(incoming)
    kinds_compatible = not (existing_kind and incoming_kind) or existing_kind == incoming_kind
    score = candidate_score(
        existing_titles, incoming_titles, existing_year, incoming_year, strategy
    )
    evidence = {
        "shared_titles": shared_titles,
        "existing_year": existing_year,
        "incoming_year": incoming_year,
        "existing_kind": existing_kind,
        "incoming_kind": incoming_kind,
    }

    if (
        shared_titles
        and existing_year
        and incoming_year
        and existing_year == incoming_year
        and kinds_compatible
    ):
        return MatchDecision(True, "exact_title_year", 1.0, evidence)
    if shared_titles and (not existing_year or not incoming_year):
        return MatchDecision(False, "exact_title_missing_year", score, evidence)
    if shared_titles and existing_year != incoming_year:
        return MatchDecision(False, "exact_title_year_mismatch", score, evidence)
    if (
        shared_titles
        and existing_year
        and incoming_year
        and existing_year == incoming_year
        and _anime_release_taxonomy_mismatch(existing_kind, incoming_kind)
    ):
        evidence["taxonomy_note"] = "anime_vs_release_format"
        return MatchDecision(False, "exact_title_year_anime_kind_review", score, evidence)
    if shared_titles and not kinds_compatible:
        return MatchDecision(False, "exact_title_kind_mismatch", score, evidence)
    if score >= strategy.similar_title_review_threshold:
        return MatchDecision(False, "similar_title_requires_review", score, evidence)
    return MatchDecision(False, "insufficient_evidence", score, evidence)


def rank_candidates(
    existing: Mapping[str, Any], results: Sequence[Mapping[str, Any]]
) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for result in results:
        if not external_urls(result):
            continue
        result_payload = dict(result)
        decision = decide_match(existing, result_payload)
        if decision.score <= 0:
            continue
        ranked.append(
            {
                "score": round(decision.score, 3),
                "decision": decision.to_dict(),
                "result": result_payload,
            }
        )
    return sorted(
        ranked, key=lambda entry: (entry["decision"]["accepted"], entry["score"]), reverse=True
    )


def find_strong_duplicate(
    items: Sequence[Mapping[str, Any]], candidate: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    for item in items:
        if decide_match(item, candidate).accepted:
            return item
    return None


def candidate_score(
    existing_titles: list[str],
    incoming_titles: list[str],
    existing_year: str,
    incoming_year: str,
    strategy: SearchStrategy = PRODUCTION_BASELINE,
) -> float:
    score = max(
        (title_similarity(left, right) for left in existing_titles for right in incoming_titles),
        default=0.0,
    )
    if existing_year and incoming_year:
        score += (
            strategy.match_year_bonus
            if existing_year == incoming_year
            else -strategy.match_year_mismatch_penalty
        )
    if set(existing_titles) & set(incoming_titles):
        score += strategy.match_shared_title_bonus
    return round(max(0.0, min(score, 1.0)), 3)


def explicit_kind(item: Mapping[str, Any]) -> str:
    raw = str(item.get("kind") or "").strip()
    return normalize_kind(raw) if raw else ""


def _anime_release_taxonomy_mismatch(left: str, right: str) -> bool:
    return {left, right} in ({"anime", "pelicula"}, {"anime", "serie"})


def _tmdb_media_type(item: Mapping[str, Any]) -> str:
    for field in ("tmdb_url", "url"):
        reference = themoviedb_media_reference(str(item.get(field) or ""))
        if reference is not None:
            return reference[0]
    kind = explicit_kind(item)
    if kind == "serie":
        return "tv"
    if kind in {"pelicula", "documental"}:
        return "movie"
    return ""
