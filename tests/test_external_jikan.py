from __future__ import annotations

import unittest
from unittest.mock import patch

from movie_inbox.external.jikan import (
    JikanAdapter,
    fetch_jikan_metadata,
    jikan_anime_id,
    jikan_anime_result,
)
from movie_inbox.web.catalog_api import item_from_search_result


def _anime_payload() -> dict[str, object]:
    return {
        "mal_id": 32281,
        "url": "https://myanimelist.net/anime/32281/Kimi_no_Na_wa",
        "title": "Kimi no Na wa.",
        "title_english": "Your Name.",
        "title_japanese": "君の名は。",
        "title_synonyms": ["Your Name", "Kimi no Namae wa"],
        "titles": [
            {"type": "Default", "title": "Kimi no Na wa."},
            {"type": "Japanese", "title": "君の名は。"},
            {"type": "English", "title": "Your Name."},
            {"type": "Synonym", "title": "Your Name"},
        ],
        "year": 2016,
        "aired": {
            "from": "2016-08-26T00:00:00+00:00",
            "prop": {"from": {"day": 26, "month": 8, "year": 2016}},
        },
        "synopsis": "Two teenagers share a profound, magical connection.",
        "images": {
            "jpg": {
                "image_url": "https://cdn.example/poster.jpg",
                "large_image_url": "https://cdn.example/poster-large.jpg",
            }
        },
        "genres": [{"mal_id": 10, "name": "Fantasy"}],
        "producers": [{"mal_id": 53, "name": "CoMix Wave Films"}],
        # Public/community values intentionally must not enter personal fields.
        "score": 8.83,
        "rank": 27,
        "duration": "1 hr 46 min",
        "episodes": 1,
    }


class JikanAdapterTests(unittest.TestCase):
    @patch("movie_inbox.external.jikan.fetch_json")
    def test_search_maps_titles_identity_and_metadata_without_personal_rating(
        self, fetch_json
    ) -> None:
        fetch_json.return_value = {"data": [_anime_payload()]}

        results = JikanAdapter().search("君の名は 2016")

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["source"], "jikan")
        self.assertEqual(result["kind"], "anime")
        self.assertEqual(result["mal_id"], "32281")
        self.assertEqual(result["url"], "https://myanimelist.net/anime/32281")
        self.assertEqual(result["myanimelist_url"], result["url"])
        self.assertEqual(result["original_title"], "君の名は。")
        self.assertEqual(result["english_title"], "Your Name.")
        self.assertEqual(result["spanish_title"], "")
        self.assertEqual(result["alternative_titles"], ["Your Name", "Kimi no Namae wa"])
        self.assertEqual(result["genres"], ["Fantasy"])
        self.assertEqual(result["producers"], ["CoMix Wave Films"])
        self.assertEqual(result["page_image"], "https://cdn.example/poster-large.jpg")
        self.assertNotIn("rating", result)
        self.assertNotIn("duration_minutes", result)
        self.assertNotIn("score", result)
        requested_url = fetch_json.call_args.args[0]
        self.assertIn("/anime?", requested_url)
        self.assertIn("limit=8", requested_url)
        self.assertNotIn("2016", requested_url)

    @patch("movie_inbox.external.jikan.fetch_json")
    def test_director_discovery_never_becomes_an_anime_title_query(self, fetch_json) -> None:
        self.assertEqual(JikanAdapter().search("director:Makoto Shinkai"), [])
        fetch_json.assert_not_called()

    def test_untrusted_rows_require_a_positive_mal_id_and_title(self) -> None:
        self.assertIsNone(jikan_anime_result(None))
        self.assertIsNone(jikan_anime_result({"mal_id": 0, "title": "Invalid"}))
        self.assertIsNone(jikan_anime_result({"mal_id": 1, "title": ""}))

    def test_year_falls_back_to_the_aired_structure(self) -> None:
        payload = _anime_payload()
        payload["year"] = None
        payload["aired"] = {
            "from": "2016-08-26T00:00:00+00:00",
            "prop": {"from": {"day": 26, "month": 8, "year": 2016}},
        }

        result = jikan_anime_result(payload)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["year"], "2016")
        self.assertEqual(
            result["release_dates"],
            [
                {
                    "date": "2016-08-26",
                    "precision": "day",
                    "country": "",
                    "release_type": "",
                    "source": "jikan",
                    "source_url": "https://myanimelist.net/anime/32281",
                    "is_primary": True,
                }
            ],
        )

    def test_mal_id_is_only_read_from_a_canonical_myanimelist_anime_url(self) -> None:
        self.assertEqual(
            jikan_anime_id("https://myanimelist.net/anime/32281/Kimi_no_Na_wa"), "32281"
        )
        self.assertEqual(jikan_anime_id("https://myanimelist.net/manga/32281/example"), "")
        self.assertEqual(jikan_anime_id("https://example.com/anime/32281"), "")

    @patch("movie_inbox.external.jikan.fetch_json")
    def test_full_metadata_is_loaded_only_for_a_selected_mal_url(self, fetch_json) -> None:
        fetch_json.side_effect = [
            {"data": _anime_payload()},
            {
                "data": [
                    {
                        "person": {"mal_id": 1117, "name": "Makoto Shinkai"},
                        "positions": ["Director", "Storyboard"],
                    },
                    {
                        "person": {"mal_id": 999, "name": "Other Person"},
                        "positions": ["Producer"],
                    },
                ]
            },
        ]

        metadata = fetch_jikan_metadata("https://myanimelist.net/anime/32281/Kimi_no_Na_wa")

        self.assertEqual(metadata["mal_id"], "32281")
        self.assertEqual(metadata["directors"], ["Makoto Shinkai"])
        self.assertEqual(
            [call.args[0] for call in fetch_json.call_args_list],
            [
                "https://api.jikan.moe/v4/anime/32281/full",
                "https://api.jikan.moe/v4/anime/32281/staff",
            ],
        )

    @patch("movie_inbox.external.jikan.fetch_json")
    def test_staff_failure_keeps_the_selected_full_metadata(self, fetch_json) -> None:
        fetch_json.side_effect = [{"data": _anime_payload()}, TimeoutError("staff timeout")]

        metadata = fetch_jikan_metadata("https://myanimelist.net/anime/32281")

        self.assertEqual(metadata["mal_id"], "32281")
        self.assertNotIn("directors", metadata)
        self.assertEqual(fetch_json.call_count, 2)

    @patch("movie_inbox.external.jikan.fetch_json")
    def test_invalid_metadata_url_never_calls_jikan(self, fetch_json) -> None:
        self.assertEqual(fetch_jikan_metadata("https://example.com/anime/32281"), {})
        fetch_json.assert_not_called()

    def test_search_result_keeps_mal_identity_when_materialized_for_the_catalog(self) -> None:
        result = jikan_anime_result(_anime_payload())

        self.assertIsNotNone(result)
        assert result is not None
        item = item_from_search_result(result)

        self.assertEqual(item["source"], "jikan")
        self.assertEqual(item["myanimelist_url"], "https://myanimelist.net/anime/32281")
        self.assertEqual(item["mal_id"], "32281")
        self.assertEqual(item["metadata_sources"]["mal_id"]["source"], "jikan")


if __name__ == "__main__":
    unittest.main()
