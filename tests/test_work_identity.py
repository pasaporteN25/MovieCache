"""[X12] One identity rule for catalogue entries.

The case that started it: two "Kingdom of Heaven" entries, one linked to the
English Wikipedia article and one to the Spanish one, never flagged by curation
-- it compared the two URLs as strings, and the Wikidata id both articles share
was not part of the question.
"""

from __future__ import annotations

import unittest
from typing import Any

from movie_inbox.application.curation_service import build_curation_payload
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.matching import decide_match
from movie_inbox.domain.titles import strip_wikipedia_disambiguator
from movie_inbox.domain.work_identity import (
    annotate_duplicate_items,
    catalog_membership,
    compare_works,
    wikipedia_article,
)


def _item(**fields: Any) -> dict[str, Any]:
    return normalize_item({"kind": "pelicula", **fields}).to_dict()


KINGDOM_EN = {
    "id": "kingdom-en",
    "title": "Kingdom of Heaven (film)",
    "wikipedia_url": "https://en.wikipedia.org/wiki/Kingdom_of_Heaven_(film)",
}
KINGDOM_ES = {
    "id": "kingdom-es",
    "title": "Kingdom of Heaven",
    "wikipedia_url": "https://es.wikipedia.org/wiki/El_reino_de_los_cielos",
}


class CrossLanguageWikipediaTests(unittest.TestCase):
    def test_two_languages_of_the_same_article_are_the_same_work_through_wikidata(self) -> None:
        verdict = compare_works(
            _item(**KINGDOM_EN, wikidata_id="Q1123433"),
            _item(**KINGDOM_ES, wikidata_id="q1123433"),
        )

        self.assertEqual(verdict.level, "same")
        self.assertEqual(verdict.reason, "shared_wikidata_id")
        self.assertIn("inglés", verdict.evidence[0])
        self.assertIn("español", verdict.evidence[0])

    def test_without_wikidata_the_title_alone_does_not_decide(self) -> None:
        # Same title once "(film)" is set aside, but no year and nothing else:
        # exactly the Frankenstein problem, so no verdict either way.
        verdict = compare_works(_item(**KINGDOM_EN), _item(**KINGDOM_ES))

        self.assertEqual(verdict.level, "none")
        self.assertEqual(verdict.reason, "exact_title_missing_year")

    def test_curation_groups_them_and_says_it_is_certain(self) -> None:
        items = [
            {**_item(**KINGDOM_EN, wikidata_id="Q1123433"), "_source_file": "a.json"},
            {**_item(**KINGDOM_ES, wikidata_id="Q1123433"), "_source_file": "a.json"},
        ]

        payload = build_curation_payload(items)

        duplicates = [case for case in payload["cases"] if case["type"] == "duplicate"]
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["level"], "same")
        self.assertEqual(duplicates[0]["reason"], "Misma obra")
        self.assertTrue(any("Wikidata" in row for row in duplicates[0]["evidence"]))

    def test_a_catalogue_holding_one_language_already_has_the_other(self) -> None:
        membership = catalog_membership(
            _item(**KINGDOM_ES, wikidata_id="Q1123433"),
            [_item(**KINGDOM_EN, wikidata_id="Q1123433")],
        )

        self.assertEqual(membership["state"], "present")
        self.assertEqual(membership["item_id"], "kingdom-en")


class RemakeTests(unittest.TestCase):
    """Frankenstein was filmed many times: a shared title is not a shared work."""

    def test_different_wikidata_ids_are_a_conflict_and_never_reach_curation(self) -> None:
        left = _item(id="f-1931", title="Frankenstein", wikidata_id="Q150204")
        right = _item(id="f-1994", title="Frankenstein", wikidata_id="Q1129478")
        items = [left, right]

        self.assertEqual(compare_works(left, right).level, "conflict")
        annotate_duplicate_items(items)
        self.assertNotIn("_duplicate_count", items[0])

    def test_same_title_without_year_and_nothing_else_is_not_flagged(self) -> None:
        items = [_item(id="a", title="Frankenstein"), _item(id="b", title="Frankenstein")]

        annotate_duplicate_items(items)

        self.assertNotIn("_duplicate_count", items[0])

    def test_same_title_without_year_and_the_same_director_is_possible(self) -> None:
        left = _item(id="a", title="Frankenstein", directors=["James Whale"])
        right = _item(id="b", title="Frankenstein", year="1931", directors=["james whale"])
        items = [left, right]

        verdict = compare_works(left, right)
        annotate_duplicate_items(items)

        self.assertEqual(verdict.level, "possible")
        self.assertIn("Coinciden en la dirección.", verdict.evidence)
        self.assertEqual(items[0]["_duplicate_level"], "possible")
        # A possible match is something to look at, never an automatic one.
        self.assertFalse(decide_match(left, right).accepted)

    def test_same_title_with_two_different_years_is_left_alone(self) -> None:
        items = [
            _item(id="a", title="Frankenstein", year="1931"),
            _item(id="b", title="Frankenstein", year="1994"),
        ]

        annotate_duplicate_items(items)

        self.assertNotIn("_duplicate_count", items[0])


class StrongIdTests(unittest.TestCase):
    def test_imdb_links_in_different_languages_carry_the_same_id(self) -> None:
        verdict = compare_works(
            _item(id="a", title="Heat", imdb_url="https://www.imdb.com/es-es/title/tt0113277/"),
            _item(id="b", title="Fuego contra fuego", imdb_url="https://imdb.com/title/tt0113277"),
        )

        self.assertEqual((verdict.level, verdict.reason), ("same", "shared_imdb_id"))

    def test_filmaffinity_links_in_different_regions_carry_the_same_id(self) -> None:
        verdict = compare_works(
            _item(
                id="a",
                title="Heat",
                filmaffinity_url="https://www.filmaffinity.com/es/film267267.html",
            ),
            _item(
                id="b",
                title="Heat",
                filmaffinity_url="https://www.filmaffinity.com/us/film267267.html",
            ),
        )

        self.assertEqual((verdict.level, verdict.reason), ("same", "shared_filmaffinity_id"))

    def test_mobile_and_encoded_wikipedia_links_are_the_same_article(self) -> None:
        self.assertEqual(
            wikipedia_article("https://es.m.wikipedia.org/wiki/El_reino_de_los_cielos"),
            wikipedia_article("https://es.wikipedia.org/wiki/El%20reino%20de%20los%20cielos"),
        )

    def test_one_shared_id_and_one_contradicting_id_need_a_person(self) -> None:
        left = _item(id="a", title="Heat", wikidata_id="Q175171", tmdb_id="949")
        right = _item(id="b", title="Heat", wikidata_id="Q175171", tmdb_id="950")

        verdict = compare_works(left, right)
        decision = decide_match(left, right)

        self.assertEqual((verdict.level, verdict.reason), ("possible", "conflicting_external_ids"))
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "tmdb_id_conflict")


class DisambiguatorTests(unittest.TestCase):
    def test_the_article_tail_is_dropped_and_real_parentheses_are_kept(self) -> None:
        cases = {
            "Kingdom of Heaven (film)": "Kingdom of Heaven",
            "Heat (1995 film)": "Heat",
            "Frankenstein (película de 1931)": "Frankenstein",
            "Fargo (serie de televisión)": "Fargo",
            "Akira (anime)": "Akira",
            "(500) Days of Summer": "(500) Days of Summer",
            "Tora! Tora! Tora!": "Tora! Tora! Tora!",
            "Love (Gaspar Noé)": "Love (Gaspar Noé)",
        }
        for article, expected in cases.items():
            with self.subTest(article=article):
                self.assertEqual(strip_wikipedia_disambiguator(article), expected)


if __name__ == "__main__":
    unittest.main()
