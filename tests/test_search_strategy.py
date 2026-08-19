from __future__ import annotations

import unittest

from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE, SearchStrategy


class SearchStrategyTests(unittest.TestCase):
    def test_production_baseline_matches_todays_real_thresholds(self) -> None:
        # One field per number this task promoted out of domain/search.py,
        # domain/matching.py, application/search_service.py and
        # application/library_service.py. If one of these changes, it must be
        # a deliberate tuning decision, not an accidental drift of the
        # baseline away from what those modules used to hardcode.
        self.assertEqual(PRODUCTION_BASELINE.name, "production-baseline")
        self.assertEqual(PRODUCTION_BASELINE.year_match_bonus, 12.0)
        self.assertEqual(PRODUCTION_BASELINE.year_mismatch_penalty, 75.0)
        self.assertEqual(PRODUCTION_BASELINE.external_relevance_threshold, 28.0)
        self.assertEqual(PRODUCTION_BASELINE.catalog_admission_threshold, 28.0)
        self.assertEqual(PRODUCTION_BASELINE.similar_title_review_threshold, 0.75)
        self.assertEqual(PRODUCTION_BASELINE.match_year_bonus, 0.18)
        self.assertEqual(PRODUCTION_BASELINE.match_year_mismatch_penalty, 0.35)
        self.assertEqual(PRODUCTION_BASELINE.match_shared_title_bonus, 0.08)
        self.assertEqual(PRODUCTION_BASELINE.scanner_review_floor, 0.72)

    def test_strategy_is_frozen(self) -> None:
        with self.assertRaises(AttributeError):
            PRODUCTION_BASELINE.year_match_bonus = 1.0  # type: ignore[misc]

    def test_a_candidate_strategy_can_override_a_subset_of_fields(self) -> None:
        candidate = SearchStrategy(name="strict-external", external_relevance_threshold=40.0)

        self.assertEqual(candidate.external_relevance_threshold, 40.0)
        # Every other field still falls back to the dataclass defaults, which
        # mirror PRODUCTION_BASELINE.
        self.assertEqual(candidate.year_match_bonus, PRODUCTION_BASELINE.year_match_bonus)


if __name__ == "__main__":
    unittest.main()
