from __future__ import annotations

import unittest

from movie_inbox.domain.search import external_result_score, parse_search_query
from movie_inbox.domain.search_strategy import SearchStrategy


class ParseSearchQueryYearTests(unittest.TestCase):
    def test_a_trailing_year_disambiguates_a_numeric_title(self) -> None:
        intent = parse_search_query("1917 2019")
        self.assertEqual(intent.title, "1917")
        self.assertEqual(intent.title_key, "1917")
        self.assertEqual(intent.year, "2019")

    def test_a_lone_numeric_title_keeps_its_year_shaped_token(self) -> None:
        intent = parse_search_query("1984")
        self.assertEqual(intent.title, "1984")
        self.assertEqual(intent.title_key, "1984")
        self.assertEqual(intent.year, "")

    def test_a_leading_year_shaped_title_is_not_treated_as_a_release_year(self) -> None:
        intent = parse_search_query("2001: A Space Odyssey")
        self.assertEqual(intent.title_key, "2001 a space odyssey")
        self.assertEqual(intent.year, "")

    def test_a_normal_title_and_year_are_still_split(self) -> None:
        intent = parse_search_query("Heat 1995")
        self.assertEqual(intent.title, "Heat")
        self.assertEqual(intent.year, "1995")

    def test_a_year_inside_a_media_qualifier_is_still_captured(self) -> None:
        intent = parse_search_query("Movie Title (2019 film)")
        self.assertEqual(intent.title, "Movie Title")
        self.assertEqual(intent.year, "2019")

    def test_a_japanese_title_keeps_its_characters_and_release_year(self) -> None:
        intent = parse_search_query("君の名は。 2016")

        self.assertEqual(intent.title, "君の名は。")
        self.assertEqual(intent.title_key, "君の名は")
        self.assertEqual(intent.year, "2016")

    def test_an_unqualified_trailing_year_still_reads_as_a_release_year(self) -> None:
        # Known gap, found while scoping [Q2] (tareas.md): with only one
        # year-shaped token there is no local signal distinguishing "year
        # that's part of the title" from "year that's a disambiguating
        # suffix" -- contrast test_a_trailing_year_disambiguates_a_numeric_
        # title above, where stripping it is exactly the wanted behavior.
        # Characterizing today's behavior on purpose, not asserting it's
        # correct; see test_external_result_score_favors_an_unrelated_work_
        # over_the_real_target_below for the downstream consequence. Fixing
        # this needs a titles reference, out of scope for [Q2] and not
        # claimed by [Q3]-[Q6] either -- tracked as its own backlog item.
        intent = parse_search_query("Verano 1993")

        self.assertEqual(intent.title, "Verano")
        self.assertEqual(intent.year, "1993")

    def test_a_parenthesized_year_disambiguates_a_year_shaped_title_token(self) -> None:
        intent = parse_search_query("Verano 1993 (2017)")

        self.assertIn("1993", intent.title)
        self.assertEqual(intent.year, "2017")


class ExternalResultScoreStrategyTests(unittest.TestCase):
    def test_a_lighter_year_mismatch_penalty_keeps_a_wrong_year_result_above_the_floor(
        self,
    ) -> None:
        result = {"title": "Heat", "year": "1986"}

        baseline = external_result_score("Heat 1995", result)
        lenient = external_result_score(
            "Heat 1995", result, SearchStrategy(year_mismatch_penalty=1.0)
        )

        self.assertLess(baseline, lenient)
        self.assertLess(baseline, 28.0)
        self.assertGreaterEqual(lenient, 28.0)

    def test_external_result_score_favors_an_unrelated_work_over_the_real_target_below(
        self,
    ) -> None:
        # Direct consequence of the parse gap above: "Verano 1993" the query
        # reads as title "Verano" + year "1993", so an unrelated work
        # actually titled "Verano" (1993) outscores the real target -- whose
        # only shared text is the alias "Verano 1993" -- because the real
        # target's true year (2017) reads as a mismatch. Characterization,
        # not an assertion that this is acceptable.
        unrelated_decoy = {"title": "Verano", "year": "1993"}
        real_target_with_alias = {
            "title": "Estiu 1993",
            "spanish_title": "Verano 1993",
            "year": "2017",
        }

        decoy_score = external_result_score("Verano 1993", unrelated_decoy)
        real_target_score = external_result_score("Verano 1993", real_target_with_alias)

        self.assertGreater(decoy_score, real_target_score)


if __name__ == "__main__":
    unittest.main()
