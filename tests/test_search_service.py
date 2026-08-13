from __future__ import annotations

import unittest

from movie_inbox.application.search_service import rank_catalog_candidates, search_catalog_items


class CatalogSearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.items = [
            {
                "id": "beautiful-person",
                "title": "The Beautiful Person",
                "original_title": "La Belle Personne",
                "spanish_title": "La bella persona",
                "english_title": "The Beautiful Person",
                "alternative_titles": ["A Bela Junie"],
                "year": "2008",
                "kind": "pelicula",
                "imdb_url": "https://www.imdb.com/title/tt1263778/",
            },
            {
                "id": "heat-1995",
                "title": "Heat",
                "year": "1995",
                "kind": "pelicula",
            },
        ]

    def test_searches_original_spanish_and_external_identifier(self) -> None:
        for query in ("la belle personne", "la bella persona", "tt1263778"):
            with self.subTest(query=query):
                results = search_catalog_items(self.items, query)
                self.assertEqual(results[0]["id"], "beautiful-person")

    def test_search_is_diacritic_insensitive(self) -> None:
        item = {"id": "one", "title": "Amélie", "year": "2001"}
        self.assertEqual(search_catalog_items([item], "amelie")[0]["id"], "one")

    def test_title_and_year_are_scored_as_separate_search_evidence(self) -> None:
        item = {"id": "evil-dead-burn", "title": "Evil Dead Burn", "year": "2026"}

        result = search_catalog_items([item], "Evil Dead Burn 2026")[0]

        self.assertEqual(result["id"], "evil-dead-burn")
        self.assertEqual(result["_search"]["reason"], "exact_title")

    def test_wikipedia_url_can_find_an_unlinked_local_title(self) -> None:
        item = {"id": "evil-dead-burn", "title": "Evil Dead Burn", "year": "2026"}

        results = search_catalog_items([item], "https://en.wikipedia.org/wiki/Evil_Dead_Burn")

        self.assertEqual(results[0]["id"], "evil-dead-burn")

    def test_exact_title_and_year_is_ranked_as_an_accepted_candidate(self) -> None:
        results = rank_catalog_candidates(
            self.items,
            {"title": "Heat", "year": "1995", "kind": "pelicula"},
        )
        self.assertEqual(results[0]["id"], "heat-1995")
        self.assertTrue(results[0]["_search"]["accepted"])
        self.assertEqual(results[0]["_search"]["reason"], "exact_title_year")

    def test_title_without_year_remains_review_only(self) -> None:
        results = rank_catalog_candidates(
            self.items,
            {"title": "Heat", "year": "", "kind": "pelicula"},
        )
        self.assertFalse(results[0]["_search"]["accepted"])
        self.assertEqual(results[0]["_search"]["reason"], "exact_title_missing_year")


if __name__ == "__main__":
    unittest.main()
