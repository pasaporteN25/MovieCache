"""[B2.3] A title Wikipedia redirects to an article is a name of that article.

Found by the live measurement of [B2.2]: `Sen to Chihiro no kamikakushi` returned
nothing from Wikipedia, though English Wikipedia redirects it to "Spirited Away".
The adapter did find the article. Its row was then scored against a query it
shares no words with (16.6, under the 28.0 relevance floor) and the registry
threw it away, and the alias retry that was meant to cover exactly this went to
English Wikipedia looking for the Japanese and the Spanish title, neither of
which is an English article title.

What was lost is a fact Wikipedia states in the response itself: the
`redirects` list. These tests hold that it is kept, that it is kept only where it
is true, and -- the part that would fail without the fix -- that the work is on
the shelf the registry hands back.
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock
from urllib.parse import unquote

from movie_inbox.domain.search import EXTERNAL_RELEVANCE_THRESHOLD, external_result_score
from movie_inbox.external import common as external_common
from movie_inbox.external import filmaffinity as external_filmaffinity
from movie_inbox.external.registry import ExternalSourceService
from movie_inbox.external.wikipedia import WikipediaAdapter, _with_redirect_titles

QUERY = "Sen to Chihiro no kamikakushi"
EN_ARTICLE = {
    "title": "Spirited Away",
    "canonicalurl": "https://en.wikipedia.org/wiki/Spirited_Away",
    "extract": "Spirited Away is a 2001 Japanese animated fantasy film by Hayao Miyazaki.",
}
ES_ARTICLE = {
    "title": "El viaje de Chihiro",
    "canonicalurl": "https://es.wikipedia.org/wiki/El_viaje_de_Chihiro",
    "extract": "El viaje de Chihiro es una película de animación japonesa de 2001.",
}


def _row(title: str, **extra: Any) -> dict[str, Any]:
    return {"title": title, "url": f"https://en.wikipedia.org/wiki/{title}", **extra}


def _raw(*redirects: tuple[str, str]) -> dict[str, Any]:
    return {"query": {"redirects": [{"from": asked, "to": target} for asked, target in redirects]}}


class RedirectTitleTests(unittest.TestCase):
    def test_the_title_that_was_asked_becomes_a_name_of_the_article(self) -> None:
        rows = _with_redirect_titles([_row("Spirited Away")], _raw((QUERY, "Spirited Away")))

        self.assertEqual(rows[0]["alternative_titles"], [QUERY])

    def test_every_title_that_leads_to_the_article_through_a_chain_is_kept(self) -> None:
        rows = _with_redirect_titles(
            [_row("Spirited Away")],
            _raw(("Sen to Chihiro", QUERY), (QUERY, "Spirited Away")),
        )

        self.assertEqual(sorted(rows[0]["alternative_titles"]), sorted([QUERY, "Sen to Chihiro"]))

    def test_a_loop_of_redirects_does_not_hang_and_names_nothing_it_cannot_reach(self) -> None:
        rows = _with_redirect_titles([_row("Spirited Away")], _raw(("A", "B"), ("B", "A")))

        self.assertNotIn("alternative_titles", rows[0])

    def test_an_article_nobody_redirected_to_is_left_exactly_as_it_was(self) -> None:
        row = _row("Music of Spirited Away")

        rows = _with_redirect_titles([row, _row("Spirited Away")], _raw((QUERY, "Spirited Away")))

        self.assertEqual(rows[0], row)
        self.assertEqual(rows[1]["alternative_titles"], [QUERY])

    def test_a_response_with_no_redirects_changes_nothing(self) -> None:
        rows = [_row("Heat (1995 film)")]

        self.assertEqual(_with_redirect_titles(rows, {"query": {"pages": []}}), rows)
        self.assertEqual(_with_redirect_titles(rows, {}), rows)

    def test_a_redirect_that_only_changes_case_is_not_an_alias(self) -> None:
        rows = _with_redirect_titles(
            [_row("Der Untergang")], _raw(("der untergang", "Der Untergang"))
        )

        self.assertNotIn("alternative_titles", rows[0])

    def test_names_the_article_already_had_are_kept_and_nothing_is_added_twice(self) -> None:
        row = _row("Spirited Away", alternative_titles=["Chihiro"])

        rows = _with_redirect_titles([row], _raw((QUERY, "Spirited Away")))
        again = _with_redirect_titles(rows, _raw((QUERY, "Spirited Away")))

        self.assertEqual(rows[0]["alternative_titles"], ["Chihiro", QUERY])
        self.assertEqual(again[0]["alternative_titles"], ["Chihiro", QUERY])

    def test_the_score_goes_from_under_the_floor_to_a_match(self) -> None:
        plain = _row("Spirited Away")
        named = _with_redirect_titles([plain], _raw((QUERY, "Spirited Away")))[0]

        self.assertLess(external_result_score(QUERY, plain), EXTERNAL_RELEVANCE_THRESHOLD)
        self.assertGreaterEqual(external_result_score(QUERY, named), EXTERNAL_RELEVANCE_THRESHOLD)


class AdapterAndRegistryTests(unittest.TestCase):
    """The whole path, offline: the fix is only worth anything if it survives it."""

    def _respond(self, url: str, accept: str = "", timeout: float = 0) -> str:
        self.requested.append(url)
        empty = json.dumps({"query": {"pages": []}})
        if "generator=search" in url:
            # The search endpoint answers with other articles, never the one asked for.
            page = {
                "title": "Studio Ghibli",
                "extract": "Studio Ghibli is a film animation studio.",
            }
            return json.dumps({"query": {"pages": [page]}})
        if "titles=" not in url:
            return empty
        asked = unquote(url.split("titles=", 1)[1])
        if asked != QUERY:
            return empty
        if url.startswith("https://en."):
            redirect, article = "Spirited Away", EN_ARTICLE
        else:
            redirect, article = "El viaje de Chihiro", ES_ARTICLE
        return json.dumps(
            {
                "query": {
                    "redirects": [{"from": QUERY, "to": redirect}],
                    "pages": [article],
                }
            }
        )

    def _run(self, query: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        self.requested: list[str] = []
        with (
            mock.patch.object(external_common, "fetch_text", self._respond),
            mock.patch.object(external_filmaffinity, "fetch_text", self._respond),
        ):
            adapter_rows = WikipediaAdapter().search(query)
            self.requested_by_adapter = list(self.requested)
            service_rows, _ = ExternalSourceService(adapters=[WikipediaAdapter()]).search(
                query, source="wikipedia"
            )
        return adapter_rows, service_rows

    def test_the_registry_hands_back_the_article_wikipedia_redirected_to(self) -> None:
        _, shelf = self._run(QUERY)

        # Without the fix this shelf is empty: both rows scored under the floor.
        self.assertEqual(
            sorted(row["title"] for row in shelf), ["El viaje de Chihiro", "Spirited Away"]
        )

    def test_the_alias_retry_no_longer_has_to_fire_for_it(self) -> None:
        self._run(QUERY)

        self.assertFalse([url for url in self.requested_by_adapter if "wikidata.org" in url])

    def test_a_work_reached_by_the_search_endpoint_is_scored_as_before(self) -> None:
        adapter_rows, _ = self._run("Studio Ghibli")

        self.assertTrue(adapter_rows)
        for row in adapter_rows:
            with self.subTest(title=row["title"]):
                self.assertEqual(row["alternative_titles"], [])


if __name__ == "__main__":
    unittest.main()
