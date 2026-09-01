from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from movie_inbox.application.curation_service import build_curation_payload
from movie_inbox.application.curation_workflow import (
    CatalogPointer,
    CurationConflict,
    CurationWorkflowService,
)
from movie_inbox.application.library_repository import LibraryRepository
from movie_inbox.application.library_service import AvailabilityService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.curation_history import (
    JsonCurationHistoryRepository,
    MemoryCurationHistoryRepository,
)
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository


class _FakeLibraryRepository:
    """Minimal LibraryRepository stand-in: AvailabilityService only ever calls
    .availability_records() on it."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def availability_records(self) -> list[dict[str, Any]]:
        return self._records


class CurationWorkflowTests(unittest.TestCase):
    def workflow(
        self,
        catalog_path: Path,
        *,
        availability_service: AvailabilityService | None = None,
    ) -> tuple[CurationWorkflowService, Path]:
        repositories: dict[str, JsonCatalogRepository] = {}

        def repository(path: Path) -> JsonCatalogRepository:
            key = str(Path(path).resolve())
            if key not in repositories:
                repositories[key] = JsonCatalogRepository(Path(key), normalize_item)
            return repositories[key]

        history_path = catalog_path.with_name(".history.json")
        service = CurationWorkflowService(
            repository,
            JsonCurationHistoryRepository(history_path),
            MemoryCurationHistoryRepository(),
            availability_service,
        )
        return service, history_path

    def test_reviewed_merge_preserves_identity_and_can_restore_both_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-local",
                            "title": "Heat",
                            "year": "1995",
                            "source": "local_files",
                            "status": "watched",
                            "watched_at": "2026-07-01",
                            "rating": 8,
                            "review": "Mi registro",
                            "en_catalogo": True,
                            "local_files": [{"path": "D:/Heat.mkv", "name": "Heat.mkv"}],
                        }
                    ),
                    normalize_item(
                        {
                            "id": "heat-imdb",
                            "title": "Heat",
                            "spanish_title": "Fuego contra fuego",
                            "year": "1995",
                            "source": "imdb",
                            "url": "https://www.imdb.com/title/tt0113277/",
                            "imdb_url": "https://www.imdb.com/title/tt0113277/",
                            "status": "to_watch",
                            "local_files": [{"path": "E:/Heat-alt.mkv", "name": "Heat-alt.mkv"}],
                        }
                    ),
                ]
            )
            workflow, history_path = self.workflow(catalog_path)
            left = CatalogPointer(catalog_path, "heat-local")
            right = CatalogPointer(catalog_path, "heat-imdb")

            review = workflow.compare(left, right=right)
            status = next(field for field in review["fields"] if field["key"] == "status")
            local_files = next(field for field in review["fields"] if field["key"] == "local_files")
            self.assertTrue(status["required"])
            self.assertEqual(status["default_choice"], "")
            self.assertEqual(local_files["default_choice"], "combine")

            result = workflow.merge(
                left,
                right=right,
                survivor_side="left",
                choices={"status": "left"},
                expected_review_id=review["review_id"],
                history_mode="persistent",
                session_id="session-a",
            )

            merged = repository.read()
            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0].id, "heat-local")
            self.assertEqual(merged[0].spanish_title, "Fuego contra fuego")
            self.assertEqual(len(merged[0].local_files), 2)
            self.assertEqual(merged[0].status, "watched")
            self.assertTrue(history_path.exists())

            operation_id = result["operation"]["id"]
            workflow.undo(
                operation_id,
                history_mode="persistent",
                session_id="session-a",
            )
            restored = repository.read()
            self.assertEqual([item.id for item in restored], ["heat-local", "heat-imdb"])
            self.assertEqual(restored[0].review, "Mi registro")
            history = workflow.history("persistent", "session-a")
            self.assertEqual(history["operations"][0]["status"], "undone")
            self.assertFalse(history["operations"][0]["can_undo"])

    def test_group_merge_is_one_operation_and_undo_restores_every_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-a",
                            "title": "Heat",
                            "year": "1995",
                            "rating": 9,
                            "description": "Sinopsis externa",
                            "local_files": [{"path": "D:/Heat.mkv", "name": "Heat.mkv"}],
                        }
                    ),
                    normalize_item(
                        {
                            "id": "heat-b",
                            "title": "Heat",
                            "year": "1995",
                            "rating": 4,
                        }
                    ),
                    normalize_item(
                        {
                            "id": "heat-c",
                            "title": "Heat",
                            "year": "1995",
                            "spanish_title": "Fuego contra fuego",
                            "description": "",
                            "locked_fields": ["description"],
                        }
                    ),
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            members = [
                CatalogPointer(catalog_path, "heat-a"),
                CatalogPointer(catalog_path, "heat-b"),
                CatalogPointer(catalog_path, "heat-c"),
            ]
            review = workflow.compare_group(members, survivor=members[2])
            rating = next(field for field in review["fields"] if field["key"] == "rating")
            self.assertTrue(rating["required"])
            rating_choice = next(
                member["ref"] for member in review["members"] if member["id"] == "heat-a"
            )

            result = workflow.merge_group(
                members,
                survivor=members[2],
                choices={"rating": rating_choice},
                expected_review_id=review["review_id"],
                history_mode="persistent",
                session_id="session-a",
            )

            remaining = repository.read()
            self.assertEqual([item.id for item in remaining], ["heat-c"])
            self.assertEqual(remaining[0].rating, 9)
            self.assertEqual(remaining[0].spanish_title, "Fuego contra fuego")
            self.assertEqual(remaining[0].description, "")
            self.assertIn("description", remaining[0].locked_fields)
            self.assertEqual(len(remaining[0].local_files), 1)
            history = workflow.history("persistent", "session-a")
            self.assertEqual(history["count"], 1)
            self.assertEqual(history["operations"][0]["action"], "merge_group")

            workflow.undo(
                result["operation"]["id"],
                history_mode="persistent",
                session_id="session-a",
            )
            restored = repository.read()
            self.assertEqual([item.id for item in restored], ["heat-a", "heat-b", "heat-c"])
            self.assertEqual([item.rating for item in restored], [9, 4, 0])

    def test_locked_empty_field_is_not_filled_implicitly_during_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-a",
                            "title": "Heat",
                            "description": "",
                            "locked_fields": ["description"],
                        }
                    ),
                    normalize_item(
                        {
                            "id": "heat-b",
                            "title": "Heat",
                            "description": "No debe entrar sin una decisión humana",
                        }
                    ),
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            left = CatalogPointer(catalog_path, "heat-a")
            right = CatalogPointer(catalog_path, "heat-b")
            review = workflow.compare(left, right=right)
            description = next(field for field in review["fields"] if field["key"] == "description")
            self.assertEqual(description["default_choice"], "left")

            workflow.merge(
                left,
                right=right,
                choices={},
                expected_review_id=review["review_id"],
            )

            stored = repository.get("heat-a")
            assert stored is not None
            self.assertEqual(stored.description, "")
            self.assertIn("description", stored.locked_fields)

    def test_group_merge_rejects_a_stale_review_without_partial_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-c", "title": "Heat", "year": "1995"}),
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            members = [
                CatalogPointer(catalog_path, item_id) for item_id in ("heat-a", "heat-b", "heat-c")
            ]
            review = workflow.compare_group(members)
            repository.update_item(
                "heat-b", lambda item: item.__setitem__("review", "Cambio concurrente")
            )

            with self.assertRaises(CurationConflict):
                workflow.merge_group(
                    members,
                    expected_review_id=review["review_id"],
                    history_mode="persistent",
                    session_id="session-a",
                )

            self.assertEqual(len(repository.read()), 3)
            changed = repository.get("heat-b")
            self.assertIsNotNone(changed)
            assert changed is not None
            self.assertEqual(changed.review, "Cambio concurrente")

    def test_group_history_failure_rolls_back_every_catalog(self) -> None:
        class FailingHistory(MemoryCurationHistoryRepository):
            def append(self, operation, namespace=""):
                raise OSError("disk full")

        with tempfile.TemporaryDirectory() as temporary:
            first_path = Path(temporary) / "catalog-a.json"
            second_path = Path(temporary) / "catalog-b.json"
            first = JsonCatalogRepository(first_path, normalize_item)
            second = JsonCatalogRepository(second_path, normalize_item)
            first.write([normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"})])
            second.write(
                [
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-c", "title": "Heat", "year": "1995"}),
                ]
            )

            def repository(path: Path):
                return first if path.resolve() == first_path.resolve() else second

            workflow = CurationWorkflowService(
                repository,
                FailingHistory(),
                MemoryCurationHistoryRepository(),
            )
            members = [
                CatalogPointer(first_path, "heat-a"),
                CatalogPointer(second_path, "heat-b"),
                CatalogPointer(second_path, "heat-c"),
            ]
            review = workflow.compare_group(members)

            with self.assertRaises(OSError):
                workflow.merge_group(
                    members,
                    expected_review_id=review["review_id"],
                    history_mode="persistent",
                    session_id="session-a",
                )

            self.assertEqual([item.id for item in first.read()], ["heat-a"])
            self.assertEqual([item.id for item in second.read()], ["heat-b", "heat-c"])

    def test_group_duplicate_decision_and_undo_update_all_members_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item({"id": item_id, "title": "Heat", "year": "1995"})
                    for item_id in ("heat-a", "heat-b", "heat-c")
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            members = [
                CatalogPointer(catalog_path, item_id) for item_id in ("heat-a", "heat-b", "heat-c")
            ]

            result = workflow.update_duplicate_group_decision(
                members,
                "not_duplicate",
                history_mode="persistent",
                session_id="session-a",
            )
            dismissed_rows = [item.to_dict() for item in repository.read()]
            for row in dismissed_rows:
                row["_source_file"] = str(catalog_path)
            self.assertEqual(build_curation_payload(dismissed_rows)["counts"]["duplicates"], 0)

            workflow.undo(
                result["operation"]["id"],
                history_mode="persistent",
                session_id="session-a",
            )
            restored_rows = [item.to_dict() for item in repository.read()]
            for row in restored_rows:
                row["_source_file"] = str(catalog_path)
            self.assertEqual(build_curation_payload(restored_rows)["counts"]["duplicates"], 1)

    def test_compare_and_merge_expose_availability_without_leaking_into_persisted_flag(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "server-only",
                            "title": "Heat",
                            "year": "1995",
                            "kind": "pelicula",
                            "en_catalogo": False,
                            "added_at": "2026-01-01T00:00:00+00:00",
                        }
                    ),
                    normalize_item(
                        {
                            "id": "not-scanned",
                            "title": "Sicario",
                            "year": "2015",
                            "kind": "pelicula",
                            "en_catalogo": False,
                        }
                    ),
                ]
            )
            availability_service = AvailabilityService(
                cast(
                    LibraryRepository,
                    _FakeLibraryRepository(
                        [
                            {
                                "identity": {"title": "Heat", "year": "1995", "kind": "pelicula"},
                                "library_id": "lib-1",
                                "library_name": "Biblioteca de prueba",
                                "file_count": 1,
                            }
                        ]
                    ),
                )
            )
            workflow, _ = self.workflow(catalog_path, availability_service=availability_service)
            left = CatalogPointer(catalog_path, "server-only")
            right = CatalogPointer(catalog_path, "not-scanned")

            review = workflow.compare(left, right=right)
            self.assertTrue(review["left"]["_availability"]["server"])
            self.assertFalse(review["left"]["_availability"]["manual"])
            self.assertEqual(review["left"]["added_at"], "2026-01-01T00:00:00+00:00")
            self.assertFalse(review["right"]["_availability"]["server"])
            # The raw manual flag on both sides is False, so the field-diff table
            # (used to decide what apply_reviewed_merge persists) must see them as
            # equivalent -- decorating before build_merge_review would make the
            # left side "True" and wrongly mark this field as different.
            en_catalogo_field = next(
                field for field in review["fields"] if field["key"] == "en_catalogo"
            )
            self.assertFalse(en_catalogo_field["different"])

            result = workflow.merge(
                left,
                right=right,
                survivor_side="left",
                choices={},
                expected_review_id=review["review_id"],
            )

            # The response is decorated for display...
            self.assertTrue(result["item"]["_availability"]["effective"])
            self.assertTrue(result["item"]["_availability"]["server"])
            # ...but what actually got written to disk uses the raw manual flags:
            # False, never the decorated "effective" True.
            persisted = repository.read()
            self.assertEqual(len(persisted), 1)
            self.assertFalse(persisted[0].en_catalogo)

    def test_undo_refuses_to_overwrite_a_later_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write([normalize_item({"id": "heat", "title": "Heat"})])
            workflow, _ = self.workflow(catalog_path)
            pointer = CatalogPointer(catalog_path, "heat")

            result = workflow.update_link_decision(
                pointer,
                "deferred",
                history_mode="persistent",
                session_id="session-a",
            )
            repository.update_item(
                "heat", lambda item: item.__setitem__("review", "Cambio posterior")
            )

            with self.assertRaises(CurationConflict):
                workflow.undo(
                    result["operation"]["id"],
                    history_mode="persistent",
                    session_id="session-a",
                )
            stored = repository.get("heat")
            assert stored is not None
            self.assertEqual(stored.review, "Cambio posterior")

    def test_session_history_can_be_cleared_without_touching_the_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write([normalize_item({"id": "heat", "title": "Heat"})])
            workflow, history_path = self.workflow(catalog_path)

            workflow.update_link_decision(
                CatalogPointer(catalog_path, "heat"),
                "not_required",
                history_mode="session",
                session_id="browser-session",
            )
            self.assertFalse(history_path.exists())
            self.assertEqual(workflow.history("session", "browser-session")["count"], 1)
            self.assertEqual(
                workflow.clear_history("session", "browser-session", confirmed=True),
                1,
            )
            self.assertEqual(workflow.history("session", "browser-session")["count"], 0)
            stored = repository.get("heat")
            assert stored is not None
            self.assertEqual(stored.link_curation_status, "not_required")

    def test_external_metadata_does_not_create_a_fake_personal_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat",
                            "title": "Heat",
                            "status": "watched",
                            "watched_at": "2026-07-01",
                            "rating": 9,
                        }
                    )
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            review = workflow.compare(
                CatalogPointer(catalog_path, "heat"),
                incoming={
                    "id": "imdb-heat",
                    "title": "Heat",
                    "year": "1995",
                    "source": "imdb",
                    "url": "https://www.imdb.com/title/tt0113277/",
                    "imdb_url": "https://www.imdb.com/title/tt0113277/",
                    "status": "to_watch",
                },
            )
            status = next(field for field in review["fields"] if field["key"] == "status")
            self.assertFalse(status["required"])
            self.assertEqual(status["default_choice"], "left")

    def test_external_merge_preserves_personal_data_and_can_be_undone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-local",
                            "title": "Heat",
                            "status": "watched",
                            "rating": 9,
                            "review": "Una favorita",
                            "en_catalogo": True,
                        }
                    )
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            pointer = CatalogPointer(catalog_path, "heat-local")
            incoming = {
                "id": "heat-imdb",
                "title": "Heat",
                "spanish_title": "Fuego contra fuego",
                "year": "1995",
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt0113277/",
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
            }

            review = workflow.compare(pointer, incoming=incoming)
            result = workflow.merge(
                pointer,
                incoming=incoming,
                choices={},
                expected_review_id=review["review_id"],
                history_mode="session",
                session_id="browser-session",
            )

            merged = repository.get("heat-local")
            self.assertIsNotNone(merged)
            assert merged is not None
            self.assertEqual(merged.status, "watched")
            self.assertEqual(merged.rating, 9)
            self.assertEqual(merged.review, "Una favorita")
            self.assertEqual(merged.spanish_title, "Fuego contra fuego")
            self.assertEqual(merged.imdb_url, "https://www.imdb.com/title/tt0113277/")

            workflow.undo(
                result["operation"]["id"],
                history_mode="session",
                session_id="browser-session",
            )
            restored = repository.get("heat-local")
            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual(restored.spanish_title, "")
            self.assertEqual(restored.imdb_url, "")
            self.assertEqual(restored.review, "Una favorita")

    def test_auto_resolve_merges_an_identical_trio_down_to_one_survivor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-c", "title": "Heat", "year": "1995"}),
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            items = [item.to_dict() for item in repository.read()]
            for item in items:
                item["_source_file"] = str(catalog_path)

            result = workflow.auto_resolve_duplicates(
                items, history_mode="persistent", session_id="session-a"
            )

            self.assertEqual(result["resolved"], 1)
            self.assertEqual(result["needs_review"], 0)
            self.assertEqual(len(repository.read()), 1)
            history = workflow.history("persistent", "session-a")
            self.assertEqual(history["count"], 1)
            self.assertEqual(history["operations"][0]["action"], "merge_group")

    def test_auto_resolve_on_a_quartet_with_one_conflict_leaves_the_group_intact(
        self,
    ) -> None:
        """One real conflict blocks the entire group without stale-reference noise."""
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                    normalize_item({"id": "heat-c", "title": "Heat", "year": "1995", "rating": 9}),
                    normalize_item({"id": "heat-d", "title": "Heat", "year": "1995", "rating": 4}),
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            items = [item.to_dict() for item in repository.read()]
            for item in items:
                item["_source_file"] = str(catalog_path)

            result = workflow.auto_resolve_duplicates(
                items, history_mode="persistent", session_id="session-a"
            )

            self.assertEqual(result, {"resolved": 0, "needs_review": 1})
            survivors = {item.id: item.rating for item in repository.read()}
            self.assertEqual(
                survivors,
                {"heat-a": 0, "heat-b": 0, "heat-c": 9, "heat-d": 4},
            )
            self.assertEqual(workflow.history("persistent", "session-a")["count"], 0)

    def test_auto_resolve_leaves_a_genuine_personal_conflict_for_manual_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995", "rating": 9}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995", "rating": 4}),
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            items = [item.to_dict() for item in repository.read()]
            for item in items:
                item["_source_file"] = str(catalog_path)

            result = workflow.auto_resolve_duplicates(
                items, history_mode="persistent", session_id="session-a"
            )

            self.assertEqual(result, {"resolved": 0, "needs_review": 1})
            self.assertEqual(len(repository.read()), 2)
            self.assertEqual(workflow.history("persistent", "session-a")["count"], 0)

    def test_auto_resolve_keeps_the_non_empty_rating_when_the_other_side_is_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item({"id": "heat-a", "title": "Heat", "year": "1995", "rating": 8}),
                    normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            items = [item.to_dict() for item in repository.read()]
            for item in items:
                item["_source_file"] = str(catalog_path)

            result = workflow.auto_resolve_duplicates(
                items, history_mode="persistent", session_id="session-a"
            )

            self.assertEqual(result, {"resolved": 1, "needs_review": 0})
            remaining = repository.read()
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].rating, 8)

    def test_auto_merge_on_add_fills_empty_fields_and_records_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-wikipedia",
                            "title": "Heat",
                            "year": "1995",
                            "source": "wikipedia",
                            "url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                            "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                            "wikidata_id": "Q846982",
                            "description": "",
                        }
                    )
                ]
            )
            workflow, history_path = self.workflow(catalog_path)
            pointer = CatalogPointer(catalog_path, "heat-wikipedia")

            incoming = {
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt0113277/",
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
                "wikidata_id": "Q846982",
                "spanish_title": "Fuego contra fuego",
                "description": "Un detective y un ladron chocan en Los Angeles.",
            }
            result = workflow.auto_merge_on_add(
                pointer, incoming, history_mode="persistent", session_id="session-a"
            )

            self.assertEqual(result["item"]["spanish_title"], "Fuego contra fuego")
            self.assertEqual(
                result["item"]["description"],
                "Un detective y un ladron chocan en Los Angeles.",
            )
            self.assertEqual(result["item"]["imdb_url"], "https://www.imdb.com/title/tt0113277/")
            self.assertTrue(result["operation"]["can_undo"])
            self.assertEqual(result["operation"]["action"], "auto_merge_on_add")

            persisted = repository.get("heat-wikipedia")
            assert persisted is not None
            self.assertEqual(persisted.spanish_title, "Fuego contra fuego")
            self.assertEqual(len(repository.read()), 1)
            self.assertTrue(history_path.exists())

    def test_auto_merge_on_add_never_overwrites_a_locked_empty_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-wikipedia",
                            "title": "Heat",
                            "description": "",
                            "locked_fields": ["description"],
                        }
                    )
                ]
            )
            workflow, _ = self.workflow(catalog_path)
            pointer = CatalogPointer(catalog_path, "heat-wikipedia")

            result = workflow.auto_merge_on_add(
                pointer,
                {"source": "imdb", "description": "Una sinopsis que no deberia entrar"},
                history_mode="persistent",
                session_id="session-a",
            )

            self.assertEqual(result["item"]["description"], "")

    def test_auto_merge_on_add_can_be_undone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write([normalize_item({"id": "heat", "title": "Heat", "description": ""})])
            workflow, _ = self.workflow(catalog_path)
            pointer = CatalogPointer(catalog_path, "heat")

            result = workflow.auto_merge_on_add(
                pointer,
                {"source": "imdb", "description": "Sinopsis nueva"},
                history_mode="persistent",
                session_id="session-a",
            )
            merged = repository.get("heat")
            assert merged is not None
            self.assertEqual(merged.description, "Sinopsis nueva")

            workflow.undo(
                result["operation"]["id"], history_mode="persistent", session_id="session-a"
            )
            reverted = repository.get("heat")
            assert reverted is not None
            self.assertEqual(reverted.description, "")

    def test_auto_merge_on_add_raises_conflict_if_the_catalog_changed_concurrently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write([normalize_item({"id": "heat", "title": "Heat", "description": ""})])
            workflow, _ = self.workflow(catalog_path)
            pointer = CatalogPointer(catalog_path, "heat")

            # Simulate a write landing between this method's own capture and its
            # commit by handing it a snapshot from before that write happened.
            stale_before = workflow._capture(pointer)
            repository.update_item(
                "heat", lambda item: item.__setitem__("review", "Cambio concurrente")
            )

            with patch.object(workflow, "_capture", return_value=stale_before):
                with self.assertRaises(CurationConflict):
                    workflow.auto_merge_on_add(
                        pointer,
                        {"source": "imdb", "description": "Sinopsis nueva"},
                        history_mode="persistent",
                        session_id="session-a",
                    )
            stored = repository.get("heat")
            assert stored is not None
            self.assertEqual(stored.review, "Cambio concurrente")
            self.assertEqual(stored.description, "")


if __name__ == "__main__":
    unittest.main()
