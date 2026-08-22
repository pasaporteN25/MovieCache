from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.curation_workflow import CurationConflict
from movie_inbox.application.library_repository import LibraryConflict
from movie_inbox.application.library_service import ManagedLibraryService
from movie_inbox.application.scanner_workflow import ScannerWorkflowService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.curation_history import MemoryCurationHistoryRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.library_repository import SqliteLibraryRepository
from movie_inbox.infrastructure.library_scanner import scan_media_files
from movie_inbox.infrastructure.scanner_history import SqliteScannerHistoryRepository


class ScannerWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.media = self.root / "media"
        self.media.mkdir()
        self.catalog = self.root / "catalog.json"
        # A same-title, different-year catalog entry so a scanned file with the
        # matching title lands in "review" with a populated (not empty)
        # candidate list, instead of auto-matching straight to "matched".
        self.catalog_items = [
            normalize_item(
                {"id": "heat-1970", "title": "Heat", "year": "1970", "kind": "pelicula"}
            ).to_dict()
        ]
        JsonCatalogRepository(self.catalog, normalize_item).write(self.catalog_items)
        self.instance = self.root / "instance.db"
        self.identity = SqliteIdentityRepository(self.instance)
        self.owner, _ = AuthService(self.identity).bootstrap_owner(
            "lucas",
            "a-long-local-password",
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog)],
            write_path=str(self.catalog),
        )
        self.repository = SqliteLibraryRepository(self.instance)
        self.now = 1_800_000_000
        self.service = ManagedLibraryService(
            self.repository,
            allowed_roots=(str(self.media),),
            catalog_universe=lambda: list(self.catalog_items),
            scanner=scan_media_files,
            clock=lambda: self.now,
        )
        self.persistent_history = SqliteScannerHistoryRepository(self.instance)
        self.session_history = MemoryCurationHistoryRepository()
        self._catalog_services: dict[str, CatalogService] = {}
        self.workflow = ScannerWorkflowService(
            self.service,
            self.repository,
            self.persistent_history,
            self.session_history,
            catalog_service_factory=self.catalog_service_factory,
            clock=lambda: self.now,
        )

    def catalog_service_factory(self, path: Path) -> CatalogService:
        key = str(Path(path).resolve())
        if key not in self._catalog_services:
            self._catalog_services[key] = CatalogService(
                JsonCatalogRepository(Path(key), normalize_item)
            )
        return self._catalog_services[key]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def seed_review_file(self, name: str = "Heat.1995.1080p.mkv") -> str:
        (self.media / name).write_bytes(b"heat")
        library = self.service.create_library(
            self.owner.id,
            {"name": "Peliculas", "root_path": str(self.media), "schedule": "manual"},
        )
        run = self.service.queue_scan(library.id, "dry_run")
        self.service.execute_run(run.id)
        run = self.service.queue_scan(library.id, "apply")
        self.service.execute_run(run.id)
        queue = self.repository.review_queue()
        self.assertEqual(len(queue), 1)
        file = queue[0]
        self.assertEqual(file.state, "review")
        self.assertTrue(file.candidates, "test setup must produce a non-empty candidate list")
        return file.id

    def test_confirm_commits_a_restorable_history_entry(self) -> None:
        file_id = self.seed_review_file()

        result = self.workflow.review(
            file_id,
            {"action": "confirm", "title": "Heat", "year": "1995", "kind": "pelicula"},
            history_mode="persistent",
            session_id="session-a",
        )

        self.assertEqual(result["item"]["state"], "matched")
        self.assertTrue(result["operation"]["can_undo"])
        history = self.workflow.history("persistent", "session-a")
        self.assertEqual(history["count"], 1)
        self.assertEqual(history["operations"][0]["action"], "scanner_confirm")
        self.assertEqual(history["operations"][0]["summary"]["file_count"], 1)

    def test_undo_restores_state_and_the_original_candidates(self) -> None:
        file_id = self.seed_review_file()
        original_candidates = self.repository.review_queue()[0].candidates

        result = self.workflow.review(
            file_id,
            {"action": "confirm", "title": "Heat", "year": "1995", "kind": "pelicula"},
            history_mode="persistent",
            session_id="session-a",
        )
        self.assertEqual(self.repository.review_queue(), [])

        undone = self.workflow.undo(
            result["operation"]["id"],
            history_mode="persistent",
            session_id="session-a",
        )
        self.assertEqual(undone["status"], "undone")
        self.assertFalse(undone["can_undo"])

        restored = self.repository.review_queue()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].id, file_id)
        self.assertEqual(restored[0].state, "review")
        # The whole point of capturing "before" ourselves: review_files() wipes
        # candidates_json to '[]' on every confirm and never regenerates it, so
        # a naive undo would restore state="review" with an empty, useless
        # candidate list instead of the original ones.
        self.assertEqual(
            [dict(candidate) for candidate in restored[0].candidates],
            [dict(candidate) for candidate in original_candidates],
        )

    def test_undo_refuses_when_the_row_changed_since_the_operation(self) -> None:
        file_id = self.seed_review_file()
        result = self.workflow.review(
            file_id,
            {"action": "confirm", "title": "Heat", "year": "1995", "kind": "pelicula"},
            history_mode="persistent",
            session_id="session-a",
        )
        # Something else touches the row after the operation -- e.g. a rescan
        # or a second review decision -- before the undo is attempted.
        self.repository.review_files([file_id], "ignore", None, self.now + 1)

        with self.assertRaises(LibraryConflict):
            self.workflow.undo(
                result["operation"]["id"],
                history_mode="persistent",
                session_id="session-a",
            )
        # The undo attempt must not have written anything: the row stays
        # exactly as the simulated drift left it, not reverted to "review"
        # (what a wrongly-applied rollback would do) nor left as "matched"
        # (what a wrongly-applied undo would do).
        self.assertEqual(self.row_state(file_id), "ignored")

    def row_state(self, file_id: str) -> str:
        with closing(sqlite3.connect(self.instance)) as connection:
            row = connection.execute(
                "SELECT state FROM library_files WHERE id = ?", (file_id,)
            ).fetchone()
        return str(row[0])

    def test_session_history_is_isolated_by_session_and_does_not_touch_disk(self) -> None:
        file_id = self.seed_review_file()
        self.workflow.review(
            file_id,
            {"action": "confirm", "title": "Heat", "year": "1995", "kind": "pelicula"},
            history_mode="session",
            session_id="browser-a",
        )
        self.assertEqual(self.workflow.history("session", "browser-a")["count"], 1)
        self.assertEqual(self.workflow.history("session", "browser-b")["count"], 0)
        self.assertEqual(self.workflow.history("persistent", "")["count"], 0)

    def test_create_undo_refuses_when_background_enrichment_already_touched_the_item(
        self,
    ) -> None:
        (self.media / "Interstellar.2014.1080p.mkv").write_bytes(b"interstellar")
        library = self.service.create_library(
            self.owner.id,
            {"name": "Peliculas", "root_path": str(self.media), "schedule": "manual"},
        )
        for mode in ("dry_run", "apply"):
            run = self.service.queue_scan(library.id, mode)
            self.service.execute_run(run.id)
        file_id = self.repository.review_queue()[0].id

        result = self.workflow.create_and_link(
            file_id,
            {"action": "create", "title": "Interstellar", "year": "2014", "kind": "pelicula"},
            catalog_path=self.catalog,
            comparison_items=[],
            history_mode="persistent",
            session_id="session-a",
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["created"])
        catalog_item_id = result["catalog_item"]["id"]

        # Background enrichment (or any other write) touches the freshly created
        # item before the undo attempt.
        catalog_repository = self.catalog_service_factory(self.catalog).repository
        catalog_repository.update_item(
            catalog_item_id, lambda item: item.__setitem__("description", "Enriched")
        )

        with self.assertRaises(CurationConflict):
            self.workflow.undo(
                result["operation"]["id"],
                history_mode="persistent",
                session_id="session-a",
            )
        # The enrichment must survive: undo refused rather than clobbering it.
        surviving = catalog_repository.get(catalog_item_id)
        self.assertIsNotNone(surviving)
        self.assertEqual(surviving.description, "Enriched")

    def test_create_of_a_genuinely_new_work_can_be_undone(self) -> None:
        (self.media / "Interstellar.2014.1080p.mkv").write_bytes(b"interstellar")
        library = self.service.create_library(
            self.owner.id,
            {"name": "Peliculas", "root_path": str(self.media), "schedule": "manual"},
        )
        for mode in ("dry_run", "apply"):
            run = self.service.queue_scan(library.id, mode)
            self.service.execute_run(run.id)
        file_id = self.repository.review_queue()[0].id

        result = self.workflow.create_and_link(
            file_id,
            {"action": "create", "title": "Interstellar", "year": "2014", "kind": "pelicula"},
            catalog_path=self.catalog,
            comparison_items=[],
            history_mode="persistent",
            session_id="session-a",
        )
        catalog_item_id = result["catalog_item"]["id"]
        catalog_repository = self.catalog_service_factory(self.catalog).repository
        self.assertIsNotNone(catalog_repository.get(catalog_item_id))
        self.assertEqual(self.repository.review_queue(), [])

        self.workflow.undo(
            result["operation"]["id"], history_mode="persistent", session_id="session-a"
        )
        self.assertIsNone(catalog_repository.get(catalog_item_id))
        restored = self.repository.review_queue()
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].id, file_id)


if __name__ == "__main__":
    unittest.main()
