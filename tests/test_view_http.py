from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


from fastapi.testclient import TestClient

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
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
        self.config = ViewerConfig(
            patterns=[str(self.catalog_path)],
            title="Movie Inbox Test",
            write_json=str(self.catalog_path),
            image_cache=False,
            image_cache_dir=str(Path(self.temporary.name) / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
        )
        self.client_context = TestClient(create_app(self.config), base_url="http://127.0.0.1:8765")
        self.client = self.client_context.__enter__()

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

    def test_healthcheck_does_not_expose_catalog_data(self) -> None:
        status, payload = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload), {"status": "ok"})

    def test_image_cache_does_not_accept_session_tokens_in_urls(self) -> None:
        status, _ = self.request(
            "GET",
            "/image-cache?url=https%3A%2F%2Fimages.example.com%2Fposter.jpg&token=test-token",
        )
        self.assertEqual(status, 403)

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
        self.assertIn("HttpOnly", response.headers.get("set-cookie", ""))
        self.assertIn("SameSite=strict", response.headers.get("set-cookie", ""))
        self.assertIn(b'/static/style.css', body)
        self.assertIn(b'/static/app.js', body)
        self.assertIn(b'class="utility-menu"', body)
        self.assertIn(b'<dialog id="detailDrawer"', body)
        self.assertIn(b'id="spotlightStage"', body)
        self.assertIn(b'id="homeButton"', body)
        self.assertIn(b'id="collectionView"', body)
        self.assertIn(b'id="adminView"', body)
        self.assertIn(b'id="adminButton"', body)
        self.assertIn(b'id="systemMenu"', body)
        self.assertIn(b'id="homeGrid"', body)
        self.assertIn(b'id="activeFilters"', body)
        self.assertIn(b'id="sort"', body)
        self.assertIn(b'id="randomButton"', body)
        self.assertIn(b'id="randomCatalogOnly"', body)
        self.assertNotIn(b'<style>', body)

        status, css = self.request("GET", "/static/style.css")
        self.assertEqual(status, 200)
        self.assertIn(b'.search-console', css)
        self.assertIn(b'.dvd-case', css)
        self.assertIn(b'.dvd-front-statuses', css)
        self.assertIn(b'.home-grid', css)
        self.assertIn(b'.admin-section-nav', css)
        self.assertIn(b'.system-menu-panel', css)
        self.assertIn(b'.active-filters', css)
        self.assertIn(b'@media (hover: hover) and (pointer: fine)', css)
        self.assertIn(b':has(.dvd-open-surface:focus-visible)', css)
        self.assertIn(b'.drawer-accordion', css)
        self.assertIn(b'.spotlight-stage', css)
        self.assertIn(b'.detail-drawer[open]', css)
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
        self.assertIn(b'function showView(view', javascript)
        self.assertIn(b'function renderHomeShelf()', javascript)
        self.assertIn(b'function renderActiveFilters()', javascript)
        self.assertIn(b'function sortItems(list)', javascript)
        self.assertIn(b'const catalogItems = items.filter((item) => isInCatalog(item.en_catalogo))', javascript)
        self.assertNotIn(b'data-click="toggle-flip"', javascript)
        self.assertNotIn(b'onclick=', javascript)
        self.assertNotIn(b'&token=', javascript)

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
            root = client.get("/")
            response = client.post("/api/status", content=body, headers=headers)
        self.assertIn("Secure", root.headers.get("set-cookie", ""))
        self.assertEqual(response.status_code, 200, response.content)

    def test_json_body_limit_is_enforced(self) -> None:
        body = json.dumps({"id": "heat", "review": "x" * MAX_JSON_BODY_BYTES})
        status, payload = self.request("POST", "/api/personal", body, self.post_headers())
        self.assertEqual(status, 400)
        self.assertIn(b"too large", payload)

    def test_invalid_catalog_is_reported_instead_of_becoming_empty(self) -> None:
        self.catalog_path.write_text('{"schema_version": 5, "items": []}', encoding="utf-8")
        status, payload = self.request(
            "GET",
            "/api/items",
            headers={"X-Movie-Inbox-Token": self.config.api_token},
        )
        self.assertEqual(status, 422, payload)
        self.assertIn(b"newer than supported", payload)


if __name__ == "__main__":
    unittest.main()
