"""[B1]: how results from several sources are composed into what a person sees.

The composition is deliberately per-source: each source keeps its own shelf and
the same work found by two of them is shown twice, once under each, because they
are two records of it and not one. What must not happen is the same work
appearing twice *within* one shelf.

That is what was happening. Wikipedia reaches an article two ways -- its own
search, and an exact-title resolve when the search did not return the title
asked for -- and the two rows carried the same article under addresses that
differ only in percent-encoding: Wikipedia's own canonicalurl keeps the
parentheses of "The Fly (1986 film)" literal, while a URL built from the article
title encodes them. Nearly every film article is disambiguated that way, so this
was the common case, and it hit exactly when the query was in a different
language than the article -- which is when the resolve fires.
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock

from movie_inbox.application.search_service import group_external_results
from movie_inbox.external import common as external_common
from movie_inbox.external import filmaffinity as external_filmaffinity
from movie_inbox.external.common import dedupe_results
from movie_inbox.external.registry import ExternalSourceService
from movie_inbox.external.wikipedia import WikipediaAdapter

ARTICLE = {"title": "The Fly (1986 film)", "extract": "The Fly is a 1986 American horror film."}
CANONICAL = "https://en.wikipedia.org/wiki/The_Fly_(1986_film)"


def _row(source: str, title: str, url: str) -> dict[str, Any]:
    return {"source": source, "title": title, "url": url, "year": "1986"}


class DedupeKeyTests(unittest.TestCase):
    def test_two_spellings_of_one_address_are_one_row(self) -> None:
        rows = dedupe_results(
            [
                _row("wikipedia", "The Fly (1986 film)", CANONICAL),
                _row(
                    "wikipedia",
                    "The Fly (1986 film)",
                    "https://en.wikipedia.org/wiki/The_Fly_%281986_film%29",
                ),
            ]
        )

        self.assertEqual([row["url"] for row in rows], [CANONICAL])

    def test_a_trailing_slash_and_case_still_do_not_split_a_row(self) -> None:
        rows = dedupe_results(
            [
                _row("imdb", "Heat", "https://www.imdb.com/title/tt0113277/"),
                _row("imdb", "Heat", "https://www.IMDb.com/title/tt0113277"),
            ]
        )

        self.assertEqual(len(rows), 1)

    def test_different_works_are_not_collapsed(self) -> None:
        rows = dedupe_results(
            [
                _row("wikipedia", "The Fly (1986 film)", CANONICAL),
                _row(
                    "wikipedia",
                    "The Fly (1958 film)",
                    "https://en.wikipedia.org/wiki/The_Fly_(1958_film)",
                ),
            ]
        )

        self.assertEqual(len(rows), 2)

    def test_rows_with_no_address_fall_back_to_source_and_title(self) -> None:
        rows = dedupe_results(
            [_row("imdb", "Heat", ""), _row("imdb", "Heat", ""), _row("wikipedia", "Heat", "")]
        )

        self.assertEqual(len(rows), 2)


class WikipediaArticleReachedTwiceTests(unittest.TestCase):
    def _search(self, query: str, *, search_has_canonical: bool) -> list[dict[str, Any]]:
        self.requested: list[str] = []

        def respond(url: str, accept: str = "", timeout: float = 0) -> str:
            self.requested.append(url)
            if not url.startswith("https://en."):
                return json.dumps({"query": {"pages": []}})
            if "generator=search" in url:
                page = (
                    dict(ARTICLE, canonicalurl=CANONICAL) if search_has_canonical else dict(ARTICLE)
                )
                return json.dumps({"query": {"pages": [page]}})
            if "titles=" in url:
                return json.dumps({"query": {"pages": [dict(ARTICLE, canonicalurl=CANONICAL)]}})
            return json.dumps({"query": {"pages": []}})

        with (
            mock.patch.object(external_common, "fetch_text", respond),
            mock.patch.object(external_filmaffinity, "fetch_text", respond),
        ):
            return WikipediaAdapter().search(query)

    def test_one_article_reached_two_ways_is_one_row(self) -> None:
        # "La mosca" is not the article's title, so the exact-title resolve runs
        # alongside the search and both come back with the same article.
        rows = self._search("La mosca", search_has_canonical=False)

        self.assertEqual([row["url"] for row in rows], [CANONICAL])

    def test_the_search_asks_for_the_article_address_instead_of_guessing_it(self) -> None:
        self._search("La mosca", search_has_canonical=True)

        search_calls = [url for url in self.requested if "generator=search" in url]
        self.assertTrue(search_calls)
        for url in search_calls:
            with self.subTest(url=url):
                self.assertIn("inprop=url", url)


class PerSourceShelfTests(unittest.TestCase):
    """The part that is deliberate, guarded so nobody "fixes" it."""

    class Fixed:
        def __init__(self, name: str, rows: list[dict[str, Any]]) -> None:
            self.name, self.label, self._rows = name, name.title(), rows

        def search(self, query: str) -> list[dict[str, Any]]:
            return [dict(row) for row in self._rows]

    def test_the_same_work_from_two_sources_keeps_one_row_each(self) -> None:
        # They are two records of the work, not one. Collapsing them would throw
        # away whichever source happened to answer second.
        service = ExternalSourceService(
            [
                self.Fixed("imdb", [_row("imdb", "Heat", "https://www.imdb.com/title/tt0113277/")]),
                self.Fixed(
                    "wikipedia",
                    [_row("wikipedia", "Heat", "https://en.wikipedia.org/wiki/Heat_(1995_film)")],
                ),
            ]
        )

        results, _ = service.search("Heat")
        shelves = {name: rows for name, rows in group_external_results(results).items() if rows}

        self.assertEqual(
            {name: len(rows) for name, rows in shelves.items()}, {"imdb": 1, "wikipedia": 1}
        )


if __name__ == "__main__":
    unittest.main()
