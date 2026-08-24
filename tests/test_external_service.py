from __future__ import annotations

import unittest
from collections.abc import Callable
from typing import Any

from movie_inbox.application.external_service import ExternalCatalogService
from movie_inbox.external.registry import ExternalSourceService


class FakeGateway:
    def __init__(self) -> None:
        self.loader_calls = 0

    def search(
        self, query: str, source: str = "all"
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return ([{"title": query, "source": source, "url": ""}], {"ok": True})

    def selected_metadata(
        self,
        url: str,
        loader: Callable[[str], dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        self.loader_calls += 1
        return loader(url), False

    def snapshot(self, cache_hit: bool | None = None) -> dict[str, Any]:
        return {"healthy": True}


class FakeAdapter:
    label = "Fake"

    def __init__(self, name: str) -> None:
        self.name = name

    def search(self, query: str) -> list[dict[str, Any]]:
        return [
            {
                "title": f"{query} {position}",
                "source": self.name,
                "url": f"https://{self.name}.example/{position}",
            }
            for position in range(10)
        ]


class FlakyAdapter:
    name = "wikipedia"
    label = "Wikipedia"

    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str) -> list[dict[str, Any]]:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("temporary lookup failure")
        return [{"title": query, "source": self.name, "url": "https://en.wikipedia.org/wiki/Heat"}]


class RelevanceAdapter:
    name = "wikipedia"
    label = "Wikipedia"

    def search(self, query: str) -> list[dict[str, Any]]:
        return [
            {
                "title": "Evil Dead Rise",
                "year": "2023",
                "source": self.name,
                "url": "https://example.test/1",
            },
            {
                "title": "Evil Dead Burn",
                "year": "2026",
                "source": self.name,
                "url": "https://example.test/2",
            },
        ]


class ExternalCatalogServiceTests(unittest.TestCase):
    def test_registry_preserves_eight_results_for_each_source(self) -> None:
        service = ExternalSourceService(
            [FakeAdapter("wikipedia"), FakeAdapter("imdb"), FakeAdapter("filmaffinity")]
        )

        results, _ = service.search("Heat")

        self.assertEqual(len(results), 24)
        self.assertEqual([row["source"] for row in results[:8]], ["wikipedia"] * 8)
        self.assertEqual([row["source"] for row in results[8:16]], ["imdb"] * 8)
        self.assertEqual([row["source"] for row in results[16:]], ["filmaffinity"] * 8)

    def test_failed_search_is_not_cached_as_an_empty_result(self) -> None:
        adapter = FlakyAdapter()
        service = ExternalSourceService([adapter])

        first, _ = service.search("Heat")
        second, _ = service.search("Heat")

        self.assertEqual(first, [])
        self.assertEqual(second[0]["title"], "Heat")
        self.assertEqual(adapter.calls, 2)

    def test_external_results_are_ranked_by_title_and_year(self) -> None:
        service = ExternalSourceService([RelevanceAdapter()])

        results, _ = service.search("Evil Dead Burn 2026")

        self.assertEqual(results[0]["title"], "Evil Dead Burn")

    def test_low_relevance_results_are_dropped_instead_of_just_ranked_last(self) -> None:
        service = ExternalSourceService([RelevanceAdapter()])

        results, _ = service.search("Evil Dead Burn 2026")

        # "Evil Dead Rise" (2023) shares two of three title words but is a
        # different, wrong-year work -- it should be filtered out entirely,
        # not merely ranked below the correct "Evil Dead Burn" (2026).
        self.assertEqual([row["title"] for row in results], ["Evil Dead Burn"])

    def test_search_and_snapshot_are_delegated(self) -> None:
        gateway = FakeGateway()
        service = ExternalCatalogService(gateway, lambda _: {})

        results, state = service.search("Heat", "imdb")

        self.assertEqual(results[0]["title"], "Heat")
        self.assertEqual(results[0]["source"], "imdb")
        self.assertEqual(state, {"ok": True})
        self.assertEqual(service.snapshot(), {"healthy": True})

    def test_enrich_uses_injected_metadata_loader(self) -> None:
        gateway = FakeGateway()
        service = ExternalCatalogService(
            gateway,
            lambda _: {
                "title": "Heat",
                "spanish_title": "Fuego contra fuego",
                "duration_minutes": 172,
                "countries": ["Estados Unidos"],
                "original_languages": ["inglés"],
                "producers": ["Art Linson"],
                "composers": ["Elliot Goldenthal"],
                "genres": ["Crime"],
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
            },
        )

        result = service.enrich(
            {
                "title": "Heat",
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt0113277/",
            }
        )

        self.assertEqual(result["spanish_title"], "Fuego contra fuego")
        self.assertEqual(result["duration_minutes"], 172)
        self.assertEqual(result["countries"], ["Estados Unidos"])
        self.assertEqual(result["original_languages"], ["inglés"])
        self.assertEqual(result["producers"], ["Art Linson"])
        self.assertEqual(result["composers"], ["Elliot Goldenthal"])
        self.assertEqual(result["genres"], ["Crime"])
        self.assertEqual(result["imdb_url"], "https://www.imdb.com/title/tt0113277/")
        self.assertEqual(gateway.loader_calls, 1)

    def test_enrich_rejects_mismatched_source_and_host(self) -> None:
        gateway = FakeGateway()
        service = ExternalCatalogService(gateway, lambda _: {"title": "Wrong"})

        original = {
            "title": "Heat",
            "source": "imdb",
            "url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
        }
        self.assertEqual(service.enrich(original), original)
        self.assertEqual(gateway.loader_calls, 0)

    def test_enrich_preserves_replaced_search_title_as_an_alias(self) -> None:
        gateway = FakeGateway()
        service = ExternalCatalogService(
            gateway,
            lambda _: {
                "title": "La Belle Personne",
                "original_title": "La Belle Personne",
                "spanish_title": "La bella persona",
                "alternative_titles": ["A Bela Junie"],
            },
        )

        result = service.enrich(
            {
                "title": "The Beautiful Person",
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt1263778/",
            }
        )

        self.assertEqual(result["title"], "La Belle Personne")
        self.assertEqual(result["alternative_titles"], ["A Bela Junie", "The Beautiful Person"])

    def test_enrich_does_not_replace_a_title_with_an_imdb_identifier(self) -> None:
        gateway = FakeGateway()
        service = ExternalCatalogService(
            gateway,
            lambda _: {
                "title": "tt0091064",
                "english_title": "tt0091064",
                "description": "David Cronenberg film",
            },
        )

        result = service.enrich(
            {
                "title": "The Fly",
                "english_title": "The Fly",
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt0091064/",
            }
        )

        self.assertEqual(result["title"], "The Fly")
        self.assertEqual(result["english_title"], "The Fly")


if __name__ == "__main__":
    unittest.main()
