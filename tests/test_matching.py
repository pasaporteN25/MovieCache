from __future__ import annotations

import sys
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from movie_inbox.domain.catalog import external_source_name, trusted_external_url
from movie_inbox.domain.matching import decide_match


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


if __name__ == "__main__":
    unittest.main()
