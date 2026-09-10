"""[B1]: letters shared inside a word are not a shared word.

Found by adding "M. Butterfly" to the golden corpus for an unrelated case.
Searching for "The Fly" ranked it at 32.2 -- above "The Flies" (29.0) and
"Fly Away Home" (31.0), the two titles a person looking for "The Fly" might
actually have meant. Two separate rules were paying for the same coincidence:

  1. a query term counted as present when it appeared anywhere inside a
     title's word, so "fly" was found in "butterfly";
  2. when nothing matched, the leftover character comparison ran over the raw
     strings, so "the" and "butterfly" shared letters worth a score.

With both anchored, "M. Butterfly" scores 24.9 and drops below the admission
floor, while the near misses keep their places. The golden corpus states it
outright as a forbidden id: without the fix the quality gate FAILS with one
forbidden hit, with it 30/30 and every metric at 1.000.
"""

from __future__ import annotations

import unittest

from movie_inbox.domain.search import search_key, text_match_score
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE

_FLOOR = PRODUCTION_BASELINE.catalog_admission_threshold


def _score(query: str, candidate: str) -> float:
    key = search_key(query)
    return text_match_score(search_key(candidate), key, tuple(key.split()))


class WordBoundaryTests(unittest.TestCase):
    def test_a_short_word_inside_a_longer_one_is_not_a_match(self) -> None:
        self.assertLess(_score("The Fly", "M. Butterfly"), _FLOOR)
        self.assertLess(_score("Butterfly", "The Fly Room"), _FLOOR)

    def test_the_titles_a_person_might_have_meant_still_surface(self) -> None:
        # The point is to drop a coincidence, not to narrow the search.
        self.assertGreaterEqual(_score("The Fly", "The Flies"), _FLOOR)
        self.assertGreaterEqual(_score("The Fly", "Fly Away Home"), _FLOOR)

    def test_the_near_miss_now_outranks_the_coincidence(self) -> None:
        self.assertGreater(_score("The Fly", "The Flies"), _score("The Fly", "M. Butterfly"))
        self.assertGreater(_score("The Fly", "Fly Away Home"), _score("The Fly", "M. Butterfly"))

    def test_a_word_still_reaches_its_own_root(self) -> None:
        # What the substring test was for: plurals and compounds finding the
        # word they are built on. Anchoring it at the start keeps all of that.
        self.assertGreaterEqual(_score("Cancion triste", "Canciones tristes"), _FLOOR)
        self.assertGreaterEqual(_score("Dead calm", "Deadpool calmo"), _FLOOR)

    def test_a_long_term_keeps_its_tolerance_for_a_prefix_it_lacks(self) -> None:
        # The fuzzy test sits underneath for terms of five characters or more,
        # so the anchor does not cost a typo its match.
        self.assertGreaterEqual(_score("Terminator 2", "Exterminator 2"), _FLOOR)


class ContentWordFallbackTests(unittest.TestCase):
    def test_an_article_cannot_pay_for_the_leftover_comparison(self) -> None:
        # No whole word matches in either pair; what is compared is what is
        # left once the articles are gone.
        self.assertLess(_score("The Fly", "M. Butterfly"), _FLOOR)
        self.assertLess(_score("The Gift", "The Beautiful Person"), _FLOOR)

    def test_a_title_that_is_only_an_article_still_compares(self) -> None:
        # Bunuel's "El". With no content word left on one side there is nothing
        # to compare, so the original comparison stands.
        self.assertEqual(_score("El", "El"), 100.0)


if __name__ == "__main__":
    unittest.main()
