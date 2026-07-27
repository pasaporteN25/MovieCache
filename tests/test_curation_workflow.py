from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.application.curation_workflow import (
    CatalogPointer,
    CurationConflict,
    CurationWorkflowService,
)
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.curation_history import (
    JsonCurationHistoryRepository,
    MemoryCurationHistoryRepository,
)
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository


class CurationWorkflowTests(unittest.TestCase):
    def workflow(self, catalog_path: Path):
        repositories = {}

        def repository(path: Path):
            key = str(Path(path).resolve())
            if key not in repositories:
                repositories[key] = JsonCatalogRepository(Path(key), normalize_item)
            return repositories[key]

        history_path = catalog_path.with_name(".history.json")
        service = CurationWorkflowService(
            repository,
            JsonCurationHistoryRepository(history_path),
            MemoryCurationHistoryRepository(),
        )
        return service, history_path

    def test_reviewed_merge_preserves_identity_and_can_restore_both_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write([
                normalize_item({
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
                }),
                normalize_item({
                    "id": "heat-imdb",
                    "title": "Heat",
                    "spanish_title": "Fuego contra fuego",
                    "year": "1995",
                    "source": "imdb",
                    "url": "https://www.imdb.com/title/tt0113277/",
                    "imdb_url": "https://www.imdb.com/title/tt0113277/",
                    "status": "to_watch",
                    "local_files": [{"path": "E:/Heat-alt.mkv", "name": "Heat-alt.mkv"}],
                }),
            ])
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
            repository.update_item("heat", lambda item: item.__setitem__("review", "Cambio posterior"))

            with self.assertRaises(CurationConflict):
                workflow.undo(
                    result["operation"]["id"],
                    history_mode="persistent",
                    session_id="session-a",
                )
            self.assertEqual(repository.get("heat").review, "Cambio posterior")

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
            self.assertEqual(repository.get("heat").link_curation_status, "not_required")

    def test_external_metadata_does_not_create_a_fake_personal_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(catalog_path, normalize_item)
            repository.write([
                normalize_item({
                    "id": "heat",
                    "title": "Heat",
                    "status": "watched",
                    "watched_at": "2026-07-01",
                    "rating": 9,
                })
            ])
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
            repository.write([
                normalize_item({
                    "id": "heat-local",
                    "title": "Heat",
                    "status": "watched",
                    "rating": 9,
                    "review": "Una favorita",
                    "en_catalogo": True,
                })
            ])
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
            self.assertEqual(restored.spanish_title, "")
            self.assertEqual(restored.imdb_url, "")
            self.assertEqual(restored.review, "Una favorita")


if __name__ == "__main__":
    unittest.main()
