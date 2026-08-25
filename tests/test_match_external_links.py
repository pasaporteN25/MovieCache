from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from movie_inbox.cli.match_external_links import main
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository


def _run(catalog_path: Path, output_path: Path, *extra_args: str) -> int:
    with redirect_stdout(io.StringIO()):
        return main([str(catalog_path), "--json", str(output_path), "--delay", "0", *extra_args])


class MatchExternalLinksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog_path = self.root / "catalog.json"
        self.output_path = self.root / "catalog-linked.json"

    @patch("movie_inbox.cli.match_external_links.enrich_external_result", side_effect=lambda r: r)
    @patch("movie_inbox.cli.match_external_links.search_external_sources")
    def test_a_wikipedia_and_an_imdb_match_in_the_same_run_are_both_merged(
        self, search, _enrich
    ) -> None:
        # This is the bug E2 fixes: rank_candidates() ranks all 3 sources
        # together, and merging only candidates[0] (the old behavior) would
        # keep whichever of these two scored marginally higher and silently
        # drop the other -- permanently, since the item would no longer look
        # "missing a link" on the next run.
        search.return_value = (
            [
                {
                    "source": "wikipedia",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                    "url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                },
                {
                    "source": "imdb",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                    "url": "https://www.imdb.com/title/tt0113277/",
                },
            ],
            {},
        )
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )

        status = _run(self.catalog_path, self.output_path)

        self.assertEqual(status, 0)
        items = JsonCatalogRepository(self.output_path, normalize_item).read()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].wikipedia_url, "https://en.wikipedia.org/wiki/Heat_(1995_film)")
        self.assertEqual(items[0].imdb_url, "https://www.imdb.com/title/tt0113277/")

    @patch("movie_inbox.cli.match_external_links.enrich_external_result", side_effect=lambda r: r)
    @patch("movie_inbox.cli.match_external_links.search_external_sources")
    def test_report_lists_every_merged_source_for_the_item(self, search, _enrich) -> None:
        search.return_value = (
            [
                {
                    "source": "wikipedia",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                    "url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                },
                {
                    "source": "imdb",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                    "url": "https://www.imdb.com/title/tt0113277/",
                },
            ],
            {},
        )
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        report_path = self.root / "report.json"

        _run(self.catalog_path, self.output_path, "--report", str(report_path))

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(len(report["matched"]), 1)
        merged_sources = {row["source"] for row in report["matched"][0]["sources"]}
        self.assertEqual(merged_sources, {"wikipedia", "imdb"})
        self.assertEqual(report["needs_review"], [])
        self.assertEqual(report["unmatched"], [])

    @patch("movie_inbox.cli.match_external_links.enrich_external_result", side_effect=lambda r: r)
    @patch("movie_inbox.cli.match_external_links.search_external_sources")
    def test_target_coverage_can_be_relaxed_to_skip_partially_linked_items(
        self, search, _enrich
    ) -> None:
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                        "imdb_url": "https://www.imdb.com/title/tt0113277/",
                    }
                )
            ]
        )
        search.return_value = ([], {})

        _run(self.catalog_path, self.output_path, "--target-coverage", "2")

        search.assert_not_called()

    @patch("movie_inbox.cli.match_external_links.enrich_external_result", side_effect=lambda r: r)
    @patch("movie_inbox.cli.match_external_links.search_external_sources")
    def test_default_target_coverage_still_searches_a_two_of_three_item(
        self, search, _enrich
    ) -> None:
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                        "imdb_url": "https://www.imdb.com/title/tt0113277/",
                    }
                )
            ]
        )
        search.return_value = ([], {})

        _run(self.catalog_path, self.output_path)

        search.assert_called_once()

    @patch("movie_inbox.cli.match_external_links.enrich_external_result", side_effect=lambda r: r)
    @patch("movie_inbox.cli.match_external_links.search_external_sources")
    def test_unmatched_and_needs_review_are_reported_distinctly(self, search, _enrich) -> None:
        def fake_search(
            query: str, source: str
        ) -> tuple[list[dict[str, object]], dict[str, object]]:
            if "Heat" in query:
                return (
                    [
                        {
                            "source": "wikipedia",
                            "title": "Heat",
                            "year": "1986",  # wrong year -- rejected by decide_match
                            "kind": "pelicula",
                            "url": "https://en.wikipedia.org/wiki/Heat_(1986_film)",
                        }
                    ],
                    {},
                )
            return ([], {})

        search.side_effect = fake_search
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}),
                normalize_item({"id": "obscure", "title": "Obscure Title", "year": "2001"}),
            ]
        )
        report_path = self.root / "report.json"

        _run(self.catalog_path, self.output_path, "--report", str(report_path))

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["matched"], [])
        self.assertEqual([row["id"] for row in report["needs_review"]], ["heat"])
        self.assertEqual([row["id"] for row in report["unmatched"]], ["obscure"])


if __name__ == "__main__":
    unittest.main()
