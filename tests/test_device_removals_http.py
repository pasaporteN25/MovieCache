"""[X5.3]/[X5.4] Removing a work in the browser leaves a record a phone can be told.

The record is asked of the service directly here: the route a phone asks it
through is a later step, and what these settle is that the right id gets
recorded from every way the browser can remove a work -- a delete, a merge of
two, of a group, or all the safe ones at once -- that an undone merge leaves no
record, and that a failure to record never takes the operation down with it.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.curation_workflow import CurationWorkflowError, _removed_works
from movie_inbox.application.pairing_service import DEVICE_SYNC_SECRET
from movie_inbox.application.removal_repository import RemovalRepositoryError
from movie_inbox.application.removal_service import RemovalService, RemovalStatus
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.removals import RemovedWork
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.device_ids import opaque_item_id

WORKS: list[dict[str, Any]] = [
    {"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"},
    {"id": "ran", "title": "Ran", "year": "1985", "kind": "pelicula"},
    {"id": "stalker", "title": "Stalker", "year": "1979", "kind": "pelicula"},
]


class _RemovalHttpCase(unittest.TestCase):
    """A running app with the owner signed in on the web and on a phone."""

    works: list[dict[str, Any]] = WORKS

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item(work) for work in self.works]
        )
        self.instance_path = root / "instance.db"
        self.password = "a-long-local-password"
        _, catalog = AuthService(SqliteIdentityRepository(self.instance_path)).bootstrap_owner(
            "lucas",
            self.password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        self.catalog_id = catalog.id
        media = root / "media"
        media.mkdir()
        self.config = ViewerConfig(
            patterns=[str(self.catalog_path)],
            title="Movie Inbox Test",
            write_json=str(self.catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(self.instance_path),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media),),
            library_scheduler_poll_seconds=3600,
        )
        self.context = TestClient(create_app(self.config), base_url="http://127.0.0.1:8765")
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        login = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": self.password}),
            headers=self._web_headers(),
        )
        self.assertEqual(login.status_code, 200, login.content)
        session = self.client.post(
            "/api/v1/auth/login",
            content=json.dumps(
                {"username": "lucas", "password": self.password, "device_name": "Pixel"}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(session.status_code, 201, session.content)
        self.bearer = {"Authorization": f"Bearer {session.json()['access_token']}"}

    def _web_headers(self) -> dict[str, str]:
        return {
            "X-Movie-Inbox-Token": self.config.api_token,
            "Origin": "http://127.0.0.1:8765",
            "Content-Type": "application/json",
        }

    def _delete(self, **body: Any) -> Any:
        return self.client.post(
            "/api/delete", content=json.dumps(body), headers=self._web_headers()
        )

    def _phone_ids(self) -> dict[str, str]:
        rows = self.client.get("/api/v1/catalog/items", headers=self.bearer).json()["items"]
        return {str(row["title"]): str(row["id"]) for row in rows}

    def _service(self) -> RemovalService:
        service: RemovalService = self.client.app.state.removal_service  # type: ignore[attr-defined]
        return service

    def _ask(self, *ids: str) -> dict[str, RemovalStatus]:
        return self._service().statuses(self.catalog_id, list(ids), frozenset())

    def _phone_id(self, item_id: str) -> str:
        """The id a phone holds for a catalogue work, by the derivation itself."""

        secret = self.client.app.state.identity_repository.instance_secret(  # type: ignore[attr-defined]
            DEVICE_SYNC_SECRET
        )
        return opaque_item_id(secret.encode("utf-8"), self.catalog_id, "source-1", item_id)

    def _ask_present(self, ids: list[str], present: set[str]) -> dict[str, RemovalStatus]:
        return self._service().statuses(self.catalog_id, ids, present)


class DeleteLeavesARecordTests(_RemovalHttpCase):
    def test_deleting_by_id_records_the_id_the_phone_knew_the_work_by(self) -> None:
        heat = self._phone_ids()["Heat"]

        response = self._delete(id="heat", confirmed=True)

        self.assertEqual(response.status_code, 200, response.content)
        answer = self._ask(heat)[heat]
        self.assertEqual(
            (answer.state, answer.reason, answer.merged_into), ("removed", "deleted", "")
        )
        self.assertGreater(answer.removed_at, 0)

    def test_deleting_by_title_records_it_too_though_the_request_never_named_an_id(self) -> None:
        ran = self._phone_ids()["Ran"]

        response = self._delete(title="Ran", year="1985", confirmed=True)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._ask(ran)[ran].state, "removed")

    def test_only_the_work_that_was_deleted_is_recorded(self) -> None:
        ids = self._phone_ids()

        self._delete(id="heat", confirmed=True)

        answers = self._ask(ids["Heat"], ids["Ran"], ids["Stalker"])
        self.assertEqual(
            [answers[ids[title]].state for title in ("Heat", "Ran", "Stalker")],
            ["removed", "unknown", "unknown"],
        )

    def test_a_deletion_that_was_not_confirmed_records_nothing_and_removes_nothing(self) -> None:
        heat = self._phone_ids()["Heat"]

        response = self._delete(id="heat")

        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(self._ask(heat)[heat].state, "unknown")
        self.assertIn("Heat", self._phone_ids())

    def test_deleting_something_that_is_not_there_records_nothing(self) -> None:
        ids = self._phone_ids()

        response = self._delete(id="no-such-work", confirmed=True)

        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual({row.state for row in self._ask(*ids.values()).values()}, {"unknown"})

    def test_a_record_that_cannot_be_written_does_not_undo_the_deletion(self) -> None:
        heat = self._phone_ids()["Heat"]

        with patch.object(
            self._service(), "record", side_effect=RemovalRepositoryError("disk full")
        ):
            response = self._delete(id="heat", confirmed=True)

        # The work is gone and the person is told so. What is lost is only the
        # record, which a phone reads as an absent work it has to ask about.
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn("Heat", self._phone_ids())
        self.assertEqual(self._ask(heat)[heat].state, "unknown")

    def test_the_catalogue_file_really_lost_the_work(self) -> None:
        self._delete(id="heat", confirmed=True)

        stored = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(sorted(row["id"] for row in stored["items"]), ["ran", "stalker"])


DUPLICATES: list[dict[str, Any]] = [
    {"id": "heat-a", "title": "Heat", "year": "1995", "kind": "pelicula"},
    {"id": "heat-b", "title": "Heat", "year": "1995", "kind": "pelicula"},
    {"id": "heat-c", "title": "Heat", "year": "1995", "kind": "pelicula"},
    {"id": "ran", "title": "Ran", "year": "1985", "kind": "pelicula"},
]


class MergeLeavesARecordTests(_RemovalHttpCase):
    works = DUPLICATES

    def _reference(self, item_id: str) -> dict[str, str]:
        return {"id": item_id, "source_file": str(self.catalog_path)}

    def _post(self, path: str, body: dict[str, Any]) -> Any:
        return self.client.post(path, content=json.dumps(body), headers=self._web_headers())

    def _merge_pair(self, survivor_side: str = "left", **extra: Any) -> Any:
        body = {
            "left": self._reference("heat-a"),
            "right": self._reference("heat-b"),
            "survivor_side": survivor_side,
        }
        compare = self._post("/api/curation/compare", body)
        self.assertEqual(compare.status_code, 200, compare.content)
        return self._post(
            "/api/curation/merge",
            {
                **body,
                "review_id": compare.json()["review_id"],
                "choices": {},
                "history_mode": "persistent",
                **extra,
            },
        )

    def _merge_the_three(self, survivor: str = "heat-c") -> Any:
        members = [self._reference(item_id) for item_id in ("heat-a", "heat-b", "heat-c")]
        pick = next(row for row in members if row["id"] == survivor)
        compare = self._post("/api/curation/compare", {"members": members, "survivor": pick})
        self.assertEqual(compare.status_code, 200, compare.content)
        return self._post(
            "/api/curation/merge",
            {
                "members": members,
                "survivor": pick,
                "review_id": compare.json()["review_id"],
                "choices": {},
                "history_mode": "persistent",
            },
        )

    def _still_in_catalogue(self) -> set[str]:
        stored = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        return {str(row["id"]) for row in stored["items"]}

    def _recorded(self, *item_ids: str) -> dict[str, Any]:
        ids = [self._phone_id(item_id) for item_id in item_ids]
        return dict(self._service().repository.get_many(self.catalog_id, ids))

    def test_the_phones_ids_are_the_ones_the_derivation_gives(self) -> None:
        # The rest of this class leans on _phone_id, so first prove it is what
        # a phone is actually shown.
        rows = self.client.get("/api/v1/catalog/items", headers=self.bearer).json()["items"]
        self.assertEqual(
            {row["id"] for row in rows},
            {self._phone_id(item_id) for item_id in ("heat-a", "heat-b", "heat-c", "ran")},
        )

    def test_merging_two_records_the_one_that_went_as_merged_into_the_one_that_stayed(
        self,
    ) -> None:
        response = self._merge_pair("left")

        self.assertEqual(response.status_code, 200, response.content)
        gone, stayed = self._phone_id("heat-b"), self._phone_id("heat-a")
        answer = self._ask_present([gone], {stayed})[gone]
        self.assertEqual(
            (answer.state, answer.reason, answer.merged_into), ("removed", "merged", stayed)
        )

    def test_the_survivor_can_be_the_other_side(self) -> None:
        response = self._merge_pair("right")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._still_in_catalogue(), {"heat-b", "heat-c", "ran"})
        gone, stayed = self._phone_id("heat-a"), self._phone_id("heat-b")
        answer = self._ask_present([gone], {stayed})[gone]
        self.assertEqual((answer.reason, answer.merged_into), ("merged", stayed))

    def test_the_work_that_stayed_and_the_ones_not_involved_are_not_recorded(self) -> None:
        self._merge_pair("left")

        self.assertEqual(self._recorded("heat-a", "heat-c", "ran"), {})

    def test_merging_a_group_records_every_member_that_went(self) -> None:
        response = self._merge_the_three("heat-c")

        self.assertEqual(response.status_code, 200, response.content)
        stayed = self._phone_id("heat-c")
        gone = [self._phone_id("heat-a"), self._phone_id("heat-b")]
        answers = self._ask_present(gone, {stayed})
        self.assertEqual(
            {(row.state, row.reason, row.merged_into) for row in answers.values()},
            {("removed", "merged", stayed)},
        )

    def test_resolving_the_safe_duplicates_records_what_each_merge_removed(self) -> None:
        response = self._post("/api/curation/auto-resolve", {"history_mode": "persistent"})

        self.assertEqual(response.status_code, 200, response.content)
        heats = {"heat-a", "heat-b", "heat-c"}
        survivor = next(iter(self._still_in_catalogue() & heats))
        gone = [self._phone_id(item_id) for item_id in sorted(heats - {survivor})]
        answers = self._ask_present(gone, {self._phone_id(survivor)})
        self.assertEqual(len(answers), 2)
        self.assertEqual(
            {(row.state, row.reason, row.merged_into) for row in answers.values()},
            {("removed", "merged", self._phone_id(survivor))},
        )

    def test_a_merge_that_is_refused_records_nothing(self) -> None:
        response = self._merge_pair("left", review_id="a-comparison-that-never-was")

        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(self._still_in_catalogue(), {"heat-a", "heat-b", "heat-c", "ran"})
        self.assertEqual(self._recorded("heat-a", "heat-b", "heat-c", "ran"), {})

    def test_undoing_a_merge_makes_the_record_go_away(self) -> None:
        merged = self._merge_pair("left")
        self.assertEqual(list(self._recorded("heat-b")), [self._phone_id("heat-b")])

        undone = self._post(
            "/api/curation/undo",
            {"operation_id": merged.json()["operation"]["id"], "history_mode": "persistent"},
        )

        self.assertEqual(undone.status_code, 200, undone.content)
        self.assertEqual(self._still_in_catalogue(), {"heat-a", "heat-b", "heat-c", "ran"})
        # Not just outranked by "it exists": the record itself is gone.
        self.assertEqual(self._recorded("heat-b"), {})

    def test_undoing_a_group_merge_forgets_all_of_it(self) -> None:
        merged = self._merge_the_three("heat-c")
        self.assertEqual(len(self._recorded("heat-a", "heat-b")), 2)

        self._post(
            "/api/curation/undo",
            {"operation_id": merged.json()["operation"]["id"], "history_mode": "persistent"},
        )

        self.assertEqual(self._recorded("heat-a", "heat-b"), {})

    def test_a_record_that_cannot_be_written_does_not_undo_the_merge(self) -> None:
        with patch.object(
            self._service(), "record", side_effect=RemovalRepositoryError("disk full")
        ):
            response = self._merge_pair("left")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._still_in_catalogue(), {"heat-a", "heat-c", "ran"})


class RemovedWorksOfAnOperationTests(unittest.TestCase):
    """What an operation counts as removed, from its own before and after."""

    @staticmethod
    def _state(source: str, item_id: str, present: bool) -> dict[str, Any]:
        return {
            "source_file": source,
            "item_id": item_id,
            "position": 0,
            "item": {"id": item_id} if present else None,
        }

    def test_a_merge_removes_the_empty_member_and_names_the_survivor(self) -> None:
        operation = {
            "before": [self._state("a.json", "1", True), self._state("a.json", "2", True)],
            "after": [self._state("a.json", "1", True), self._state("a.json", "2", False)],
        }
        self.assertEqual(_removed_works(operation), [RemovedWork("a.json", "2", "a.json", "1")])

    def test_the_survivor_can_live_in_another_source(self) -> None:
        operation = {
            "before": [self._state("a.json", "1", True), self._state("b.json", "9", True)],
            "after": [self._state("a.json", "1", True), self._state("b.json", "9", False)],
        }
        self.assertEqual(_removed_works(operation), [RemovedWork("b.json", "9", "a.json", "1")])

    def test_an_operation_that_only_edits_removes_nothing(self) -> None:
        operation = {
            "before": [self._state("a.json", "1", True)],
            "after": [self._state("a.json", "1", True)],
        }
        self.assertEqual(_removed_works(operation), [])

    def test_a_member_that_was_not_there_before_is_not_counted_as_removed(self) -> None:
        operation = {
            "before": [self._state("a.json", "1", True), self._state("a.json", "2", False)],
            "after": [self._state("a.json", "1", True), self._state("a.json", "2", False)],
        }
        self.assertEqual(_removed_works(operation), [])

    def test_a_group_removes_every_member_but_the_survivor(self) -> None:
        operation = {
            "before": [self._state("a.json", str(n), True) for n in (1, 2, 3)],
            "after": [
                self._state("a.json", "3", True),
                self._state("a.json", "1", False),
                self._state("a.json", "2", False),
            ],
        }
        self.assertEqual(
            _removed_works(operation),
            [RemovedWork("a.json", "1", "a.json", "3"), RemovedWork("a.json", "2", "a.json", "3")],
        )

    def test_a_malformed_operation_is_refused_not_guessed_at(self) -> None:
        with self.assertRaises(CurationWorkflowError):
            _removed_works({"before": "nothing", "after": []})


if __name__ == "__main__":
    unittest.main()
