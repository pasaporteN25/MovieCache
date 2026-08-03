from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.web.app import MAX_JSON_BODY_BYTES, create_app
from movie_inbox.web.catalog_api import background_enrich_catalog_item
from movie_inbox.web.config import ViewerConfig


class ViewerHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.catalog_path = Path(self.temporary.name) / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        self.owner_password = "a-long-local-password"
        self.instance_path = Path(self.temporary.name) / "instance.db"
        AuthService(SqliteIdentityRepository(self.instance_path)).bootstrap_owner(
            "lucas",
            self.owner_password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        self.config = ViewerConfig(
            patterns=[str(self.catalog_path)],
            title="Movie Inbox Test",
            write_json=str(self.catalog_path),
            image_cache=False,
            image_cache_dir=str(Path(self.temporary.name) / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(self.instance_path),
            member_catalog_dir=str(Path(self.temporary.name) / "member-catalogs"),
        )
        self.client_context = TestClient(create_app(self.config), base_url="http://127.0.0.1:8765")
        self.client = self.client_context.__enter__()
        self.login_response = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": self.owner_password}),
            headers=self.post_headers(),
        )
        self.assertEqual(self.login_response.status_code, 200, self.login_response.content)

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary.cleanup()

    def request(self, method: str, path: str, body: str = "", headers: dict[str, str] | None = None):
        response = self.client.request(method, path, content=body, headers=headers or {})
        return response.status_code, response.content

    def post_headers(self, content_type: str = "application/json") -> dict[str, str]:
        return {
            "X-Movie-Inbox-Token": self.config.api_token,
            "Origin": "http://127.0.0.1:8765",
            "Content-Type": content_type,
        }

    def test_api_requires_token(self) -> None:
        status, _ = self.request("GET", "/api/items")
        self.assertEqual(status, 403)

    def test_catalog_and_api_require_an_authenticated_session(self) -> None:
        with TestClient(create_app(self.config), base_url="http://127.0.0.1:8765") as client:
            root = client.get("/", follow_redirects=False)
            api = client.get("/api/items", headers={"X-Movie-Inbox-Token": self.config.api_token})
            login = client.get("/login")
        self.assertEqual(root.status_code, 303)
        self.assertEqual(root.headers["location"], "/login")
        self.assertEqual(api.status_code, 401)
        self.assertEqual(login.status_code, 200)
        self.assertIn(b'id="loginForm"', login.content)
        self.assertIn(b'/static/login.js', login.content)

    def test_member_must_change_password_and_catalog_is_isolated_by_session(self) -> None:
        created = self.client.post(
            "/api/members",
            content=json.dumps({
                "username": "maria",
                "temporary_password": "a-temporary-password",
            }),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        member_payload = created.json()["member"]
        self.assertNotIn(str(self.temporary.name), created.text)

        identity_repository = SqliteIdentityRepository(self.instance_path)
        member_catalog = identity_repository.default_catalog_for(member_payload["id"])
        self.assertIsNotNone(member_catalog)
        member_repository = open_catalog_repository(Path(member_catalog.write_path), normalize_item)
        member_repository.write([
            normalize_item({"id": "heat", "title": "Heat", "year": "1995", "status": "to_watch"})
        ])

        with TestClient(create_app(self.config), base_url="http://127.0.0.1:8765") as member_client:
            login = member_client.post(
                "/auth/login",
                content=json.dumps({"username": "maria", "password": "a-temporary-password"}),
                headers=self.post_headers(),
            )
            self.assertEqual(login.status_code, 200, login.content)
            self.assertTrue(login.json()["user"]["must_change_password"])

            blocked = member_client.get(
                "/api/items",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            password_page = member_client.get("/password-change")
            self.assertEqual(blocked.status_code, 403)
            self.assertEqual(blocked.json()["reason"], "password_change_required")
            self.assertEqual(password_page.status_code, 200)

            changed = member_client.post(
                "/auth/change-password",
                content=json.dumps({
                    "current_password": "a-temporary-password",
                    "new_password": "a-permanent-password",
                    "confirm_password": "a-permanent-password",
                }),
                headers=self.post_headers(),
            )
            self.assertEqual(changed.status_code, 200, changed.content)
            self.assertFalse(changed.json()["user"]["must_change_password"])

            member_items = member_client.get(
                "/api/items",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(member_items.status_code, 200, member_items.content)
            self.assertEqual([item["id"] for item in member_items.json()["items"]], ["heat"])
            self.assertEqual(member_items.json()["items"][0]["_source_file"], "source-1")
            self.assertNotIn(str(member_catalog.write_path), member_items.text)

            updated = member_client.post(
                "/api/status",
                content=json.dumps({
                    "id": "heat",
                    "status": "watched",
                    "source_file": str(self.catalog_path),
                }),
                headers=self.post_headers(),
            )
            forbidden_members = member_client.get(
                "/api/members",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(updated.status_code, 200, updated.content)
            self.assertEqual(forbidden_members.status_code, 403)

        owner_item = JsonCatalogRepository(self.catalog_path, normalize_item).get("heat")
        member_item = member_repository.get("heat")
        self.assertEqual(owner_item.status, "to_watch")
        self.assertEqual(member_item.status, "watched")

    def test_owner_can_deactivate_and_reset_a_member(self) -> None:
        created = self.client.post(
            "/api/members",
            content=json.dumps({"username": "maria"}),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        member_id = created.json()["member"]["id"]
        generated_password = created.json()["temporary_password"]
        self.assertGreaterEqual(len(generated_password), 12)

        deactivated = self.client.post(
            f"/api/members/{member_id}/status",
            content=json.dumps({"active": False}),
            headers=self.post_headers(),
        )
        reset = self.client.post(
            f"/api/members/{member_id}/password-reset",
            content="{}",
            headers=self.post_headers(),
        )
        listed = self.client.get(
            "/api/members",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.content)
        self.assertFalse(deactivated.json()["member"]["active"])
        self.assertEqual(reset.status_code, 200, reset.content)
        self.assertTrue(reset.json()["member"]["must_change_password"])
        self.assertEqual(len(listed.json()["members"]), 1)

    def test_owner_can_edit_archive_and_restore_a_member_catalog(self) -> None:
        owner_id = self.login_response.json()["user"]["id"]
        created = self.client.post(
            "/api/members",
            content=json.dumps({"username": "maria", "temporary_password": "a-temporary-password"}),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        member_id = created.json()["member"]["id"]
        identity_repository = SqliteIdentityRepository(self.instance_path)
        original_catalog = identity_repository.default_catalog_for(member_id)
        self.assertIsNotNone(original_catalog)
        original_catalog_path = Path(original_catalog.write_path)

        updated = self.client.post(
            f"/api/members/{member_id}/profile",
            content=json.dumps({"username": "maria.cine", "catalog_name": "Videoteca de Maria"}),
            headers=self.post_headers(),
        )
        invalid = self.client.post(
            f"/api/members/{member_id}/profile",
            content=json.dumps({"username": "", "catalog_name": "Videoteca de Maria"}),
            headers=self.post_headers(),
        )
        active_archive = self.client.post(
            f"/api/members/{member_id}/archive",
            content=json.dumps({"confirmed_username": "maria.cine"}),
            headers=self.post_headers(),
        )
        protected_owner = self.client.post(
            f"/api/members/{owner_id}/archive",
            content=json.dumps({"confirmed_username": "lucas"}),
            headers=self.post_headers(),
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["member"]["username"], "maria.cine")
        self.assertEqual(updated.json()["member"]["catalog"]["name"], "Videoteca de Maria")
        self.assertEqual(invalid.status_code, 400, invalid.content)
        self.assertEqual(active_archive.status_code, 409, active_archive.content)
        self.assertEqual(active_archive.json()["reason"], "member_must_be_inactive")
        self.assertEqual(protected_owner.status_code, 409, protected_owner.content)
        self.assertEqual(protected_owner.json()["reason"], "owner_account_protected")

        deactivated = self.client.post(
            f"/api/members/{member_id}/status",
            content=json.dumps({"active": False}),
            headers=self.post_headers(),
        )
        wrong_confirmation = self.client.post(
            f"/api/members/{member_id}/archive",
            content=json.dumps({"confirmed_username": "maria"}),
            headers=self.post_headers(),
        )
        archived = self.client.post(
            f"/api/members/{member_id}/archive",
            content=json.dumps({"confirmed_username": "maria.cine"}),
            headers=self.post_headers(),
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.content)
        self.assertEqual(wrong_confirmation.status_code, 400, wrong_confirmation.content)
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertTrue(original_catalog_path.exists())
        self.assertNotIn(str(self.temporary.name), archived.text)

        listed = self.client.get(
            "/api/members",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        archive_id = archived.json()["archived"]["id"]
        self.assertEqual(listed.json()["members"], [])
        self.assertEqual([entry["id"] for entry in listed.json()["archived"]], [archive_id])
        self.assertNotIn(str(self.temporary.name), listed.text)

        invalid_restore = self.client.post(
            f"/api/member-archives/{archive_id}/restore",
            content=json.dumps({"username": "!"}),
            headers=self.post_headers(),
        )
        self.assertEqual(invalid_restore.status_code, 400, invalid_restore.content)

        restored = self.client.post(
            f"/api/member-archives/{archive_id}/restore",
            content="{}",
            headers=self.post_headers(),
        )
        self.assertEqual(restored.status_code, 200, restored.content)
        self.assertTrue(restored.json()["member"]["must_change_password"])
        self.assertGreaterEqual(len(restored.json()["temporary_password"]), 12)
        restored_catalog = identity_repository.default_catalog_for(restored.json()["member"]["id"])
        self.assertIsNotNone(restored_catalog)
        self.assertEqual(Path(restored_catalog.write_path), original_catalog_path)
        self.assertFalse(identity_repository.privacy_for(restored.json()["member"]["id"]).catalog_shared)

    def test_shared_catalog_respects_user_preferences_and_item_overrides(self) -> None:
        owner_id = self.login_response.json()["user"]["id"]
        JsonCatalogRepository(self.catalog_path, normalize_item).write([
            normalize_item({
                "id": "heat",
                "title": "Heat",
                "year": "1995",
                "kind": "pelicula",
                "status": "watched",
                "watched_at": "2026-07-31",
                "rating": 9,
                "review": "Una review que puede compartirse.",
                "notes": "nota privada",
                "local_path": "D:/private/Heat.mkv",
                "local_files": [{"name": "Heat.mkv", "path": "D:/private/Heat.mkv"}],
                "locked_fields": ["title"],
            })
        ])
        created = self.client.post(
            "/api/members",
            content=json.dumps({"username": "maria", "temporary_password": "a-temporary-password"}),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)

        with TestClient(create_app(self.config), base_url="http://127.0.0.1:8765") as member_client:
            login = member_client.post(
                "/auth/login",
                content=json.dumps({"username": "maria", "password": "a-temporary-password"}),
                headers=self.post_headers(),
            )
            self.assertEqual(login.status_code, 200, login.content)
            changed = member_client.post(
                "/auth/change-password",
                content=json.dumps({
                    "current_password": "a-temporary-password",
                    "new_password": "a-permanent-password",
                    "confirm_password": "a-permanent-password",
                }),
                headers=self.post_headers(),
            )
            self.assertEqual(changed.status_code, 200, changed.content)
            private_list = member_client.get(
                "/api/community",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(private_list.status_code, 200, private_list.content)
            self.assertEqual(private_list.json()["catalogs"], [])

            preferences = self.client.post(
                "/api/privacy",
                content=json.dumps({
                    "catalog_shared": True,
                    "share_status": True,
                    "share_watched_at": False,
                    "share_history": False,
                    "share_rating": False,
                    "share_review": True,
                }),
                headers=self.post_headers(),
            )
            override = self.client.post(
                "/api/privacy/items/heat",
                content=json.dumps({"rating": "shared", "review": "private"}),
                headers=self.post_headers(),
            )
            self.assertEqual(preferences.status_code, 200, preferences.content)
            self.assertEqual(override.status_code, 200, override.content)

            shared_list = member_client.get(
                "/api/community",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            shared_detail = member_client.get(
                f"/api/community/{owner_id}",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(shared_list.status_code, 200, shared_list.content)
            self.assertEqual([entry["user"]["id"] for entry in shared_list.json()["catalogs"]], [owner_id])
            self.assertNotIn(str(self.temporary.name), shared_list.text)
            self.assertEqual(shared_detail.status_code, 200, shared_detail.content)
            shared_item = shared_detail.json()["items"][0]
            self.assertEqual(shared_item["status"], "watched")
            self.assertEqual(shared_item["rating"], 9)
            self.assertNotIn("watched_at", shared_item)
            self.assertNotIn("review", shared_item)
            for private_field in (
                "notes",
                "local_path",
                "local_files",
                "locked_fields",
                "metadata_sources",
                "_source_file",
                "_privacy",
            ):
                self.assertNotIn(private_field, shared_item)
            self.assertEqual(shared_detail.json()["history"], [])
            self.assertNotIn("D:/private", shared_detail.text)

            hidden = self.client.post(
                "/api/privacy",
                content=json.dumps({
                    "catalog_shared": False,
                    "share_status": True,
                    "share_watched_at": False,
                    "share_history": False,
                    "share_rating": False,
                    "share_review": True,
                }),
                headers=self.post_headers(),
            )
            unavailable = member_client.get(
                f"/api/community/{owner_id}",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(hidden.status_code, 200, hidden.content)
            self.assertEqual(unavailable.status_code, 404, unavailable.content)

    def test_starter_collection_can_be_followed_and_copied_to_personal_catalog(self) -> None:
        listed = self.client.get(
            "/api/collections",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(listed.status_code, 200, listed.content)
        collection = listed.json()["collections"][0]
        self.assertEqual(collection["title"], "Akira Kurosawa")
        self.assertEqual(collection["counts"]["total"], 31)
        self.assertFalse(collection["followed"])

        followed = self.client.post(
            f"/api/collections/{collection['id']}/follow",
            content=json.dumps({"following": True}),
            headers=self.post_headers(),
        )
        detail = self.client.get(
            f"/api/collections/{collection['id']}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(followed.status_code, 200, followed.content)
        self.assertTrue(followed.json()["collection"]["followed"])
        self.assertEqual(detail.status_code, 200, detail.content)
        rashomon = next(item for item in detail.json()["items"] if item["title"] == "Rashomon")
        self.assertEqual(rashomon["catalog"]["state"], "missing")

        added = self.client.post(
            f"/api/collections/{collection['id']}/add",
            content=json.dumps({"item_ids": [rashomon["collection_item_id"]]}),
            headers=self.post_headers(),
        )
        repeated = self.client.post(
            f"/api/collections/{collection['id']}/add",
            content=json.dumps({"item_ids": [rashomon["collection_item_id"]]}),
            headers=self.post_headers(),
        )
        self.assertEqual(added.status_code, 200, added.content)
        self.assertEqual(added.json()["summary"]["added"], 1)
        self.assertEqual(repeated.status_code, 200, repeated.content)
        self.assertEqual(repeated.json()["summary"]["present"], 1)

        item = JsonCatalogRepository(self.catalog_path, normalize_item).get(rashomon["id"])
        self.assertIsNotNone(item)
        self.assertEqual(item.status, "to_watch")
        self.assertEqual(item.rating, 0)
        self.assertEqual(item.review, "")
        self.assertFalse(item.en_catalogo)
        self.assertEqual(item.extra["collection_sources"][0]["collection_id"], collection["id"])

    def test_import_draft_previews_and_idempotently_writes_the_personal_catalog(self) -> None:
        raw_private_path = "D:/Private/Ikiru.mkv"
        created = self.client.post(
            "/api/imports",
            content=json.dumps({
                "source_name": "watched.json",
                "source_format": "json",
                "content": json.dumps([{
                    "title": "Ikiru",
                    "year": "1952",
                    "status": "watched",
                    "watched_at": "2026-08-01",
                    "rating": 10,
                    "review": "Una obra enorme.",
                    "en_catalogo": True,
                    "local_path": raw_private_path,
                    "local_files": [{"name": "Ikiru.mkv", "path": raw_private_path}],
                }]),
            }),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        draft = created.json()
        self.assertEqual(draft["counts"]["new"], 1)
        self.assertTrue(draft["items"][0]["catalog_eligible"])
        self.assertEqual(draft["items"][0]["item"]["local_files"], [])
        self.assertNotIn(raw_private_path, created.text)
        self.assertNotIn(raw_private_path.encode("utf-8"), self.instance_path.read_bytes())

        body = json.dumps({
            "destination": "catalog",
            "item_ids": [draft["items"][0]["id"]],
            "personal_options": {
                "include_status": True,
                "include_watched_at": True,
                "include_rating": True,
                "include_review": True,
            },
        })
        first = self.client.post(
            f"/api/imports/{draft['id']}/apply",
            content=body,
            headers=self.post_headers(),
        )
        repeated = self.client.post(
            f"/api/imports/{draft['id']}/apply",
            content=body,
            headers=self.post_headers(),
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json(), repeated.json())
        self.assertEqual(first.json()["summary"]["added"], 1)

        catalog = JsonCatalogRepository(self.catalog_path, normalize_item).read()
        self.assertEqual([item.title for item in catalog].count("Ikiru"), 1)
        ikiru = next(item for item in catalog if item.title == "Ikiru")
        self.assertEqual(ikiru.status, "watched")
        self.assertEqual(ikiru.rating, 10)
        self.assertEqual(ikiru.review, "Una obra enorme.")
        self.assertEqual(ikiru.local_files, [])

    def test_owner_can_turn_a_draft_into_a_private_collection_without_catalog_writes(self) -> None:
        created = self.client.post(
            "/api/imports",
            content=json.dumps({
                "source_name": "japanese.csv",
                "source_format": "csv",
                "content": "title,year,status,rating,review\nHeat,1995,watched,8,Great\nIkiru,1952,watched,10,Perfect\n",
            }),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        draft = created.json()
        selected = [entry["id"] for entry in draft["items"] if entry["collection_eligible"]]
        self.assertEqual(len(selected), 2)

        applied = self.client.post(
            f"/api/imports/{draft['id']}/apply",
            content=json.dumps({
                "destination": "collection",
                "item_ids": selected,
                "collection_title": "Noches japonesas",
                "collection_description": "Selección privada",
            }),
            headers=self.post_headers(),
        )
        self.assertEqual(applied.status_code, 200, applied.content)
        collection_id = applied.json()["collection"]["id"]
        detail = self.client.get(
            f"/api/collections/{collection_id}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()["visibility"], "private")
        self.assertEqual(detail.json()["source_kind"], "import")
        self.assertEqual(len(detail.json()["items"]), 2)
        for entry in detail.json()["items"]:
            self.assertNotIn("status", entry)
            self.assertNotIn("rating", entry)
            self.assertNotIn("review", entry)
        self.assertEqual([item.title for item in JsonCatalogRepository(self.catalog_path, normalize_item).read()], ["Heat"])

    def test_login_requires_token_origin_and_json(self) -> None:
        body = json.dumps({"username": "lucas", "password": self.owner_password})
        with TestClient(create_app(self.config), base_url="http://127.0.0.1:8765") as client:
            missing_token = client.post(
                "/auth/login",
                content=body,
                headers={"Origin": "http://127.0.0.1:8765", "Content-Type": "application/json"},
            )
            wrong_origin = client.post(
                "/auth/login",
                content=body,
                headers={
                    "X-Movie-Inbox-Token": self.config.api_token,
                    "Origin": "https://attacker.example",
                    "Content-Type": "application/json",
                },
            )
            wrong_type = client.post(
                "/auth/login",
                content=body,
                headers=self.post_headers("text/plain"),
            )
        self.assertEqual(missing_token.status_code, 403)
        self.assertEqual(wrong_origin.status_code, 403)
        self.assertEqual(wrong_type.status_code, 400)

    def test_invalid_login_is_generic_and_logout_revokes_the_session(self) -> None:
        with TestClient(create_app(self.config), base_url="http://127.0.0.1:8765") as client:
            invalid = client.post(
                "/auth/login",
                content=json.dumps({"username": "lucas", "password": "incorrect-password"}),
                headers=self.post_headers(),
            )
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json()["reason"], "invalid_credentials")

        logout = self.client.post("/auth/logout", content="{}", headers=self.post_headers())
        after = self.client.get("/api/items", headers={"X-Movie-Inbox-Token": self.config.api_token})
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(after.status_code, 401)

    def test_healthcheck_does_not_expose_catalog_data(self) -> None:
        status, payload = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload), {"status": "ok"})

    def test_image_cache_does_not_accept_session_tokens_in_urls(self) -> None:
        with TestClient(create_app(self.config), base_url="http://127.0.0.1:8765") as client:
            response = client.get(
                "/image-cache?url=https%3A%2F%2Fimages.example.com%2Fposter.jpg&token=test-token",
            )
        self.assertEqual(response.status_code, 401)

    def test_image_cache_rejects_hosts_outside_the_allowlist(self) -> None:
        status, payload = self.request(
            "GET",
            "/image-cache?url=https%3A%2F%2Fattacker.example%2Fposter.jpg",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(status, 400)
        self.assertIn(b"invalid_image_url", payload)

    def test_untrusted_host_is_rejected(self) -> None:
        status, _ = self.request("GET", "/", headers={"Host": "evil.example"})
        self.assertEqual(status, 400)

    def test_frontend_assets_are_served_without_inline_code(self) -> None:
        response = self.client.get("/")
        status, body = response.status_code, response.content
        self.assertEqual(status, 200)
        self.assertIn("HttpOnly", self.login_response.headers.get("set-cookie", ""))
        self.assertIn("SameSite=strict", self.login_response.headers.get("set-cookie", ""))
        self.assertIn(b'/static/style.css', body)
        self.assertIn(b'/static/app.js', body)
        self.assertIn(b'viewport-fit=cover', body)
        self.assertIn(b'class="utility-menu"', body)
        self.assertIn(b'<dialog id="detailDrawer"', body)
        self.assertIn(b'id="detailNavigation"', body)
        self.assertIn(b'id="detailFeedback"', body)
        self.assertIn(b'id="unsavedDetailDialog"', body)
        self.assertIn(b'id="saveDetailChanges"', body)
        self.assertIn(b'id="spotlightStage"', body)
        self.assertIn(b'id="homeButton"', body)
        self.assertIn(b'id="inboxButton"', body)
        self.assertIn(b'id="inboxBadge"', body)
        self.assertIn(b'id="inboxView"', body)
        self.assertIn(b'id="curationQueue"', body)
        self.assertIn(b'id="curationDetail"', body)
        self.assertIn(b'id="curationHistoryCount"', body)
        self.assertIn(b'id="persistCurationHistory"', body)
        self.assertIn(b'id="mergeComparatorDialog"', body)
        self.assertIn(b'id="mergeComparatorFields"', body)
        self.assertIn(b'id="collectionView"', body)
        self.assertIn(b'id="adminView"', body)
        self.assertIn(b'id="clubButton"', body)
        self.assertIn(b'id="clubView"', body)
        self.assertIn(b'id="clubModeTabs"', body)
        self.assertIn(b'id="clubCollectionsPanel"', body)
        self.assertIn(b'id="collectionList"', body)
        self.assertIn(b'id="collectionDetailPanel"', body)
        self.assertIn(b'id="addCollectionSelection"', body)
        self.assertIn(b'id="privacyDialog"', body)
        self.assertIn(b'id="editMemberDialog"', body)
        self.assertIn(b'id="archiveMemberDialog"', body)
        self.assertIn(b'id="sharedDetailDialog"', body)
        self.assertIn(b'id="adminButton"', body)
        self.assertIn(b'id="systemMenu"', body)
        self.assertIn(b'id="currentUserName"', body)
        self.assertIn(b'id="currentCatalogName"', body)
        self.assertIn(b'id="logoutButton"', body)
        self.assertIn(b'id="adminMembers"', body)
        self.assertIn(b'id="memberList"', body)
        self.assertIn(b'id="memberDialog"', body)
        self.assertIn(b'id="temporaryPasswordDialog"', body)
        self.assertIn(b'id="homeGrid"', body)
        self.assertIn(b'id="activeFilters"', body)
        self.assertIn(b'id="catalogSummary"', body)
        self.assertIn(b'id="catalogMergeTitle"', body)
        self.assertIn(b'id="catalogCount"', body)
        self.assertIn(b'id="sort"', body)
        self.assertIn(b'id="randomButton"', body)
        self.assertIn(b'id="randomCatalogOnly"', body)
        self.assertIn(b'id="mobileRandomCatalogOnly"', body)
        self.assertIn(b'class="mobile-control-label"', body)
        self.assertIn(b'id="inboxTitle" class="view-focus-target" tabindex="-1"', body)
        self.assertIn(b'id="catalogTitle" class="view-focus-target" tabindex="-1"', body)
        self.assertIn(b'id="adminTitle" class="view-focus-target" tabindex="-1"', body)
        self.assertNotIn(b'id="catalogSource"', body)
        self.assertNotIn(b'<style>', body)

        status, css = self.request("GET", "/static/style.css")
        self.assertEqual(status, 200)
        self.assertIn(b'.search-console', css)
        self.assertIn(b'.dvd-case', css)
        self.assertIn(b'.dvd-front-statuses', css)
        self.assertIn(b'.home-grid', css)
        self.assertIn(b'.curation-workbench', css)
        self.assertIn(b'.curation-queue-item', css)
        self.assertIn(b'.curation-pair', css)
        self.assertIn(b'.merge-comparator-dialog', css)
        self.assertIn(b'.merge-field-options', css)
        self.assertIn(b'.history-operation-mark', css)
        self.assertIn(b'.admin-section-nav', css)
        self.assertIn(b'.member-row', css)
        self.assertIn(b'.member-dialog', css)
        self.assertIn(b'.club-grid', css)
        self.assertIn(b'.club-mode-tabs', css)
        self.assertIn(b'.collection-card', css)
        self.assertIn(b'.collection-mosaic', css)
        self.assertIn(b'.collection-bulk-bar', css)
        self.assertIn(b'.collection-item-actions', css)
        self.assertIn(b'.privacy-fieldset', css)
        self.assertIn(b'.personal-privacy-fields', css)
        self.assertIn(b'.system-menu-panel', css)
        self.assertIn(b'.active-filters', css)
        self.assertIn(b'.collection-view.is-compare-mode #grid', css)
        self.assertIn(b'.system-menu-toggle.mobile-random-scope', css)
        self.assertIn(b'grid-template-columns: repeat(5, minmax(0, 1fr))', css)
        self.assertIn(b'env(safe-area-inset-bottom', css)
        self.assertIn(b'input, select, textarea, button', css)
        self.assertIn(b'textarea:focus-visible', css)
        self.assertIn(b'button:disabled', css)
        self.assertIn(b'body[data-input-method="keyboard"] .view-focus-target:focus', css)
        self.assertIn(b'.metadata-row textarea { font-size: 14px; }', css)
        self.assertIn(b'scroll-snap-type: x proximity', css)
        self.assertIn(b'--ease-out: cubic-bezier', css)
        self.assertIn(b'.section-kicker', css)
        self.assertIn(b'@media (hover: hover) and (pointer: fine)', css)
        self.assertIn(b'@media (hover: none) and (pointer: coarse)', css)
        self.assertIn(b':has(.dvd-open-surface:focus-visible)', css)
        self.assertIn(b'.drawer-accordion', css)
        self.assertIn(b'.spotlight-stage', css)
        self.assertIn(b'.detail-drawer[open]', css)
        self.assertIn(b'.personal-record-read', css)
        self.assertIn(b'.drawer-navigation', css)
        self.assertIn(b'.unsaved-dialog', css)
        self.assertIn(b'prefers-reduced-motion', css)

        status, javascript = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b'const API_TOKEN', javascript)
        self.assertIn(b'class="card dvd-card"', javascript)
        self.assertIn(b'class="dvd-back-statuses"', javascript)
        self.assertIn(b'class="dvd-front-statuses"', javascript)
        self.assertIn(b'class="dvd-open-surface"', javascript)
        self.assertIn(b'0 pts', javascript)
        self.assertIn(b'showModal()', javascript)
        self.assertIn(b'SEARCH_TIMEOUT_MS', javascript)
        self.assertIn(b'backdrop_image', javascript)
        self.assertIn(b'spotlight-cta', javascript)
        self.assertIn(b'spotlightDetailPaused', javascript)
        self.assertIn(b'function openRandomDetail()', javascript)
        self.assertIn(b'function randomCandidates()', javascript)
        self.assertIn(b'function changeRandomScope(source)', javascript)
        self.assertIn(b'mobileRandomCatalogOnly', javascript)
        self.assertIn(b'function focusViewHeading(view)', javascript)
        self.assertIn(b'function loadIdentity()', javascript)
        self.assertIn(b'function logout()', javascript)
        self.assertIn(b'function loadMembers(', javascript)
        self.assertIn(b'function createMember(', javascript)
        self.assertIn(b'function handleMemberAction(', javascript)
        self.assertIn(b'function handleKeyboardModality(event)', javascript)
        self.assertIn(b'fields.detailBody.scrollTop = 0;', javascript)
        self.assertIn(b'function retryMergeComparison()', javascript)
        self.assertIn(b'invalid_comparison_payload', javascript)
        self.assertIn(b'aria-busy', javascript)
        self.assertIn(b'function personalRecordPanel(item)', javascript)
        self.assertIn(b'function requestDetailTransition(action)', javascript)
        self.assertIn(b'function saveDirtyDetailForms()', javascript)
        self.assertIn(b'function navigateDetail(offset)', javascript)
        self.assertIn(b'function openAnotherRandomDetail()', javascript)
        self.assertIn(b'function showView(view', javascript)
        self.assertIn(b'function goToCollectionRoot()', javascript)
        self.assertIn(b'const query = requestedView === "catalog" ? rawQuery : "";', javascript)
        self.assertIn(b'function collectionRouteValues()', javascript)
        self.assertIn(b'function setCollectionSearchMode(', javascript)
        self.assertIn(b'function collectionSearchMessage()', javascript)
        self.assertIn(b'function renderHomeShelf()', javascript)
        self.assertIn(b'function renderCollectionDirectory()', javascript)
        self.assertIn(b'function loadCollectionDetail(', javascript)
        self.assertIn(b'function toggleCollectionFollow(', javascript)
        self.assertIn(b'function addCollectionItems(', javascript)
        self.assertIn(b'function loadCurationQueue(', javascript)
        self.assertIn(b'function renderCuration()', javascript)
        self.assertIn(b'function postCurationDecision(', javascript)
        self.assertIn(b'function openInternalMergeComparator(', javascript)
        self.assertIn(b'function submitReviewedMerge()', javascript)
        self.assertIn(b'function undoCurationOperation(', javascript)
        self.assertIn(b'function changeCurationHistoryMode()', javascript)
        self.assertIn(b'function renderActiveFilters()', javascript)
        self.assertIn(b'function sortItems(list)', javascript)
        self.assertIn(b'const catalogItems = items.filter((item) => isInCatalog(item.en_catalogo))', javascript)
        self.assertNotIn(b'searchCatalogForMerge(activeQuery);', javascript)
        self.assertNotIn(b'data-click="toggle-flip"', javascript)
        self.assertNotIn(b'onclick=', javascript)
        self.assertNotIn(b'&token=', javascript)
        self.assertNotIn(b'alert(', javascript)
        self.assertNotIn(b'console.log(', javascript)

    def test_post_requires_same_origin_and_json(self) -> None:
        body = json.dumps({"id": "heat", "status": "watched"})
        status, _ = self.request(
            "POST",
            "/api/status",
            body,
            {"X-Movie-Inbox-Token": self.config.api_token, "Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)

        status, _ = self.request("POST", "/api/status", body, self.post_headers("text/plain"))
        self.assertEqual(status, 400)

    def test_valid_write_returns_success_and_persists(self) -> None:
        body = json.dumps({"id": "heat", "status": "watched", "watched_at": "2026-07-13"})
        status, payload = self.request("POST", "/api/status", body, self.post_headers())
        self.assertEqual(status, 200, payload)
        item = JsonCatalogRepository(self.catalog_path, normalize_item).read()[0]
        self.assertEqual(item.status, "watched")
        self.assertEqual(item.watched_at, "2026-07-13")

    def test_link_curation_decision_is_persisted_and_reactivatable(self) -> None:
        status, raw_payload = self.request(
            "GET",
            "/api/curation",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        payload = json.loads(raw_payload)
        self.assertEqual(status, 200, raw_payload)
        self.assertEqual(payload["counts"]["missing_link"], 1)

        body = json.dumps({
            "id": "heat",
            "source_file": str(self.catalog_path),
            "status": "deferred",
        })
        status, raw_payload = self.request("POST", "/api/curation/link", body, self.post_headers())
        self.assertEqual(status, 200, raw_payload)

        status, raw_payload = self.request(
            "GET",
            "/api/curation",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        payload = json.loads(raw_payload)
        self.assertEqual(payload["counts"]["missing_link"], 0)
        self.assertEqual(payload["counts"]["deferred"], 1)
        item = JsonCatalogRepository(self.catalog_path, normalize_item).get("heat")
        self.assertEqual(item.link_curation_status, "deferred")

    def test_duplicate_pair_can_be_dismissed_from_the_queue(self) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write([
            normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
            normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
        ])
        status, raw_payload = self.request(
            "GET",
            "/api/curation",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        payload = json.loads(raw_payload)
        duplicate = next(case for case in payload["cases"] if case["type"] == "duplicate")
        self.assertEqual(status, 200, raw_payload)
        self.assertEqual(payload["counts"]["duplicates"], 1)

        body = json.dumps({
            "id": duplicate["primary"]["id"],
            "source_file": duplicate["primary"]["source_file"],
            "other_reference": duplicate["secondary"]["ref"],
            "status": "not_duplicate",
        })
        status, raw_payload = self.request("POST", "/api/curation/duplicate", body, self.post_headers())
        self.assertEqual(status, 200, raw_payload)

        status, raw_payload = self.request(
            "GET",
            "/api/curation",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(json.loads(raw_payload)["counts"]["duplicates"], 0)

    def test_reviewed_duplicate_merge_is_recorded_and_undo_restores_both_items(self) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write([
            normalize_item({
                "id": "heat-a",
                "title": "Heat",
                "year": "1995",
                "status": "watched",
                "rating": 8,
                "en_catalogo": True,
                "local_files": [{"path": "D:/Heat.mkv", "name": "Heat.mkv"}],
            }),
            normalize_item({
                "id": "heat-b",
                "title": "Heat",
                "spanish_title": "Fuego contra fuego",
                "year": "1995",
                "status": "to_watch",
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
                "url": "https://www.imdb.com/title/tt0113277/",
                "source": "imdb",
            }),
        ])
        reference = lambda item_id: {"id": item_id, "source_file": str(self.catalog_path)}
        compare_body = json.dumps({
            "left": reference("heat-a"),
            "right": reference("heat-b"),
            "survivor_side": "left",
        })
        status, raw_payload = self.request(
            "POST",
            "/api/curation/compare",
            compare_body,
            self.post_headers(),
        )
        self.assertEqual(status, 200, raw_payload)
        comparison = json.loads(raw_payload)
        status_field = next(field for field in comparison["fields"] if field["key"] == "status")
        self.assertTrue(status_field["required"])

        merge_body = json.dumps({
            "left": reference("heat-a"),
            "right": reference("heat-b"),
            "survivor_side": "left",
            "review_id": comparison["review_id"],
            "choices": {"status": "left"},
            "history_mode": "persistent",
        })
        status, raw_payload = self.request(
            "POST",
            "/api/curation/merge",
            merge_body,
            self.post_headers(),
        )
        self.assertEqual(status, 200, raw_payload)
        merged_payload = json.loads(raw_payload)
        self.assertEqual([item.id for item in repository.read()], ["heat-a"])
        self.assertEqual(repository.get("heat-a").spanish_title, "Fuego contra fuego")

        status, raw_payload = self.request(
            "GET",
            "/api/curation/history?mode=persistent",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(status, 200, raw_payload)
        history = json.loads(raw_payload)
        self.assertEqual(history["count"], 1)
        self.assertTrue(history["operations"][0]["can_undo"])

        undo_body = json.dumps({
            "operation_id": merged_payload["operation"]["id"],
            "history_mode": "persistent",
        })
        status, raw_payload = self.request(
            "POST",
            "/api/curation/undo",
            undo_body,
            self.post_headers(),
        )
        self.assertEqual(status, 200, raw_payload)
        self.assertEqual([item.id for item in repository.read()], ["heat-a", "heat-b"])

    @patch("movie_inbox.web.catalog_api.external_metadata_by_title")
    def test_background_enrichment_updates_the_existing_item(self, title_lookup) -> None:
        title_lookup.return_value = {
            "title": "Heat",
            "year": "1995",
            "wikidata_id": "Q175171",
            "url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
            "alternative_titles": ["Fuego contra fuego"],
        }

        background_enrich_catalog_item(
            self.catalog_path,
            "heat",
            {"title": "Heat", "year": "1995"},
        )

        items = JsonCatalogRepository(self.catalog_path, normalize_item).read()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].wikidata_id, "Q175171")
        self.assertEqual(items[0].alternative_titles, ["Fuego contra fuego"])
        self.assertEqual(items[0].wikipedia_url, "https://en.wikipedia.org/wiki/Heat_(1995_film)")

    @patch("movie_inbox.web.app.background_enrich_catalog_item")
    @patch("movie_inbox.web.app.enrich_selected_result", side_effect=lambda result: result)
    def test_add_schedules_title_enrichment_when_wikidata_is_missing(self, _, background_enrichment) -> None:
        body = json.dumps(
            {
                "title": "The Beautiful Person",
                "english_title": "The Beautiful Person",
                "year": "2008",
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt1263778/",
            }
        )

        status, raw_payload = self.request("POST", "/api/add", body, self.post_headers())
        payload = json.loads(raw_payload)

        self.assertEqual(status, 200, raw_payload)
        self.assertEqual(payload["reason"], "added")
        self.assertEqual(payload["background_enrichment"], "scheduled")
        background_enrichment.assert_called_once()
        self.assertEqual(len(JsonCatalogRepository(self.catalog_path, normalize_item).read()), 2)

    def test_public_origin_is_accepted_for_proxy_deployment(self) -> None:
        proxy_config = replace(self.config, public_origin="https://movies.example.com")
        headers = {
            "X-Movie-Inbox-Token": proxy_config.api_token,
            "Origin": "https://movies.example.com",
            "Content-Type": "application/json",
        }
        body = json.dumps({"id": "heat", "status": "watched", "watched_at": "2026-07-15"})
        with TestClient(create_app(proxy_config), base_url="https://movies.example.com") as client:
            login = client.post(
                "/auth/login",
                content=json.dumps({"username": "lucas", "password": self.owner_password}),
                headers=headers,
            )
            root = client.get("/")
            response = client.post("/api/status", content=body, headers=headers)
        self.assertIn("Secure", login.headers.get("set-cookie", ""))
        self.assertEqual(root.status_code, 200)
        self.assertEqual(response.status_code, 200, response.content)

    def test_json_body_limit_is_enforced(self) -> None:
        body = json.dumps({"id": "heat", "review": "x" * MAX_JSON_BODY_BYTES})
        status, payload = self.request("POST", "/api/personal", body, self.post_headers())
        self.assertEqual(status, 400)
        self.assertIn(b"too large", payload)

    def test_invalid_catalog_is_reported_instead_of_becoming_empty(self) -> None:
        self.catalog_path.write_text('{"schema_version": 6, "items": []}', encoding="utf-8")
        status, payload = self.request(
            "GET",
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(status, 422, payload)
        self.assertIn(b"newer than supported", payload)


if __name__ == "__main__":
    unittest.main()
