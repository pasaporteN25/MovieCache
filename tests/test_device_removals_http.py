"""[X5.3] Deleting a work in the browser leaves a record a phone can be told.

The record is asked of the service directly here: the route a phone asks it
through is the next step, and what this one settles is only that the right id
gets recorded, from every way the browser can name a work, and that a failure
to record never takes the deletion down with it.
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
from movie_inbox.application.removal_repository import RemovalRepositoryError
from movie_inbox.application.removal_service import RemovalService, RemovalStatus
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

WORKS: list[dict[str, Any]] = [
    {"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"},
    {"id": "ran", "title": "Ran", "year": "1985", "kind": "pelicula"},
    {"id": "stalker", "title": "Stalker", "year": "1979", "kind": "pelicula"},
]


class DeleteLeavesARecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item(work) for work in WORKS]
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


if __name__ == "__main__":
    unittest.main()
