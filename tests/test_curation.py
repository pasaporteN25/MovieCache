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

    def test_duplicate_case_summaries_expose_added_at_and_local_files_for_disambiguation(
        self,
    ) -> None:
        items = curation_rows(
            [
                normalize_item(
                    {
                        "id": "heat-local",
                        "title": "Heat",
                        "year": "1995",
                        "source": "local_files",
                        "added_at": "2026-01-01T00:00:00+00:00",
                        "local_files": [{"path": "D:/Heat.mkv", "name": "Heat.mkv"}],
                    }
                ),
                normalize_item(
                    {
                        "id": "heat-imdb",
                        "title": "Heat",
                        "year": "1995",
                        "source": "imdb",
                        "added_at": "2026-02-01T00:00:00+00:00",
                    }
                ),
            ]
        )

        payload = build_curation_payload(items)

        duplicate_cases = [case for case in payload["cases"] if case["type"] == "duplicate"]
        self.assertEqual(len(duplicate_cases), 1)
        sides = {member["id"]: member for member in duplicate_cases[0]["members"]}
        self.assertEqual(sides["heat-local"]["added_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(sides["heat-imdb"]["added_at"], "2026-02-01T00:00:00+00:00")
        self.assertEqual(sides["heat-local"]["local_files"][0]["name"], "Heat.mkv")
        self.assertEqual(sides["heat-imdb"]["local_files"], [])

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

    def test_not_duplicate_on_one_edge_of_a_trio_still_leaves_a_connected_path(self) -> None:
        """One dismissed edge does not split a still-connected three-member case."""
        with tempfile.TemporaryDirectory() as temporary:
            repository = JsonCatalogRepository(Path(temporary) / "catalog.json", normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-c", "title": "Heat", "year": "1995"}),
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
            duplicate_cases = [case for case in payload["cases"] if case["type"] == "duplicate"]
            self.assertEqual(payload["counts"]["duplicates"], 1)
            self.assertEqual(
                {member["id"] for member in duplicate_cases[0]["members"]},
                {"heat-a", "heat-b", "heat-c"},
            )

    def test_cross_file_group_with_colliding_ids_is_disambiguated_by_source_file(self) -> None:
        """Cross-file id collisions remain distinct members of one group."""
        items = [
            *curation_rows(
                [normalize_item({"id": "same-id", "title": "Heat", "year": "1995"})],
                source_file="catalog-a.json",
            ),
            *curation_rows(
                [
                    normalize_item({"id": "same-id", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "other", "title": "Heat", "year": "1995"}),
                ],
                source_file="catalog-b.json",
            ),
        ]

        payload = build_curation_payload(items)

        duplicate_cases = [case for case in payload["cases"] if case["type"] == "duplicate"]
        self.assertEqual(payload["counts"]["duplicates"], 1)
        refs = {member["ref"] for member in duplicate_cases[0]["members"]}
        self.assertEqual(
            refs,
            {
                "same-id::catalog-a.json",
                "same-id::catalog-b.json",
                "other::catalog-b.json",
            },
        )

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
                    "partial_link": 0,
                    "deferred": 1,
                },
            )

            service.update_link_curation("heat", "pending")
            pending = build_curation_payload(curation_rows(repository.read()))
            self.assertEqual(pending["counts"]["missing_link"], 1)
            self.assertEqual(pending["counts"]["deferred"], 0)

    def test_partial_link_counts_items_with_one_or_two_of_three_sources(self) -> None:
        items = curation_rows(
            [
                normalize_item({"id": "no-links", "title": "A"}),
                normalize_item(
                    {
                        "id": "one-source",
                        "title": "B",
                        "imdb_url": "https://www.imdb.com/title/tt0000001/",
                    }
                ),
                normalize_item(
                    {
                        "id": "two-sources",
                        "title": "C",
                        "wikipedia_url": "https://en.wikipedia.org/wiki/C",
                        "imdb_url": "https://www.imdb.com/title/tt0000002/",
                    }
                ),
                normalize_item(
                    {
                        "id": "three-sources",
                        "title": "D",
                        "wikipedia_url": "https://en.wikipedia.org/wiki/D",
                        "imdb_url": "https://www.imdb.com/title/tt0000003/",
                        "filmaffinity_url": "https://www.filmaffinity.com/es/film456.html",
                    }
                ),
            ]
        )

        payload = build_curation_payload(items)

        self.assertEqual(payload["counts"]["partial_link"], 2)

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
            assert loaded is not None
            self.assertEqual(loaded.link_curation_status, "not_required")
            self.assertEqual(loaded.duplicate_decisions["heat-b::catalog.db"]["status"], "deferred")


if __name__ == "__main__":
    unittest.main()
