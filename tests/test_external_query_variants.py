from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_inbox.external.query_variants import (
    MAX_ALIAS_VARIANTS,
    AliasVariant,
    alias_variants,
    needs_alias_retry,
    with_alias_identity,
)

_METADATA = {
    "original_title": "Estiu 1993",
    "spanish_title": "Verano 1993",
    "english_title": "Summer 1993",
    "alternative_titles": ["A Different Alias"],
    "year": "2017",
}


def _titles(variants: list[AliasVariant]) -> list[str]:
    return [variant.title for variant in variants]


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

        self.assertEqual(variants[0].title, "Estiu 1993")

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_filmaffinity_prioritizes_the_spanish_title(self, title_matches) -> None:
        # Spanish-only site: its own market title is the best bet.
        title_matches.return_value = {"tt0000001": _METADATA}

        variants = alias_variants("filmaffinity", "Estiu Nou")

        self.assertEqual(variants[0].title, "Verano 1993")

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_a_candidate_identical_to_the_query_is_never_offered_as_its_own_variant(
        self, title_matches
    ) -> None:
        title_matches.return_value = {"tt0000001": _METADATA}

        variants = alias_variants("filmaffinity", "verano 1993")

        self.assertNotIn("Verano 1993", _titles(variants))

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

        self.assertIn("A Different Alias", _titles(variants))

    @patch("movie_inbox.external.query_variants.fetch_wikidata_title_matches")
    def test_never_touches_director_or_cast_data(self, title_matches) -> None:
        # [Q3] safety rule: never blindly concatenate people into a query.
        # Satisfied by construction -- confirm no such field is even read.
        metadata = dict(_METADATA)
        metadata["directors"] = ["Someone Who Must Not Appear"]
        title_matches.return_value = {"tt0000001": metadata}

        variants = alias_variants("wikipedia", "Estiu Nou")

        self.assertTrue(all("Someone Who Must Not Appear" not in v for v in _titles(variants)))


class AliasIdentityTests(unittest.TestCase):
    """A row found under a translated title has to arrive carrying the alias.

    Measured before the fix, with the query the retry started from: "Der
    Untergang" retried as "El hundimiento" scored 13.9, "Kimi no na wa" as
    "Your Name." 21.5, "Sen to Chihiro no kamikakushi" as "El viaje de
    Chihiro" 25.5 -- all under the 28.0 relevance floor. The retry found the
    film and the floor threw it away, so [Q3] bought nothing for exactly the
    queries it was built for. Only cognates got through.
    """

    VARIANT = AliasVariant(title="El hundimiento", identity=dict(_METADATA))

    def _row(self, title: str, **fields: object) -> dict[str, object]:
        return {"source": "filmaffinity", "title": title, "url": f"u/{title}", **fields}

    def test_the_row_the_alias_found_is_annotated(self) -> None:
        [row] = with_alias_identity([self._row("El hundimiento")], self.VARIANT)

        self.assertEqual(row["original_title"], "Estiu 1993")
        self.assertEqual(row["spanish_title"], "Verano 1993")
        self.assertEqual(row["english_title"], "Summer 1993")

    def test_a_year_suffix_does_not_stop_it(self) -> None:
        # FilmAffinity puts the year in the title text itself.
        [row] = with_alias_identity([self._row("El hundimiento (2004)")], self.VARIANT)

        self.assertEqual(row["original_title"], "Estiu 1993")

    def test_a_sibling_told_apart_only_by_its_year_cannot_borrow_it(self) -> None:
        # "Estiu 1993" parses to the title "estiu" plus the year 1993, so
        # comparing titles alone would let "Estiu 1994" answer for it.
        variant = AliasVariant(title="Estiu 1993", identity=dict(_METADATA))

        rows = with_alias_identity([self._row("Estiu 1994"), self._row("Estiu 1993")], variant)

        self.assertEqual(rows[0].get("original_title"), None)
        self.assertEqual(rows[1]["original_title"], "Estiu 1993")

    def test_every_other_row_on_the_page_is_left_alone(self) -> None:
        # A search for the alias title can return a whole page. Stamping a
        # confirmed identity on all of it would be inventing one.
        rows = with_alias_identity(
            [self._row("El hundimiento"), self._row("Otra pelicula")], self.VARIANT
        )

        self.assertEqual(rows[1].get("original_title"), None)

    def test_what_the_source_already_said_is_not_overwritten(self) -> None:
        [row] = with_alias_identity(
            [self._row("El hundimiento", spanish_title="Lo que dijo la fuente")], self.VARIANT
        )

        self.assertEqual(row["spanish_title"], "Lo que dijo la fuente")
        self.assertEqual(row["original_title"], "Estiu 1993")

    def test_alternative_titles_are_merged_not_replaced(self) -> None:
        [row] = with_alias_identity(
            [self._row("El hundimiento", alternative_titles=["Propio"])], self.VARIANT
        )

        self.assertEqual(row["alternative_titles"], ["Propio", "A Different Alias"])

    def test_a_title_the_source_already_claimed_is_kept_as_an_alternative(self) -> None:
        # FilmAffinity labels every title it returns as the Spanish one, so a
        # film whose FilmAffinity row is titled in Catalan blocks the confirmed
        # Spanish title from its own field. Dropping it there would leave the
        # row unreachable from the query that found it, so it lands where the
        # scorer still reads it.
        [row] = with_alias_identity(
            [self._row("El hundimiento", spanish_title="El hundimiento")], self.VARIANT
        )

        self.assertEqual(row["spanish_title"], "El hundimiento")
        self.assertIn("Verano 1993", row["alternative_titles"])

    def test_the_annotated_row_clears_the_relevance_floor(self) -> None:
        # The point of the whole thing, stated as the number it moves.
        from movie_inbox.domain.search import EXTERNAL_RELEVANCE_THRESHOLD, external_result_score

        variant = AliasVariant(title="El hundimiento", identity={"original_title": "Der Untergang"})
        plain = self._row("El hundimiento (2004)")
        [annotated] = with_alias_identity([plain], variant)

        self.assertLess(external_result_score("Der Untergang", plain), EXTERNAL_RELEVANCE_THRESHOLD)
        self.assertGreaterEqual(
            external_result_score("Der Untergang", annotated), EXTERNAL_RELEVANCE_THRESHOLD
        )


class RetryConditionTests(unittest.TestCase):
    """[B1]: "did it answer" is not the same question as "did it answer usefully".

    Only an empty response triggered the retry, so a FilmAffinity listing for
    "Der Untergang" -- five rows, best one 17.4 against a floor of 28.0 -- never
    got one, even though searching its Spanish title finds the film at 100.
    IMDb's own bridge has fired on this condition since [Q3]; this is the same
    rule for the two sources that only got half of it.
    """

    def _row(self, title: str) -> dict[str, object]:
        return {"source": "filmaffinity", "title": title, "url": "u"}

    def test_an_empty_answer_still_triggers_a_retry(self) -> None:
        self.assertTrue(needs_alias_retry("Der Untergang", []))

    def test_rows_that_all_miss_the_floor_trigger_one_too(self) -> None:
        listing = [self._row("El hundimiento"), self._row("El hundimiento del Titanic")]

        self.assertTrue(needs_alias_retry("Der Untergang", listing))

    def test_one_row_over_the_floor_is_enough_to_stop_it(self) -> None:
        # The bar is one usable answer, not a good average: a source that found
        # the work must not be asked again just because it also returned noise.
        listing = [self._row("Der Untergang"), self._row("El hundimiento del Titanic")]

        self.assertFalse(needs_alias_retry("Der Untergang", listing))


if __name__ == "__main__":
    unittest.main()
