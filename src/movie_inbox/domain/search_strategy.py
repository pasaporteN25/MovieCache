"""Named, swappable thresholds for search ranking and identity matching.

Every field here replaces a number that used to be hardcoded in one of four
places: domain/search.py, domain/matching.py, application/search_service.py
and application/library_service.py (the Scanner's real classification
logic). PRODUCTION_BASELINE holds today's exact values, so passing it
explicitly -- or omitting the parameter, since it is every scoring
function's default -- reproduces current behavior exactly. A different
SearchStrategy instance is how Search Lab compares a ranking candidate
against the baseline without touching any ranking logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchStrategy:
    name: str = "production-baseline"

    # domain/search.py: external_result_score() and search_service.py's
    # _catalog_search_score().
    year_match_bonus: float = 12.0
    year_mismatch_penalty: float = 75.0
    external_relevance_threshold: float = 28.0

    # application/search_service.py: search_catalog_items()'s and
    # rank_catalog_candidates()'s admission floor. Kept independent from
    # external_relevance_threshold even though both start at 28.0, so the
    # two contexts can be tuned separately.
    catalog_admission_threshold: float = 28.0

    # domain/matching.py: decide_match()'s "needs human review" floor and
    # candidate_score()'s bonuses/penalty.
    similar_title_review_threshold: float = 0.75
    match_year_bonus: float = 0.18
    match_year_mismatch_penalty: float = 0.35
    match_shared_title_bonus: float = 0.08

    # application/search_evaluation.py's _scanner_results() and
    # application/library_service.py's ManagedLibraryService._classification()
    # (the Scanner's real production classification, not a test mirror) both
    # hardcode this floor today, independently of each other.
    scanner_review_floor: float = 0.72


PRODUCTION_BASELINE = SearchStrategy()
