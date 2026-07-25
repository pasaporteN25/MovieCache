from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_inbox.external.imdb import ImdbAdapter
from movie_inbox.external.metadata import fetch_metadata_by_title
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
