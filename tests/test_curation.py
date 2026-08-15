from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.curation_service import build_curation_payload
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.sqlite_repository import SqliteCatalogRepository


def curation_rows(items, source_file: str = "catalog.json"):
    rows = [item.to_dict() for item in items]
    for row in rows:
        row["_source_file"] = source_file
    return rows


class CurationTests(unittest.TestCase):
    def test_numeric_title_with_legacy_year_is_offered_for_duplicate_review(self) -> None:
        items = curation_rows(
            [
                normalize_item(
                    {
                        "id": "legacy-1917",
                        "title": "1917",
                        "year": "1917",
                        "imdb_url": "https://www.imdb.com/title/tt8579674/",
                    }
                ),
                normalize_item(
                    {
                        "id": "correct-1917",
                        "title": "1917",
                        "year": "2019",
                        "wikipedia_url": "https://en.wikipedia.org/wiki/1917_(2019_film)",
                    }
                ),
            ]
        )

        payload = build_curation_payload(items)

        duplicate_cases = [case for case in payload["cases"] if case["type"] == "duplicate"]
        self.assertEqual(payload["counts"]["duplicates"], 1)
        self.assertEqual(len(duplicate_cases), 1)
        self.assertIn(
            "Una ficha parece usar el título numérico como año heredado",
            duplicate_cases[0]["evidence"],
        )

    def test_remakes_with_different_years_are_not_automatically_duplicate_cases(self) -> None:
        items = curation_rows(
            [
                normalize_item({"id": "heat-1986", "title": "Heat", "year": "1986"}),
                normalize_item({"id": "heat-1995", "title": "Heat", "year": "1995"}),
            ]
        )

        payload = build_curation_payload(items)

        self.assertEqual(payload["counts"]["duplicates"], 0)

    def test_not_duplicate_decision_removes_the_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = JsonCatalogRepository(Path(temporary) / "catalog.json", normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                ]
            )
            service = CatalogService(repository)
            updated, reason = service.update_duplicate_curation(
                "heat-a",
                "heat-b::catalog.json",
                "not_duplicate",
            )

            self.assertTrue(updated)
            self.assertEqual(reason, "updated")
            payload = build_curation_payload(curation_rows(repository.read()))
            self.assertEqual(payload["counts"]["duplicates"], 0)
            self.assertNotIn("duplicate", {case["type"] for case in payload["cases"]})

    def test_deferred_cases_can_return_to_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = JsonCatalogRepository(Path(temporary) / "catalog.json", normalize_item)
            repository.write([normalize_item({"id": "heat", "title": "Heat"})])
            service = CatalogService(repository)

            service.update_link_curation("heat", "deferred")
            deferred = build_curation_payload(curation_rows(repository.read()))
            self.assertEqual(
                deferred["counts"],
                {
                    "pending": 0,
                    "duplicates": 0,
                    "missing_link": 0,
                    "deferred": 1,
                },
            )

            service.update_link_curation("heat", "pending")
            pending = build_curation_payload(curation_rows(repository.read()))
            self.assertEqual(pending["counts"]["missing_link"], 1)
            self.assertEqual(pending["counts"]["deferred"], 0)

    def test_sqlite_persists_curation_decisions_relationally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.db", normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                ]
            )
            service = CatalogService(repository)
            service.update_link_curation("heat-a", "not_required")
            service.update_duplicate_curation("heat-a", "heat-b::catalog.db", "deferred")

            loaded = repository.get("heat-a")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.link_curation_status, "not_required")
            self.assertEqual(loaded.duplicate_decisions["heat-b::catalog.db"]["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
