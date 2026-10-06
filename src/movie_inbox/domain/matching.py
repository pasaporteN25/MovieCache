#!/usr/bin/env python3
"""Conservative, auditable matching rules for catalog entries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, TypedDict

from movie_inbox.domain.catalog import external_urls, title_similarity
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE, SearchStrategy
from movie_inbox.domain.work_identity import (
    anime_release_taxonomy_mismatch,
    compare_profiles,
    explicit_kind,
    tmdb_media_type,
    work_profile,
)

__all__ = [
    "MatchDecision",
    "RankedCandidate",
    "candidate_score",
    "decide_match",
    "explicit_kind",
    "find_strong_duplicate",
    "rank_candidates",
]


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
    """Whether `incoming` may be taken as `existing` without asking anyone.

    The identity question is answered by `work_identity` ([X12]); only a
    ``same`` verdict is accepted. What this adds is the ranking score for
    everything that is not accepted, which the search ranks results by.
    """

    existing_profile = work_profile(existing)
    incoming_profile = work_profile(incoming)
    verdict = compare_profiles(existing_profile, incoming_profile)
    if verdict.level == "conflict":
        return MatchDecision(False, verdict.reason, 1.0, dict(verdict.details))
    if verdict.reason == "conflicting_external_ids":
        # A conflict overrides whatever the two otherwise share, and is
        # reported as the conflict it is.
        details = dict(verdict.details)
        return MatchDecision(False, str(details.pop("conflict_reason")), 1.0, details)
    if verdict.level == "same" and verdict.reason != "exact_title_year":
        return MatchDecision(True, verdict.reason, 1.0, dict(verdict.details))

    existing_titles = sorted(existing_profile.titles)
    incoming_titles = sorted(incoming_profile.titles)
    score = candidate_score(
        existing_titles,
        incoming_titles,
        existing_profile.year,
        incoming_profile.year,
        strategy,
    )
    evidence = dict(verdict.details)
    if verdict.level == "same":
        return MatchDecision(True, verdict.reason, 1.0, evidence)
    if verdict.reason == "exact_title_missing_year_corroborated":
        # Corroboration proposes a review; for automatic matching a missing
        # year is still a missing year.
        return MatchDecision(False, "exact_title_missing_year", score, evidence)
    if verdict.reason != "insufficient_evidence":
        return MatchDecision(False, verdict.reason, score, evidence)
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


# Kept importable from here: libraries and the scanner reach for them by this
# path, and they now live with the rest of the identity rules.
_tmdb_media_type = tmdb_media_type
_anime_release_taxonomy_mismatch = anime_release_taxonomy_mismatch
