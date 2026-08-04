from __future__ import annotations

import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.library_service import (
    AvailabilityService,
    LibraryPathError,
    ManagedLibraryScheduler,
    ManagedLibraryService,
    _CatalogMatchIndex,
)
from movie_inbox.application.library_repository import LibraryRunBusy
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.library_repository import SqliteLibraryRepository
from movie_inbox.infrastructure.library_scanner import scan_media_files


class ManagedLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.media = self.root / "media"
        self.media.mkdir()
        self.catalog = self.root / "catalog.json"
        self.catalog_items = [
            normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}).to_dict()
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

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_library(self, **values):  # type: ignore[no-untyped-def]
        return self.service.create_library(
            self.owner.id,
            {
                "name": values.get("name", "Peliculas principales"),
                "root_path": str(values.get("root_path", self.media)),
                "schedule": values.get("schedule", "manual"),
                "max_missing_ratio": values.get("max_missing_ratio", 0.5),
            },
        )

    def execute(self, library_id: str, mode: str):  # type: ignore[no-untyped-def]
        run = self.service.queue_scan(library_id, mode)
        self.service.execute_run(run.id)
        return self.repository.get_run(run.id)

    def test_paths_must_be_absolute_and_inside_the_server_allowlist(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        with self.assertRaises(LibraryPathError):
            self.create_library(root_path=outside)
        with self.assertRaises(LibraryPathError):
            self.service.create_library(
                self.owner.id,
                {"name": "Relative", "root_path": "media", "schedule": "manual"},
            )

    def test_catalog_match_index_limits_work_without_losing_exact_matches(self) -> None:
        items = [
            {"id": f"unrelated-{position}", "title": f"Unrelated title {position}", "year": "1995"}
            for position in range(2_000)
        ]
        items.append({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})

        candidates = _CatalogMatchIndex.build(items).candidates(
            {"title": "Heat", "year": "1995", "kind": "pelicula"}
        )

        self.assertEqual([item["id"] for item in candidates], ["heat"])

    def test_test_scan_verifies_without_writing_inventory(self) -> None:
        (self.media / "Heat.1995.1080p.mkv").write_bytes(b"heat")
        library = self.create_library()

        run = self.execute(library.id, "dry_run")
        detail = self.service.library_detail(library.id)

        self.assertEqual(run.status, "completed")
        self.assertEqual(run.summary["matched"], 1)
        self.assertGreater(detail["verified_at"], 0)
        self.assertEqual(detail["counts"]["files"], 0)

    def test_apply_requires_a_successful_test_scan(self) -> None:
        library = self.create_library()

        with self.assertRaisesRegex(ValueError, "successful test scan"):
            self.service.queue_scan(library.id, "apply")

    def test_apply_creates_shared_verified_availability_without_changing_manual_flag(self) -> None:
        (self.media / "Heat.1995.1080p.mkv").write_bytes(b"heat")
        library = self.create_library()
        self.execute(library.id, "dry_run")
        self.execute(library.id, "apply")

        decorated = AvailabilityService(self.repository).decorate_items(
            [{"id": "heat-member", "title": "Heat", "year": "1995", "kind": "pelicula", "en_catalogo": False}],
            include_sources=False,
        )[0]

        self.assertTrue(decorated["en_catalogo"])
        self.assertFalse(decorated["_availability"]["manual"])
        self.assertTrue(decorated["_availability"]["server"])
        self.assertEqual(decorated["_availability"]["file_count"], 1)
        self.assertNotIn("sources", decorated["_availability"])

    def test_unknown_file_stays_in_owner_queue_until_confirmed(self) -> None:
        (self.media / "Arrival.2016.1080p.mkv").write_bytes(b"arrival")
        library = self.create_library()
        self.execute(library.id, "dry_run")
        self.execute(library.id, "apply")

        queue = self.service.review_queue()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["state"], "new")
        reviewed = self.service.review_file(
            queue[0]["id"],
            {"action": "confirm", "title": "Arrival", "year": "2016", "kind": "pelicula"},
        )
        self.assertEqual(reviewed["state"], "matched")
        self.assertEqual(self.service.review_queue(), [])

        decorated = AvailabilityService(self.repository).decorate_items(
            [{"id": "arrival", "title": "Arrival", "year": "2016", "kind": "pelicula"}]
        )[0]
        self.assertTrue(decorated["_availability"]["server"])

    def test_missing_file_guard_preserves_last_valid_inventory(self) -> None:
        first = self.media / "Heat.1995.mkv"
        second = self.media / "Arrival.2016.mkv"
        first.write_bytes(b"heat")
        second.write_bytes(b"arrival")
        library = self.create_library(max_missing_ratio=0.4)
        self.execute(library.id, "dry_run")
        self.execute(library.id, "apply")
        first.unlink()
        second.unlink()

        blocked = self.execute(library.id, "apply")
        detail = self.service.library_detail(library.id)

        self.assertEqual(blocked.status, "blocked")
        self.assertTrue(blocked.summary["removals_skipped"])
        self.assertEqual(detail["counts"]["files"], 2)

    def test_hourly_library_becomes_due_and_queues_a_scheduled_run(self) -> None:
        (self.media / "Heat.1995.mkv").write_bytes(b"heat")
        library = self.create_library(schedule="hourly")
        self.execute(library.id, "dry_run")
        with self.assertRaisesRegex(ValueError, "Apply inventory"):
            self.service.set_active(library.id, True)
        self.execute(library.id, "apply")
        activated = self.service.set_active(library.id, True)
        self.assertEqual(activated.next_scan_at, self.now + 3600)

        self.now += 3600
        queued = self.service.queue_due_scans()

        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].trigger, "scheduled")
        self.assertEqual(queued[0].mode, "apply")

    def test_scheduler_executes_a_due_scan_and_persists_inventory(self) -> None:
        (self.media / "Heat.1995.mkv").write_bytes(b"heat")
        library = self.create_library(schedule="hourly")
        self.execute(library.id, "dry_run")
        self.execute(library.id, "apply")
        self.service.set_active(library.id, True)
        self.now += 3600
        scanned = threading.Event()

        def observed_scan(*args, **kwargs):  # type: ignore[no-untyped-def]
            result = scan_media_files(*args, **kwargs)
            scanned.set()
            return result

        scheduled_service = ManagedLibraryService(
            self.repository,
            allowed_roots=(str(self.media),),
            catalog_universe=lambda: list(self.catalog_items),
            scanner=observed_scan,
            clock=lambda: self.now,
        )
        scheduler = ManagedLibraryScheduler(scheduled_service, poll_seconds=1)
        scheduler.start()
        try:
            self.assertTrue(scanned.wait(2), "The due library scan did not start")
        finally:
            scheduler.stop()

        runs = self.repository.list_runs(library.id)
        scheduled = next(run for run in runs if run.trigger == "scheduled")
        self.assertEqual(scheduled.status, "completed")
        self.assertEqual(self.service.library_detail(library.id)["counts"]["files"], 1)

    def test_library_configuration_cannot_change_while_a_scan_is_queued(self) -> None:
        (self.media / "Heat.1995.mkv").write_bytes(b"heat")
        library = self.create_library(schedule="hourly")
        self.execute(library.id, "dry_run")
        run = self.service.queue_scan(library.id, "apply")
        self.assertEqual(self.repository.get_library(library.id).status, "scanning")

        with self.assertRaises(LibraryRunBusy):
            self.service.set_active(library.id, True)
        with self.assertRaises(LibraryRunBusy):
            self.service.update_library(library.id, {"name": "Otro nombre"})

        self.service.execute_run(run.id)
        self.assertEqual(self.repository.get_library(library.id).status, "ready")
        updated = self.service.set_active(library.id, True)
        self.assertTrue(updated.active)

    def test_manual_library_does_not_use_scheduled_activation(self) -> None:
        library = self.create_library()
        self.execute(library.id, "dry_run")
        self.execute(library.id, "apply")

        with self.assertRaisesRegex(ValueError, "Manual libraries"):
            self.service.set_active(library.id, True)

    def test_switching_to_manual_disables_automatic_scans(self) -> None:
        library = self.create_library(schedule="hourly")
        self.execute(library.id, "dry_run")
        self.execute(library.id, "apply")
        self.service.set_active(library.id, True)

        updated = self.service.update_library(library.id, {"schedule": "manual"})

        self.assertFalse(updated.active)
        self.assertEqual(updated.status, "ready")
        self.assertEqual(updated.next_scan_at, 0)

    def test_persistent_run_history_is_bounded_per_library(self) -> None:
        library = self.create_library()
        for _ in range(105):
            self.execute(library.id, "dry_run")

        with closing(sqlite3.connect(self.instance)) as connection:
            stored = connection.execute(
                "SELECT COUNT(*) FROM library_scan_runs WHERE library_id = ?",
                (library.id,),
            ).fetchone()[0]
        self.assertEqual(stored, 100)

    def test_copy_that_sorts_before_original_does_not_reuse_the_same_inventory_id(self) -> None:
        original_dir = self.media / "z-original"
        original_dir.mkdir()
        original = original_dir / "Heat.1995.mkv"
        original.write_bytes(b"same-video")
        library = self.create_library()
        self.execute(library.id, "dry_run")
        self.execute(library.id, "apply")
        original_id = self.repository.previous_files(library.id)[0].id

        copy_dir = self.media / "a-copy"
        copy_dir.mkdir()
        (copy_dir / original.name).write_bytes(original.read_bytes())
        self.execute(library.id, "apply")

        inventory = self.repository.previous_files(library.id)
        self.assertEqual(len([item for item in inventory if item.available]), 2)
        self.assertEqual(len({item.id for item in inventory if item.available}), 2)
        self.assertEqual(
            next(item.id for item in inventory if item.relative_path == "z-original/Heat.1995.mkv"),
            original_id,
        )


if __name__ == "__main__":
    unittest.main()
