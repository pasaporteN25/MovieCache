from __future__ import annotations

import unittest

from movie_inbox.domain.search import external_result_score, parse_search_query
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE, SearchStrategy


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
        # Nothing was actually ambiguous here (the numeric-title exception
        # applied, no split happened) -- no alternate reading to offer.
        self.assertEqual(intent.alternate_title_key, "")

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
        # [Q7] (tareas.md): with only one year-shaped token there is no local
        # signal distinguishing "year that's part of the title" from "year
        # that's a disambiguating suffix" -- contrast
        # test_a_trailing_year_disambiguates_a_numeric_title above, where
        # stripping it is exactly the wanted behavior. The primary reading
        # stays the year-stripped one (unchanged, still the right default for
        # "Heat 1995"-shaped queries), but parse_search_query now also
        # offers the unsplit reading as alternate_title/alternate_title_key,
        # so scoring functions can consider both instead of committing to a
        # guess with no signal to base it on -- see
        # test_a_verbatim_alias_match_rescues_a_result_the_year_split_would_
        # otherwise_discard for the downstream fix this enables.
        intent = parse_search_query("Verano 1993")

        self.assertEqual(intent.title, "Verano")
        self.assertEqual(intent.year, "1993")
        self.assertEqual(intent.alternate_title, "Verano 1993")
        self.assertEqual(intent.alternate_title_key, "verano 1993")

    def test_a_parenthesized_year_disambiguates_a_year_shaped_title_token(self) -> None:
        intent = parse_search_query("Verano 1993 (2017)")

        self.assertEqual(intent.title, "Verano 1993")
        self.assertEqual(intent.year, "2017")
        # Two year-shaped tokens: the last one is unambiguously the
        # disambiguator, so there's nothing for an alternate reading to add.
        self.assertEqual(intent.alternate_title_key, "")


class ExternalResultScoreStrategyTests(unittest.TestCase):
    def test_an_external_id_match_is_admitted_without_title_text(self) -> None:
        result = {
            "title": "Adiós, tío Tom",
            "imdb_url": "https://www.imdb.com/title/tt0180396/",
        }

        self.assertEqual(external_result_score("tt0180396", result), 140.0)

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

    def test_a_verbatim_alias_match_rescues_a_result_the_year_split_would_otherwise_discard(
        self,
    ) -> None:
        # [Q7] fix: "Verano 1993" the query reads as title "Verano" + year
        # "1993" (see ParseSearchQueryYearTests above), so under the primary
        # reading alone, a real target whose only shared text is the alias
        # "Verano 1993" scores just 13.0 -- silently discarded, well below
        # external_relevance_threshold (28.0), because its true year (2017)
        # reads as a mismatch. The fix isn't "make the real target always
        # outrank a same-titled decoy" -- with no signal to tell the two
        # apart, an unrelated work actually titled "Verano" (1993) legitimately
        # scores just as high (112.0, an exact title+year match) and nothing
        # here should suppress that. The bar is that the real target stops
        # being invisible: once its alias match is verbatim enough to trust
        # (SearchStrategy.ambiguous_year_alternate_floor), it clears the
        # acceptance threshold too, so a human comparing results sees both
        # legitimate candidates instead of only the decoy.
        unrelated_decoy = {"title": "Verano", "year": "1993"}
        real_target_with_alias = {
            "title": "Estiu 1993",
            "spanish_title": "Verano 1993",
            "year": "2017",
        }

        decoy_score = external_result_score("Verano 1993", unrelated_decoy)
        real_target_score = external_result_score("Verano 1993", real_target_with_alias)

        self.assertEqual(decoy_score, 112.0)
        self.assertGreaterEqual(real_target_score, PRODUCTION_BASELINE.external_relevance_threshold)


class DirectorQueryTests(unittest.TestCase):
    """[Q4] tareas.md: "director:X" is explicit discovery, parsed as its
    own kind of query rather than an empty title query."""

    def test_a_director_query_is_recognized_and_consumes_the_whole_value(self) -> None:
        intent = parse_search_query("director:Jacopetti")

        self.assertEqual(intent.director_query, "Jacopetti")
        self.assertEqual(intent.director_query_key, "jacopetti")
        self.assertEqual(intent.title, "")
        self.assertEqual(intent.title_key, "")
        self.assertEqual(intent.year, "")

    def test_the_prefix_is_case_insensitive_and_trims_surrounding_space(self) -> None:
        intent = parse_search_query("DIRECTOR:  Jacopetti  ")

        self.assertEqual(intent.director_query, "Jacopetti")

    def test_a_normal_query_never_populates_the_director_fields(self) -> None:
        intent = parse_search_query("Heat 1995")

        self.assertEqual(intent.director_query, "")
        self.assertEqual(intent.director_query_key, "")

    def test_external_result_score_trusts_the_source_for_any_named_candidate(self) -> None:
        # A surname has nothing sensible to compare against title text --
        # any candidate carrying a recognizable title is accepted at a
        # score that clears the admission threshold everywhere it's used
        # (registry.py's _rank_batch, imdb.py's own bridge gate).
        named_result = {"title": "Mondo Cane"}

        score = external_result_score("director:Jacopetti", named_result)

        self.assertGreaterEqual(score, PRODUCTION_BASELINE.external_relevance_threshold)

    def test_external_result_score_rejects_a_result_with_no_title_at_all(self) -> None:
        self.assertEqual(external_result_score("director:Jacopetti", {}), 0.0)

    def test_a_bare_title_query_never_scores_as_a_director_match(self) -> None:
        # The old title/year-based scoring path is untouched for anything
        # that isn't a director query -- confirms the branch is additive.
        score = external_result_score("Heat 1995", {"title": "Heat", "year": "1986"})

        self.assertLess(score, PRODUCTION_BASELINE.external_relevance_threshold)


if __name__ == "__main__":
    unittest.main()
