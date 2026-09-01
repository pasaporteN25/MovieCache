from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from movie_inbox.external.registry import ExternalSourceService, default_source_adapters
from movie_inbox.external.tmdb import (
    TmdbAdapter,
    fetch_tmdb_metadata,
    tmdb_reference,
)
from movie_inbox.infrastructure.external_catalog import (
    configure_external_catalog,
    enrich_external_result,
    external_sources_snapshot,
)
from movie_inbox.web.catalog_api import item_from_search_result


def _movie_search_row(
    *,
    tmdb_id: int = 48691,
    title: str = "Adiós, tío Tom",
    original_title: str = "Addio zio Tom",
    release_date: str = "1971-09-23",
) -> dict[str, object]:
    return {
        "id": tmdb_id,
        "media_type": "movie",
        "title": title,
        "original_title": original_title,
        "original_language": "it",
        "release_date": release_date,
        "overview": "Dos cineastas reconstruyen episodios históricos.",
        "poster_path": "/addio-poster.jpg",
        "backdrop_path": "/addio-backdrop.jpg",
        "vote_average": 6.4,
        "popularity": 12.3,
    }


def _movie_detail_payload() -> dict[str, object]:
    return {
        **_movie_search_row(),
        "runtime": 136,
        "genres": [{"id": 99, "name": "Documental"}, {"id": 18, "name": "Drama"}],
        "production_countries": [{"iso_3166_1": "IT", "name": "Italia"}],
        "spoken_languages": [{"iso_639_1": "it", "english_name": "Italian", "name": "Italiano"}],
        "translations": {
            "translations": [
                {
                    "iso_639_1": "es",
                    "data": {
                        "title": "Adiós, tío Tom",
                        "overview": "Descripción localizada.",
                    },
                },
                {
                    "iso_639_1": "en",
                    "data": {"title": "Goodbye Uncle Tom", "overview": "English overview."},
                },
            ]
        },
        "alternative_titles": {
            "titles": [
                {"iso_3166_1": "IT", "title": "Zio Tom"},
                {"iso_3166_1": "US", "title": "Goodbye Uncle Tom"},
            ]
        },
        "credits": {
            "crew": [
                {"name": "Gualtiero Jacopetti", "job": "Director", "department": "Directing"},
                {"name": "Franco Prosperi", "job": "Director", "department": "Directing"},
                {"name": "Gualtiero Jacopetti", "job": "Writer", "department": "Writing"},
                {"name": "Franco Prosperi", "job": "Producer", "department": "Production"},
                {
                    "name": "Riz Ortolani",
                    "job": "Original Music Composer",
                    "department": "Sound",
                },
            ],
            "cast": [{"name": "Stefano Sibaldi"}, {"name": "Dick Gregory"}],
        },
        "external_ids": {"imdb_id": "tt0180396", "wikidata_id": "Q3605118"},
        "release_dates": {
            "results": [
                {
                    "iso_3166_1": "IT",
                    "release_dates": [{"release_date": "1971-09-23T00:00:00.000Z", "type": 3}],
                },
                {
                    "iso_3166_1": "US",
                    "release_dates": [{"release_date": "1972-10-27T00:00:00.000Z", "type": 3}],
                },
            ]
        },
        "images": {"posters": [], "backdrops": []},
    }


def _tv_detail_payload() -> dict[str, object]:
    return {
        "id": 1399,
        "name": "Juego de tronos",
        "original_name": "Game of Thrones",
        "original_language": "en",
        "first_air_date": "2011-04-17",
        "overview": "Nueve familias nobles luchan por el poder.",
        "poster_path": "/got-poster.jpg",
        "backdrop_path": "/got-backdrop.jpg",
        "episode_run_time": [57],
        "genres": [{"id": 18, "name": "Drama"}],
        "production_countries": [{"iso_3166_1": "US", "name": "Estados Unidos"}],
        "spoken_languages": [{"iso_639_1": "en", "name": "English"}],
        "translations": {
            "translations": [
                {"iso_639_1": "es", "data": {"name": "Juego de tronos", "overview": ""}},
                {"iso_639_1": "en", "data": {"name": "Game of Thrones", "overview": ""}},
            ]
        },
        "alternative_titles": {"results": [{"iso_3166_1": "ES", "title": "Tronos"}]},
        "credits": {"crew": [], "cast": [{"name": "Emilia Clarke"}]},
        "external_ids": {"imdb_id": "tt0944947", "wikidata_id": "Q23572"},
        "images": {"posters": [], "backdrops": []},
    }


class TmdbAdapterTests(unittest.TestCase):
    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_multisearch_maps_addio_without_putting_token_in_the_url(self, fetch_json) -> None:
        fetch_json.return_value = {
            "results": [
                {"id": 1, "media_type": "person", "name": "Gualtiero Jacopetti"},
                _movie_search_row(),
            ]
        }

        results = TmdbAdapter("secret-read-token").search("Addio Zio Tom")

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["source"], "tmdb")
        self.assertEqual(result["tmdb_id"], "48691")
        self.assertEqual(result["original_title"], "Addio zio Tom")
        self.assertEqual(result["spanish_title"], "Adiós, tío Tom")
        self.assertEqual(result["kind"], "pelicula")
        self.assertEqual(result["year"], "1971")
        self.assertEqual(result["url"], "https://www.themoviedb.org/movie/48691")
        self.assertEqual(result["tmdb_url"], "https://www.themoviedb.org/movie/48691")
        self.assertEqual(result["page_image"], "https://image.tmdb.org/t/p/w500/addio-poster.jpg")
        self.assertNotIn("rating", result)
        self.assertNotIn("vote_average", result)
        requested_url = fetch_json.call_args.args[0]
        self.assertIn("/search/multi?", requested_url)
        self.assertNotIn("secret-read-token", requested_url)
        self.assertEqual(
            fetch_json.call_args.kwargs["headers"]["Authorization"],
            "Bearer secret-read-token",
        )

    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_problematic_titles_are_sent_without_rewriting_their_meaning(self, fetch_json) -> None:
        fetch_json.return_value = {"results": []}
        adapter = TmdbAdapter("secret")

        cases = {
            "Fanny & Alexander": "Fanny & Alexander",
            "Verano 1993": "Verano 1993",
            "Verano 1993 (2017)": "Verano 1993",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                adapter.search(query)
                parameters = parse_qs(urlparse(fetch_json.call_args.args[0]).query)
                self.assertEqual(parameters["query"], [expected])
                self.assertNotIn("year", parameters)

    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_an_imdb_id_uses_find_and_keeps_movie_tv_separate(self, fetch_json) -> None:
        fetch_json.return_value = {
            "movie_results": [_movie_search_row()],
            "tv_results": [
                {
                    "id": 900,
                    "name": "Heat",
                    "original_name": "Heat",
                    "original_language": "en",
                    "first_air_date": "1995-01-01",
                }
            ],
        }

        results = TmdbAdapter("secret").search("tt0180396")

        self.assertIn("/find/tt0180396?", fetch_json.call_args.args[0])
        self.assertEqual([row["kind"] for row in results], ["pelicula", "serie"])
        self.assertEqual(results[0]["imdb_url"], "https://www.imdb.com/title/tt0180396/")
        self.assertEqual(
            [row["url"] for row in results],
            [
                "https://www.themoviedb.org/movie/48691",
                "https://www.themoviedb.org/tv/900",
            ],
        )

    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_registry_keeps_a_tmdb_find_result_for_an_imdb_id(self, fetch_json) -> None:
        fetch_json.return_value = {"movie_results": [_movie_search_row()], "tv_results": []}
        service = ExternalSourceService([TmdbAdapter("secret")])

        results, _state = service.search("tt0180396", "tmdb")

        self.assertEqual([row["tmdb_id"] for row in results], ["48691"])

    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_selected_movie_loads_one_appended_detail_and_maps_structured_fields(
        self, fetch_json
    ) -> None:
        fetch_json.return_value = _movie_detail_payload()

        metadata = fetch_tmdb_metadata(
            "https://www.themoviedb.org/movie/48691-goodbye-uncle-tom",
            "secret",
        )

        self.assertEqual(fetch_json.call_count, 1)
        requested_url = fetch_json.call_args.args[0]
        parameters = parse_qs(urlparse(requested_url).query)
        self.assertEqual(parameters["language"], ["es-AR"])
        self.assertIn("translations", parameters["append_to_response"][0])
        self.assertIn("external_ids", parameters["append_to_response"][0])
        self.assertIn("credits", parameters["append_to_response"][0])
        self.assertEqual(metadata["english_title"], "Goodbye Uncle Tom")
        self.assertEqual(metadata["alternative_titles"], ["Zio Tom"])
        self.assertEqual(metadata["duration_minutes"], 136)
        self.assertEqual(metadata["countries"], ["Italia"])
        self.assertEqual(metadata["original_languages"], ["Italiano"])
        self.assertEqual(metadata["directors"], ["Gualtiero Jacopetti", "Franco Prosperi"])
        self.assertEqual(metadata["writers"], ["Gualtiero Jacopetti"])
        self.assertEqual(metadata["producers"], ["Franco Prosperi"])
        self.assertEqual(metadata["composers"], ["Riz Ortolani"])
        self.assertEqual(metadata["cast"], ["Stefano Sibaldi", "Dick Gregory"])
        self.assertEqual(metadata["imdb_url"], "https://www.imdb.com/title/tt0180396/")
        self.assertEqual(metadata["wikidata_id"], "Q3605118")
        self.assertEqual(len(metadata["release_dates"]), 3)
        self.assertEqual({row["country"] for row in metadata["release_dates"]}, {"", "IT", "US"})
        self.assertNotIn("rating", metadata)
        self.assertNotIn("vote_average", metadata)

    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_direct_tmdb_url_loads_detail_but_invalid_or_unconfigured_urls_do_not(
        self, fetch_json
    ) -> None:
        fetch_json.return_value = _movie_detail_payload()
        adapter = TmdbAdapter("secret")

        results = adapter.search("https://www.themoviedb.org/movie/48691")

        self.assertEqual(results[0]["tmdb_id"], "48691")
        fetch_json.reset_mock()
        self.assertEqual(fetch_tmdb_metadata("https://example.com/movie/48691", "secret"), {})
        self.assertEqual(fetch_tmdb_metadata("https://www.themoviedb.org/movie/48691", ""), {})
        fetch_json.assert_not_called()

    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_selected_tv_detail_uses_tv_names_without_inventing_a_series_runtime(
        self, fetch_json
    ) -> None:
        fetch_json.return_value = _tv_detail_payload()

        metadata = fetch_tmdb_metadata("https://www.themoviedb.org/tv/1399", "secret")

        self.assertIn("/tv/1399?", fetch_json.call_args.args[0])
        self.assertEqual(metadata["kind"], "serie")
        self.assertEqual(metadata["spanish_title"], "Juego de tronos")
        self.assertEqual(metadata["english_title"], "Game of Thrones")
        self.assertEqual(metadata["alternative_titles"], ["Tronos"])
        self.assertEqual(metadata["cast"], ["Emilia Clarke"])
        self.assertEqual(metadata["imdb_url"], "https://www.imdb.com/title/tt0944947/")
        self.assertNotIn("duration_minutes", metadata)

    def test_tmdb_reference_rejects_lookalike_hosts_and_non_media_paths(self) -> None:
        self.assertEqual(
            tmdb_reference("https://www.themoviedb.org/tv/1399-game-of-thrones"),
            ("tv", "1399"),
        )
        self.assertIsNone(tmdb_reference("https://themoviedb.org.example/tv/1399"))
        self.assertIsNone(tmdb_reference("https://www.themoviedb.org/person/1399"))

    def test_registry_contains_tmdb_only_when_a_token_is_supplied(self) -> None:
        without_token = {adapter.name for adapter in default_source_adapters()}
        with_token = {adapter.name for adapter in default_source_adapters("secret")}

        self.assertNotIn("tmdb", without_token)
        self.assertIn("tmdb", with_token)

    @patch("movie_inbox.external.tmdb.fetch_json")
    def test_selected_tmdb_result_flows_through_enrichment_and_materialization(
        self, fetch_json
    ) -> None:
        fetch_json.return_value = _movie_detail_payload()
        lightweight = {
            "source": "tmdb",
            "title": "Adiós, tío Tom",
            "original_title": "Addio zio Tom",
            "year": "1971",
            "kind": "pelicula",
            "url": "https://www.themoviedb.org/movie/48691",
            "tmdb_id": "48691",
        }
        try:
            configure_external_catalog("secret")

            enriched = enrich_external_result(lightweight)
            item = item_from_search_result(dict(enriched))

            self.assertEqual(fetch_json.call_count, 1)
            self.assertEqual(item["tmdb_id"], "48691")
            self.assertEqual(item["tmdb_url"], "https://www.themoviedb.org/movie/48691")
            self.assertEqual(item["imdb_url"], "https://www.imdb.com/title/tt0180396/")
            self.assertEqual(item["metadata_sources"]["tmdb_id"]["source"], "tmdb")
            self.assertEqual(item["metadata_sources"]["tmdb_url"]["source"], "tmdb")
            self.assertEqual(item["metadata_sources"]["directors"]["source"], "tmdb")
        finally:
            configure_external_catalog("")

    def test_process_gateway_has_no_tmdb_health_entry_without_a_token(self) -> None:
        try:
            configure_external_catalog("")
            self.assertNotIn("tmdb", external_sources_snapshot()["sources"])
            configure_external_catalog("secret")
            self.assertIn("tmdb", external_sources_snapshot()["sources"])
        finally:
            configure_external_catalog("")


if __name__ == "__main__":
    unittest.main()
