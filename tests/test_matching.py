from __future__ import annotations

import unittest

from movie_inbox.domain.catalog import (
    external_link_coverage,
    external_source_name,
    linked_sources,
    possible_duplicate_candidates,
    title_match_key,
    trusted_external_url,
)
from movie_inbox.domain.libraries import work_identity_key
from movie_inbox.domain.matching import decide_match
from movie_inbox.domain.search_strategy import SearchStrategy


class MatchingTests(unittest.TestCase):
    def test_exact_title_without_year_requires_review(self) -> None:
        decision = decide_match(
            {"title": "Heat", "year": "", "kind": "pelicula"},
            {"title": "Heat", "year": "1995", "kind": "pelicula"},
        )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "exact_title_missing_year")

    def test_exact_title_and_year_is_accepted(self) -> None:
        decision = decide_match(
            {"title": "Heat", "year": "1995", "kind": "pelicula"},
            {"title": "Heat", "year": "1995", "kind": "pelicula"},
        )
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.reason, "exact_title_year")

        without_kind = decide_match(
            {"title": "Heat", "year": "1995", "kind": "pelicula"},
            {"title": "Heat", "year": "1995"},
        )
        self.assertTrue(without_kind.accepted)

    def test_kind_or_year_mismatch_is_not_automatic(self) -> None:
        for candidate in (
            {"title": "Crash", "year": "2004", "kind": "pelicula"},
            {"title": "Crash", "year": "1996", "kind": "serie"},
        ):
            with self.subTest(candidate=candidate):
                self.assertFalse(
                    decide_match(
                        {"title": "Crash", "year": "1996", "kind": "pelicula"},
                        candidate,
                    ).accepted
                )

    def test_anime_and_release_format_mismatch_is_a_named_review_case(self) -> None:
        decision = decide_match(
            {"title": "Akira", "year": "1988", "kind": "anime"},
            {"title": "Akira", "year": "1988", "kind": "pelicula"},
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "exact_title_year_anime_kind_review")
        self.assertEqual(decision.evidence["taxonomy_note"], "anime_vs_release_format")

    def test_exact_title_with_a_different_year_remains_a_review_candidate(self) -> None:
        candidates = possible_duplicate_candidates(
            [{"id": "legacy-1917", "title": "1917", "year": "1917", "kind": "pelicula"}],
            {"title": "1917", "year": "2019", "kind": "pelicula"},
        )

        self.assertEqual([candidate["id"] for candidate in candidates], ["legacy-1917"])
        self.assertEqual(candidates[0]["reason"], "exact_title_year_mismatch")

        unrelated = possible_duplicate_candidates(
            [{"id": "crash-1996", "title": "Crash", "year": "1996"}],
            {"title": "Crush", "year": "2022"},
        )
        self.assertEqual(unrelated, [])

    def test_shared_external_identifier_is_strong_evidence(self) -> None:
        decision = decide_match(
            {"title": "Unknown", "imdb_url": "https://www.imdb.com/title/tt0113277/"},
            {"title": "Heat", "url": "https://imdb.com/title/tt0113277"},
        )
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.reason, "shared_external_url")

    def test_trusted_hosts_are_compared_by_hostname(self) -> None:
        self.assertEqual(external_source_name("https://www.imdb.com/title/tt0113277/"), "imdb")
        self.assertEqual(external_source_name("https://imdb.com.example.org/title/tt0113277/"), "")
        self.assertEqual(trusted_external_url("https://imdb.com.example.org/title/tt0113277/"), "")
        self.assertEqual(external_source_name("https://user@imdb.com/title/tt0113277/"), "")
        self.assertEqual(external_source_name("https://imdb.com:8443/title/tt0113277/"), "")

    def test_a_stricter_strategy_can_require_review_where_the_baseline_would_not(self) -> None:
        existing = {"title": "Heat", "year": ""}
        incoming = {"title": "Heat 2", "year": ""}

        baseline = decide_match(existing, incoming)
        stricter = decide_match(
            existing, incoming, SearchStrategy(similar_title_review_threshold=0.01)
        )

        self.assertEqual(baseline.reason, "insufficient_evidence")
        self.assertEqual(stricter.reason, "similar_title_requires_review")

    def test_linked_sources_counts_each_named_source_independently(self) -> None:
        item = {
            "url": "https://www.themoviedb.org/movie/280",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
            "imdb_url": "https://www.imdb.com/title/tt0113277/",
            "filmaffinity_url": "",
        }

        self.assertEqual(linked_sources(item), {"wikipedia", "imdb"})
        self.assertEqual(external_link_coverage(item), 2)

    def test_linked_sources_ignores_the_generic_url_field(self) -> None:
        # A generic `url` pointing at a trusted host (e.g. copied into `url`
        # instead of `wikipedia_url`) must not count -- has_external_link()/
        # external_urls() already cover that field; this one is specifically
        # about the three named per-source fields.
        item = {"url": "https://en.wikipedia.org/wiki/Heat_(1995_film)"}

        self.assertEqual(linked_sources(item), set())
        self.assertEqual(external_link_coverage(item), 0)

    def test_linked_sources_reaches_full_coverage_with_all_three(self) -> None:
        item = {
            "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
            "imdb_url": "https://www.imdb.com/title/tt0113277/",
            "filmaffinity_url": "https://www.filmaffinity.com/es/film267267.html",
        }

        self.assertEqual(linked_sources(item), {"wikipedia", "imdb", "filmaffinity"})
        self.assertEqual(external_link_coverage(item), 3)

    def test_year_shaped_titles_keep_their_identity(self) -> None:
        self.assertEqual(title_match_key("1917"), "1917")
        self.assertEqual(title_match_key("1984"), "1984")
        self.assertEqual(title_match_key("2001: A Space Odyssey"), "2001 a space odyssey")
        self.assertEqual(title_match_key("1917 2019"), "1917")
        self.assertEqual(title_match_key("Heat 1995"), "heat")
        self.assertTrue(
            work_identity_key({"title": "1917", "year": "2019", "kind": "pelicula"}).startswith(
                "work:"
            )
        )

    def test_japanese_titles_keep_their_identity(self) -> None:
        self.assertEqual(title_match_key("君の名は。"), "君の名は")
        self.assertEqual(title_match_key("がっこうぐらし!"), "がっこうぐらし")

    def test_sharing_a_director_never_produces_a_match_on_its_own(self) -> None:
        # [Q4] tareas.md safety rule: a shared director must never enable an
        # automatic merge. decide_match doesn't read "directors" at all --
        # two clearly different works by the same person stay unmatched.
        decision = decide_match(
            {"title": "Mondo Cane", "year": "1962", "directors": ["Gualtiero Jacopetti"]},
            {"title": "Africa Addio", "year": "1966", "directors": ["Gualtiero Jacopetti"]},
        )

        self.assertFalse(decision.accepted)
        self.assertLessEqual(decision.score, 0)


if __name__ == "__main__":
    unittest.main()
