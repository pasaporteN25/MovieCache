"""[IP] `GET /api/search?membership=true`: pertenencia de los resultados externos."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.catalog_service import classify_incoming
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

HEAT_URL = "https://en.wikipedia.org/wiki/Heat_(1995_film)"


def external(title: str, url: str, **extra: Any) -> dict[str, Any]:
    return {"source": "wikipedia", "title": title, "url": url, **extra}


class ClassifyIncomingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.items = [
            normalize_item(
                {
                    "id": "heat",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                    "wikipedia_url": HEAT_URL,
                }
            )
        ]

    def test_a_shared_external_link_is_a_duplicate_and_names_the_work(self) -> None:
        incoming = normalize_item({"id": "otro", "title": "Otra", "url": HEAT_URL})
        verdict, extra = classify_incoming(self.items, incoming)
        self.assertEqual(verdict, "duplicate")
        self.assertEqual(extra["existing_id"], "heat")

    def test_the_same_title_with_another_year_is_left_for_review(self) -> None:
        incoming = normalize_item(
            {"id": "x", "title": "Heat", "year": "1986", "url": "https://example.org/a"}
        )
        verdict, extra = classify_incoming(self.items, incoming)
        self.assertEqual(verdict, "possible_duplicate")
        self.assertEqual(extra["candidates"][0]["id"], "heat")

    def test_an_unrelated_title_is_new(self) -> None:
        incoming = normalize_item({"id": "y", "title": "Stalker", "year": "1979"})
        self.assertEqual(classify_incoming(self.items, incoming), ("new", {}))


class SearchMembershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        self.repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        self.repository.write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "wikipedia_url": HEAT_URL,
                    }
                )
            ]
        )
        instance_path = root / "instance.db"
        media_path = root / "media"
        media_path.mkdir()
        password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(instance_path)).bootstrap_owner(
            "lucas",
            password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        self.config = ViewerConfig(
            patterns=[str(self.catalog_path)],
            title="Movie Inbox Test",
            write_json=str(self.catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(instance_path),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media_path),),
            library_scheduler_poll_seconds=3600,
        )
        context = TestClient(create_app(self.config), base_url="http://127.0.0.1:8765")
        self.client_context = context
        self.client = context.__enter__()
        login = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": password}),
            headers={
                "X-Movie-Inbox-Token": self.config.api_token,
                "Origin": "http://127.0.0.1:8765",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(login.status_code, 200, login.content)

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary.cleanup()

    def search(self, results: list[dict[str, Any]], **params: str) -> dict[str, Any]:
        with patch("movie_inbox.web.routers.search.search_sources", return_value=results):
            response = self.client.get(
                "/api/search",
                params={"q": "heat", "external": "true", **params},
                headers={"X-Movie-Inbox-Token": self.config.api_token},
            )
        self.assertEqual(response.status_code, 200, response.content)
        payload: dict[str, Any] = response.json()
        return payload

    def test_the_three_states_are_reported_per_result(self) -> None:
        payload = self.search(
            [
                external("Heat", HEAT_URL),
                external("Heat", "https://en.wikipedia.org/wiki/Heat_(1986_film)", year="1986"),
                external(
                    "Stalker", "https://en.wikipedia.org/wiki/Stalker_(1979_film)", year="1979"
                ),
            ],
            membership="true",
        )
        states = [row["_membership"] for row in payload["results"]]
        self.assertEqual(
            states,
            [
                {"state": "present", "item_id": "heat"},
                {"state": "review", "item_id": None},
                {"state": "missing", "item_id": None},
            ],
        )

    def test_the_membership_is_also_on_the_per_source_groups(self) -> None:
        payload = self.search([external("Heat", HEAT_URL)], membership="true")
        grouped = payload["sources"]["wikipedia"]["results"][0]
        self.assertEqual(grouped["_membership"], {"state": "present", "item_id": "heat"})

    def test_a_shared_external_id_is_present_even_with_another_title(self) -> None:
        payload = self.search([external("Calor", HEAT_URL)], membership="true")
        self.assertEqual(payload["results"][0]["_membership"]["state"], "present")

    def test_a_result_without_url_is_missing_instead_of_failing(self) -> None:
        payload = self.search([{"source": "wikipedia", "title": "Sin enlace"}], membership="true")
        self.assertEqual(payload["results"][0]["_membership"]["state"], "missing")

    def test_without_membership_the_response_is_unchanged(self) -> None:
        results = [
            external("Heat", HEAT_URL),
            external("Stalker", "https://en.wikipedia.org/wiki/S"),
        ]
        payload = self.search(results)
        for row in payload["results"]:
            self.assertNotIn("_membership", row)
        for group in payload["sources"].values():
            for row in group["results"]:
                self.assertNotIn("_membership", row)
        explicit = self.search(results, membership="false")
        self.assertNotIn("_membership", explicit["results"][0])

    def test_the_catalog_is_not_modified_by_the_query(self) -> None:
        before = self.catalog_path.read_bytes()
        self.search(
            [external("Stalker", "https://en.wikipedia.org/wiki/Stalker_(1979_film)")],
            membership="true",
        )
        self.assertEqual(self.catalog_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
