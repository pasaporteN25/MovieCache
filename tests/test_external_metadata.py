from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError

from movie_inbox.external.imdb import ImdbAdapter
from movie_inbox.external.metadata import fetch_metadata_by_title
from movie_inbox.external.registry import ExternalSourceService
from movie_inbox.external.wikidata import (
    fetch_wikidata_metadata,
    fetch_wikidata_title_matches,
    wikidata_claim_duration_minutes,
    wikidata_kind,
)
from movie_inbox.external.wikipedia import (
    WikipediaAdapter,
    _find_synopsis_section,
    _split_wikipedia_sections,
    fetch_wikipedia_by_title,
    fetch_wikipedia_by_wikidata_title,
    fetch_wikipedia_metadata_action_api,
)

# Modeled on real explaintext=1 (no exintro=1) responses fetched live from
# en.wikipedia.org/w/api.php and es.wikipedia.org/w/api.php: "== Heading =="
# markers survive as plain text, and a top-level section can be immediately
# followed by a deeper "===" subsection before the next real "==" section.
_ENGLISH_ARTICLE_EXTRACT = (
    "Heat is a 1995 American epic crime film written and directed by Michael Mann. "
    "It features an ensemble cast starring Al Pacino and Robert De Niro.\n\n\n"
    "== Plot ==\n"
    "Neil McCauley, a Los Angeles professional thief, and his crew rob an armored car.\n\n\n"
    "== Cast ==\n"
    "Al Pacino as Vincent Hanna\nRobert De Niro as Neil McCauley\n\n\n"
    "== Reception ==\n"
    "The film received critical acclaim.\n"
)

_SPANISH_ARTICLE_EXTRACT_WITH_NESTED_SUBSECTION = (
    "El padrino es una película estadounidense de 1972 dirigida por Francis Ford Coppola.\n\n\n"
    "== Argumento ==\n"
    "La historia comienza en el verano de 1945, durante la boda de Connie Corleone.\n\n\n"
    "=== Reestreno remasterizado ===\n"
    "En 2008 se realizó una restauración digital de la película.\n\n\n"
    "== Reparto ==\n"
    "Marlon Brando como Vito Corleone\nAl Pacino como Michael Corleone\n"
)


class ExternalMetadataTests(unittest.TestCase):
    def test_wikidata_duration_is_normalized_to_integer_minutes(self) -> None:
        claims = {
            "P2047": [
                {
                    "rank": "normal",
                    "mainsnak": {
                        "datavalue": {
                            "value": {
                                "amount": "+5400",
                                "unit": "http://www.wikidata.org/entity/Q11574",
                            }
                        }
                    },
                }
            ]
        }

        self.assertEqual(wikidata_claim_duration_minutes(claims), 90)

    @patch("movie_inbox.external.wikidata.fetch_wikidata_labels")
    @patch("movie_inbox.external.wikidata.fetch_json_safe")
    def test_wikidata_metadata_extracts_the_five_e6_fields(
        self, fetch_json_safe, fetch_labels
    ) -> None:
        def entity_claim(item_id: str) -> dict[str, object]:
            return {
                "rank": "normal",
                "mainsnak": {"datavalue": {"value": {"id": item_id}}},
            }

        fetch_json_safe.return_value = {
            "entities": {
                "Q1": {
                    "labels": {},
                    "aliases": {},
                    "claims": {
                        "P2047": [
                            {
                                "rank": "preferred",
                                "mainsnak": {
                                    "datavalue": {
                                        "value": {
                                            "amount": "+172",
                                            "unit": "http://www.wikidata.org/entity/Q7727",
                                        }
                                    }
                                },
                            }
                        ],
                        "P495": [entity_claim("Q30")],
                        "P364": [entity_claim("Q1860")],
                        "P162": [entity_claim("Q2")],
                        "P86": [entity_claim("Q3")],
                    },
                }
            }
        }
        fetch_labels.return_value = {
            "Q30": "Estados Unidos",
            "Q1860": "inglés",
            "Q2": "Productora",
            "Q3": "Compositor",
        }

        metadata = fetch_wikidata_metadata("Q1")

        self.assertEqual(metadata["duration_minutes"], 172)
        self.assertEqual(metadata["countries"], ["Estados Unidos"])
        self.assertEqual(metadata["original_languages"], ["inglés"])
        self.assertEqual(metadata["producers"], ["Productora"])
        self.assertEqual(metadata["composers"], ["Compositor"])
        fetch_labels.assert_called_once_with(["Q30", "Q1860", "Q2", "Q3"])

    @patch("movie_inbox.external.metadata.fetch_wikipedia_by_title")
    @patch("movie_inbox.external.metadata.fetch_wikipedia_by_wikidata_title")
    def test_title_lookup_prefers_richer_wikidata_metadata(
        self, wikidata_lookup, wikipedia_lookup
    ) -> None:
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
        self.assertEqual(
            metadata["alternative_titles"], ["The Beautiful Person", "La bella persona"]
        )

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

    @patch("movie_inbox.external.imdb.fetch_wikidata_title_matches")
    @patch("movie_inbox.external.imdb.fetch_json")
    def test_imdb_keeps_a_multilingual_alias_tied_to_the_same_imdb_id(
        self, fetch_json, title_matches
    ) -> None:
        fetch_json.return_value = {
            "d": [
                {
                    "id": "tt0180396",
                    "l": "Goodbye Uncle Tom",
                    "qid": "movie",
                    "y": 1971,
                }
            ]
        }
        title_matches.return_value = {
            "tt0180396": {
                "original_title": "Addio zio Tom",
                "spanish_title": "Adiós tío Tom",
                "english_title": "Goodbye Uncle Tom",
                "alternative_titles": ["Addio zio Tom", "Adiós tío Tom"],
            }
        }

        results, _state = ExternalSourceService([ImdbAdapter()]).search("Addio zio Tom")

        self.assertEqual(results[0]["url"], "https://www.imdb.com/title/tt0180396/")
        self.assertEqual(results[0]["original_title"], "Addio zio Tom")
        self.assertIn("Adiós tío Tom", results[0]["alternative_titles"])
        title_matches.assert_called_once_with("Addio zio Tom")

    @patch("movie_inbox.external.imdb.fetch_json")
    def test_imdb_suggestion_key_preserves_accented_letters(self, fetch_json) -> None:
        fetch_json.return_value = {"d": []}

        ImdbAdapter().search("Adiós Tío Tom")

        self.assertIn("/adios_tio_tom.json", fetch_json.call_args.args[0])

    @patch("movie_inbox.external.imdb.fetch_wikidata_title_matches")
    @patch("movie_inbox.external.imdb.fetch_json")
    def test_imdb_does_not_borrow_an_alias_from_a_different_imdb_id(
        self, fetch_json, title_matches
    ) -> None:
        fetch_json.return_value = {
            "d": [
                {
                    "id": "tt0180396",
                    "l": "Goodbye Uncle Tom",
                    "qid": "movie",
                    "y": 1971,
                }
            ]
        }
        title_matches.return_value = {"tt9999999": {"alternative_titles": ["Addio zio Tom"]}}

        results, _state = ExternalSourceService([ImdbAdapter()]).search("Addio zio Tom")

        self.assertEqual(results, [])

    @patch("movie_inbox.external.wikidata.fetch_json_safe")
    def test_wikidata_title_match_maps_the_matched_alias_to_its_imdb_id(
        self, fetch_json_safe
    ) -> None:
        def response(url: str, **_kwargs: object) -> dict[str, object]:
            if "wbsearchentities" in url:
                if "language=en" not in url:
                    return {"search": []}
                return {
                    "search": [
                        {
                            "id": "Q3605118",
                            "label": "Adiós tío Tom",
                            "match": {
                                "type": "alias",
                                "language": "en",
                                "text": "Addio zio Tom",
                            },
                            "aliases": ["Addio zio Tom"],
                        }
                    ]
                }
            return {
                "entities": {
                    "Q3605118": {
                        "labels": {
                            "es": {"value": "Adiós tío Tom"},
                            "en": {"value": "Goodbye Uncle Tom"},
                        },
                        "aliases": {},
                        "claims": {
                            "P345": [{"mainsnak": {"datavalue": {"value": "tt0180396"}}}],
                            "P1476": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {
                                                "text": "Addio zio Tom",
                                                "language": "it",
                                            }
                                        }
                                    }
                                }
                            ],
                        },
                    }
                }
            }

        fetch_json_safe.side_effect = response

        matches = fetch_wikidata_title_matches("Addio zio Tom")

        self.assertEqual(matches["tt0180396"]["original_title"], "Addio zio Tom")
        self.assertEqual(matches["tt0180396"]["spanish_title"], "Adiós tío Tom")
        self.assertEqual(matches["tt0180396"]["english_title"], "Goodbye Uncle Tom")

    @patch("movie_inbox.external.wikidata.fetch_json_safe")
    def test_wikidata_title_match_searches_japanese_aliases(self, fetch_json_safe) -> None:
        def response(url: str, **_kwargs: object) -> dict[str, object]:
            if "wbsearchentities" in url:
                if "language=ja" not in url:
                    return {"search": []}
                return {"search": [{"id": "Q27419", "label": "君の名は。"}]}
            return {
                "entities": {
                    "Q27419": {
                        "labels": {
                            "en": {"value": "Your Name"},
                            "ja": {"value": "君の名は。"},
                        },
                        "aliases": {"en": [{"value": "Kimi no Na wa"}]},
                        "claims": {
                            "P345": [{"mainsnak": {"datavalue": {"value": "tt5311514"}}}],
                            "P1476": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {"text": "君の名は。", "language": "ja"}
                                        }
                                    }
                                }
                            ],
                        },
                    }
                }
            }

        fetch_json_safe.side_effect = response
        matches = fetch_wikidata_title_matches("君の名は。")

        self.assertEqual(matches["tt5311514"]["original_title"], "君の名は。")
        self.assertIn("Kimi no Na wa", matches["tt5311514"]["alternative_titles"])

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
    def test_wikipedia_search_keeps_alternatives_when_the_exact_film_is_present(
        self, fetch_json
    ) -> None:
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

    @patch("movie_inbox.external.wikipedia.fetch_wikipedia_metadata")
    def test_fetch_wikipedia_by_title_accepts_a_genuine_title_and_year_match(
        self, fetch_metadata
    ) -> None:
        fetch_metadata.return_value = {
            "title": "Heat",
            "wikipedia_title": "Heat",
            "year": "1995",
            "url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
            "wikidata_id": "Q184090",
        }

        metadata = fetch_wikipedia_by_title("Heat", "1995")

        self.assertEqual(metadata["wikidata_id"], "Q184090")
        fetch_metadata.assert_called_once()

    @patch("movie_inbox.external.wikipedia.fetch_wikipedia_search")
    @patch("movie_inbox.external.wikipedia.fetch_wikipedia_metadata")
    def test_fetch_wikipedia_by_title_rejects_the_same_title_with_a_different_year(
        self, fetch_metadata, fetch_search
    ) -> None:
        # The bug this guards: wikipedia_match_score() used to accept this on
        # fuzzy title overlap alone, wiring up a different film's Wikidata id,
        # genres and cast onto the wrong catalog item.
        fetch_metadata.return_value = {
            "title": "Heat",
            "wikipedia_title": "Heat",
            "year": "1986",
            "url": "https://en.wikipedia.org/wiki/Heat_(1986_film)",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1986_film)",
        }
        fetch_search.return_value = {"query": {"search": []}}

        metadata = fetch_wikipedia_by_title("Heat", "1995")

        self.assertEqual(metadata, {})

    @patch("movie_inbox.external.wikipedia.fetch_wikipedia_search")
    @patch("movie_inbox.external.wikipedia.fetch_wikipedia_metadata")
    def test_fetch_wikipedia_by_title_accepts_a_match_found_only_via_search(
        self, fetch_metadata, fetch_search
    ) -> None:
        def metadata_for(url: str) -> dict[str, object]:
            if "Evil_Dead_Burn" in url:
                return {
                    "title": "Evil Dead Burn",
                    "wikipedia_title": "Evil Dead Burn",
                    "year": "2026",
                    "url": url,
                    "wikipedia_url": url,
                }
            return {}

        fetch_metadata.side_effect = metadata_for
        fetch_search.return_value = {
            "query": {"search": [{"title": "Evil Dead Burn", "snippet": ""}]}
        }

        metadata = fetch_wikipedia_by_title("Evil Dead Burn", "2026")

        self.assertEqual(metadata["title"], "Evil Dead Burn")

    @patch("movie_inbox.external.wikipedia.fetch_wikipedia_metadata")
    @patch("movie_inbox.external.wikipedia.fetch_wikidata_article_url")
    @patch("movie_inbox.external.wikipedia.fetch_json_safe")
    def test_fetch_wikipedia_by_wikidata_title_rejects_the_same_title_with_a_different_year(
        self, fetch_json_safe, article_url, fetch_metadata
    ) -> None:
        fetch_json_safe.return_value = {
            "search": [
                {"id": "Q184090", "label": "Heat", "description": "1986 film by Dick Richards"}
            ]
        }
        article_url.return_value = "https://en.wikipedia.org/wiki/Heat_(1986_film)"
        fetch_metadata.return_value = {
            "title": "Heat",
            "wikipedia_title": "Heat",
            "year": "1986",
            "url": "https://en.wikipedia.org/wiki/Heat_(1986_film)",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1986_film)",
        }

        metadata = fetch_wikipedia_by_wikidata_title("Heat", "1995")

        self.assertEqual(metadata, {})

    @patch("movie_inbox.external.wikipedia.fetch_wikidata_metadata", return_value={})
    @patch("movie_inbox.external.wikipedia.fetch_json_safe")
    def test_fetch_wikipedia_metadata_action_api_stores_the_full_synopsis_not_just_the_intro(
        self, fetch_json_safe, _wikidata
    ) -> None:
        fetch_json_safe.return_value = {
            "query": {
                "pages": {
                    "43566": {
                        "title": "Heat (1995 film)",
                        "canonicalurl": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                        "extract": _ENGLISH_ARTICLE_EXTRACT,
                        "pageprops": {"wikibase_item": "Q184090"},
                    }
                }
            }
        }

        metadata = fetch_wikipedia_metadata_action_api("en", "Heat (1995 film)")

        self.assertIn("Neil McCauley", metadata["wikipedia_extract"])
        self.assertNotIn("Vincent Hanna", metadata["wikipedia_extract"])  # that's the Cast section
        self.assertEqual(metadata["kind"], "pelicula")

    @patch("movie_inbox.external.wikipedia.fetch_wikidata_metadata", return_value={})
    @patch("movie_inbox.external.wikipedia.fetch_json_safe")
    def test_fetch_wikipedia_metadata_action_api_falls_back_to_the_intro_without_a_plot_section(
        self, fetch_json_safe, _wikidata
    ) -> None:
        fetch_json_safe.return_value = {
            "query": {
                "pages": {
                    "1": {
                        "title": "Some Film",
                        "extract": "Some Film is a 2020 film.\n\n\n== Awards ==\nWon an award.\n",
                    }
                }
            }
        }

        metadata = fetch_wikipedia_metadata_action_api("en", "Some Film")

        self.assertEqual(metadata["wikipedia_extract"], "Some Film is a 2020 film.")

    def test_split_wikipedia_sections_finds_the_intro_and_each_top_level_heading(self) -> None:
        intro, sections = _split_wikipedia_sections(_ENGLISH_ARTICLE_EXTRACT)

        self.assertIn("Heat is a 1995 American epic crime film", intro)
        self.assertEqual([title for _, title, _ in sections], ["Plot", "Cast", "Reception"])

    def test_find_synopsis_section_returns_the_plot_body_only(self) -> None:
        _intro, sections = _split_wikipedia_sections(_ENGLISH_ARTICLE_EXTRACT)

        synopsis = _find_synopsis_section(sections, "en")

        self.assertIn("Neil McCauley", synopsis)
        self.assertNotIn("Vincent Hanna", synopsis)

    def test_find_synopsis_section_includes_a_nested_subsection(self) -> None:
        # "Argumento" is directly followed by a "===" subsection before the
        # next real "==" heading ("Reparto"); that subsection has to stay
        # part of the synopsis instead of getting cut off by the first
        # heading found, regardless of its level.
        _intro, sections = _split_wikipedia_sections(
            _SPANISH_ARTICLE_EXTRACT_WITH_NESTED_SUBSECTION
        )

        synopsis = _find_synopsis_section(sections, "es")

        self.assertIn("boda de Connie Corleone", synopsis)
        self.assertIn("restauración digital", synopsis)
        self.assertNotIn("Marlon Brando", synopsis)

    def test_find_synopsis_section_returns_empty_when_no_matching_heading_exists(self) -> None:
        _intro, sections = _split_wikipedia_sections(
            "Intro text.\n\n\n== Awards ==\nSome awards.\n"
        )

        self.assertEqual(_find_synopsis_section(sections, "en"), "")

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
