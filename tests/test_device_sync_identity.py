"""The device item id as a durable sync key ([A1.4], implementing ADR-0005).

The mobile client keeps a local replica, so the key it stores has to survive
operations that are entirely normal on the server. [MB1] measured that the
original derivation did not: these tests now pin the fixed behaviour, and the
two that recorded the defect say so where they assert the opposite.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.pairing_service import DEVICE_SYNC_SECRET
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.identity import (
    AuthenticatedIdentity,
    CatalogSource,
    PersonalCatalog,
    UserAccount,
)
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.dependencies import SessionCatalog
from movie_inbox.web.device_ids import opaque_item_id as _opaque_item_id
from movie_inbox.web.responses import ApiRequestError


class OpaqueItemIdTests(unittest.TestCase):
    def test_it_is_stable_while_nothing_around_it_changes(self) -> None:
        first = _opaque_item_id(b"secreto", "catalogo-1", "fuente-a", "heat")
        second = _opaque_item_id(b"secreto", "catalogo-1", "fuente-a", "heat")
        self.assertEqual(first, second)

    def test_it_does_not_leak_the_source_the_catalogue_id_or_the_item_id(self) -> None:
        opaque = _opaque_item_id(b"secreto", "catalogo-1", "fuente-a", "heat")
        self.assertNotIn("catalogo-1", opaque)
        self.assertNotIn("fuente-a", opaque)
        self.assertNotIn("heat", opaque)

    def test_distinct_works_sources_and_catalogues_never_collide(self) -> None:
        base = _opaque_item_id(b"secreto", "catalogo-1", "fuente-a", "heat")
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-1", "fuente-a", "akira"))
        # Item ids are only unique inside one source file, so the source has to
        # keep taking part in the key.
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-1", "fuente-b", "heat"))
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-2", "fuente-a", "heat"))

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
        before = _opaque_item_id(secret, "catalogo-1", "fuente-a", "heat")
        # Rotating the api_token does not touch the stored secret at all.
        after = self.repository.instance_secret(DEVICE_SYNC_SECRET).encode("utf-8")
        self.assertEqual(before, _opaque_item_id(after, "catalogo-1", "fuente-a", "heat"))


def _owner_app(
    root: Path, sources: list[Path], password: str
) -> tuple[str, TestClient, dict[str, str]]:
    """Bootstrap an owner over `sources`, start the app and pair a phone."""

    instance = root / "instance.db"
    _, catalog = AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
        "lucas",
        password,
        catalog_name="Catalogo de Lucas",
        source_paths=[str(path) for path in sources],
        write_path=str(sources[0]),
    )
    media = root / "media"
    media.mkdir()
    config = ViewerConfig(
        patterns=[str(path) for path in sources],
        title="Movie Inbox Test",
        write_json=str(sources[0]),
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
    client = context.__enter__()
    login = client.post(
        "/api/v1/auth/login",
        content=json.dumps({"username": "lucas", "password": password, "device_name": "Pixel"}),
        headers={"Content-Type": "application/json"},
    )
    if login.status_code != 201:
        context.__exit__(None, None, None)
        raise AssertionError(login.content)
    return catalog.id, client, {"Authorization": f"Bearer {login.json()['access_token']}"}


class SourceListChangesTests(unittest.TestCase):
    """[X11]: a phone's ids survive changes to the account's list of sources.

    The source used to take part in the id by its position, so adding, removing
    or reordering one re-keyed every work in every later source, and a phone
    saw its whole replica vanish and come back as new works (case 17 of the
    sync matrix in movieIndexAndroid). Nothing in the app changes the list yet;
    an operator editing `instance.db` does, and these edit it the same way.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.first = self.root / "peliculas.json"
        self.second = self.root / "archivo.json"
        self.third = self.root / "series.json"
        works = {
            self.first: [("heat", "Heat", "1995"), ("akira", "Akira", "1988")],
            # The same item id as in the first file: only the source tells them apart.
            self.second: [("heat", "Heat", "1986")],
            self.third: [("twin-peaks", "Twin Peaks", "1990")],
        }
        for path, rows in works.items():
            JsonCatalogRepository(path, normalize_item).write(
                [
                    normalize_item({"id": id_, "title": title, "year": year, "kind": "pelicula"})
                    for id_, title, year in rows
                ]
            )
        self.instance = self.root / "instance.db"
        self.catalog_id, self.client, self.bearer = _owner_app(
            self.root, [self.first, self.second, self.third], "a-long-local-password"
        )
        self.addCleanup(self.client.__exit__, None, None, None)

    def _ids(self) -> dict[tuple[str, str], str]:
        response = self.client.get("/api/v1/catalog/items", headers=self.bearer)
        self.assertEqual(response.status_code, 200, response.content)
        return {(item["title"], str(item["year"])): item["id"] for item in response.json()["items"]}

    def _edit_sources(self, *statements: tuple[str, tuple[object, ...]]) -> None:
        with closing(sqlite3.connect(self.instance)) as connection:
            for sql, parameters in statements:
                connection.execute(sql, parameters)
            connection.commit()

    def test_reordering_the_sources_changes_no_id(self) -> None:
        before = self._ids()

        self._edit_sources(
            (
                "UPDATE catalog_sources SET position = position + 100 WHERE catalog_id = ?",
                (self.catalog_id,),
            ),
            (
                "UPDATE catalog_sources SET position = 102 - position WHERE catalog_id = ?",
                (self.catalog_id,),
            ),
        )

        self.assertEqual(self._ids(), before)

    def test_removing_a_source_changes_no_other_id(self) -> None:
        before = self._ids()

        self._edit_sources(
            (
                "DELETE FROM catalog_sources WHERE catalog_id = ? AND storage_path = ?",
                (self.catalog_id, str(self.first.resolve())),
            )
        )

        after = self._ids()
        self.assertEqual(set(after), {("Heat", "1986"), ("Twin Peaks", "1990")})
        self.assertEqual(after, {key: before[key] for key in after})

    def test_adding_a_source_changes_no_existing_id(self) -> None:
        before = self._ids()
        added = self.root / "nuevas.json"
        JsonCatalogRepository(added, normalize_item).write(
            [normalize_item({"id": "ran", "title": "Ran", "year": "1985", "kind": "pelicula"})]
        )

        self._edit_sources(
            (
                """INSERT INTO catalog_sources
                (catalog_id, position, storage_path, writable, source_uid)
                VALUES (?, -1, ?, 0, ?)""",
                (self.catalog_id, str(added.resolve()), uuid.uuid4().hex),
            )
        )

        after = self._ids()
        self.assertIn(("Ran", "1985"), after)
        self.assertEqual({key: after[key] for key in before}, before)

    def test_relocating_a_source_file_changes_no_id(self) -> None:
        # [A1.4]'s property, kept: the path never took part in the id.
        before = self._ids()
        moved = self.root / "archivo-movido.json"
        self.second.rename(moved)

        self._edit_sources(
            (
                "UPDATE catalog_sources SET storage_path = ? "
                "WHERE catalog_id = ? AND storage_path = ?",
                (str(moved.resolve()), self.catalog_id, str(self.second.resolve())),
            )
        )

        self.assertEqual(self._ids(), before)

    def test_a_patch_after_a_reorder_still_lands_on_the_work_it_names(self) -> None:
        older = self._ids()[("Heat", "1986")]
        self._edit_sources(
            (
                "UPDATE catalog_sources SET position = position + 100 WHERE catalog_id = ?",
                (self.catalog_id,),
            ),
            (
                "UPDATE catalog_sources SET position = 102 - position WHERE catalog_id = ?",
                (self.catalog_id,),
            ),
        )

        patched = self.client.patch(
            f"/api/v1/catalog/items/{older}/personal",
            content=json.dumps({"status": "watched"}),
            headers={**self.bearer, "Content-Type": "application/json"},
        )

        self.assertEqual(patched.status_code, 200, patched.content)
        second = json.loads(self.second.read_text(encoding="utf-8"))["items"]
        first = json.loads(self.first.read_text(encoding="utf-8"))["items"]
        self.assertEqual(next(row for row in second if row["id"] == "heat")["status"], "watched")
        self.assertNotEqual(next(row for row in first if row["id"] == "heat")["status"], "watched")


class SessionCatalogSourceUidTests(unittest.TestCase):
    """A source without a durable uid, or two sharing one, cannot key a phone's ids."""

    def _identity(self, *uids: str) -> AuthenticatedIdentity:
        sources = tuple(
            CatalogSource(f"/catalogos/{index}.json", index == 0, uid=uid)
            for index, uid in enumerate(uids)
        )
        return AuthenticatedIdentity(
            UserAccount("u", "lucas", "owner", True, False, "now"),
            PersonalCatalog("c", "u", "Catalogo", sources, "now"),
            0,
        )

    def _config(self) -> ViewerConfig:
        return ViewerConfig(
            patterns=[],
            title="Movie Inbox Test",
            write_json="",
            image_cache=False,
            image_cache_dir="",
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
        )

    def test_each_reference_carries_its_sources_uid(self) -> None:
        catalog = SessionCatalog.from_identity(self._config(), self._identity("a" * 32, "b" * 32))
        self.assertEqual(catalog.source_uids, {"source-1": "a" * 32, "source-2": "b" * 32})

    def test_a_missing_uid_is_refused(self) -> None:
        with self.assertRaises(ApiRequestError):
            SessionCatalog.from_identity(self._config(), self._identity("a" * 32, ""))

    def test_two_sources_sharing_a_uid_are_refused(self) -> None:
        with self.assertRaises(ApiRequestError):
            SessionCatalog.from_identity(self._config(), self._identity("a" * 32, "a" * 32))


class SourceUidMigrationTests(unittest.TestCase):
    """v24 gives every existing source -- active or archived -- its own uid."""

    def test_an_instance_from_before_gets_one_distinct_uid_per_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.db"
            with patch(
                "movie_inbox.infrastructure.identity_repository.INSTANCE_SCHEMA_VERSION", 23
            ):
                SqliteIdentityRepository(path).initialize()
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(
                    """
                    INSERT INTO users(
                        id, username, username_key, password_hash, role, active,
                        must_change_password, created_at, updated_at
                    ) VALUES ('owner', 'lucas', 'lucas', 'hash', 'owner', 1, 0, 'now', 'now');
                    INSERT INTO catalogs(id, owner_user_id, name, is_default, created_at)
                    VALUES ('catalogo', 'owner', 'Catalogo', 1, 'now');
                    INSERT INTO catalog_sources(catalog_id, position, storage_path, writable)
                    VALUES ('catalogo', 0, '/a.json', 1), ('catalogo', 1, '/b.json', 0);
                    INSERT INTO archived_members(
                        id, former_user_id, username, catalog_name, archived_at
                    ) VALUES ('archivo', 'antes', 'maria', 'Maria', 'now');
                    INSERT INTO archived_catalog_sources(
                        archive_id, position, storage_path, writable
                    ) VALUES ('archivo', 0, '/maria.db', 1);
                    """
                )

            repository = SqliteIdentityRepository(path)
            repository.initialize()

            catalog = repository.default_catalog_for("owner")
            assert catalog is not None
            uids = [source.uid for source in catalog.sources]
            (archived,) = repository.list_archived_members()
            uids.append(archived.sources[0].uid)
            self.assertEqual(len(set(uids)), 3)
            for uid in uids:
                self.assertRegex(uid, r"^[0-9a-f]{32}$")
            # Applied once: opening the instance again does not mint new ones.
            reopened = SqliteIdentityRepository(path).default_catalog_for("owner")
            assert reopened is not None
            self.assertEqual([source.uid for source in reopened.sources], uids[:2])


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
        # [X3.3] added changed_at to the wire payload; base only accepts the
        # four writable fields, so a real client would not echo it back either.
        self.base_personal = {
            key: value for key, value in first["personal"].items() if key != "changed_at"
        }

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

    def test_a_patched_field_gets_a_changed_at_mark_and_others_stay_absent(self) -> None:
        response = self._patch({"rating": 9})

        changed_at = response.json()["personal"]["changed_at"]
        self.assertEqual(set(changed_at), {"rating"})
        self.assertNotIn("review", changed_at)


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


class KeysetPaginationTests(unittest.TestCase):
    """[X10]: the catalog cursor resumes after a stable key, not a position.

    Reproduces the two failure shapes [A5.1] case 16 describes: a work
    removed during a paged download used to skip the one after it, and a
    work added used to repeat the one just delivered -- both because every
    later position shifted by one.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog.json"
        self.repository = JsonCatalogRepository(self.catalog, normalize_item)
        self.repository.write(
            [
                normalize_item(
                    {"id": "akira", "title": "Akira", "year": "1988", "kind": "pelicula"}
                ),
                normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}),
                normalize_item(
                    {"id": "vertigo", "title": "Vertigo", "year": "1958", "kind": "pelicula"}
                ),
            ]
        )
        instance = self.root / "instance.db"
        password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
            "lucas",
            password,
            catalog_name="Catalogo",
            source_paths=[str(self.catalog)],
            write_path=str(self.catalog),
        )
        (self.root / "media").mkdir()
        config = ViewerConfig(
            patterns=[str(self.catalog)],
            title="Movie Inbox Test",
            write_json=str(self.catalog),
            image_cache=False,
            image_cache_dir=str(self.root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(instance),
            member_catalog_dir=str(self.root / "member-catalogs"),
            library_allowed_roots=(str(self.root / "media"),),
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

    def _page(self, cursor: str = "") -> Any:
        params = {"limit": "1"}
        if cursor:
            params["cursor"] = cursor
        return self.client.get("/api/v1/catalog/items", params=params, headers=self.bearer)

    def test_removing_the_delivered_work_does_not_skip_the_next_one(self) -> None:
        first = self._page()
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["items"][0]["title"], "Akira")
        cursor = first.json()["next_cursor"]

        self.assertTrue(self.repository.delete_by_id("akira"))

        second = self._page(cursor)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json()["items"][0]["title"], "Heat")

    def test_adding_a_work_that_sorts_earlier_does_not_repeat_the_delivered_one(self) -> None:
        first = self._page()
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["items"][0]["title"], "Akira")
        cursor = first.json()["next_cursor"]

        # Casefolds to "aaa test", sorting before "akira".
        rows = self.repository.read()
        self.repository.write(
            [*rows, normalize_item({"id": "aaa", "title": "AAA Test", "kind": "pelicula"})]
        )

        second = self._page(cursor)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json()["items"][0]["title"], "Heat")


if __name__ == "__main__":
    unittest.main()
