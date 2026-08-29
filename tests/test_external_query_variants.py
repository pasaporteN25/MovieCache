from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_inbox.external.query_variants import MAX_ALIAS_VARIANTS, alias_variants

_METADATA = {
    "original_title": "Estiu 1993",
    "spanish_title": "Verano 1993",
    "english_title": "Summer 1993",
    "alternative_titles": ["A Different Alias"],
    "year": "2017",
}


class AliasVariantsTests(unittest.TestCase):
    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_returns_nothing_when_wikidata_finds_no_entity(self, title_matches) -> None:
        title_matches.return_value = {}

        self.assertEqual(alias_variants("wikipedia", "Some Unknown Title"), [])

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_returns_nothing_when_the_best_match_is_below_the_relevance_floor(
        self, title_matches
    ) -> None:
        # A decoy that shares almost no text with the query -- scores far
        # below EXTERNAL_RELEVANCE_THRESHOLD, so it must never seed a variant.
        title_matches.return_value = {"tt0000001": {"original_title": "Completely Unrelated"}}

        self.assertEqual(alias_variants("wikipedia", "Verano 1993"), [])

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_wikipedia_prioritizes_the_original_title(self, title_matches) -> None:
        # Wikipedia already covers en/es itself every call (WikipediaAdapter.
        # search) -- what it's missing is a title outside those two editions.
        title_matches.return_value = {"tt0000001": _METADATA}

        variants = alias_variants("wikipedia", "Estiu Nou")

        self.assertEqual(variants[0], "Estiu 1993")

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_filmaffinity_prioritizes_the_spanish_title(self, title_matches) -> None:
        # Spanish-only site: its own market title is the best bet.
        title_matches.return_value = {"tt0000001": _METADATA}

        variants = alias_variants("filmaffinity", "Estiu Nou")

        self.assertEqual(variants[0], "Verano 1993")

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_a_candidate_identical_to_the_query_is_never_offered_as_its_own_variant(
        self, title_matches
    ) -> None:
        title_matches.return_value = {"tt0000001": _METADATA}

        variants = alias_variants("filmaffinity", "verano 1993")

        self.assertNotIn("Verano 1993", variants)

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_variants_are_capped_at_the_documented_budget(self, title_matches) -> None:
        title_matches.return_value = {"tt0000001": _METADATA}

        variants = alias_variants("filmaffinity", "Estiu Nou")

        self.assertLessEqual(len(variants), MAX_ALIAS_VARIANTS)

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_alternative_titles_are_used_once_the_primary_fields_are_exhausted(
        self, title_matches
    ) -> None:
        title_matches.return_value = {
            "tt0000001": {
                "original_title": "Estiu 1993",
                "spanish_title": "Verano 1993",
                "alternative_titles": ["A Different Alias"],
            }
        }

        # Query matches original_title exactly, so it's excluded as
        # identical-to-query, and only two other candidates remain: the
        # source-priority title and, once that's used, the alternative pool.
        variants = alias_variants("wikipedia", "Estiu 1993")

        self.assertIn("A Different Alias", variants)

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_never_touches_director_or_cast_data(self, title_matches) -> None:
        # [Q3] safety rule: never blindly concatenate people into a query.
        # Satisfied by construction -- confirm no such field is even read.
        metadata = dict(_METADATA)
        metadata["directors"] = ["Someone Who Must Not Appear"]
        title_matches.return_value = {"tt0000001": metadata}

        variants = alias_variants("wikipedia", "Estiu Nou")

        self.assertTrue(all("Someone Who Must Not Appear" not in v for v in variants))


if __name__ == "__main__":
    unittest.main()
