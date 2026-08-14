from __future__ import annotations

import csv
import io
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
from movie_inbox.infrastructure.schema import SCHEMA_VERSION
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
        self.media_path = Path(self.temporary.name) / "media"
        self.media_path.mkdir()
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
            library_allowed_roots=(str(self.media_path),),
            library_scheduler_poll_seconds=3600,
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
        home_status, _ = self.request("GET", "/api/home?date=2026-08-10")
        export_status, _ = self.request("GET", "/api/catalog/export?format=json")
        cache_status, _ = self.request("GET", "/api/image-cache/status")
        path_status, _ = self.request("GET", "/api/library-paths")
        self.assertEqual(status, 403)
        self.assertEqual(home_status, 403)
        self.assertEqual(export_status, 403)
        self.assertEqual(cache_status, 403)
        self.assertEqual(path_status, 403)

    def test_owner_can_browse_and_check_only_configured_library_paths(self) -> None:
        films = self.media_path / "Peliculas"
        films.mkdir()
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()

        roots = self.client.get(
            "/api/library-paths",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        listing = self.client.get(
            "/api/library-paths",
            params={"path": str(self.media_path)},
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        checked = self.client.post(
            "/api/library-paths/check",
            content=json.dumps({"path": str(films)}),
            headers=self.post_headers(),
        )
        denied = self.client.post(
            "/api/library-paths/check",
            content=json.dumps({"path": str(outside)}),
            headers=self.post_headers(),
        )

        self.assertEqual(roots.status_code, 200, roots.content)
        self.assertEqual(roots.json()["directories"][0]["path"], str(self.media_path.resolve()))
        self.assertEqual(listing.status_code, 200, listing.content)
        self.assertEqual(listing.json()["directories"][0]["name"], "Peliculas")
        self.assertEqual(checked.status_code, 200, checked.content)
        self.assertTrue(checked.json()["readable"])
        self.assertEqual(denied.status_code, 400, denied.content)

    def test_search_returns_local_matches_and_external_results_grouped_by_source(self) -> None:
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item({
                "id": "beautiful-person",
                "title": "The Beautiful Person",
                "original_title": "La Belle Personne",
                "spanish_title": "La bella persona",
                "year": "2008",
                "kind": "pelicula",
            })]
        )
        external = [
            {"source": "wikipedia", "title": "La Belle Personne", "url": "https://en.wikipedia.org/wiki/The_Beautiful_Person"},
            {"source": "imdb", "title": "The Beautiful Person", "url": "https://www.imdb.com/title/tt1263778/"},
            {"source": "filmaffinity", "title": "La bella persona", "url": "https://www.filmaffinity.com/es/film123.html"},
        ]

        with patch("movie_inbox.web.app.search_sources", return_value=external):
            response = self.client.get(
                "/api/search",
                params={"q": "la belle personne", "external": "true"},
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["catalog"]["results"][0]["id"], "beautiful-person")
        self.assertEqual(payload["sources"]["wikipedia"]["count"], 1)
        self.assertEqual(payload["sources"]["imdb"]["count"], 1)
        self.assertEqual(payload["sources"]["filmaffinity"]["count"], 1)

    def test_progressive_external_search_can_skip_catalog_lookup(self) -> None:
        external = [{
            "source": "wikipedia",
            "title": "Evil Dead Burn",
            "year": "2026",
            "url": "https://en.wikipedia.org/wiki/Evil_Dead_Burn",
        }]

        with (
            patch("movie_inbox.web.app.search_catalog_items") as catalog_search,
            patch("movie_inbox.web.app.search_sources", return_value=external) as external_search,
        ):
            response = self.client.get(
                "/api/search",
                params={
                    "q": "Evil Dead Burn 2026",
                    "source": "wikipedia",
                    "external": "true",
                    "catalog": "false",
                },
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["catalog"], {"results": [], "count": 0})
        self.assertEqual(payload["sources"]["wikipedia"]["count"], 1)
        catalog_search.assert_not_called()
        external_search.assert_called_once_with("Evil Dead Burn 2026", "wikipedia")

    def test_external_comparison_uses_enriched_titles_before_ranking_catalog(self) -> None:
        with patch(
            "movie_inbox.web.app.enrich_selected_result",
            return_value={
                "source": "imdb",
                "title": "Heat",
                "original_title": "Heat",
                "year": "1995",
                "kind": "pelicula",
                "url": "https://www.imdb.com/title/tt0113277/",
            },
        ):
            response = self.client.post(
                "/api/search/catalog-candidates",
                content=json.dumps({
                    "result": {
                        "source": "imdb",
                        "title": "tt0113277",
                        "url": "https://www.imdb.com/title/tt0113277/",
                    }
                }),
                headers=self.post_headers(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["results"][0]["id"], "heat")
        self.assertTrue(response.json()["results"][0]["_search"]["accepted"])

    def test_image_cache_status_is_scoped_to_the_authenticated_catalog(self) -> None:
        headers = {"X-Movie-Inbox-Token": self.config.api_token}
        items = self.client.get("/api/items", headers=headers)
        response = self.client.get("/api/image-cache/status", headers=headers)

        self.assertEqual(items.status_code, 200, items.content)
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["personal"]["state"], "disabled")
        self.assertEqual(payload["personal"]["eligible"], 0)
        self.assertEqual(payload["personal"]["without_url"], 1)
        self.assertEqual(payload["global"]["registered_scopes"], 2)

    def test_editorial_home_is_explainable_stable_and_includes_followed_collections(self) -> None:
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item({
                    "id": "heat",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                    "status": "to_watch",
                    "en_catalogo": True,
                    "page_image": "https://upload.wikimedia.org/heat.jpg",
                }),
                normalize_item({
                    "id": "memories",
                    "title": "Memories of Murder",
                    "year": "2003",
                    "kind": "pelicula",
                    "status": "watched",
                    "rating": 0,
                    "review": "",
                }),
            ]
        )
        headers = {"X-Movie-Inbox-Token": self.config.api_token}
        listed = self.client.get("/api/collections", headers=headers)
        collection_id = listed.json()["collections"][0]["id"]
        followed = self.client.post(
            f"/api/collections/{collection_id}/follow",
            content=json.dumps({"following": True}),
            headers=self.post_headers(),
        )
        self.assertEqual(followed.status_code, 200, followed.content)

        first = self.client.get("/api/home?date=2026-08-10", headers=headers)
        second = self.client.get("/api/home?date=2026-08-10", headers=headers)
        items_response = self.client.get("/api/items?home_date=2026-08-10", headers=headers)
        invalid = self.client.get("/api/home?date=2026-02-30", headers=headers)

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json(), second.json())
        payload = first.json()
        self.assertEqual(payload["generated_for"], "2026-08-10")
        self.assertEqual(len(payload["featured"]), 1)
        self.assertEqual(payload["hero"], payload["featured"][0])
        self.assertEqual(payload["hero"]["item"]["id"], "heat")
        self.assertEqual(payload["hero"]["reason"]["code"], "available_pending")
        section_ids = {section["id"] for section in payload["sections"]}
        self.assertIn("followed", section_ids)
        self.assertIn("memory", section_ids)
        self.assertEqual(payload["warnings"], [])
        keys = [entry["key"] for entry in payload["featured"]] + [
            entry["key"]
            for section in payload["sections"]
            for entry in section["items"]
        ]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertNotIn(str(self.temporary.name), first.text)

        self.assertEqual(items_response.status_code, 200, items_response.content)
        self.assertEqual(items_response.json()["home"], payload)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["reason"], "invalid_home_date")

    def test_personal_catalog_can_be_downloaded_as_json_or_csv(self) -> None:
        headers = {"X-Movie-Inbox-Token": self.config.api_token}
        json_export = self.client.get("/api/catalog/export?format=json", headers=headers)
        csv_export = self.client.get("/api/catalog/export?format=csv", headers=headers)
        invalid = self.client.get("/api/catalog/export?format=xml", headers=headers)

        self.assertEqual(json_export.status_code, 200, json_export.content)
        self.assertEqual(json_export.headers["cache-control"], "no-store")
        self.assertRegex(
            json_export.headers["content-disposition"],
            r'attachment; filename="movie-inbox-lucas-\d{4}-\d{2}-\d{2}\.json"',
        )
        document = json_export.json()
        self.assertEqual(document["schema_version"], SCHEMA_VERSION)
        self.assertEqual([item["id"] for item in document["items"]], ["heat"])
        self.assertNotIn("_source_file", document["items"][0])
        self.assertNotIn(str(self.temporary.name), json_export.text)

        self.assertEqual(csv_export.status_code, 200, csv_export.content)
        self.assertIn("text/csv", csv_export.headers["content-type"])
        rows = list(csv.DictReader(io.StringIO(csv_export.text.lstrip("\ufeff"))))
        self.assertEqual([row["id"] for row in rows], ["heat"])
        self.assertEqual(rows[0]["title"], "Heat")
        self.assertNotIn(str(self.temporary.name), csv_export.text)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["reason"], "unsupported_export_format")

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
            member_export = member_client.get(
                "/api/catalog/export?format=json",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            member_cache_status = member_client.get(
                "/api/image-cache/status",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(member_items.status_code, 200, member_items.content)
            self.assertEqual([item["id"] for item in member_items.json()["items"]], ["heat"])
            self.assertEqual(member_items.json()["items"][0]["_source_file"], "source-1")
            self.assertNotIn(str(member_catalog.write_path), member_items.text)
            self.assertEqual(member_export.status_code, 200, member_export.content)
            self.assertEqual(member_export.json()["items"][0]["status"], "to_watch")
            self.assertEqual(member_cache_status.status_code, 200, member_cache_status.content)
            self.assertEqual(member_cache_status.json()["personal"]["without_url"], 1)
            self.assertNotIn("global", member_cache_status.json())
            self.assertIn("movie-inbox-maria-", member_export.headers["content-disposition"])
            self.assertNotIn(str(member_catalog.write_path), member_export.text)

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
            forbidden_libraries = member_client.get(
                "/api/libraries",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            forbidden_scanner_queue = member_client.get(
                "/api/scanner/queue",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(updated.status_code, 200, updated.content)
            self.assertEqual(forbidden_members.status_code, 403)
            self.assertEqual(forbidden_libraries.status_code, 403)
            self.assertEqual(forbidden_scanner_queue.status_code, 403)

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
        self.assertIn(b'id="homeDate"', body)
        self.assertIn(b'id="homeSections"', body)
        self.assertIn(b'id="homeFeedback"', body)
        self.assertIn(b'id="activeFilters"', body)
        self.assertIn(b'id="statusQuickFilters"', body)
        self.assertIn(b'id="availabilityQuickFilters"', body)
        self.assertIn(b'id="kindQuickFilters"', body)
        self.assertIn(b'id="advancedFiltersMenu"', body)
        self.assertIn(b'id="decadeFilter"', body)
        self.assertIn(b'id="genreFilter"', body)
        self.assertIn(b'id="directorFilter"', body)
        self.assertIn(b'id="yearFromFilter"', body)
        self.assertIn(b'id="catalogSummary"', body)
        self.assertIn(b'id="catalogMergeTitle"', body)
        self.assertIn(b'id="catalogCount"', body)
        self.assertIn(b'id="sort"', body)
        self.assertIn(b'id="randomButton"', body)
        self.assertIn(b'id="randomCatalogOnly"', body)
        self.assertIn(b'class="header-utilities"', body)
        self.assertNotIn(b'id="mobileRandomCatalogOnly"', body)
        self.assertIn(b'id="descriptionDialog" aria-labelledby="descriptionDialogTitle"', body)
        self.assertNotIn(b'id="collectionList" class="collection-list" aria-live=', body)
        self.assertNotIn(b'id="scannerQueue" class="scanner-queue" aria-live=', body)
        self.assertNotIn(b'id="memberList" class="member-list" aria-live=', body)
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
        self.assertIn(b'.home-program-grid', css)
        self.assertIn(b'.spotlight-program', css)
        self.assertIn(b'.collection-filter-toolbar', css)
        self.assertIn(b'.filter-segments', css)
        self.assertIn(b'.home-empty-state', css)
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
        self.assertIn(b'.header-utilities', css)
        self.assertIn(b'.system-menu-toggle', css)
        self.assertIn(b'grid-template-columns: repeat(4, minmax(0, 1fr))', css)
        self.assertIn(b'env(safe-area-inset-bottom', css)
        self.assertIn(b'input, select, textarea, button', css)
        self.assertIn(b'textarea:focus-visible', css)
        self.assertIn(b'button:disabled', css)
        self.assertIn(b'body[data-input-method="keyboard"] .view-focus-target:focus', css)
        self.assertIn(b'.metadata-row textarea { font-size: var(--text-control); }', css)
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
        self.assertIn(b'.search-source-feedback', css)
        self.assertIn(b'.source-search-spinner', css)
        self.assertIn(b'prefers-reduced-motion', css)
        self.assertIn(b'@media (forced-colors: active)', css)
        self.assertIn(b'--on-accent: #080a18', css)
        self.assertIn(b'--text-label: 10px', css)

        status, javascript = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b'const API_TOKEN', javascript)
        self.assertIn(b'<article class="card dvd-card${', javascript)
        self.assertIn(b'class="dvd-back-statuses"', javascript)
        self.assertIn(b'class="dvd-front-statuses"', javascript)
        self.assertIn(b'class="dvd-open-surface"', javascript)
        self.assertIn(b'0 pts', javascript)
        self.assertIn(b'showModal()', javascript)
        self.assertIn(b'SEARCH_TIMEOUT_MS', javascript)
        self.assertIn(b'Promise.allSettled(tasks)', javascript)
        self.assertIn(b'catalog=false', javascript)
        self.assertIn(b'retry-external-source', javascript)
        self.assertIn(b'function loadExternalSourceResults(', javascript)
        self.assertIn(b'backdrop_image', javascript)
        self.assertIn(b'spotlight-cta', javascript)
        self.assertIn(b'function renderEditorialHome()', javascript)
        self.assertNotIn(b'home-entry-reason', javascript)
        self.assertIn(b'function applyCollectionFilterDescriptor(', javascript)
        self.assertIn(b'function syncCollectionFilterControls()', javascript)
        self.assertIn(b'function matchesYearFilters(', javascript)
        self.assertIn(b'function moveSpotlight(', javascript)
        self.assertIn(b'function openHomeCollectionDetail(', javascript)
        self.assertIn(b'function refreshEditorialHome()', javascript)
        self.assertIn(b'function openRandomDetail()', javascript)
        self.assertIn(b'function randomCandidates()', javascript)
        self.assertIn(b'function changeRandomScope(source)', javascript)
        self.assertNotIn(b'mobileRandomCatalogOnly', javascript)
        self.assertIn(b'function prepareCatalogViewModel()', javascript)
        self.assertIn(b'function matchesNormalizedSearchText(', javascript)
        self.assertIn(b'function restoreDescriptionFocus()', javascript)
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
        self.assertIn(b'function editorialPersonalIds()', javascript)
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
        self.assertIn(b'editorialHome = normalizeEditorialHome(payload.home);', javascript)
        self.assertNotIn(b'SPOTLIGHT_INTERVAL_MS', javascript)
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

    def test_owner_can_test_apply_and_read_shared_scanner_availability(self) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps({
                "name": "Peliculas principales",
                "root_path": str(self.media_path),
                "schedule": "manual",
                "max_missing_ratio": 0.5,
            }),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        library_id = created.json()["library"]["id"]

        tested = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "dry_run"}),
            headers=self.post_headers(),
        )
        self.assertEqual(tested.status_code, 202, tested.content)
        test_run = self.client.get(
            f"/api/library-runs/{tested.json()['run']['id']}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(test_run.json()["run"]["status"], "completed")
        self.assertEqual(test_run.json()["run"]["preview"][0]["relative_path"], "Heat.1995.1080p.mkv")
        self.assertEqual(test_run.json()["run"]["preview"][0]["state"], "matched")

        applied = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )
        items = self.client.get(
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )

        self.assertEqual(applied.status_code, 202, applied.content)
        self.assertTrue(items.json()["items"][0]["en_catalogo"])
        self.assertFalse(items.json()["items"][0]["_availability"]["manual"])
        self.assertTrue(items.json()["items"][0]["_availability"]["server"])
        self.assertNotIn(str(self.media_path), items.text)

    def test_scheduled_scans_require_applied_inventory_and_manual_libraries_reject_activation(self) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps({
                "name": "Peliculas programadas",
                "root_path": str(self.media_path),
                "schedule": "hourly",
            }),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        library_id = created.json()["library"]["id"]
        apply_before_test = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )
        tested = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "dry_run"}),
            headers=self.post_headers(),
        )
        after_test = self.client.get(
            f"/api/libraries/{library_id}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )

        before_apply = self.client.post(
            f"/api/libraries/{library_id}/status",
            content=json.dumps({"active": True}),
            headers=self.post_headers(),
        )
        applied = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )
        after_apply = self.client.get(
            f"/api/libraries/{library_id}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        activated = self.client.post(
            f"/api/libraries/{library_id}/status",
            content=json.dumps({"active": True}),
            headers=self.post_headers(),
        )
        switched_to_manual = self.client.post(
            f"/api/libraries/{library_id}/update",
            content=json.dumps({"schedule": "manual"}),
            headers=self.post_headers(),
        )
        manual_activation = self.client.post(
            f"/api/libraries/{library_id}/status",
            content=json.dumps({"active": True}),
            headers=self.post_headers(),
        )

        self.assertEqual(apply_before_test.status_code, 409, apply_before_test.content)
        self.assertEqual(
            apply_before_test.json()["reason"],
            "Run a successful test scan before applying changes",
        )
        self.assertEqual(tested.status_code, 202, tested.content)
        self.assertGreater(after_test.json()["library"]["verified_at"], 0)
        self.assertEqual(after_test.json()["library"]["counts"]["files"], 0)
        self.assertEqual(before_apply.status_code, 409, before_apply.content)
        self.assertEqual(before_apply.json()["reason"], "Apply inventory before activating scheduled scans")
        self.assertEqual(applied.status_code, 202, applied.content)
        self.assertEqual(after_apply.json()["library"]["counts"]["files"], 1)
        self.assertEqual(activated.status_code, 200, activated.content)
        self.assertTrue(activated.json()["library"]["active"])
        self.assertGreater(activated.json()["library"]["next_scan_at"], 0)
        self.assertFalse(switched_to_manual.json()["library"]["active"])
        self.assertEqual(switched_to_manual.json()["library"]["next_scan_at"], 0)
        self.assertEqual(manual_activation.status_code, 409, manual_activation.content)
        self.assertEqual(manual_activation.json()["reason"], "Manual libraries do not use scheduled activation")

    def test_offline_library_run_keeps_previous_availability_over_http(self) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps({
                "name": "Disco removible",
                "root_path": str(self.media_path),
                "schedule": "manual",
            }),
            headers=self.post_headers(),
        )
        library_id = created.json()["library"]["id"]
        self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "dry_run"}),
            headers=self.post_headers(),
        )
        self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )
        self.media_path.rename(Path(self.temporary.name) / "detached-media")

        failed = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )
        run = self.client.get(
            f"/api/library-runs/{failed.json()['run']['id']}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        library = self.client.get(
            f"/api/libraries/{library_id}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        items = self.client.get(
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )

        self.assertEqual(failed.status_code, 202, failed.content)
        self.assertEqual(run.json()["run"]["status"], "failed")
        self.assertEqual(library.json()["library"]["status"], "offline")
        self.assertEqual(library.json()["library"]["counts"]["files"], 1)
        self.assertTrue(items.json()["items"][0]["_availability"]["server"])

    @patch("movie_inbox.web.app.background_enrich_catalog_item")
    def test_unknown_scanner_file_can_create_a_personal_catalog_item(self, enrich) -> None:
        (self.media_path / "Arrival.2016.mkv").write_bytes(b"arrival-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps({
                "name": "Peliculas principales",
                "root_path": str(self.media_path),
                "schedule": "manual",
            }),
            headers=self.post_headers(),
        )
        library_id = created.json()["library"]["id"]
        self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "dry_run"}),
            headers=self.post_headers(),
        )
        self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )

        queue = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(queue.status_code, 200, queue.content)
        self.assertEqual(queue.json()["count"], 1)
        queue_item = queue.json()["items"][0]
        self.assertEqual(queue_item["relative_path"], "Arrival.2016.mkv")

        reviewed = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps({
                "action": "create",
                "title": "Arrival",
                "year": "2016",
                "kind": "pelicula",
            }),
            headers=self.post_headers(),
        )
        empty = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        catalog = JsonCatalogRepository(self.catalog_path, normalize_item).read()
        arrival = next(item for item in catalog if item.title == "Arrival")
        items = self.client.get(
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )

        self.assertEqual(reviewed.status_code, 201, reviewed.content)
        self.assertEqual(reviewed.json()["catalog_action"], "created")
        self.assertEqual(empty.json()["count"], 0)
        self.assertFalse(arrival.en_catalogo)
        self.assertTrue(next(item for item in items.json()["items"] if item["id"] == arrival.id)["_availability"]["server"])
        enrich.assert_called_once()

    def test_scanner_blocks_duplicate_creation_and_can_link_the_existing_catalog_item(self) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write([
            normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}),
            normalize_item({
                "id": "legacy-1917",
                "title": "1917",
                "year": "1917",
                "kind": "pelicula",
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt8579674/",
                "imdb_url": "https://www.imdb.com/title/tt8579674/",
            }),
        ])
        (self.media_path / "1917.2019.1080p.BluRay.mkv").write_bytes(b"numeric-title")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps({
                "name": "Peliculas principales",
                "root_path": str(self.media_path),
                "schedule": "manual",
            }),
            headers=self.post_headers(),
        )
        library_id = created.json()["library"]["id"]
        for mode in ("dry_run", "apply"):
            response = self.client.post(
                f"/api/libraries/{library_id}/runs",
                content=json.dumps({"mode": mode}),
                headers=self.post_headers(),
            )
            self.assertEqual(response.status_code, 202, response.content)

        queue = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()
        self.assertEqual(queue["count"], 1)
        queue_item = queue["items"][0]
        self.assertEqual(queue_item["state"], "review")

        blocked = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps({
                "action": "create",
                "title": "1917",
                "year": "2019",
                "kind": "pelicula",
            }),
            headers=self.post_headers(),
        )

        self.assertEqual(blocked.status_code, 409, blocked.content)
        self.assertEqual(blocked.json()["reason"], "possible_duplicate")
        self.assertEqual(blocked.json()["candidates"][0]["id"], "legacy-1917")
        self.assertEqual(len(repository.read()), 2)

        linked = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps({
                "action": "link_catalog",
                "catalog_item_id": "legacy-1917",
            }),
            headers=self.post_headers(),
        )
        remaining = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        items = self.client.get(
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )

        self.assertEqual(linked.status_code, 200, linked.content)
        self.assertEqual(linked.json()["catalog_action"], "existing")
        self.assertEqual(remaining.json()["count"], 0)
        self.assertEqual(len(repository.read()), 2)
        legacy = next(item for item in items.json()["items"] if item["id"] == "legacy-1917")
        self.assertTrue(legacy["_availability"]["server"])

    def test_scanner_create_does_not_write_for_a_missing_queue_item(self) -> None:
        response = self.client.post(
            "/api/scanner/queue/missing-file",
            content=json.dumps({
                "action": "create",
                "title": "Arrival",
                "year": "2016",
                "kind": "pelicula",
            }),
            headers=self.post_headers(),
        )

        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual([item.title for item in JsonCatalogRepository(self.catalog_path, normalize_item).read()], ["Heat"])

    def test_scanner_candidates_do_not_reveal_a_private_member_catalog(self) -> None:
        created_member = self.client.post(
            "/api/members",
            content=json.dumps({
                "username": "maria",
                "temporary_password": "a-temporary-password",
            }),
            headers=self.post_headers(),
        )
        self.assertEqual(created_member.status_code, 201, created_member.content)
        member_id = created_member.json()["member"]["id"]
        identity_repository = SqliteIdentityRepository(self.instance_path)
        member_catalog = identity_repository.default_catalog_for(member_id)
        self.assertIsNotNone(member_catalog)
        open_catalog_repository(Path(member_catalog.write_path), normalize_item).write([
            normalize_item({
                "id": "private-member-film",
                "title": "Private Member Film",
                "year": "2024",
                "kind": "pelicula",
            })
        ])
        (self.media_path / "Private.Member.Film.2024.mkv").write_bytes(b"private-video")

        created_library = self.client.post(
            "/api/libraries",
            content=json.dumps({
                "name": "Peliculas principales",
                "root_path": str(self.media_path),
                "schedule": "manual",
            }),
            headers=self.post_headers(),
        )
        library_id = created_library.json()["library"]["id"]
        self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "dry_run"}),
            headers=self.post_headers(),
        )
        self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )

        queue = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(queue.status_code, 200, queue.content)
        self.assertEqual(queue.json()["count"], 1)
        self.assertEqual(queue.json()["items"][0]["state"], "new")
        self.assertEqual(queue.json()["items"][0]["candidates"], [])

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
        self.catalog_path.write_text(
            json.dumps({"schema_version": SCHEMA_VERSION + 1, "items": []}),
            encoding="utf-8",
        )
        status, payload = self.request(
            "GET",
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(status, 422, payload)
        self.assertIn(b"newer than supported", payload)


if __name__ == "__main__":
    unittest.main()
