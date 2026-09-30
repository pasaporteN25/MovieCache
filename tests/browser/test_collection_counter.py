"""Unified Collection, cumulative shelves and return navigation on disposable data."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from tests.browser import test_ui_browser as fixture


class CollectionCounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture.BrowserInterfaceTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        fixture.BrowserInterfaceTests.tearDownClass.__func__(cls)

    setUp = fixture.BrowserInterfaceTests.setUp
    tearDown = fixture.BrowserInterfaceTests.tearDown

    def open_collection(self, *, count=65, query="?view=catalog") -> None:
        payload = self.page.request.get(
            f"{self.base_url}/api/items", headers={"X-Movie-Inbox-Token": self.config.api_token}
        ).json()
        payload["items"] = [
            {
                **payload["items"][0],
                "id": f"counter-{index}",
                "title": f"Película de prueba {index:02d}",
                "year": str(1960 + index),
                "kind": "pelicula",
                "status": "watched" if index % 2 else "to_watch",
                "en_catalogo": bool(index % 3),
                "_availability": {"effective": bool(index % 3), "manual": bool(index % 3)},
                "page_image": (
                    "https://example.test/metropolis.jpg"
                    if index == 0
                    else "https://example.test/missing.png"
                    if index == 1
                    else ""
                ),
            }
            for index in range(count)
        ]
        if count > 2:
            payload["items"][2]["title"] = (
                "Película de prueba con un título extraordinariamente largo "
                "que conserva sus palabras y también Supercalifragilisticoespialidoso"
            )
        self.page.route("**/api/items?*", lambda route: route.fulfill(json=payload))
        poster = Path("docs/design/u4-2b-integrated-junction-v1/metropolis-poster.jpg").read_bytes()
        self.page.route(
            "**/image-cache?*",
            lambda route: (
                route.fulfill(body=poster, content_type="image/jpeg")
                if "metropolis" in route.request.url
                else route.fulfill(status=404)
            ),
        )
        self.page.route(
            "**/api/search?*",
            lambda route: route.fulfill(json={"results": [], "catalog": {"results": []}}),
        )
        self.page.goto(self.base_url + query)
        fixture.wait_for_app_ready(self.page)
        self.page.wait_for_selector("#collectionView:not([hidden])")

    def test_search_filters_clear_and_legacy_url_share_one_shelf(self) -> None:
        self.open_collection(query="?view=catalog&mode=search&status=watched&q=prueba")
        page = self.page
        self.assertTrue(page.locator("#query").is_visible())
        self.assertEqual(page.locator('[data-mode="search"]').count(), 0)
        self.assertEqual(page.locator("#query").input_value(), "prueba")
        page.locator("#clearManualSearch").click()
        self.assertIn("status=watched", page.url)
        self.assertEqual(page.locator("#query").input_value(), "")
        self.assertEqual(page.evaluate("document.activeElement.id"), "query")
        self.assertTrue(page.locator("#activeFilters").is_visible())
        page.locator("#query").fill("no-existe")
        page.locator("#query").press("Enter")
        self.assertTrue(page.locator("#empty").is_visible())
        self.assertEqual(page.locator("#grid .collection-case").count(), 0)
        page.locator("#advancedFiltersMenu > summary").click()
        page.locator("#clearFilters").click()
        self.assertNotIn("status=", page.url)
        self.assertNotIn("q=", page.url)
        self.assertEqual(page.locator("#grid .collection-case").count(), 30)

    def test_add_preserves_query_and_return_restores_filters_sort_and_count(self) -> None:
        self.open_collection()
        page = self.page
        page.locator('[data-filter="status"][data-value="watched"]').first.click()
        page.locator("#query").fill("prueba")
        page.locator("#query").press("Enter")
        page.locator("#sort").select_option("year-desc")
        page.locator("#catalogLoadMore").click()
        self.assertEqual(page.locator("#grid .collection-case").count(), 32)
        page.locator('#collectionModeTabs [data-mode="add"]').click()
        page.wait_for_function("!document.querySelector('#searchButton').disabled")
        self.assertEqual(page.locator("#query").input_value(), "prueba")
        self.assertIn("mode=add", page.url)
        self.assertIn("q=prueba", page.url)
        self.assertTrue(page.locator("#grid").is_hidden())
        self.assertTrue(page.locator(".collection-filter-toolbar").is_hidden())
        page.get_by_role("button", name="Volver a Colección", exact=True).click()
        page.wait_for_selector("#grid .collection-case")
        self.assertIn("status=watched", page.url)
        self.assertEqual(page.locator("#sort").input_value(), "year-desc")
        self.assertEqual(page.locator("#query").input_value(), "prueba")
        self.assertEqual(page.locator("#grid .collection-case").count(), 32)
        page.go_back()
        page.wait_for_function(
            "document.querySelector('#collectionView').dataset.searchMode === 'add'"
        )
        page.go_forward()
        page.wait_for_selector("#grid .collection-case")
        self.assertEqual(page.locator("#grid .collection-case").count(), 32)

    def test_cumulative_loading_survives_history_and_reload(self) -> None:
        self.open_collection()
        page = self.page
        page.locator("#query").fill("prueba")
        page.locator("#query").press("Enter")
        self.assertEqual(page.locator("#grid .collection-case").count(), 30)
        first = page.locator("#grid .collection-case").first.get_attribute("data-id")
        page.evaluate(
            "window.firstCollectionCase = document.querySelector('#grid').firstElementChild"
        )
        page.locator("#catalogLoadMore").click()
        self.assertEqual(page.locator("#grid .collection-case").count(), 60)
        self.assertTrue(
            page.evaluate(
                "window.firstCollectionCase === document.querySelector('#grid').firstElementChild"
            )
        )
        self.assertEqual(page.evaluate("document.activeElement.dataset.id"), "counter-30")
        self.assertEqual(
            page.locator("#grid .collection-case").first.get_attribute("data-id"), first
        )
        saved_scroll = page.evaluate("window.scrollY")
        page.reload()
        page.wait_for_function("document.querySelectorAll('#grid .collection-case').length === 60")
        page.wait_for_function("y => Math.abs(scrollY - y) < 3", arg=saved_scroll)
        page.locator("#query").fill("no-existe")
        page.locator("#query").press("Enter")
        page.go_back()
        page.wait_for_function("document.querySelectorAll('#grid .collection-case').length === 60")
        page.locator("#catalogLoadMore").click()
        self.assertEqual(page.locator("#grid .collection-case").count(), 65)
        self.assertTrue(page.locator("#catalogLoadMore").is_hidden())
        self.assertEqual(page.evaluate("document.activeElement.dataset.id"), "counter-60")

    def test_detail_back_and_external_results_have_reachable_return_points(self) -> None:
        self.open_collection()
        page = self.page
        page.locator("#catalogLoadMore").click()
        page.locator('#grid [data-id="counter-31"] .dvd-open-surface').click()
        page.wait_for_selector("#detailDrawer[open]")
        saved_scroll = page.evaluate("history.state.collection.scrollY")
        page.go_back()
        page.wait_for_selector("#detailDrawer[open]", state="hidden")
        page.wait_for_function("document.activeElement.dataset.id === 'counter-31'")
        self.assertEqual(page.locator("#grid .collection-case").count(), 60)
        self.assertAlmostEqual(page.evaluate("scrollY"), saved_scroll, delta=3)
        page.locator("#externalSource").check()
        page.locator("#query").fill("prueba")
        page.locator("#query").press("Enter")
        page.wait_for_function("!document.querySelector('#searchButton').disabled")
        page.locator("#externalResultsJump").click()
        self.assertEqual(page.evaluate("document.activeElement.id"), "externalSearchSection")
        page.locator("#clearManualSearch").click()
        self.assertTrue(page.locator("#externalResultsJump").is_hidden())

    def test_responsive_posters_labels_focus_and_empty_catalog(self) -> None:
        self.open_collection(count=15)
        page = self.page
        page.emulate_media(reduced_motion="reduce")
        output = Path("docs/design/collection-counter-v1")
        for width in (1920, 1440, 1280, 860, 640, 390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            page.evaluate("document.fonts.ready")
            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"))
            if width <= 640:
                query_box = page.locator("#query").bounding_box()
                button_box = page.locator("#searchButton").bounding_box()
                self.assertGreaterEqual(button_box["y"], query_box["y"] + query_box["height"])
            geometry = page.locator("#grid").evaluate("""grid => ({
                columns: getComputedStyle(grid).gridTemplateColumns.split(' ').length,
                cards: [...grid.children].map(card => {
                    const poster = card.querySelector('.collection-poster').getBoundingClientRect();
                    const labelEl = card.querySelector('.collection-case-label');
                    const label = labelEl.getBoundingClientRect();
                    return {width: poster.width, height: poster.height,
                        gap: label.top - poster.bottom,
                        overflow: labelEl.scrollWidth > label.width + 2};
                })
            })""")
            self.assertEqual(geometry["columns"], 5 if width >= 1280 else 3 if width == 860 else 2)
            for card in geometry["cards"]:
                self.assertGreaterEqual(card["gap"], -1)
                self.assertAlmostEqual(card["height"] / card["width"], 1.5, delta=0.03)
                self.assertFalse(card["overflow"])
            if width >= 1280:
                self.assertGreater(geometry["cards"][0]["width"], 185)
            if os.environ.get("COLLECTION_EVIDENCE") and width in (1920, 1440, 1280, 390, 320):
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / f"actual-{width}.png"), full_page=True)
                page.screenshot(path=str(output / f"viewport-{width}.png"))
        page.locator("#grid .dvd-open-surface").first.focus()
        self.assertEqual(
            page.locator("#grid .dvd-open-surface").first.evaluate(
                "el => getComputedStyle(el).outlineStyle"
            ),
            "solid",
        )
        self.assertTrue(page.locator(".collection-poster .dvd-placeholder").nth(1).is_visible())
        self.assertTrue(page.locator(".collection-poster img.is-loaded").first.is_visible())

    def test_empty_catalog_still_opens_collection_and_add(self) -> None:
        self.open_collection(count=0)
        page = self.page
        self.assertTrue(page.locator("#query").is_visible())
        self.assertIn("videoteca todavía está vacía", page.locator("#empty").inner_text())
        page.locator('#collectionModeTabs [data-mode="add"]').click()
        self.assertEqual(page.locator("#catalogTitle").text_content(), "Agregar obra")
        page.get_by_role("button", name="Volver a Colección", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#collectionView').dataset.searchMode === 'browse'"
        )
        self.assertTrue(page.locator("#empty").is_visible())


if __name__ == "__main__":
    unittest.main()
