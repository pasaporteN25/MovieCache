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
            self.assertEqual(deferred["counts"], {
                "pending": 0,
                "duplicates": 0,
                "missing_link": 0,
                "deferred": 1,
            })

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
