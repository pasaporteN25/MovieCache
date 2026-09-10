"""[B1]: a shared article is not evidence that two titles are related.

Measured on the golden corpus before touching anything: every homonym case --
"The Fly", "The Gift" -- dragged unrelated films into its top five, and the
score doing the dragging came entirely from the leading article. That took
Precision@5 from 0.933 to 1.000 and strict cases from 26/29 to 29/29, with
Recall@5 and auto-match precision unchanged at 1.000.

The direction matters as much as the result: dropping articles can only lower a
similarity, so it cannot turn a non-match into a match. No auto-match becomes
possible that was not possible before, which is what keeps v0.3.0's
zero-known-false-positives gate intact.
"""

from __future__ import annotations

import unittest

from movie_inbox.domain.catalog import FUNCTION_WORDS, title_similarity
from movie_inbox.domain.search import search_key, text_match_score
from movie_inbox.domain.search_strategy import PRODUCTION_BASELINE


def _score(query: str, candidate: str) -> float:
    key = search_key(query)
    return text_match_score(search_key(candidate), key, tuple(key.split()))


class TitleSimilarityArticleTests(unittest.TestCase):
    def test_two_unrelated_films_sharing_an_article_are_not_similar(self) -> None:
        # This was 0.5 -- the same score it gave a genuine near miss.
        self.assertEqual(title_similarity("the fly", "the gift"), 0.0)
        self.assertEqual(title_similarity("los siete samurais", "los olvidados"), 0.0)
        self.assertEqual(title_similarity("das boot", "das experiment"), 0.0)

    def test_a_shared_content_word_still_counts(self) -> None:
        # "the" is discounted, "fly" is not: the rule removes noise, it does not
        # start ruling on which real words matter.
        self.assertGreater(title_similarity("the fly", "the fly returns"), 0.0)
        self.assertEqual(title_similarity("the fly", "the fly"), 1.0)

    def test_an_article_no_longer_inflates_a_partial_match(self) -> None:
        # "dawn of the dead" vs "shaun of the dead" share "of" and "dead" as
        # well as "the"; the real overlap survives, the article stops padding it.
        similarity = title_similarity("dawn of the dead", "shaun of the dead")
        self.assertGreater(similarity, 0.0)
        self.assertLess(similarity, 1.0)

    def test_a_title_that_is_only_an_article_still_compares(self) -> None:
        # Bunuel's "El" is a real film. With no content word on one side there
        # is nothing to compare, so the plain overlap stands rather than being
        # replaced by an empty one.
        self.assertEqual(title_similarity("el", "el"), 1.0)
        self.assertGreater(title_similarity("el", "el angel exterminador"), 0.0)

    def test_it_can_only_ever_lower_a_score(self) -> None:
        # The property that keeps the auto-match gate safe, stated directly.
        pairs = [
            ("the fly", "the gift"),
            ("the fly", "the fly"),
            ("dawn of the dead", "shaun of the dead"),
            ("un chien andalou", "una mujer"),
            ("heat", "heat"),
        ]
        for left, right in pairs:
            with self.subTest(pair=(left, right)):
                left_terms, right_terms = set(left.split()), set(right.split())
                original = len(left_terms & right_terms) / max(len(left_terms), len(right_terms))
                self.assertLessEqual(title_similarity(left, right), original)


class SearchScoreArticleTests(unittest.TestCase):
    def test_an_article_alone_does_not_clear_the_admission_floor(self) -> None:
        floor = PRODUCTION_BASELINE.catalog_admission_threshold
        for query, candidate in (
            ("The Fly", "The Gift"),
            ("The Fly", "The Beautiful Person"),
            ("El secreto de sus ojos", "El angel exterminador"),
        ):
            with self.subTest(query=query, candidate=candidate):
                self.assertLess(_score(query, candidate), floor)

    def test_a_near_miss_still_surfaces(self) -> None:
        # The point is to drop noise, not to hide anything a person might have
        # meant. "The Flies" is a plausible thing to be looking for.
        floor = PRODUCTION_BASELINE.catalog_admission_threshold
        self.assertGreaterEqual(_score("The Fly", "The Flies"), floor)
        self.assertGreaterEqual(_score("The Fly", "Fly Away Home"), floor)

    def test_an_exact_title_is_untouched(self) -> None:
        self.assertEqual(_score("The Fly", "The Fly"), 100.0)
        self.assertEqual(_score("Heat", "Heat"), 100.0)


class FunctionWordListTests(unittest.TestCase):
    def test_it_holds_articles_and_leaves_the_ambiguous_words_alone(self) -> None:
        for article in ("the", "a", "an", "el", "la", "los", "das", "il", "o"):
            with self.subTest(word=article):
                self.assertIn(article, FUNCTION_WORDS)
        # Prepositions and conjunctions stay out on purpose: they carry more
        # weight in a title than they look like they do, and discounting them
        # would start deciding which real words matter.
        for carrier in ("de", "of", "and", "y", "en", "para", "con"):
            with self.subTest(word=carrier):
                self.assertNotIn(carrier, FUNCTION_WORDS)


if __name__ == "__main__":
    unittest.main()
