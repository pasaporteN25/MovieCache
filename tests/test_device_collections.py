"""[A2.6] first step: the collections an account follows, over the device API.

Two things these tests exist to hold. A device replica gets what its owner
reads -- followed collections only, never a directory of the instance. And a
collection item crosses to a phone through an allowlist, so invariant 4 does not
depend on a promise made in another module.
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
from movie_inbox.domain.collections import CollectionItem, CuratedCollection
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

# Operational fields a collection row must never carry to a phone. They are
# stripped when a collection is written, so finding one here would mean a leak
# opened somewhere between storage and the wire.
FORBIDDEN = ("path", "local_files", "local_name", "absolute_path", "notes", "_source_file")


class DeviceCollectionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        self.instance_path = root / "instance.db"
        self.password = "a-long-local-password"
        identity = SqliteIdentityRepository(self.instance_path)
        AuthService(identity).bootstrap_owner(
            "lucas",
            self.password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        owner = identity.owner()
        assert owner is not None
        self.owner_id = owner.id

        self.collections = SqliteCollectionRepository(self.instance_path)
        self.followed_id = self._collection("seguida", "Kurosawa", follow=True)
        self._collection("ignorada", "Sin seguir", follow=False)

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
        session = self.client.post(
            "/api/v1/auth/login",
            content=json.dumps(
                {"username": "lucas", "password": self.password, "device_name": "Pixel"}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(session.status_code, 201, session.content)
        self.bearer = {"Authorization": f"Bearer {session.json()['access_token']}"}

    def _collection(self, slug: str, title: str, *, follow: bool) -> str:
        collection = CuratedCollection(
            id=slug,
            slug=slug,
            title=title,
            description="Una lista",
            owner_user_id=self.owner_id,
            source_kind="import",
            items=tuple(
                CollectionItem(
                    id=f"{slug}-{position}",
                    position=position,
                    item={
                        "id": f"{slug}-{position}",
                        "title": f"Obra {position}",
                        "year": "1954",
                        "kind": "pelicula",
                        # Deliberately handed operational fields to check they do
                        # not survive the trip.
                        "path": "/media/disco1/obra.mkv",
                        "local_files": ["/media/disco1/obra.mkv"],
                        "notes": "nota privada",
                    },
                )
                for position in range(3)
            ),
        )
        self.collections.create_private(collection)
        if follow:
            self.collections.set_following(self.owner_id, collection.id, True)
        return collection.id

    def _get(self, path: str) -> Any:
        return self.client.get(path, headers=self.bearer)

    def test_only_followed_collections_reach_the_device(self) -> None:
        response = self._get("/api/v1/collections")
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()["collections"]
        self.assertEqual([row["title"] for row in rows], ["Kurosawa"])
        self.assertEqual(rows[0]["count"], 3)

    def test_the_collection_id_is_opaque_and_stable(self) -> None:
        first = self._get("/api/v1/collections").json()["collections"][0]["id"]
        again = self._get("/api/v1/collections").json()["collections"][0]["id"]
        self.assertEqual(first, again, "a replica keys on this; it cannot move")
        self.assertNotIn(self.followed_id, first)
        self.assertNotIn("Kurosawa", first)

    def test_items_come_back_paged_and_without_operational_fields(self) -> None:
        collection_id = self._get("/api/v1/collections").json()["collections"][0]["id"]
        page = self._get(f"/api/v1/collections/{collection_id}/items?limit=2")
        self.assertEqual(page.status_code, 200, page.content)
        body = page.json()
        self.assertEqual(len(body["items"]), 2)
        self.assertTrue(body["next_cursor"])

        raw = page.content.decode("utf-8")
        for field in FORBIDDEN:
            with self.subTest(field=field):
                self.assertNotIn(field, raw)
        # Nor is there personal state: following a collection does not copy its
        # works into your catalogue, so there is none to report.
        self.assertNotIn("personal", raw)
        self.assertNotIn("rating", raw)

        rest = self._get(
            f"/api/v1/collections/{collection_id}/items?limit=2&cursor={body['next_cursor']}"
        ).json()
        self.assertEqual(len(rest["items"]), 1)
        self.assertIsNone(rest["next_cursor"])

    def test_a_collection_the_account_does_not_follow_is_not_readable(self) -> None:
        # Its real id is useless here: ids are opaque, and only followed
        # collections are even considered.
        self.assertEqual(self._get("/api/v1/collections/ignorada/items").status_code, 404)
        self.assertEqual(self._get("/api/v1/collections/inventado/items").status_code, 404)

    def test_unfollowing_takes_it_away_from_the_device_too(self) -> None:
        collection_id = self._get("/api/v1/collections").json()["collections"][0]["id"]
        self.assertEqual(self._get(f"/api/v1/collections/{collection_id}/items").status_code, 200)
        self.collections.set_following(self.owner_id, self.followed_id, False)
        self.assertEqual(self._get("/api/v1/collections").json()["collections"], [])
        self.assertEqual(self._get(f"/api/v1/collections/{collection_id}/items").status_code, 404)

    def test_a_cursor_from_one_collection_does_not_work_on_another(self) -> None:
        # Cursors are signed and bound to their context, so a page token cannot
        # be carried across collections.
        self._collection("otra", "Otra lista", follow=True)
        rows = self._get("/api/v1/collections").json()["collections"]
        first, second = (row["id"] for row in rows[:2])
        cursor = self._get(f"/api/v1/collections/{first}/items?limit=1").json()["next_cursor"]
        crossed = self._get(f"/api/v1/collections/{second}/items?limit=1&cursor={cursor}")
        self.assertEqual(crossed.status_code, 400)

    def test_both_endpoints_need_a_device_session(self) -> None:
        self.assertEqual(self.client.get("/api/v1/collections").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/collections/x/items").status_code, 401)


if __name__ == "__main__":
    unittest.main()
