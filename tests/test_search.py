from __future__ import annotations

import unittest

from movie_inbox.domain.search import parse_search_query


class ParseSearchQueryYearTests(unittest.TestCase):
    def test_a_trailing_year_disambiguates_a_numeric_title(self) -> None:
        intent = parse_search_query("1917 2019")
        self.assertEqual(intent.title, "1917")
        self.assertEqual(intent.title_key, "1917")
        self.assertEqual(intent.year, "2019")

    def test_a_lone_numeric_title_keeps_its_year_shaped_token(self) -> None:
        intent = parse_search_query("1984")
        self.assertEqual(intent.title, "1984")
        self.assertEqual(intent.title_key, "1984")
        self.assertEqual(intent.year, "")

    def test_a_leading_year_shaped_title_is_not_treated_as_a_release_year(self) -> None:
        intent = parse_search_query("2001: A Space Odyssey")
        self.assertEqual(intent.title_key, "2001 a space odyssey")
        self.assertEqual(intent.year, "")

    def test_a_normal_title_and_year_are_still_split(self) -> None:
        intent = parse_search_query("Heat 1995")
        self.assertEqual(intent.title, "Heat")
        self.assertEqual(intent.year, "1995")

    def test_a_year_inside_a_media_qualifier_is_still_captured(self) -> None:
        intent = parse_search_query("Movie Title (2019 film)")
        self.assertEqual(intent.title, "Movie Title")
        self.assertEqual(intent.year, "2019")


if __name__ == "__main__":
    unittest.main()
