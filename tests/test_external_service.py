from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from movie_inbox.application.external_service import ExternalCatalogService


class FakeGateway:
    def __init__(self) -> None:
        self.loader_calls = 0

    def search(self, query: str, source: str = "all") -> tuple[list[dict[str, Any]], dict[str, Any]]:
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


class ExternalCatalogServiceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
