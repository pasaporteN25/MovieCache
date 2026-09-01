"""Opt-in smoke test against the real TMDb API.

Skipped unless MOVIE_INBOX_TMDB_LIVE_SMOKE_TOKEN carries a real TMDb API Read
Access Token. Never runs in CI: no such secret is configured there, so this
file contributes zero real network calls to the default gate. Run locally,
voluntarily, with your own token, to validate [F5.3] against the live API
over the corpus already recorded offline in tests/test_external_tmdb.py:
Addio Zio Tom, Fanny & Alexander, Verano 1993 (2017) and the Heat movie/TV
homonym (tt0180396).
"""

from __future__ import annotations

import os
import unittest

from movie_inbox.external.tmdb import TmdbAdapter

_TOKEN = os.environ.get("MOVIE_INBOX_TMDB_LIVE_SMOKE_TOKEN", "")


@unittest.skipUnless(_TOKEN, "set MOVIE_INBOX_TMDB_LIVE_SMOKE_TOKEN for a voluntary live smoke")
class TmdbLiveSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = TmdbAdapter(_TOKEN)

    def test_addio_zio_tom_resolves_original_and_translated_titles(self) -> None:
        results = self.adapter.search("Addio Zio Tom")
        self.assertTrue(results)
        top = results[0]
        self.assertEqual(top["kind"], "pelicula")
        self.assertIn("addio zio tom", top["original_title"].casefold())

        detail = self.adapter.metadata(top["url"])
        self.assertTrue(detail.get("spanish_title") or detail.get("english_title"))
        self.assertIn("directors", detail)

    def test_fanny_and_alexander_search_is_not_mangled_by_the_ampersand(self) -> None:
        results = self.adapter.search("Fanny & Alexander")
        self.assertTrue(results)
        self.assertTrue(
            any("fanny" in row["original_title"].casefold() for row in results),
            results,
        )

    def test_verano_1993_with_a_qualifying_year_keeps_the_literal_title(self) -> None:
        results = self.adapter.search("Verano 1993 (2017)")
        self.assertTrue(results)
        self.assertTrue(any(row["year"] == "2017" for row in results), results)

    def test_heat_imdb_id_lookup_keeps_movie_and_tv_homonyms_separate(self) -> None:
        results = self.adapter.search("tt0113277")
        kinds = {row["kind"] for row in results}
        self.assertIn("pelicula", kinds)
        movie = next(row for row in results if row["kind"] == "pelicula")
        self.assertEqual(movie["imdb_url"], "https://www.imdb.com/title/tt0113277/")

        detail = self.adapter.metadata(movie["url"])
        self.assertEqual(detail["imdb_url"], "https://www.imdb.com/title/tt0113277/")
        self.assertIn("alternative_titles", detail)


if __name__ == "__main__":
    unittest.main()
