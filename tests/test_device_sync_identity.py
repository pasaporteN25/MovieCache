"""The device item id as a durable sync key ([A1.4], implementing ADR-0005).

The mobile client keeps a local replica, so the key it stores has to survive
operations that are entirely normal on the server. [MB1] measured that the
original derivation did not: these tests now pin the fixed behaviour, and the
two that recorded the defect say so where they assert the opposite.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.routers.device_catalog import DEVICE_SYNC_SECRET, _opaque_item_id


class OpaqueItemIdTests(unittest.TestCase):
    def test_it_is_stable_while_nothing_around_it_changes(self) -> None:
        first = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        second = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertEqual(first, second)

    def test_it_does_not_leak_the_path_the_catalogue_id_or_the_item_id(self) -> None:
        opaque = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertNotIn("catalogo-1", opaque)
        self.assertNotIn("source-1", opaque)
        self.assertNotIn("heat", opaque)

    def test_the_source_slot_carries_no_path(self) -> None:
        # [A1.4]: relocating a catalogue used to re-key every work, because the
        # absolute file path was part of the message. The slot replaces it.
        moved = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertEqual(moved, _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat"))

    def test_distinct_works_sources_and_catalogues_never_collide(self) -> None:
        base = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-1", "source-1", "akira"))
        # Item ids are only unique inside one source file, so the slot has to
        # keep taking part in the key.
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-1", "source-2", "heat"))
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-2", "source-1", "heat"))

    def test_the_separator_cannot_be_forged_from_field_contents(self) -> None:
        self.assertNotEqual(
            _opaque_item_id(b"s", "a", "b", "c"),
            _opaque_item_id(b"s", "a\x1fb", "", "c"),
        )


class InstanceSecretTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "instance.db"
        repository = SqliteIdentityRepository(self.path)
        repository.initialize()
        AuthService(repository).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(Path(self.temporary.name) / "catalog.json")],
            write_path=str(Path(self.temporary.name) / "catalog.json"),
        )
        self.repository = repository

    def test_the_sync_secret_is_created_once_and_then_kept(self) -> None:
        first = self.repository.instance_secret(DEVICE_SYNC_SECRET)
        self.assertTrue(first)
        self.assertEqual(self.repository.instance_secret(DEVICE_SYNC_SECRET), first)
        # A fresh handle on the same database sees the same secret, which is
        # what makes the key survive a server restart.
        self.assertEqual(
            SqliteIdentityRepository(self.path).instance_secret(DEVICE_SYNC_SECRET), first
        )

    def test_different_names_get_different_secrets(self) -> None:
        self.assertNotEqual(
            self.repository.instance_secret(DEVICE_SYNC_SECRET),
            self.repository.instance_secret("otro_proposito"),
        )

    def test_the_key_no_longer_depends_on_the_rotatable_api_token(self) -> None:
        # This is the defect [MB1] measured: the secret used to be
        # viewer_config.api_token, so rotating it re-keyed every work and a
        # paired client could no longer match its replica.
        secret = self.repository.instance_secret(DEVICE_SYNC_SECRET).encode("utf-8")
        before = _opaque_item_id(secret, "catalogo-1", "source-1", "heat")
        # Rotating the api_token does not touch the stored secret at all.
        after = self.repository.instance_secret(DEVICE_SYNC_SECRET).encode("utf-8")
        self.assertEqual(before, _opaque_item_id(after, "catalogo-1", "source-1", "heat"))


class TwoSourceCatalogueTests(unittest.TestCase):
    """The same item id in two source files is two works, with two device ids.

    Found by the 0.9.0 security review. The slot was looked up by resolving the
    row's source as a path, but the rows already carry the public reference
    (`source-1`, `source-2`), so the lookup never matched and every work fell
    back to one slot: two sources sharing an id shared a device id, and a PATCH
    could land on the other work.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.first = root / "peliculas.json"
        self.second = root / "archivo.json"
        for path, year in ((self.first, "1995"), (self.second, "1986")):
            JsonCatalogRepository(path, normalize_item).write(
                [normalize_item({"id": "heat", "title": "Heat", "year": year, "kind": "pelicula"})]
            )
        instance = root / "instance.db"
        password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
            "lucas",
            password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.first), str(self.second)],
            write_path=str(self.first),
        )
        media = root / "media"
        media.mkdir()
        config = ViewerConfig(
            patterns=[str(self.first), str(self.second)],
            title="Movie Inbox Test",
            write_json=str(self.first),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(instance),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media),),
            library_scheduler_poll_seconds=3600,
        )
        context = TestClient(create_app(config), base_url="http://127.0.0.1:8765")
        self.client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        login = self.client.post(
            "/api/v1/auth/login",
            content=json.dumps({"username": "lucas", "password": password, "device_name": "Pixel"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(login.status_code, 201, login.content)
        self.bearer = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def _status_in(self, path: Path) -> str:
        items = json.loads(path.read_text(encoding="utf-8"))["items"]
        return str(next(item for item in items if item["id"] == "heat").get("status") or "")

    def test_each_source_keeps_its_own_device_id(self) -> None:
        response = self.client.get("/api/v1/catalog/items", headers=self.bearer)
        self.assertEqual(response.status_code, 200, response.content)
        ids = [item["id"] for item in response.json()["items"]]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2, "two works cannot share one device id")

    def test_a_patch_lands_on_the_work_it_names_and_no_other(self) -> None:
        items = self.client.get("/api/v1/catalog/items", headers=self.bearer).json()["items"]
        older = next(item for item in items if str(item["year"]) == "1986")
        patched = self.client.patch(
            f"/api/v1/catalog/items/{older['id']}/personal",
            content=json.dumps({"status": "watched"}),
            headers={**self.bearer, "Content-Type": "application/json"},
        )
        self.assertEqual(patched.status_code, 200, patched.content)
        self.assertEqual(self._status_in(self.second), "watched")
        self.assertNotEqual(self._status_in(self.first), "watched")


class PersonalPatchConflictHttpTests(unittest.TestCase):
    """[X2] over HTTP: the exact case [A5.3] of movieIndexAndroid reproduced
    2026-09-15 -- a phone uploads what it saw when it last downloaded, without
    looking at the server again first, and used to silently overwrite a
    change another session made in between.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog = root / "catalog.json"
        JsonCatalogRepository(self.catalog, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        instance = root / "instance.db"
        password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
            "lucas",
            password,
            catalog_name="Catalogo",
            source_paths=[str(self.catalog)],
            write_path=str(self.catalog),
        )
        media = root / "media"
        media.mkdir()
        config = ViewerConfig(
            patterns=[str(self.catalog)],
            title="Movie Inbox Test",
            write_json=str(self.catalog),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(instance),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media),),
            library_scheduler_poll_seconds=3600,
        )
        context = TestClient(create_app(config), base_url="http://127.0.0.1:8765")
        self.client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        login = self.client.post(
            "/api/v1/auth/login",
            content=json.dumps({"username": "lucas", "password": password, "device_name": "Pixel"}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(login.status_code, 201, login.content)
        self.bearer = {"Authorization": f"Bearer {login.json()['access_token']}"}
        first = self.client.get("/api/v1/catalog/items", headers=self.bearer).json()["items"][0]
        self.item_id = first["id"]
        self.base_personal = first["personal"]

    def _patch(self, body: dict[str, Any]) -> Any:
        return self.client.patch(
            f"/api/v1/catalog/items/{self.item_id}/personal",
            content=json.dumps(body),
            headers={**self.bearer, "Content-Type": "application/json"},
        )

    def test_a_stale_base_is_refused_with_409_and_the_other_change_survives(self) -> None:
        # The web rates it while the phone is offline, holding the personal
        # state it downloaded before that (self.base_personal) as its base.
        rated = self._patch({"rating": 9})
        self.assertEqual(rated.status_code, 200, rated.content)

        stale_upload = self._patch({"review": "Buenisima.", "base": self.base_personal})

        self.assertEqual(stale_upload.status_code, 409, stale_upload.content)
        self.assertEqual(stale_upload.json(), {"error": {"code": "personal_conflict"}})
        current = self.client.get(
            f"/api/v1/catalog/items/{self.item_id}", headers=self.bearer
        ).json()
        self.assertEqual(current["personal"]["rating"], 9, "the web's rating must survive")
        self.assertIsNone(current["personal"]["review"], "the stale upload must not apply")

    def test_a_base_that_still_matches_applies_normally(self) -> None:
        response = self._patch({"rating": 9, "base": self.base_personal})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["personal"]["rating"], 9)

    def test_omitting_base_keeps_last_write_wins(self) -> None:
        self._patch({"rating": 9})

        response = self._patch({"review": "Sin comparar nada."})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["personal"]["rating"], 9)
        self.assertEqual(response.json()["personal"]["review"], "Sin comparar nada.")


class CursorSurvivesRestartTests(unittest.TestCase):
    """[X9]: the pagination cursor is signed with the durable instance secret,
    not api_token, so a restart mid-download no longer orphans the next page.
    Same defect shape as [MB1], applied to `_cursor_signature` instead of
    `_opaque_item_id`.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog.json"
        JsonCatalogRepository(self.catalog, normalize_item).write(
            [
                normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}),
                normalize_item(
                    {"id": "akira", "title": "Akira", "year": "1988", "kind": "pelicula"}
                ),
            ]
        )
        self.instance = self.root / "instance.db"
        self.password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(self.instance)).bootstrap_owner(
            "lucas",
            self.password,
            catalog_name="Catalogo",
            source_paths=[str(self.catalog)],
            write_path=str(self.catalog),
        )
        (self.root / "media").mkdir()

    def _login(self, api_token: str) -> tuple[TestClient, dict[str, str]]:
        config = ViewerConfig(
            patterns=[str(self.catalog)],
            title="Movie Inbox Test",
            write_json=str(self.catalog),
            image_cache=False,
            image_cache_dir=str(self.root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token=api_token,
            instance_db=str(self.instance),
            member_catalog_dir=str(self.root / "member-catalogs"),
            library_allowed_roots=(str(self.root / "media"),),
            library_scheduler_poll_seconds=3600,
        )
        context = TestClient(create_app(config), base_url="http://127.0.0.1:8765")
        client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        login = client.post(
            "/api/v1/auth/login",
            content=json.dumps(
                {"username": "lucas", "password": self.password, "device_name": "Pixel"}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(login.status_code, 201, login.content)
        return client, {"Authorization": f"Bearer {login.json()['access_token']}"}

    def test_a_cursor_minted_before_a_restart_still_pages_after_it(self) -> None:
        before_run, before_bearer = self._login("token-before-restart")
        first_page = before_run.get(
            "/api/v1/catalog/items", params={"limit": "1"}, headers=before_bearer
        )
        self.assertEqual(first_page.status_code, 200, first_page.content)
        cursor = first_page.json()["next_cursor"]
        self.assertIsNotNone(cursor)
        first_id = first_page.json()["items"][0]["id"]

        # `serve` mints a fresh random api_token on every restart; this used
        # to be the cursor's signing key, so the next page died with it.
        after_run, after_bearer = self._login("token-after-restart")
        second_page = after_run.get(
            "/api/v1/catalog/items",
            params={"limit": "1", "cursor": cursor},
            headers=after_bearer,
        )
        self.assertEqual(second_page.status_code, 200, second_page.content)
        second_id = second_page.json()["items"][0]["id"]
        self.assertNotEqual(first_id, second_id)


if __name__ == "__main__":
    unittest.main()
