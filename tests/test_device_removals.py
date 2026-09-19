"""[X5.2] The record of works a person removed, and what it says when asked.

ADR-0005's amendment lets removals travel on three conditions, and these tests
hold them: a removal is an explicit record and never an inference from absence
(an id nobody recorded is `unknown`, not removed); a work that still exists is
never reported as removed; and a merge points at the work that stayed.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.removal_repository import RemovalRepositoryError
from movie_inbox.application.removal_service import (
    MAX_MERGE_HOPS,
    REMOVAL_RETENTION_SECONDS,
    RemovalService,
    RemovalStatus,
)
from movie_inbox.domain.removals import DeviceRemoval
from movie_inbox.infrastructure.identity_repository import (
    INSTANCE_SCHEMA_VERSION,
    SqliteIdentityRepository,
)
from movie_inbox.infrastructure.removal_repository import SqliteRemovalRepository


class DeviceRemovalTests(unittest.TestCase):
    def test_a_removal_needs_the_id_a_device_knew_the_work_by(self) -> None:
        with self.assertRaises(ValueError):
            DeviceRemoval("", "deleted")

    def test_only_a_deletion_or_a_merge_is_a_removal(self) -> None:
        with self.assertRaises(ValueError):
            DeviceRemoval("a", "vanished")

    def test_a_merge_has_to_say_what_it_was_merged_into(self) -> None:
        with self.assertRaises(ValueError):
            DeviceRemoval("a", "merged")

    def test_a_deletion_is_not_merged_into_anything(self) -> None:
        with self.assertRaises(ValueError):
            DeviceRemoval("a", "deleted", merged_into="b")

    def test_a_work_cannot_be_merged_into_itself(self) -> None:
        with self.assertRaises(ValueError):
            DeviceRemoval("a", "merged", merged_into="a")


class RemovalRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.instance = root / "instance.db"
        identity = SqliteIdentityRepository(self.instance)
        identity.initialize()
        _, catalog = AuthService(identity).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(root / "catalog.json")],
            write_path=str(root / "catalog.json"),
        )
        self.catalog_id = catalog.id
        self.now = 1_000_000.0
        self.repository = SqliteRemovalRepository(self.instance)
        self.service = RemovalService(self.repository, clock=lambda: self.now)

    def _ask(self, *ids: str, present: frozenset[str] = frozenset()) -> dict[str, RemovalStatus]:
        return self.service.statuses(self.catalog_id, list(ids), present)

    def test_a_deleted_work_is_answered_as_removed_with_when(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("heat", "deleted")])
        self.assertEqual(
            self._ask("heat"),
            {"heat": RemovalStatus("removed", "deleted", "", 1_000_000)},
        )

    def test_a_merged_work_says_which_one_it_became(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("a", "merged", merged_into="b")])
        self.assertEqual(
            self._ask("a", present=frozenset({"b"})),
            {"a": RemovalStatus("removed", "merged", "b", 1_000_000)},
        )

    def test_an_id_nobody_recorded_is_unknown_never_removed(self) -> None:
        # The rule the whole feature rests on: absence is not a removal.
        self.assertEqual(self._ask("never-seen"), {"never-seen": RemovalStatus("unknown")})

    def test_a_work_that_exists_is_present_even_when_a_stale_record_says_otherwise(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("heat", "deleted")])
        self.assertEqual(
            self._ask("heat", present=frozenset({"heat"})), {"heat": RemovalStatus("present")}
        )

    def test_every_id_asked_about_is_answered_once(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("gone", "deleted")])
        answers = self._ask("here", "gone", "gone", "nobody", present=frozenset({"here"}))
        self.assertEqual(list(answers), ["here", "gone", "nobody"])
        self.assertEqual([row.state for row in answers.values()], ["present", "removed", "unknown"])

    def test_a_chain_of_merges_is_followed_to_the_work_that_stayed(self) -> None:
        self.service.record(
            self.catalog_id,
            [DeviceRemoval("a", "merged", merged_into="b"), DeviceRemoval("b", "merged", "c")],
        )
        self.assertEqual(
            self._ask("a", present=frozenset({"c"}))["a"],
            RemovalStatus("removed", "merged", "c", 1_000_000),
        )

    def test_a_merge_into_a_work_that_was_deleted_afterwards_is_a_deletion(self) -> None:
        self.service.record(
            self.catalog_id,
            [DeviceRemoval("a", "merged", merged_into="b"), DeviceRemoval("b", "deleted")],
        )
        self.assertEqual(self._ask("a")["a"], RemovalStatus("removed", "deleted", "", 1_000_000))

    def test_a_merge_whose_survivor_has_no_record_points_at_it_for_the_device_to_ask(
        self,
    ) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("a", "merged", merged_into="b")])
        self.assertEqual(self._ask("a")["a"], RemovalStatus("removed", "merged", "b", 1_000_000))

    def test_a_loop_of_merges_does_not_hang_the_answer(self) -> None:
        self.service.record(
            self.catalog_id,
            [DeviceRemoval("a", "merged", merged_into="b"), DeviceRemoval("b", "merged", "a")],
        )
        answer = self._ask("a")["a"]
        self.assertEqual((answer.state, answer.reason), ("removed", "merged"))

    def test_a_chain_longer_than_the_guard_still_answers(self) -> None:
        links = [
            DeviceRemoval(f"w{n}", "merged", merged_into=f"w{n + 1}")
            for n in range(MAX_MERGE_HOPS + 4)
        ]
        self.service.record(self.catalog_id, links)
        answer = self._ask("w0")["w0"]
        self.assertEqual((answer.state, answer.reason), ("removed", "merged"))

    def test_removing_the_same_work_again_replaces_how_it_left(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("a", "deleted")])
        self.now += 60
        self.service.record(self.catalog_id, [DeviceRemoval("a", "merged", merged_into="b")])
        self.assertEqual(self._ask("a")["a"], RemovalStatus("removed", "merged", "b", 1_000_060))

    def test_undoing_a_removal_makes_the_record_disappear(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("a", "deleted")])
        self.service.forget(self.catalog_id, ["a"])
        self.assertEqual(self._ask("a"), {"a": RemovalStatus("unknown")})

    def test_records_belong_to_one_catalogue(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("a", "deleted")])
        self.assertEqual(
            self.service.statuses("some-other-catalogue", ["a"], frozenset()),
            {"a": RemovalStatus("unknown")},
        )

    def test_records_past_retention_are_forgotten_and_read_as_unknown(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("old", "deleted")])
        self.now += REMOVAL_RETENTION_SECONDS + 1
        # Recording anything sweeps: nothing else schedules a purge.
        self.service.record(self.catalog_id, [DeviceRemoval("recent", "deleted")])
        self.assertEqual(
            [row.state for row in self._ask("old", "recent").values()], ["unknown", "removed"]
        )

    def test_a_record_just_inside_retention_is_still_answered(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("a", "deleted")])
        self.now += REMOVAL_RETENTION_SECONDS - 1
        self.service.record(self.catalog_id, [])
        self.assertEqual(self._ask("a")["a"].state, "removed")

    def test_a_long_list_of_ids_is_asked_in_chunks(self) -> None:
        removals = [DeviceRemoval(f"id-{n}", "deleted") for n in range(450)]
        self.service.record(self.catalog_id, removals)
        answers = self._ask(*(f"id-{n}" for n in range(450)))
        self.assertEqual({row.state for row in answers.values()}, {"removed"})
        self.assertEqual(len(answers), 450)

    def test_the_record_goes_with_its_catalogue(self) -> None:
        self.service.record(self.catalog_id, [DeviceRemoval("a", "deleted")])
        with closing(sqlite3.connect(self.instance)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("DELETE FROM catalogs WHERE id = ?", (self.catalog_id,))
            connection.commit()
            (left,) = connection.execute("SELECT COUNT(*) FROM device_removals").fetchone()
        self.assertEqual(left, 0)

    def test_recording_for_a_catalogue_that_does_not_exist_is_an_error_not_a_silent_loss(
        self,
    ) -> None:
        with self.assertRaises(RemovalRepositoryError):
            self.service.record("no-such-catalogue", [DeviceRemoval("a", "deleted")])

    def test_an_unreachable_store_is_reported_as_the_repositorys_own_error(self) -> None:
        broken = RemovalService(SqliteRemovalRepository(Path(self.temporary.name) / "no" / "x.db"))
        with self.assertRaises(RemovalRepositoryError):
            broken.statuses(self.catalog_id, ["a"], frozenset())


class RemovalMigrationTests(unittest.TestCase):
    def test_an_instance_from_before_the_record_gains_it_without_losing_anything(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.db"
            with patch(
                "movie_inbox.infrastructure.identity_repository.INSTANCE_SCHEMA_VERSION",
                INSTANCE_SCHEMA_VERSION - 1,
            ):
                SqliteIdentityRepository(path).initialize()
            with closing(sqlite3.connect(path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            self.assertNotIn("device_removals", tables)

            SqliteIdentityRepository(path).initialize()
            with closing(sqlite3.connect(path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                (version,) = connection.execute(
                    "SELECT MAX(version) FROM instance_migrations"
                ).fetchone()
            self.assertIn("device_removals", tables)
            self.assertEqual(version, INSTANCE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
