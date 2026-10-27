"""[IP] T2: pegar un enlace de una fuente devuelve esa obra, y sólo esa.

Respuestas grabadas, sin red: cada prueba declara las únicas URL que el adaptador
puede pedir; cualquier otra levanta `UnrecordedRequestError`.
"""

from __future__ import annotations

import unittest
from typing import Any

from movie_inbox.external.filmaffinity import FilmAffinityAdapter
from movie_inbox.external.imdb import ImdbAdapter
from movie_inbox.external.jikan import JikanAdapter
from movie_inbox.search_lab.recorded_responses import replay_recorded_responses
from tests.test_external_filmaffinity import LISTING_SEARCH_HTML, SPIRITED_AWAY_SEARCH_HTML
from tests.test_external_jikan import _anime_payload

IMDB_SUGGESTION_URL = "https://v3.sg.media-imdb.com/suggestion/x/{key}.json"
FILM_URL = "https://www.filmaffinity.com/es/film759533.html"
JIKAN_FULL_URL = "https://api.jikan.moe/v4/anime/32281/full"


def _imdb_row(imdb_id: str, title: str, year: int) -> dict[str, Any]:
    return {"id": imdb_id, "l": title, "qid": "movie", "y": year}


class PastedImdbUrlTests(unittest.TestCase):
    def test_a_title_url_returns_only_that_title_with_its_canonical_url(self) -> None:
        recorded = {
            IMDB_SUGGESTION_URL.format(key="tt0113277"): {
                "d": [_imdb_row("tt0113277", "Heat", 1995), _imdb_row("tt0000001", "Otra", 1900)]
            }
        }
        with replay_recorded_responses(recorded) as log:
            results = ImdbAdapter().search("https://www.imdb.com/title/tt0113277/?ref_=nv_sr_1")

        self.assertEqual([r["url"] for r in results], ["https://www.imdb.com/title/tt0113277/"])
        self.assertEqual(results[0]["title"], "Heat")
        self.assertEqual(log.urls, list(recorded))

    def test_an_id_the_suggestions_do_not_confirm_returns_nothing_without_bridging(self) -> None:
        recorded: dict[str, object] = {IMDB_SUGGESTION_URL.format(key="tt0113277"): {"d": []}}
        with replay_recorded_responses(recorded) as log:
            results = ImdbAdapter().search("https://www.imdb.com/title/tt0113277/")

        self.assertEqual(results, [])
        self.assertEqual(log.urls, list(recorded))

    def test_an_imdb_url_without_a_title_id_makes_no_request(self) -> None:
        with replay_recorded_responses({}) as log:
            results = ImdbAdapter().search("https://www.imdb.com/name/nm0000199/")

        self.assertEqual(results, [])
        self.assertEqual(log.urls, [])

    def test_other_sources_urls_are_ignored(self) -> None:
        with replay_recorded_responses({}) as log:
            self.assertEqual(ImdbAdapter().search("https://myanimelist.net/anime/32281"), [])
        self.assertEqual(log.urls, [])


class PastedFilmAffinityUrlTests(unittest.TestCase):
    def test_a_film_url_returns_that_film_with_its_canonical_url(self) -> None:
        with replay_recorded_responses({FILM_URL: SPIRITED_AWAY_SEARCH_HTML}) as log:
            results = FilmAffinityAdapter().search(
                "https://filmaffinity.com/es/film759533.html?utm=x"
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "filmaffinity")
        self.assertEqual(results[0]["url"], FILM_URL)
        self.assertEqual(results[0]["spanish_title"], "El viaje de Chihiro")
        self.assertEqual(log.urls, [FILM_URL])

    def test_a_page_that_is_not_a_film_returns_nothing(self) -> None:
        with replay_recorded_responses({FILM_URL: LISTING_SEARCH_HTML}):
            self.assertEqual(FilmAffinityAdapter().search(FILM_URL), [])

    def test_a_filmaffinity_url_that_is_not_a_film_page_makes_no_request(self) -> None:
        with replay_recorded_responses({}) as log:
            results = FilmAffinityAdapter().search("https://www.filmaffinity.com/es/main.html")
        self.assertEqual(results, [])
        self.assertEqual(log.urls, [])

    def test_other_sources_urls_are_ignored(self) -> None:
        with replay_recorded_responses({}) as log:
            self.assertEqual(
                FilmAffinityAdapter().search("https://www.imdb.com/title/tt0113277/"), []
            )
        self.assertEqual(log.urls, [])


class PastedJikanUrlTests(unittest.TestCase):
    def test_an_anime_url_returns_that_anime_by_id_not_by_slug(self) -> None:
        recorded = {JIKAN_FULL_URL: {"data": _anime_payload()}}
        with replay_recorded_responses(recorded) as log:
            results = JikanAdapter().search("https://myanimelist.net/anime/32281/Kimi_no_Na_wa?q=1")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://myanimelist.net/anime/32281")
        self.assertEqual(results[0]["mal_id"], "32281")
        self.assertEqual(log.urls, [JIKAN_FULL_URL])

    def test_an_unknown_anime_returns_nothing(self) -> None:
        with replay_recorded_responses({JIKAN_FULL_URL: {"data": {}}}):
            self.assertEqual(JikanAdapter().search("https://myanimelist.net/anime/32281"), [])

    def test_a_manga_url_makes_no_request(self) -> None:
        with replay_recorded_responses({}) as log:
            self.assertEqual(JikanAdapter().search("https://myanimelist.net/manga/1/Berserk"), [])
        self.assertEqual(log.urls, [])


if __name__ == "__main__":
    unittest.main()
