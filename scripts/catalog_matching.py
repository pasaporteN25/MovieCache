#!/usr/bin/env python3
"""Conservative, auditable matching rules for catalog entries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, TypedDict

from catalog_domain import (
    external_urls,
    normalize_kind,
    title_match_keys_for_item,
    title_similarity,
)


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


def decide_match(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> MatchDecision:
    shared_urls = sorted(external_urls(dict(existing)) & external_urls(dict(incoming)))
    if shared_urls:
        return MatchDecision(True, "shared_external_url", 1.0, {"urls": shared_urls})

    existing_wikidata = str(existing.get("wikidata_id") or "").strip().upper()
    incoming_wikidata = str(incoming.get("wikidata_id") or "").strip().upper()
    if existing_wikidata and existing_wikidata == incoming_wikidata:
        return MatchDecision(True, "shared_wikidata_id", 1.0, {"wikidata_id": existing_wikidata})

    existing_titles = title_match_keys_for_item(dict(existing))
    incoming_titles = title_match_keys_for_item(dict(incoming))
    shared_titles = sorted(set(existing_titles) & set(incoming_titles))
    existing_year = str(existing.get("year") or "").strip()
    incoming_year = str(incoming.get("year") or "").strip()
    existing_kind = explicit_kind(existing)
    incoming_kind = explicit_kind(incoming)
    kinds_compatible = not (existing_kind and incoming_kind) or existing_kind == incoming_kind
    score = candidate_score(existing_titles, incoming_titles, existing_year, incoming_year)
    evidence = {
        "shared_titles": shared_titles,
        "existing_year": existing_year,
        "incoming_year": incoming_year,
        "existing_kind": existing_kind,
        "incoming_kind": incoming_kind,
    }

    if shared_titles and existing_year and incoming_year and existing_year == incoming_year and kinds_compatible:
        return MatchDecision(True, "exact_title_year", 1.0, evidence)
    if shared_titles and (not existing_year or not incoming_year):
        return MatchDecision(False, "exact_title_missing_year", score, evidence)
    if shared_titles and existing_year != incoming_year:
        return MatchDecision(False, "exact_title_year_mismatch", score, evidence)
    if shared_titles and not kinds_compatible:
        return MatchDecision(False, "exact_title_kind_mismatch", score, evidence)
    if score >= 0.75:
        return MatchDecision(False, "similar_title_requires_review", score, evidence)
    return MatchDecision(False, "insufficient_evidence", score, evidence)


def rank_candidates(existing: Mapping[str, Any], results: list[dict[str, Any]]) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for result in results:
        if not external_urls(result):
            continue
        decision = decide_match(existing, result)
        if decision.score <= 0:
            continue
        ranked.append(
            {
                "score": round(decision.score, 3),
                "decision": decision.to_dict(),
                "result": result,
            }
        )
    return sorted(ranked, key=lambda entry: (entry["decision"]["accepted"], entry["score"]), reverse=True)


def find_strong_duplicate(items: list[Mapping[str, Any]], candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for item in items:
        if decide_match(item, candidate).accepted:
            return item
    return None


def candidate_score(
    existing_titles: list[str],
    incoming_titles: list[str],
    existing_year: str,
    incoming_year: str,
) -> float:
    score = max(
        (title_similarity(left, right) for left in existing_titles for right in incoming_titles),
        default=0.0,
    )
    if existing_year and incoming_year:
        score += 0.18 if existing_year == incoming_year else -0.35
    if set(existing_titles) & set(incoming_titles):
        score += 0.08
    return round(max(0.0, min(score, 1.0)), 3)


def explicit_kind(item: Mapping[str, Any]) -> str:
    raw = str(item.get("kind") or "").strip()
    return normalize_kind(raw) if raw else ""
