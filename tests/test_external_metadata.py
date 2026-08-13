from __future__ import annotations

import unittest
from urllib.error import URLError
from unittest.mock import patch

from movie_inbox.external.imdb import ImdbAdapter
from movie_inbox.external.metadata import fetch_metadata_by_title
from movie_inbox.external.wikipedia import WikipediaAdapter
from movie_inbox.external.wikidata import wikidata_kind


class ExternalMetadataTests(unittest.TestCase):
    @patch("movie_inbox.external.metadata.fetch_wikipedia_by_title")
    @patch("movie_inbox.external.metadata.fetch_wikipedia_by_wikidata_title")
    def test_title_lookup_prefers_richer_wikidata_metadata(self, wikidata_lookup, wikipedia_lookup) -> None:
        wikidata_lookup.return_value = {
            "title": "La Belle Personne",
            "year": "2008",
            "wikidata_id": "Q3209193",
            "wikipedia_url": "https://fr.wikipedia.org/wiki/La_Belle_Personne",
            "alternative_titles": ["The Beautiful Person", "La bella persona"],
        }
        wikipedia_lookup.return_value = {
            "title": "La Belle Personne",
            "year": "2008",
            "wikipedia_url": "https://en.wikipedia.org/wiki/La_Belle_Personne",
        }

        metadata = fetch_metadata_by_title("The Beautiful Person", "2008")

        self.assertEqual(metadata["wikidata_id"], "Q3209193")
        self.assertEqual(metadata["alternative_titles"], ["The Beautiful Person", "La bella persona"])

    @patch("movie_inbox.external.imdb.fetch_json")
    def test_imdb_results_propagate_series_kind(self, fetch_json) -> None:
        fetch_json.return_value = {
            "d": [
                {"id": "tt0361245", "l": "Tantei Monogatari", "qid": "tvSeries", "y": 1979},
                {"id": "tt0091064", "l": "The Fly", "qid": "movie", "y": 1986},
            ]
        }

        results = ImdbAdapter().search("Tantei Monogatari")

        self.assertEqual(results[0]["kind"], "serie")
        self.assertEqual(results[1]["kind"], "pelicula")

    @patch("movie_inbox.external.wikipedia.fetch_json")
    def test_wikipedia_keeps_english_result_when_spanish_lookup_fails(self, fetch_json) -> None:
        def response(url: str) -> dict[str, object]:
            if "es.wikipedia.org" in url:
                raise URLError("temporary Spanish endpoint failure")
            return {
                "query": {
                    "pages": [
                        {
                            "title": "Evil Dead Burn",
                            "canonicalurl": "https://en.wikipedia.org/wiki/Evil_Dead_Burn",
                            "extract": "Evil Dead Burn is a 2026 supernatural horror film.",
                            "pageprops": {"wikibase_item": "Q134093975"},
                        }
                    ]
                }
            }

        fetch_json.side_effect = response

        results = WikipediaAdapter().search("Evil Dead Burn")

        self.assertEqual(results[0]["title"], "Evil Dead Burn")
        self.assertEqual(results[0]["year"], "2026")
        self.assertEqual(results[0]["url"], "https://en.wikipedia.org/wiki/Evil_Dead_Burn")

    @patch("movie_inbox.external.wikipedia.fetch_json")
    def test_wikipedia_search_keeps_alternatives_when_the_exact_film_is_present(self, fetch_json) -> None:
        fetch_json.return_value = {
            "query": {
                "pages": [
                    {
                        "title": "Titanic (1997 film)",
                        "extract": "Titanic is a 1997 American epic romance and disaster film.",
                        "pageprops": {"wikibase_item": "Q44578"},
                    },
                    {
                        "title": "Titanic (1953 film)",
                        "extract": "Titanic is a 1953 American drama film.",
                        "pageprops": {"wikibase_item": "Q151895"},
                    },
                ]
            }
        }

        results = WikipediaAdapter()._search_language("Titanic", "en")

        self.assertEqual(results[0]["title"], "Titanic (1997 film)")
        self.assertEqual(len(results), 2)
        self.assertEqual(fetch_json.call_count, 1)

    @patch("movie_inbox.external.wikipedia.fetch_json")
    def test_wikipedia_uses_direct_title_when_search_has_no_matching_work(self, fetch_json) -> None:
        fetch_json.side_effect = [
            {"query": {"pages": [{"title": "Unrelated", "extract": "Unrelated is a 2026 film."}]}},
            {
                "query": {
                    "pages": [
                        {
                            "title": "Evil Dead Burn",
                            "canonicalurl": "https://en.wikipedia.org/wiki/Evil_Dead_Burn",
                            "extract": "Evil Dead Burn is a 2026 supernatural horror film.",
                        }
                    ]
                }
            },
        ]

        results = WikipediaAdapter()._search_language("Evil Dead Burn", "en")

        self.assertEqual(results[0]["title"], "Evil Dead Burn")
        self.assertEqual(fetch_json.call_count, 2)

    @patch("movie_inbox.external.wikipedia.fetch_wikipedia_metadata")
    def test_wikipedia_url_is_resolved_directly(self, fetch_metadata) -> None:
        fetch_metadata.return_value = {
            "title": "Evil Dead Burn",
            "wikipedia_title": "Evil Dead Burn",
            "year": "2026",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Evil_Dead_Burn",
        }

        results = WikipediaAdapter().search("https://en.wikipedia.org/wiki/Evil_Dead_Burn")

        self.assertEqual(results[0]["title"], "Evil Dead Burn")
        fetch_metadata.assert_called_once()

    @patch("movie_inbox.external.imdb.fetch_json")
    def test_imdb_url_search_uses_the_title_identifier(self, fetch_json) -> None:
        fetch_json.return_value = {"d": []}

        ImdbAdapter().search("https://www.imdb.com/title/tt0091064/")

        self.assertIn("/tt0091064.json", fetch_json.call_args.args[0])

    def test_wikidata_instance_type_detects_series(self) -> None:
        claims = {
            "P31": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"id": "Q5398426"},
                        }
                    }
                }
            ]
        }

        self.assertEqual(wikidata_kind(claims), "serie")


if __name__ == "__main__":
    unittest.main()
