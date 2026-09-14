"""Opt-in smoke test against the real TMDb API.

Skipped unless MOVIE_INBOX_TMDB_LIVE_SMOKE_TOKEN carries a real TMDb API Read
Access Token. Never runs in CI: no such secret is configured there, so this
file contributes zero real network calls to the default gate. Run locally,
voluntarily, with your own token, to validate [F5.3] against the live API
over the corpus already recorded offline in tests/test_external_tmdb.py:
Addio Zio Tom, Fanny & Alexander, Verano 1993 (2017) and the Heat movie/TV
homonym (tt0180396).

It also reads the two halves 0.9.0 added: public scores ([F6.2]) and streaming
availability ([S1], [S3]). No offline test calls the adapter's streaming
methods, so the last three tests are their only check against TMDb's answers.
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

    def test_public_scores_come_back_as_a_number_and_a_vote_count(self) -> None:
        # [F6.2]: the score half of the API, which the offline tests can only
        # check against a payload we wrote ourselves. Heat is rated by enough
        # people that both numbers are stable enough to assert loosely.
        found = self.adapter.public_rating("movie", "949")
        self.assertTrue(found, "TMDb should have a score for Heat")
        self.assertGreater(found["average"], 0.0)
        self.assertLessEqual(found["average"], 10.0)
        self.assertGreater(found["votes"], 1000)

    def test_an_unusable_reference_asks_nothing_and_yields_nothing(self) -> None:
        self.assertEqual(self.adapter.public_rating("libro", "949"), {})
        self.assertEqual(self.adapter.public_rating("movie", "no-es-un-id"), {})

    def test_argentina_is_among_the_markets_availability_can_be_asked_for(self) -> None:
        # [S1]: the markets Administrar offers. ADR-0004 measured 139 regions,
        # Argentina among them; the exact count drifts, so only a floor.
        regions = self.adapter.watch_regions()
        self.assertIn("AR", {row["code"] for row in regions})
        self.assertGreater(len(regions), 50)

    def test_the_argentine_platform_list_keeps_the_upstream_names(self) -> None:
        # [S1]: what refreshing a market's platforms stores, movies and TV
        # merged. ADR-0004 found 59 for Argentina, Netflix under that literal name.
        providers = self.adapter.watch_providers("AR")
        self.assertGreater(len(providers), 10)
        self.assertIn("Netflix", {row["name"] for row in providers})
        for row in providers:
            self.assertEqual(row["region_code"], "AR")
            self.assertTrue(row["provider_id"].isdigit(), row)

    def test_one_work_in_one_market_yields_offers_or_nothing(self) -> None:
        # [S3]: nothing means the market has no data for the work, never that it
        # is not offered, so both answers are valid; what must hold is the shape.
        found = self.adapter.watch_availability("movie", "949", "AR")
        if found:
            self.assertTrue(found["offers"] or found["link"], found)
            for offer in found["offers"]:
                self.assertIn(offer["kind"], {"flatrate", "free", "ads", "rent", "buy"})
                self.assertTrue(offer["provider_id"].isdigit(), offer)
        self.assertEqual(self.adapter.watch_availability("libro", "949", "AR"), {})


if __name__ == "__main__":
    unittest.main()
