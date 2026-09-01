from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.privacy import PrivacyPreferences
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.infrastructure.schema import SCHEMA_VERSION
from movie_inbox.web.app import create_app
from movie_inbox.web.catalog_api import background_enrich_catalog_item
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.responses import MAX_JSON_BODY_BYTES


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

    def request(
        self, method: str, path: str, body: str = "", headers: dict[str, str] | None = None
    ):
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
            [
                normalize_item(
                    {
                        "id": "beautiful-person",
                        "title": "The Beautiful Person",
                        "original_title": "La Belle Personne",
                        "spanish_title": "La bella persona",
                        "year": "2008",
                        "kind": "pelicula",
                    }
                )
            ]
        )
        external = [
            {
                "source": "wikipedia",
                "title": "La Belle Personne",
                "url": "https://en.wikipedia.org/wiki/The_Beautiful_Person",
            },
            {
                "source": "imdb",
                "title": "The Beautiful Person",
                "url": "https://www.imdb.com/title/tt1263778/",
            },
            {
                "source": "filmaffinity",
                "title": "La bella persona",
                "url": "https://www.filmaffinity.com/es/film123.html",
            },
        ]

        with patch("movie_inbox.web.routers.search.search_sources", return_value=external):
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

    def test_a_director_query_labels_both_local_and_external_results_as_discovery(self) -> None:
        # [Q4] tareas.md: "director:X" is a distinct discovery match, never
        # a title match, in both the local catalog and external sources.
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "mondo-cane",
                        "title": "Mondo Cane",
                        "year": "1962",
                        "kind": "pelicula",
                        "directors": ["Gualtiero Jacopetti"],
                    }
                )
            ]
        )
        external = [
            {
                "source": "wikipedia",
                "title": "Africa Addio",
                "url": "https://en.wikipedia.org/wiki/Africa_Addio",
            }
        ]

        with patch("movie_inbox.web.routers.search.search_sources", return_value=external):
            response = self.client.get(
                "/api/search",
                params={"q": "director:Jacopetti", "external": "true"},
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["catalog"]["results"][0]["id"], "mondo-cane")
        self.assertEqual(payload["catalog"]["results"][0]["_search"]["reason"], "director_match")
        self.assertEqual(payload["results"][0]["_search"]["reason"], "director_match")
        self.assertEqual(
            payload["sources"]["wikipedia"]["results"][0]["_search"]["reason"], "director_match"
        )

    def test_progressive_external_search_can_skip_catalog_lookup(self) -> None:
        external = [
            {
                "source": "wikipedia",
                "title": "Evil Dead Burn",
                "year": "2026",
                "url": "https://en.wikipedia.org/wiki/Evil_Dead_Burn",
            }
        ]

        with (
            patch("movie_inbox.web.routers.search.search_catalog_items") as catalog_search,
            patch(
                "movie_inbox.web.routers.search.search_sources", return_value=external
            ) as external_search,
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
            "movie_inbox.web.routers.search.enrich_selected_result",
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
                content=json.dumps(
                    {
                        "result": {
                            "source": "imdb",
                            "title": "tt0113277",
                            "url": "https://www.imdb.com/title/tt0113277/",
                        }
                    }
                ),
                headers=self.post_headers(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["results"][0]["id"], "heat")
        self.assertTrue(response.json()["results"][0]["_search"]["accepted"])

    def test_external_movie_format_can_compare_with_a_local_anime(self) -> None:
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "akira-anime",
                        "title": "Akira",
                        "original_title": "アキラ",
                        "year": "1988",
                        "kind": "anime",
                    }
                )
            ]
        )
        with patch(
            "movie_inbox.web.routers.search.enrich_selected_result",
            return_value={
                "source": "imdb",
                "title": "Akira",
                "year": "1988",
                "kind": "pelicula",
                "url": "https://www.imdb.com/title/tt0094625/",
            },
        ):
            response = self.client.post(
                "/api/search/catalog-candidates",
                content=json.dumps(
                    {
                        "result": {
                            "source": "imdb",
                            "title": "Akira",
                            "url": "https://www.imdb.com/title/tt0094625/",
                        }
                    }
                ),
                headers=self.post_headers(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()["results"][0]
        self.assertEqual(result["id"], "akira-anime")
        self.assertFalse(result["_search"]["accepted"])
        self.assertEqual(result["_search"]["reason"], "exact_title_year_anime_kind_review")

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
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "status": "to_watch",
                        "en_catalogo": True,
                        "page_image": "https://upload.wikimedia.org/heat.jpg",
                    }
                ),
                normalize_item(
                    {
                        "id": "memories",
                        "title": "Memories of Murder",
                        "year": "2003",
                        "kind": "pelicula",
                        "status": "watched",
                        "rating": 0,
                        "review": "",
                    }
                ),
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
            entry["key"] for section in payload["sections"] for entry in section["items"]
        ]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertNotIn(str(self.temporary.name), first.text)

        self.assertEqual(items_response.status_code, 200, items_response.content)
        self.assertEqual(items_response.json()["home"], payload)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["reason"], "invalid_home_date")

    def test_saved_featured_recommendations_survive_catalog_changes(self) -> None:
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "status": "to_watch",
                        "en_catalogo": True,
                        "page_image": "https://upload.wikimedia.org/heat.jpg",
                    }
                )
            ]
        )
        headers = {"X-Movie-Inbox-Token": self.config.api_token}

        initial = self.client.get("/api/home?date=2026-08-13", headers=headers)
        self.assertEqual(initial.status_code, 200, initial.content)
        self.assertEqual(initial.json()["featured"][0]["item"]["id"], "heat")
        self.assertEqual(initial.json()["featured_source"], "live")

        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "status": "watched",
                        "en_catalogo": False,
                        "page_image": "https://upload.wikimedia.org/heat.jpg",
                    }
                ),
                normalize_item(
                    {
                        "id": "collateral",
                        "title": "Collateral",
                        "year": "2004",
                        "kind": "pelicula",
                        "status": "to_watch",
                        "en_catalogo": True,
                        "page_image": "https://upload.wikimedia.org/collateral.jpg",
                    }
                ),
            ]
        )

        saved = self.client.get(
            "/api/home?date=2026-08-13&saved_featured=true",
            headers=headers,
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(saved.json()["featured_source"], "saved")
        self.assertEqual([row["item"]["id"] for row in saved.json()["featured"]], ["heat"])
        self.assertEqual(saved.json()["featured"][0]["item"]["status"], "watched")

        live = self.client.get("/api/home?date=2026-08-13", headers=headers)
        self.assertEqual(live.status_code, 200, live.content)
        self.assertEqual(live.json()["featured_source"], "live")
        self.assertEqual(live.json()["featured"][0]["item"]["id"], "collateral")

        still_saved = self.client.get(
            "/api/home?date=2026-08-13&saved_featured=true",
            headers=headers,
        )
        self.assertEqual(still_saved.status_code, 200, still_saved.content)
        self.assertEqual(still_saved.json()["featured"][0]["item"]["id"], "heat")

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
        self.assertIn(b"/static/login.js", login.content)

    def test_owner_can_preview_purge_audit_and_undo_tmdb_metadata(self) -> None:
        tmdb_url = "https://www.themoviedb.org/movie/48691"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "addio",
                        "source": "tmdb",
                        "url": tmdb_url,
                        "tmdb_url": tmdb_url,
                        "tmdb_id": "48691",
                        "title": "Adiós, tío Tom",
                        "kind": "pelicula",
                        "directors": ["Gualtiero Jacopetti"],
                        "status": "watched",
                        "rating": 8,
                        "review": "Personal",
                        "metadata_sources": {
                            field: {
                                "source": "tmdb",
                                "url": tmdb_url,
                                "updated_at": "2026-08-31T00:00:00Z",
                                "inferred": False,
                            }
                            for field in (
                                "title",
                                "kind",
                                "directors",
                                "tmdb_id",
                                "tmdb_url",
                            )
                        },
                    }
                )
            ]
        )
        token_header = {"X-Movie-Inbox-Token": self.config.api_token}

        preview = self.client.get(
            "/api/integrations/tmdb/retirement/preview",
            headers=token_header,
        )
        unconfirmed = self.client.post(
            "/api/integrations/tmdb/retirement/purge",
            content=json.dumps({"preview_id": preview.json()["preview_id"]}),
            headers=self.post_headers(),
        )
        purged = self.client.post(
            "/api/integrations/tmdb/retirement/purge",
            content=json.dumps({"preview_id": preview.json()["preview_id"], "confirmed": True}),
            headers=self.post_headers(),
        )

        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(preview.json()["affected_items"], 1)
        self.assertTrue(preview.json()["can_purge"])
        self.assertEqual(unconfirmed.status_code, 400, unconfirmed.content)
        self.assertEqual(purged.status_code, 200, purged.content)
        retired = JsonCatalogRepository(self.catalog_path, normalize_item).get("addio")
        assert retired is not None
        self.assertEqual(retired.tmdb_id, "")
        self.assertEqual(retired.directors, [])
        self.assertEqual(retired.rating, 8)
        self.assertEqual(retired.review, "Personal")

        history = self.client.get(
            "/api/integrations/tmdb/retirement/history",
            headers=token_header,
        )
        undo = self.client.post(
            "/api/integrations/tmdb/retirement/undo",
            content=json.dumps({"operation_id": purged.json()["operation"]["id"]}),
            headers=self.post_headers(),
        )

        self.assertEqual(history.status_code, 200, history.content)
        self.assertEqual(history.json()["count"], 1)
        self.assertEqual(undo.status_code, 200, undo.content)
        restored = JsonCatalogRepository(self.catalog_path, normalize_item).get("addio")
        assert restored is not None
        self.assertEqual(restored.tmdb_id, "48691")
        self.assertEqual(restored.review, "Personal")

    def test_member_must_change_password_and_catalog_is_isolated_by_session(self) -> None:
        created = self.client.post(
            "/api/members",
            content=json.dumps(
                {
                    "username": "maria",
                    "temporary_password": "a-temporary-password",
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        member_payload = created.json()["member"]
        self.assertNotIn(str(self.temporary.name), created.text)

        identity_repository = SqliteIdentityRepository(self.instance_path)
        member_catalog = identity_repository.default_catalog_for(member_payload["id"])
        self.assertIsNotNone(member_catalog)
        assert member_catalog is not None
        member_repository = open_catalog_repository(Path(member_catalog.write_path), normalize_item)
        member_repository.write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "status": "to_watch"})]
        )

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
                content=json.dumps(
                    {
                        "current_password": "a-temporary-password",
                        "new_password": "a-permanent-password",
                        "confirm_password": "a-permanent-password",
                    }
                ),
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
                content=json.dumps(
                    {
                        "id": "heat",
                        "status": "watched",
                        "source_file": str(self.catalog_path),
                    }
                ),
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
            forbidden_tmdb_retirement = member_client.get(
                "/api/integrations/tmdb/retirement/preview",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
            self.assertEqual(updated.status_code, 200, updated.content)
            self.assertEqual(forbidden_members.status_code, 403)
            self.assertEqual(forbidden_libraries.status_code, 403)
            self.assertEqual(forbidden_scanner_queue.status_code, 403)
            self.assertEqual(forbidden_tmdb_retirement.status_code, 403)

        owner_item = JsonCatalogRepository(self.catalog_path, normalize_item).get("heat")
        member_item = member_repository.get("heat")
        assert owner_item is not None
        assert member_item is not None
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
        assert original_catalog is not None
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
        assert restored_catalog is not None
        self.assertEqual(Path(restored_catalog.write_path), original_catalog_path)
        self.assertFalse(
            identity_repository.privacy_for(restored.json()["member"]["id"]).catalog_shared
        )

    def test_shared_catalog_respects_user_preferences_and_item_overrides(self) -> None:
        owner_id = self.login_response.json()["user"]["id"]
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
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
                    }
                )
            ]
        )
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
                content=json.dumps(
                    {
                        "current_password": "a-temporary-password",
                        "new_password": "a-permanent-password",
                        "confirm_password": "a-permanent-password",
                    }
                ),
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
                content=json.dumps(
                    {
                        "catalog_shared": True,
                        "share_status": True,
                        "share_watched_at": False,
                        "share_history": False,
                        "share_rating": False,
                        "share_review": True,
                    }
                ),
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
            self.assertEqual(
                [entry["user"]["id"] for entry in shared_list.json()["catalogs"]], [owner_id]
            )
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
                content=json.dumps(
                    {
                        "catalog_shared": False,
                        "share_status": True,
                        "share_watched_at": False,
                        "share_history": False,
                        "share_rating": False,
                        "share_review": True,
                    }
                ),
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
        assert item is not None
        self.assertEqual(item.status, "to_watch")
        self.assertEqual(item.rating, 0)
        self.assertEqual(item.review, "")
        self.assertFalse(item.en_catalogo)
        self.assertEqual(item.extra["collection_sources"][0]["collection_id"], collection["id"])

    def test_import_draft_previews_and_idempotently_writes_the_personal_catalog(self) -> None:
        raw_private_path = "D:/Private/Ikiru.mkv"
        created = self.client.post(
            "/api/imports",
            content=json.dumps(
                {
                    "source_name": "watched.json",
                    "source_format": "json",
                    "content": json.dumps(
                        [
                            {
                                "title": "Ikiru",
                                "year": "1952",
                                "status": "watched",
                                "watched_at": "2026-08-01",
                                "rating": 10,
                                "review": "Una obra enorme.",
                                "en_catalogo": True,
                                "local_path": raw_private_path,
                                "local_files": [{"name": "Ikiru.mkv", "path": raw_private_path}],
                            }
                        ]
                    ),
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        draft = created.json()
        self.assertEqual(draft["counts"]["new"], 1)
        self.assertTrue(draft["items"][0]["catalog_eligible"])
        self.assertEqual(draft["items"][0]["item"]["local_files"], [])
        self.assertNotIn(raw_private_path, created.text)
        self.assertNotIn(raw_private_path.encode("utf-8"), self.instance_path.read_bytes())

        body = json.dumps(
            {
                "destination": "catalog",
                "item_ids": [draft["items"][0]["id"]],
                "personal_options": {
                    "include_status": True,
                    "include_watched_at": True,
                    "include_rating": True,
                    "include_review": True,
                },
            }
        )
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
            content=json.dumps(
                {
                    "source_name": "japanese.csv",
                    "source_format": "csv",
                    "content": (
                        "title,year,status,rating,review\n"
                        "Heat,1995,watched,8,Great\n"
                        "Ikiru,1952,watched,10,Perfect\n"
                    ),
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        draft = created.json()
        selected = [entry["id"] for entry in draft["items"] if entry["collection_eligible"]]
        self.assertEqual(len(selected), 2)

        applied = self.client.post(
            f"/api/imports/{draft['id']}/apply",
            content=json.dumps(
                {
                    "destination": "collection",
                    "item_ids": selected,
                    "collection_title": "Noches japonesas",
                    "collection_description": "Selección privada",
                }
            ),
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
        self.assertEqual(
            [
                item.title
                for item in JsonCatalogRepository(self.catalog_path, normalize_item).read()
            ],
            ["Heat"],
        )

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
        after = self.client.get(
            "/api/items", headers={"X-Movie-Inbox-Token": self.config.api_token}
        )
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
        self.assertIn(b"/static/style.css", body)
        self.assertIn(b"/static/app.js", body)
        self.assertIn(b"viewport-fit=cover", body)
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
        self.assertIn(b'id="curationQueueSearch"', body)
        self.assertIn(b'id="curationDetail"', body)
        self.assertIn(b'id="curationHistoryCount"', body)
        self.assertIn(b'id="persistCurationHistory"', body)
        self.assertIn(b'id="mergeComparatorDialog"', body)
        self.assertIn(b'id="mergeComparatorFields"', body)
        self.assertIn(b'<div aria-live="polite">', body)
        self.assertIn(b'aria-describedby="mergeDecisionStatus"', body)
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
        self.assertIn(b'id="homeDateToday"', body)
        self.assertIn(b'id="homeDateYesterday"', body)
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
        self.assertNotIn(b"<style>", body)

        status, entry_css = self.request("GET", "/static/style.css")
        self.assertEqual(status, 200)
        imports = re.findall(rb'@import\s+"([^"]+)";', entry_css)
        self.assertTrue(imports, "expected style.css to @import its per-surface css/*.css files")
        css_parts = []
        for import_path in imports:
            part_status, part_css = self.request("GET", "/static/" + import_path.decode("ascii"))
            self.assertEqual(part_status, 200)
            css_parts.append(part_css)
        css = b"\n".join(css_parts)
        self.assertIn(b".search-console", css)
        self.assertIn(b".dvd-case", css)
        self.assertIn(b".dvd-front-statuses", css)
        self.assertIn(b".home-program-grid", css)
        self.assertIn(b".spotlight-program", css)
        self.assertIn(b".collection-filter-toolbar", css)
        self.assertIn(b".filter-segments", css)
        self.assertIn(b".home-empty-state", css)
        self.assertIn(b".curation-workbench", css)
        self.assertIn(b".curation-queue-item", css)
        self.assertIn(b".curation-queue-search", css)
        self.assertIn(b".curation-pair", css)
        self.assertIn(b".merge-comparator-dialog", css)
        self.assertIn(b".merge-field-options", css)
        self.assertIn(b".history-operation-mark", css)
        self.assertIn(b".admin-section-nav", css)
        self.assertIn(b".member-row", css)
        self.assertIn(b".member-dialog", css)
        self.assertIn(b".club-grid", css)
        self.assertIn(b".club-mode-tabs", css)
        self.assertIn(b".collection-card", css)
        self.assertIn(b".collection-mosaic", css)
        self.assertIn(b".collection-bulk-bar", css)
        self.assertIn(b".collection-item-actions", css)
        self.assertIn(b".privacy-fieldset", css)
        self.assertIn(b".personal-privacy-fields", css)
        self.assertIn(b".system-menu-panel", css)
        self.assertIn(b".active-filters", css)
        self.assertIn(b".collection-view.is-compare-mode #grid", css)
        self.assertIn(b".header-utilities", css)
        self.assertIn(b".system-menu-toggle", css)
        self.assertIn(b"grid-template-columns: repeat(4, minmax(0, 1fr))", css)
        self.assertIn(b"env(safe-area-inset-bottom", css)
        self.assertIn(b"input, select, textarea, button", css)
        self.assertIn(b"textarea:focus-visible", css)
        self.assertIn(b"button:disabled", css)
        self.assertIn(b'body[data-input-method="keyboard"] .view-focus-target:focus', css)
        self.assertIn(b".metadata-row textarea { font-size: var(--text-control); }", css)
        self.assertIn(b"scroll-snap-type: x proximity", css)
        self.assertIn(b"--ease-out: cubic-bezier", css)
        self.assertIn(b".section-kicker", css)
        self.assertIn(b"@media (hover: hover) and (pointer: fine)", css)
        self.assertIn(b"@media (hover: none) and (pointer: coarse)", css)
        self.assertIn(b":has(.dvd-open-surface:focus-visible)", css)
        self.assertIn(b".drawer-accordion", css)
        self.assertIn(b".spotlight-stage", css)
        self.assertIn(b".detail-drawer[open]", css)
        self.assertIn(b".personal-record-read", css)
        self.assertIn(b".drawer-navigation", css)
        self.assertIn(b".unsaved-dialog", css)
        self.assertIn(b".search-source-feedback", css)
        self.assertIn(b".source-search-spinner", css)
        self.assertIn(b"prefers-reduced-motion", css)
        self.assertIn(b"@media (forced-colors: active)", css)
        self.assertIn(b"--on-accent: #080a18", css)
        self.assertIn(b"--text-label: 10px", css)

        # app.js is now a thin ES module entrypoint (Fase 4); it only imports the real
        # bootstrap module, so this checks packaging (200 + native-module shape), not
        # the copy/markup any individual surface module renders. Playwright covers the
        # actual rendered behavior (tests/browser/test_ui_browser.py).
        status, javascript = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b'import "/static/js/core/bootstrap.js";', javascript)
        status, bootstrap_js = self.request("GET", "/static/js/core/bootstrap.js")
        self.assertEqual(status, 200)
        self.assertIn(b"handleDelegatedClick", bootstrap_js)
        # Removed here (Fase 4): ~60 asserts that grepped specific function names,
        # internal code lines, and historical anti-patterns (inline onclick=, &token=
        # in URLs, alert(), console.log()) out of the single app.js blob. None of that
        # survives a real module split, and none of it tested behavior — it tested that
        # certain source text existed in one particular file. The security-relevant
        # ones (no inline handlers, no token leakage, no debug leftovers) are worth
        # reintroducing as a real check across every static/js/**/*.js file if this
        # matters again; the rest (specific function names/signatures) shouldn't come
        # back in this form. Real behavioral coverage lives in
        # tests/browser/test_ui_browser.py.

    def test_static_assets_are_cached_with_etag_revalidation(self) -> None:
        first = self.client.get("/static/js/core/bootstrap.js")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["cache-control"], "public, max-age=3600, must-revalidate")
        etag = first.headers["etag"]
        self.assertTrue(etag)

        revalidated = self.client.get(
            "/static/js/core/bootstrap.js", headers={"If-None-Match": etag}
        )
        self.assertEqual(revalidated.status_code, 304)
        self.assertEqual(
            revalidated.headers["cache-control"], "public, max-age=3600, must-revalidate"
        )
        self.assertFalse(revalidated.content)

        # API responses stay uncached: they carry per-session catalog data.
        api_headers = {"X-Movie-Inbox-Token": self.config.api_token}
        api_response = self.client.get("/api/items", headers=api_headers)
        self.assertEqual(api_response.headers["cache-control"], "no-store")

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

        body = json.dumps(
            {
                "id": "heat",
                "source_file": str(self.catalog_path),
                "status": "deferred",
            }
        )
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
        assert item is not None
        self.assertEqual(item.link_curation_status, "deferred")

    def test_items_response_exposes_external_link_counts(self) -> None:
        status, raw_payload = self.request(
            "GET",
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        payload = json.loads(raw_payload)
        self.assertEqual(status, 200, raw_payload)
        self.assertEqual(payload["links"], {"with_link": 0, "without_link": 1})

    def test_duplicate_pair_can_be_dismissed_from_the_queue(self) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write(
            [
                normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
            ]
        )
        status, raw_payload = self.request(
            "GET",
            "/api/curation",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        payload = json.loads(raw_payload)
        duplicate = next(case for case in payload["cases"] if case["type"] == "duplicate")
        self.assertEqual(status, 200, raw_payload)
        self.assertEqual(payload["counts"]["duplicates"], 1)

        body = json.dumps(
            {
                "id": duplicate["primary"]["id"],
                "source_file": duplicate["primary"]["source_file"],
                "other_reference": duplicate["secondary"]["ref"],
                "status": "not_duplicate",
            }
        )
        status, raw_payload = self.request(
            "POST", "/api/curation/duplicate", body, self.post_headers()
        )
        self.assertEqual(status, 200, raw_payload)

        status, raw_payload = self.request(
            "GET",
            "/api/curation",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(json.loads(raw_payload)["counts"]["duplicates"], 0)

    def test_reviewed_duplicate_merge_is_recorded_and_undo_restores_both_items(self) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write(
            [
                normalize_item(
                    {
                        "id": "heat-a",
                        "title": "Heat",
                        "year": "1995",
                        "status": "watched",
                        "rating": 8,
                        "en_catalogo": True,
                        "local_files": [{"path": "D:/Heat.mkv", "name": "Heat.mkv"}],
                    }
                ),
                normalize_item(
                    {
                        "id": "heat-b",
                        "title": "Heat",
                        "spanish_title": "Fuego contra fuego",
                        "year": "1995",
                        "status": "to_watch",
                        "imdb_url": "https://www.imdb.com/title/tt0113277/",
                        "url": "https://www.imdb.com/title/tt0113277/",
                        "source": "imdb",
                    }
                ),
            ]
        )

        def reference(item_id):
            return {"id": item_id, "source_file": str(self.catalog_path)}

        compare_body = json.dumps(
            {
                "left": reference("heat-a"),
                "right": reference("heat-b"),
                "survivor_side": "left",
            }
        )
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

        merge_body = json.dumps(
            {
                "left": reference("heat-a"),
                "right": reference("heat-b"),
                "survivor_side": "left",
                "review_id": comparison["review_id"],
                "choices": {"status": "left"},
                "history_mode": "persistent",
            }
        )
        status, raw_payload = self.request(
            "POST",
            "/api/curation/merge",
            merge_body,
            self.post_headers(),
        )
        self.assertEqual(status, 200, raw_payload)
        merged_payload = json.loads(raw_payload)
        self.assertEqual([item.id for item in repository.read()], ["heat-a"])
        merged = repository.get("heat-a")
        assert merged is not None
        self.assertEqual(merged.spanish_title, "Fuego contra fuego")

        status, raw_payload = self.request(
            "GET",
            "/api/curation/history?mode=persistent",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(status, 200, raw_payload)
        history = json.loads(raw_payload)
        self.assertEqual(history["count"], 1)
        self.assertTrue(history["operations"][0]["can_undo"])

        undo_body = json.dumps(
            {
                "operation_id": merged_payload["operation"]["id"],
                "history_mode": "persistent",
            }
        )
        status, raw_payload = self.request(
            "POST",
            "/api/curation/undo",
            undo_body,
            self.post_headers(),
        )
        self.assertEqual(status, 200, raw_payload)
        self.assertEqual([item.id for item in repository.read()], ["heat-a", "heat-b"])

    def test_auto_resolve_endpoint_merges_clear_duplicates_and_leaves_conflicts_pending(
        self,
    ) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write(
            [
                normalize_item({"id": "heat-a", "title": "Heat", "year": "1995"}),
                normalize_item({"id": "heat-b", "title": "Heat", "year": "1995"}),
                normalize_item(
                    {"id": "sicario-a", "title": "Sicario", "year": "2015", "rating": 9}
                ),
                normalize_item(
                    {"id": "sicario-b", "title": "Sicario", "year": "2015", "rating": 3}
                ),
            ]
        )

        status, raw_payload = self.request(
            "POST",
            "/api/curation/auto-resolve",
            json.dumps({"history_mode": "persistent"}),
            self.post_headers(),
        )
        self.assertEqual(status, 200, raw_payload)
        result = json.loads(raw_payload)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(result["needs_review"], 1)

        remaining = {item.id for item in repository.read()}
        self.assertEqual(remaining, {"sicario-a", "sicario-b"} | (remaining & {"heat-a", "heat-b"}))
        self.assertEqual(len(remaining & {"heat-a", "heat-b"}), 1)

        status, raw_payload = self.request(
            "GET",
            "/api/curation/history?mode=persistent",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(status, 200, raw_payload)
        self.assertEqual(json.loads(raw_payload)["count"], 1)

        status, raw_payload = self.request(
            "GET", "/api/curation", headers={"X-Movie-Inbox-Token": self.config.api_token}
        )
        self.assertEqual(status, 200, raw_payload)
        pending_duplicates = [
            case
            for case in json.loads(raw_payload)["cases"]
            if case["type"] == "duplicate" and case["status"] == "pending"
        ]
        self.assertEqual(len(pending_duplicates), 1)
        self.assertEqual(pending_duplicates[0]["primary"]["title"], "Sicario")

    def test_curation_endpoints_expose_availability_alongside_the_manual_flag(self) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write(
            [
                normalize_item(
                    {
                        "id": "heat-scanned",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "added_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
                normalize_item(
                    {
                        "id": "sicario-manual",
                        "title": "Sicario",
                        "year": "2015",
                        "kind": "pelicula",
                        "en_catalogo": True,
                    }
                ),
            ]
        )

        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                    "max_missing_ratio": 0.5,
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(created.status_code, 201, created.content)
        library_id = created.json()["library"]["id"]
        self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "dry_run"}),
            headers=self.post_headers(),
        )
        applied = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "apply"}),
            headers=self.post_headers(),
        )
        self.assertEqual(applied.status_code, 202, applied.content)

        status, raw_payload = self.request(
            "GET", "/api/curation", headers={"X-Movie-Inbox-Token": self.config.api_token}
        )
        self.assertEqual(status, 200, raw_payload)
        queue = json.loads(raw_payload)
        scanned_case = next(
            case for case in queue["cases"] if case["primary"]["id"] == "heat-scanned"
        )
        self.assertTrue(scanned_case["primary"]["_availability"]["server"])
        self.assertFalse(scanned_case["primary"]["_availability"]["manual"])
        self.assertEqual(scanned_case["primary"]["added_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(scanned_case["primary"]["local_files"], [])

        def reference(item_id):
            return {"id": item_id, "source_file": str(self.catalog_path)}

        compare_body = json.dumps(
            {
                "left": reference("heat-scanned"),
                "right": reference("sicario-manual"),
                "survivor_side": "left",
            }
        )
        status, raw_payload = self.request(
            "POST", "/api/curation/compare", compare_body, self.post_headers()
        )
        self.assertEqual(status, 200, raw_payload)
        comparison = json.loads(raw_payload)
        self.assertTrue(comparison["left"]["_availability"]["server"])
        self.assertFalse(comparison["left"]["_availability"]["manual"])
        self.assertFalse(comparison["right"]["_availability"]["server"])
        self.assertTrue(comparison["right"]["_availability"]["manual"])
        self.assertEqual(comparison["left"]["added_at"], "2026-01-01T00:00:00+00:00")

        merge_body = json.dumps(
            {
                "left": reference("heat-scanned"),
                "right": reference("sicario-manual"),
                "survivor_side": "left",
                "review_id": comparison["review_id"],
            }
        )
        status, raw_payload = self.request(
            "POST", "/api/curation/merge", merge_body, self.post_headers()
        )
        self.assertEqual(status, 200, raw_payload)
        merged_payload = json.loads(raw_payload)
        self.assertTrue(merged_payload["item"]["_availability"]["effective"])
        merged = repository.get("heat-scanned")
        assert merged is not None
        self.assertTrue(merged.en_catalogo)

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

    @patch("movie_inbox.web.routers.catalog.background_enrich_catalog_item")
    @patch(
        "movie_inbox.web.routers.catalog.enrich_selected_result",
        side_effect=lambda result: result,
    )
    def test_add_schedules_title_enrichment_when_wikidata_is_missing(
        self, _, background_enrichment
    ) -> None:
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

    @patch("movie_inbox.web.routers.catalog.background_enrich_catalog_item")
    @patch(
        "movie_inbox.web.routers.catalog.enrich_selected_result",
        side_effect=lambda result: result,
    )
    def test_adding_the_same_title_from_a_different_source_merges_instead_of_duplicating(
        self, _, __
    ) -> None:
        # [Q6]: the seeded catalog item is {"id": "heat", "title": "Heat", "year":
        # "1995"} with no external links yet -- an IMDb-sourced add for the exact
        # same title+year should fold into it (decide_match's exact_title_year
        # acceptance) instead of prompting for a manual merge or creating a
        # second, unlinked entry.
        body = json.dumps(
            {
                "title": "Heat",
                "spanish_title": "Fuego contra fuego",
                "year": "1995",
                "source": "imdb",
                "url": "https://www.imdb.com/title/tt0113277/",
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
            }
        )

        status, raw_payload = self.request("POST", "/api/add", body, self.post_headers())
        payload = json.loads(raw_payload)

        self.assertEqual(status, 200, raw_payload)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["reason"], "merged_into_existing")
        self.assertEqual(payload["item"]["id"], "heat")
        self.assertEqual(payload["item"]["spanish_title"], "Fuego contra fuego")
        self.assertEqual(payload["item"]["imdb_url"], "https://www.imdb.com/title/tt0113277/")
        self.assertTrue(payload["operation"]["can_undo"])

        items = JsonCatalogRepository(self.catalog_path, normalize_item).read()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].spanish_title, "Fuego contra fuego")

        # A third add, from yet another source, keeps accumulating into the same
        # item -- exactly "sin pedir tres altas ni una fusion manual".
        third_body = json.dumps(
            {
                "title": "Heat",
                "year": "1995",
                "source": "filmaffinity",
                "url": "https://www.filmaffinity.com/es/film267267.html",
                "filmaffinity_url": "https://www.filmaffinity.com/es/film267267.html",
                "description": "Un detective y un ladron chocan en Los Angeles.",
            }
        )
        third_status, third_raw = self.request("POST", "/api/add", third_body, self.post_headers())
        third_payload = json.loads(third_raw)

        self.assertEqual(third_status, 200, third_raw)
        self.assertEqual(third_payload["reason"], "merged_into_existing")
        self.assertEqual(third_payload["item"]["id"], "heat")
        self.assertEqual(
            third_payload["item"]["description"],
            "Un detective y un ladron chocan en Los Angeles.",
        )
        self.assertEqual(
            third_payload["item"]["filmaffinity_url"],
            "https://www.filmaffinity.com/es/film267267.html",
        )
        # The IMDb link from the second add survives the third merge untouched.
        self.assertEqual(third_payload["item"]["imdb_url"], "https://www.imdb.com/title/tt0113277/")

        final_items = JsonCatalogRepository(self.catalog_path, normalize_item).read()
        self.assertEqual(len(final_items), 1)

    def test_owner_can_test_apply_and_read_shared_scanner_availability(self) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                    "max_missing_ratio": 0.5,
                }
            ),
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
        self.assertEqual(
            test_run.json()["run"]["preview"][0]["relative_path"], "Heat.1995.1080p.mkv"
        )
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

    def test_sharing_a_librarys_availability_publishes_a_club_collection_without_leaking_paths(
        self,
    ) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Blu-rays del living",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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

        shared = self.client.post(
            f"/api/libraries/{library_id}/share-availability",
            content=json.dumps({"enabled": True}),
            headers=self.post_headers(),
        )
        self.assertEqual(shared.status_code, 200, shared.content)
        self.assertTrue(shared.json()["collection_synced"])
        self.assertTrue(shared.json()["library"]["share_availability_as_collection"])
        self.assertEqual(shared.json()["library"]["club_title"], "Blu-rays del living")

        listed = self.client.get(
            "/api/collections", headers={"X-Movie-Inbox-Token": self.config.api_token}
        )
        collection = next(
            item for item in listed.json()["collections"] if item["title"] == "Blu-rays del living"
        )
        self.assertEqual(collection["source_kind"], "user")

        detail = self.client.get(
            f"/api/collections/{collection['id']}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(detail.status_code, 200, detail.content)
        heat = next(item for item in detail.json()["items"] if item["title"] == "Heat")
        self.assertEqual(heat["year"], "1995")
        self.assertNotIn(library_id, detail.text)
        self.assertNotIn(str(self.media_path), detail.text)
        self.assertNotIn("Heat.1995.1080p.mkv", detail.text)
        self.assertNotIn("library_id", detail.text)
        self.assertNotIn("library_name", detail.text)

        disabled = self.client.post(
            f"/api/libraries/{library_id}/share-availability",
            content=json.dumps({"enabled": False}),
            headers=self.post_headers(),
        )
        self.assertEqual(disabled.status_code, 200, disabled.content)
        after_disable = self.client.get(
            f"/api/collections/{collection['id']}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(after_disable.json()["visibility"], "private")
        self.assertEqual(after_disable.json()["title"], "Blu-rays del living")

    def test_owner_can_set_exclusion_rules_and_the_next_scan_respects_them(self) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        bonus_dir = self.media_path / "Bonus"
        bonus_dir.mkdir()
        (bonus_dir / "clip.mp4").write_bytes(b"bonus-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {"name": "Con reglas", "root_path": str(self.media_path), "schedule": "manual"}
            ),
            headers=self.post_headers(),
        )
        library_id = created.json()["library"]["id"]

        invalid = self.client.post(
            f"/api/libraries/{library_id}/exclusion-rules",
            content=json.dumps({"patterns": ["ok-pattern", "*"]}),
            headers=self.post_headers(),
        )
        self.assertEqual(invalid.status_code, 400, invalid.content)
        payload = invalid.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["reason"], "invalid_patterns")
        self.assertEqual(
            {(entry["pattern"], entry["reason"]) for entry in payload["errors"]},
            {("*", "excludes_everything")},
        )

        valid = self.client.post(
            f"/api/libraries/{library_id}/exclusion-rules",
            content=json.dumps({"patterns": ["bonus*"]}),
            headers=self.post_headers(),
        )
        self.assertEqual(valid.status_code, 200, valid.content)
        self.assertEqual(valid.json()["library"]["exclusion_patterns"], ["bonus*"])

        tested = self.client.post(
            f"/api/libraries/{library_id}/runs",
            content=json.dumps({"mode": "dry_run"}),
            headers=self.post_headers(),
        )
        run = self.client.get(
            f"/api/library-runs/{tested.json()['run']['id']}",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()["run"]

        self.assertEqual(run["summary"]["discovered"], 1)  # only Heat.1995.1080p.mkv
        self.assertEqual(run["summary"]["newly_excluded"], 0)  # Bonus was never applied/tracked

    def test_scheduled_scans_require_applied_inventory_and_manual_libraries_reject_activation(
        self,
    ) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas programadas",
                    "root_path": str(self.media_path),
                    "schedule": "hourly",
                }
            ),
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
        self.assertEqual(
            before_apply.json()["reason"], "Apply inventory before activating scheduled scans"
        )
        self.assertEqual(applied.status_code, 202, applied.content)
        self.assertEqual(after_apply.json()["library"]["counts"]["files"], 1)
        self.assertEqual(activated.status_code, 200, activated.content)
        self.assertTrue(activated.json()["library"]["active"])
        self.assertGreater(activated.json()["library"]["next_scan_at"], 0)
        self.assertFalse(switched_to_manual.json()["library"]["active"])
        self.assertEqual(switched_to_manual.json()["library"]["next_scan_at"], 0)
        self.assertEqual(manual_activation.status_code, 409, manual_activation.content)
        self.assertEqual(
            manual_activation.json()["reason"], "Manual libraries do not use scheduled activation"
        )

    def test_offline_library_run_keeps_previous_availability_over_http(self) -> None:
        (self.media_path / "Heat.1995.1080p.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Disco removible",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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

    @patch("movie_inbox.web.routers.scanner.background_enrich_catalog_item")
    def test_unknown_scanner_file_can_create_a_personal_catalog_item(self, enrich) -> None:
        (self.media_path / "Arrival.2016.mkv").write_bytes(b"arrival-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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
            content=json.dumps(
                {
                    "action": "create",
                    "title": "Arrival",
                    "year": "2016",
                    "kind": "pelicula",
                }
            ),
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
        self.assertTrue(
            next(item for item in items.json()["items"] if item["id"] == arrival.id)[
                "_availability"
            ]["server"]
        )
        enrich.assert_called_once()

    @patch("movie_inbox.web.routers.scanner.background_enrich_catalog_item")
    def test_scanner_create_can_be_undone_and_removes_the_created_item(self, _enrich) -> None:
        (self.media_path / "Interstellar.2014.mkv").write_bytes(b"interstellar-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
            headers=self.post_headers(),
        )
        library_id = created.json()["library"]["id"]
        for mode in ("dry_run", "apply"):
            self.client.post(
                f"/api/libraries/{library_id}/runs",
                content=json.dumps({"mode": mode}),
                headers=self.post_headers(),
            )
        queue_item = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()["items"][0]

        reviewed = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps(
                {
                    "action": "create",
                    "title": "Interstellar",
                    "year": "2014",
                    "kind": "pelicula",
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(reviewed.status_code, 201, reviewed.content)
        self.assertEqual(reviewed.json()["catalog_action"], "created")
        operation = reviewed.json()["operation"]
        self.assertTrue(operation["can_undo"])
        created_item_id = reviewed.json()["catalog_item"]["id"]
        self.assertTrue(
            any(
                item.id == created_item_id
                for item in JsonCatalogRepository(self.catalog_path, normalize_item).read()
            )
        )
        self.assertEqual(
            self.client.get(
                "/api/scanner/queue",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            ).json()["count"],
            0,
        )

        undone = self.client.post(
            "/api/scanner/undo",
            content=json.dumps({"operation_id": operation["id"]}),
            headers=self.post_headers(),
        )
        self.assertEqual(undone.status_code, 200, undone.content)

        catalog_after_undo = JsonCatalogRepository(self.catalog_path, normalize_item).read()
        self.assertFalse(any(item.id == created_item_id for item in catalog_after_undo))
        restored_queue = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()
        self.assertEqual(restored_queue["count"], 1)
        self.assertEqual(restored_queue["items"][0]["id"], queue_item["id"])

    @patch("movie_inbox.web.routers.scanner.background_enrich_catalog_item")
    def test_scanner_create_undo_reports_a_conflict_instead_of_crashing(self, _enrich) -> None:
        (self.media_path / "Dune.2021.mkv").write_bytes(b"dune-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
            headers=self.post_headers(),
        )
        library_id = created.json()["library"]["id"]
        for mode in ("dry_run", "apply"):
            self.client.post(
                f"/api/libraries/{library_id}/runs",
                content=json.dumps({"mode": mode}),
                headers=self.post_headers(),
            )
        queue_item = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()["items"][0]

        reviewed = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps(
                {
                    "action": "create",
                    "title": "Dune",
                    "year": "2021",
                    "kind": "pelicula",
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(reviewed.status_code, 201, reviewed.content)
        operation = reviewed.json()["operation"]
        created_item_id = reviewed.json()["catalog_item"]["id"]

        # Something else -- e.g. real background enrichment -- touches the
        # freshly created item before the undo attempt.
        JsonCatalogRepository(self.catalog_path, normalize_item).update_item(
            created_item_id,
            lambda item: item.__setitem__("description", "Enriched in the meantime"),
        )

        undo_attempt = self.client.post(
            "/api/scanner/undo",
            content=json.dumps({"operation_id": operation["id"]}),
            headers=self.post_headers(),
        )
        # This must be a reported conflict, not an unhandled 500: the catalog-side
        # restore reuses Curacion's CurationConflict, a different exception type
        # than the scanner-queue side's LibraryConflict, and both need mapping.
        self.assertEqual(undo_attempt.status_code, 409, undo_attempt.content)
        surviving = next(
            item
            for item in JsonCatalogRepository(self.catalog_path, normalize_item).read()
            if item.id == created_item_id
        )
        self.assertEqual(surviving.description, "Enriched in the meantime")

    @patch("movie_inbox.web.routers.scanner.background_enrich_catalog_item")
    def test_scanner_create_undo_leaves_a_reused_catalog_item_untouched(self, _enrich) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        # No year in the filename, so the scan itself can't auto-match this to the
        # existing "Heat" (1995) item -- it lands in the queue needing a manual
        # decision, and the create form below is what supplies the matching year.
        (self.media_path / "Heat.mkv").write_bytes(b"heat-video")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
            headers=self.post_headers(),
        )
        library_id = created.json()["library"]["id"]
        for mode in ("dry_run", "apply"):
            self.client.post(
                f"/api/libraries/{library_id}/runs",
                content=json.dumps({"mode": mode}),
                headers=self.post_headers(),
            )
        queue_item = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()["items"][0]

        reviewed = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps(
                {
                    "action": "create",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertEqual(reviewed.json()["catalog_action"], "existing")
        operation = reviewed.json()["operation"]

        undone = self.client.post(
            "/api/scanner/undo",
            content=json.dumps({"operation_id": operation["id"]}),
            headers=self.post_headers(),
        )
        self.assertEqual(undone.status_code, 200, undone.content)
        catalog_after_undo = JsonCatalogRepository(self.catalog_path, normalize_item).read()
        self.assertEqual([item.id for item in catalog_after_undo], ["heat"])

    def test_scanner_blocks_duplicate_creation_and_can_link_the_existing_catalog_item(self) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write(
            [
                normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}),
                normalize_item(
                    {
                        "id": "legacy-1917",
                        "title": "1917",
                        "year": "1917",
                        "kind": "pelicula",
                        "source": "imdb",
                        "url": "https://www.imdb.com/title/tt8579674/",
                        "imdb_url": "https://www.imdb.com/title/tt8579674/",
                    }
                ),
            ]
        )
        (self.media_path / "1917.2019.1080p.BluRay.mkv").write_bytes(b"numeric-title")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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
            content=json.dumps(
                {
                    "action": "create",
                    "title": "1917",
                    "year": "2019",
                    "kind": "pelicula",
                }
            ),
            headers=self.post_headers(),
        )

        self.assertEqual(blocked.status_code, 409, blocked.content)
        self.assertEqual(blocked.json()["reason"], "possible_duplicate")
        self.assertEqual(blocked.json()["candidates"][0]["id"], "legacy-1917")
        self.assertEqual(blocked.json()["candidates"][0]["catalog_origin"], "own_catalog")
        self.assertTrue(blocked.json()["distinct_review_token"])
        self.assertEqual(len(repository.read()), 2)

        linked = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps(
                {
                    "action": "link_catalog",
                    "catalog_item_id": "legacy-1917",
                }
            ),
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

    def test_scanner_link_can_be_undone_from_its_history_entry(self) -> None:
        repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        repository.write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        (self.media_path / "Heat.1970.1080p.mkv").write_bytes(b"heat-1970")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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
        queue_item = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()["items"][0]

        linked = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps({"action": "link_catalog", "catalog_item_id": "heat"}),
            headers=self.post_headers(),
        )
        self.assertEqual(linked.status_code, 200, linked.content)
        operation = linked.json()["operation"]
        self.assertTrue(operation["can_undo"])

        history = self.client.get(
            "/api/scanner/history",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(history.json()["count"], 1)
        self.assertEqual(history.json()["operations"][0]["id"], operation["id"])

        undone = self.client.post(
            "/api/scanner/undo",
            content=json.dumps({"operation_id": operation["id"]}),
            headers=self.post_headers(),
        )
        self.assertEqual(undone.status_code, 200, undone.content)

        restored_queue = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()
        self.assertEqual(restored_queue["count"], 1)
        self.assertEqual(restored_queue["items"][0]["id"], queue_item["id"])

        second_undo = self.client.post(
            "/api/scanner/undo",
            content=json.dumps({"operation_id": operation["id"]}),
            headers=self.post_headers(),
        )
        self.assertEqual(second_undo.status_code, 409, second_undo.content)

    def test_scanner_ignore_can_be_undone_and_restores_the_queue_item(self) -> None:
        (self.media_path / "Unrelated.2020.1080p.mkv").write_bytes(b"unrelated")
        created = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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
        queue_item = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()["items"][0]

        ignored = self.client.post(
            f"/api/scanner/queue/{queue_item['id']}",
            content=json.dumps({"action": "ignore"}),
            headers=self.post_headers(),
        )
        self.assertEqual(ignored.status_code, 200, ignored.content)
        operation = ignored.json()["operation"]
        self.assertTrue(operation["can_undo"])
        self.assertEqual(operation["action"], "scanner_ignore")
        self.assertEqual(
            self.client.get(
                "/api/scanner/queue",
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            ).json()["count"],
            0,
        )

        undone = self.client.post(
            "/api/scanner/undo",
            content=json.dumps({"operation_id": operation["id"]}),
            headers=self.post_headers(),
        )
        self.assertEqual(undone.status_code, 200, undone.content)
        restored = self.client.get(
            "/api/scanner/queue",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        ).json()
        self.assertEqual(restored["count"], 1)
        self.assertEqual(restored["items"][0]["id"], queue_item["id"])

    def test_scanner_create_does_not_write_for_a_missing_queue_item(self) -> None:
        response = self.client.post(
            "/api/scanner/queue/missing-file",
            content=json.dumps(
                {
                    "action": "create",
                    "title": "Arrival",
                    "year": "2016",
                    "kind": "pelicula",
                }
            ),
            headers=self.post_headers(),
        )

        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(
            [
                item.title
                for item in JsonCatalogRepository(self.catalog_path, normalize_item).read()
            ],
            ["Heat"],
        )

    def test_scanner_candidates_do_not_reveal_a_private_member_catalog(self) -> None:
        created_member = self.client.post(
            "/api/members",
            content=json.dumps(
                {
                    "username": "maria",
                    "temporary_password": "a-temporary-password",
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(created_member.status_code, 201, created_member.content)
        member_id = created_member.json()["member"]["id"]
        identity_repository = SqliteIdentityRepository(self.instance_path)
        member_catalog = identity_repository.default_catalog_for(member_id)
        self.assertIsNotNone(member_catalog)
        assert member_catalog is not None
        open_catalog_repository(Path(member_catalog.write_path), normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "private-member-film",
                        "title": "Private Member Film",
                        "year": "2024",
                        "kind": "pelicula",
                    }
                )
            ]
        )
        (self.media_path / "Private.Member.Film.2024.mkv").write_bytes(b"private-video")

        created_library = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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

    def test_scanner_candidates_tag_a_shared_member_catalog_origin(self) -> None:
        created_member = self.client.post(
            "/api/members",
            content=json.dumps(
                {
                    "username": "maria",
                    "temporary_password": "a-temporary-password",
                }
            ),
            headers=self.post_headers(),
        )
        self.assertEqual(created_member.status_code, 201, created_member.content)
        member_id = created_member.json()["member"]["id"]
        identity_repository = SqliteIdentityRepository(self.instance_path)
        identity_repository.update_privacy(member_id, PrivacyPreferences(catalog_shared=True))
        member_catalog = identity_repository.default_catalog_for(member_id)
        self.assertIsNotNone(member_catalog)
        assert member_catalog is not None
        open_catalog_repository(Path(member_catalog.write_path), normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "shared-1917",
                        "title": "1917",
                        "year": "1917",
                        "kind": "pelicula",
                    }
                )
            ]
        )
        (self.media_path / "1917.2019.1080p.BluRay.mkv").write_bytes(b"numeric-title")

        created_library = self.client.post(
            "/api/libraries",
            content=json.dumps(
                {
                    "name": "Peliculas principales",
                    "root_path": str(self.media_path),
                    "schedule": "manual",
                }
            ),
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
        queue_item = queue.json()["items"][0]
        self.assertEqual(queue_item["state"], "review")
        self.assertEqual(len(queue_item["candidates"]), 1)
        self.assertEqual(queue_item["candidates"][0]["catalog_origin"], "shared_catalog")

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
