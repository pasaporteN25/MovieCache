from __future__ import annotations

import unittest

from movie_inbox.application.search_service import rank_catalog_candidates, search_catalog_items
from movie_inbox.domain.search_strategy import SearchStrategy


class CatalogSearchServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.items: list[dict[str, object]] = [
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

    def test_searches_a_native_japanese_title(self) -> None:
        item = {
            "id": "your-name",
            "title": "Your Name",
            "alternative_titles": ["君の名は。", "Kimi no Na wa"],
            "year": "2016",
            "kind": "anime",
        }

        self.assertEqual(search_catalog_items([item], "君の名は 2016")[0]["id"], "your-name")

    def test_a_higher_admission_threshold_excludes_a_borderline_match(self) -> None:
        item = {"id": "one", "title": "Amelie", "year": ""}
        baseline = search_catalog_items([item], "amelia")
        stricter = search_catalog_items(
            [item], "amelia", strategy=SearchStrategy(catalog_admission_threshold=99.0)
        )

        self.assertEqual([row["id"] for row in baseline], ["one"])
        self.assertEqual(stricter, [])

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

    def test_anime_can_be_compared_with_a_movie_typed_external_result(self) -> None:
        results = rank_catalog_candidates(
            [{"id": "akira", "title": "Akira", "year": "1988", "kind": "anime"}],
            {"title": "Akira", "year": "1988", "kind": "pelicula"},
        )

        self.assertEqual([row["id"] for row in results], ["akira"])
        self.assertFalse(results[0]["_search"]["accepted"])
        self.assertEqual(results[0]["_search"]["reason"], "exact_title_year_anime_kind_review")


class DirectorSearchTests(unittest.TestCase):
    """[Q4] tareas.md: "director:X" is explicit discovery, never blended
    into the title-scoring path above."""

    def setUp(self) -> None:
        self.items: list[dict[str, object]] = [
            {
                "id": "mondo-cane",
                "title": "Mondo Cane",
                "year": "1962",
                "directors": ["Gualtiero Jacopetti", "Paolo Cavara"],
            },
            {
                "id": "africa-addio",
                "title": "Africa Addio",
                "year": "1966",
                "directors": ["Gualtiero Jacopetti", "Franco Prosperi"],
            },
            {"id": "heat-1995", "title": "Heat", "year": "1995", "directors": ["Michael Mann"]},
        ]

    def test_finds_every_work_by_a_director_regardless_of_co_director_order(self) -> None:
        results = search_catalog_items(self.items, "director:Jacopetti")

        self.assertEqual({row["id"] for row in results}, {"mondo-cane", "africa-addio"})

    def test_a_director_match_is_labeled_as_discovery_not_a_title_match(self) -> None:
        results = search_catalog_items(self.items, "director:Jacopetti")

        for row in results:
            self.assertEqual(row["_search"]["matched_field"], "director")
            self.assertEqual(row["_search"]["reason"], "director_match")
            self.assertEqual(row["_search"]["matched_value"], "Gualtiero Jacopetti")

    def test_a_director_query_never_matches_by_title_text(self) -> None:
        # "director:Heat" must not fall back to matching the title "Heat" --
        # it's a name lookup, not title text with a stripped prefix.
        results = search_catalog_items(self.items, "director:Heat")

        self.assertEqual(results, [])

    def test_a_title_query_never_reads_the_directors_field(self) -> None:
        # Searching "Jacopetti" as a plain title query (no prefix) must not
        # surface his films -- directors stay excluded from ordinary search.
        self.assertEqual(search_catalog_items(self.items, "Jacopetti"), [])

    def test_the_full_given_name_also_matches(self) -> None:
        results = search_catalog_items(self.items, "director:Gualtiero Jacopetti")

        self.assertEqual({row["id"] for row in results}, {"mondo-cane", "africa-addio"})

    def test_a_stricter_admission_threshold_can_exclude_a_borderline_director_match(self) -> None:
        loose = search_catalog_items(self.items, "director:Jacopetti")
        strict = search_catalog_items(
            self.items,
            "director:Jacopetti",
            strategy=SearchStrategy(catalog_admission_threshold=99.0),
        )

        self.assertEqual(len(loose), 2)
        self.assertEqual(strict, [])


class SearchRankingPrecisionTests(unittest.TestCase):
    """Regression coverage for the golden-corpus false positives fixed alongside
    docs/search-quality.md problems #1 (short tokens) and #2 (secondary metadata)."""

    def test_short_title_does_not_match_as_a_substring_of_a_longer_title(self) -> None:
        items: list[dict[str, object]] = [
            {"id": "up-2009", "title": "Up", "year": "2009"},
            {"id": "setup-2011", "title": "Setup", "year": "2011"},
        ]
        results = search_catalog_items(items, "Up 2009")
        self.assertEqual([row["id"] for row in results], ["up-2009"])

    def test_short_title_is_not_found_inside_an_unrelated_word(self) -> None:
        items = [
            {"id": "us-2019", "title": "Us", "year": "2019"},
            {"id": "suspiria-1977", "title": "Suspiria", "year": "1977"},
        ]
        results = search_catalog_items(items, "Us 2019")
        self.assertEqual([row["id"] for row in results], ["us-2019"])

    def test_short_candidate_word_does_not_bleed_into_a_query_by_letter_overlap(self) -> None:
        items = [
            {"id": "heat-1995", "title": "Heat", "year": "1995"},
            {"id": "different-film", "title": "A Different Film", "year": "2018"},
        ]
        results = search_catalog_items(items, "Heat")
        self.assertEqual([row["id"] for row in results], ["heat-1995"])

    def test_cast_and_description_do_not_count_as_title_search_evidence(self) -> None:
        items: list[dict[str, object]] = [
            {"id": "heat-1995", "title": "Heat", "year": "1995"},
            {
                "id": "different-film",
                "title": "A Different Film",
                "year": "2018",
                "cast": ["Heather Young"],
            },
            {
                "id": "moonlight-2016",
                "title": "Moonlight",
                "year": "2016",
                "description": "Heat and humidity frame one short scene, "
                "but this is a different work.",
            },
        ]
        results = search_catalog_items(items, "Heat")
        self.assertEqual([row["id"] for row in results], ["heat-1995"])

    def test_genre_and_tags_are_not_searchable_by_the_main_search_box(self) -> None:
        items = [{"id": "one", "title": "Some Movie", "genres": ["Horror"], "tags": ["Horror"]}]
        self.assertEqual(search_catalog_items(items, "Horror"), [])

    def test_a_year_disambiguated_query_drops_the_wrong_year_title_match(self) -> None:
        # Also guards [Q7]'s alternate-reading rescue: "It 2017" is itself an
        # "ambiguous" single-year-token query by that fix's own definition,
        # so a naive rescue could have let the unsplit reading ("it 2017",
        # scored with no year signal) resurrect it-1990. It doesn't, because
        # that reading's raw text match against "It" alone never clears
        # SearchStrategy.ambiguous_year_alternate_floor.
        items = [
            {"id": "it-2017", "title": "It", "year": "2017"},
            {"id": "it-1990", "title": "It", "year": "1990"},
        ]
        results = search_catalog_items(items, "It 2017")
        self.assertEqual([row["id"] for row in results], ["it-2017"])

    def test_a_verbatim_alias_rescues_a_result_the_year_split_would_otherwise_discard(
        self,
    ) -> None:
        # Catalog-search counterpart of the [Q7] fix in
        # tests/test_search.py's ExternalResultScoreStrategyTests -- same
        # underlying ambiguity, but through _catalog_search_score's own
        # separate year-bonus/penalty logic rather than external_result_score.
        items = [
            {"id": "decoy", "title": "Verano", "year": "1993", "kind": "pelicula"},
            {
                "id": "real-target",
                "title": "Estiu 1993",
                "spanish_title": "Verano 1993",
                "year": "2017",
                "kind": "pelicula",
            },
        ]
        results = search_catalog_items(items, "Verano 1993")
        self.assertEqual({row["id"] for row in results}, {"decoy", "real-target"})

    def test_a_verbatim_alias_rescue_still_works_past_the_large_catalog_prefilter(
        self,
    ) -> None:
        # The >=200 item prefilter (_catalog_search_positions) picks
        # candidate positions by the rarest exact query token. Untested
        # before [Q7]: it must union the primary and alternate readings'
        # rarest positions separately, not merge their terms into one pool --
        # merging risks a rare alternate-only token like "1993" winning the
        # single-rarest-term selection and excluding every primary-reading
        # match that doesn't happen to share it (the decoy below, whose only
        # "1993" is in its year field, never its title text).
        filler = [
            {"id": f"filler-{index}", "title": f"Filler Title Number {index}", "year": "2010"}
            for index in range(250)
        ]
        items = filler + [
            {"id": "decoy", "title": "Verano", "year": "1993", "kind": "pelicula"},
            {
                "id": "real-target",
                "title": "Estiu 1993",
                "spanish_title": "Verano 1993",
                "year": "2017",
                "kind": "pelicula",
            },
        ]
        results = search_catalog_items(items, "Verano 1993")
        self.assertEqual({row["id"] for row in results}, {"decoy", "real-target"})

    def test_comparing_a_remake_does_not_surface_the_wrong_year_original(self) -> None:
        items = [
            {"id": "the-fly-1986", "title": "The Fly", "year": "1986", "kind": "pelicula"},
            {"id": "the-fly-1958", "title": "The Fly", "year": "1958", "kind": "pelicula"},
        ]
        results = rank_catalog_candidates(
            items, {"title": "The Fly", "year": "1986", "kind": "pelicula"}
        )
        self.assertEqual([row["id"] for row in results], ["the-fly-1986"])

    def test_a_numeric_title_with_a_disambiguating_year_is_found(self) -> None:
        items = [
            {"id": "1917-2019", "title": "1917", "year": "2019"},
            {"id": "1917-legacy-bad-year", "title": "1917", "year": "1917"},
        ]
        results = search_catalog_items(items, "1917 2019")
        self.assertEqual([row["id"] for row in results], ["1917-2019"])

    def test_a_leading_year_shaped_title_is_still_searchable(self) -> None:
        items = [{"id": "odyssey", "title": "2001: A Space Odyssey", "year": "1968"}]
        results = search_catalog_items(items, "2001: A Space Odyssey")
        self.assertEqual([row["id"] for row in results], ["odyssey"])

    def test_a_distinctive_token_avoids_generic_large_catalog_matches(self) -> None:
        items = [
            {"id": str(index), "title": f"Anime Title {index}", "kind": "anime"}
            for index in range(300)
        ]

        results = search_catalog_items(items, "Anime Title 287")

        self.assertEqual([row["id"] for row in results], ["287"])


if __name__ == "__main__":
    unittest.main()
