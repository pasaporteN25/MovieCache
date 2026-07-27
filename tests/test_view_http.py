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
        self.assertIn(b'.curation-workbench', css)
        self.assertIn(b'.curation-queue-item', css)
        self.assertIn(b'.curation-pair', css)
        self.assertIn(b'.merge-comparator-dialog', css)
        self.assertIn(b'.merge-field-options', css)
        self.assertIn(b'.history-operation-mark', css)
        self.assertIn(b'.admin-section-nav', css)
        self.assertIn(b'.system-menu-panel', css)
        self.assertIn(b'.active-filters', css)
        self.assertIn(b'@media (hover: hover) and (pointer: fine)', css)
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
        self.assertIn(b'function personalRecordPanel(item)', javascript)
        self.assertIn(b'function requestDetailTransition(action)', javascript)
        self.assertIn(b'function saveDirtyDetailForms()', javascript)
        self.assertIn(b'function navigateDetail(offset)', javascript)
        self.assertIn(b'function openAnotherRandomDetail()', javascript)
        self.assertIn(b'function showView(view', javascript)
        self.assertIn(b'function goToCollectionRoot()', javascript)
        self.assertIn(b'const query = requestedView === "catalog" ? rawQuery : "";', javascript)
        self.assertIn(b'function renderHomeShelf()', javascript)
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
