"""U8: the terminal "Al azar" VHS at the end of the Home library."""

from __future__ import annotations

import unittest
from typing import Any

from tests.browser import test_ui_browser as fixture

UNAVAILABLE = {
    "id": "lost-tape",
    "title": "Cinta perdida",
    "year": "1983",
    "kind": "pelicula",
    "en_catalogo": False,
    "status": "to_watch",
}


class HomeRandomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture.BrowserInterfaceTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        fixture.BrowserInterfaceTests.tearDownClass.__func__(cls)

    setUp = fixture.BrowserInterfaceTests.setUp
    tearDown = fixture.BrowserInterfaceTests.tearDown

    def open_home(self, *, only_unavailable: bool = False) -> None:
        """Serve one editorial shelf; optionally make the catalogue a single
        unavailable work, so every draw has one known result."""

        def shape(route: Any) -> None:
            response = route.fetch()
            payload = response.json()
            items = [dict(UNAVAILABLE)] if only_unavailable else payload["items"]
            payload["items"] = items
            def entries(prefix: str) -> list[dict[str, Any]]:
                return [
                    {"key": f"{prefix}-{item['id']}", "origin": {"kind": "catalog"},
                     "item": item, "reason": {"label": "Memoria"}}
                    for item in items
                ]

            payload["home"] = {
                **payload.get("home", {}),
                "featured": [] if only_unavailable else entries("daily"),
                "sections": [
                    {"id": "memory", "title": "Tu archivo pide memoria", "items": entries("memory")}
                ],
            }
            route.fulfill(response=response, json=payload)

        self.page.route("**/api/items?*", shape)
        self.page.goto(self.base_url)
        fixture.wait_for_app_ready(self.page)
        self.page.wait_for_selector(".home-random-tape")

    def set_only_available(self, value: bool) -> None:
        self.page.evaluate(
            """value => {
                const box = document.querySelector('#randomCatalogOnly');
                box.checked = value;
                box.dispatchEvent(new Event('change', {bubbles: true}));
            }""",
            value,
        )

    def spine_state(self) -> str:
        return self.page.locator(".home-random-tape").get_attribute("data-random-state") or ""

    def wait_for_result(self) -> None:
        self.page.wait_for_function(
            "!['busy', 'initial'].includes("
            "document.querySelector('.home-random-tape').dataset.randomState)"
        )

    def test_one_result_feeds_spine_console_poster_and_back_cover(self) -> None:
        self.open_home()
        page = self.page
        tape = page.locator(".home-random-tape")
        self.assertEqual(self.spine_state(), "initial")
        self.assertIn("Elegir una obra", tape.get_attribute("aria-label"))
        # Not an editorial section: the shelf count stays at the real shelves.
        self.assertEqual(page.locator("#homeSections").get_attribute("data-bay-count"), "1")
        source_before = page.locator("[data-playlist-source]").text_content()

        tape.click()
        self.assertEqual(self.spine_state(), "busy")
        self.assertEqual(tape.get_attribute("aria-busy"), "true")
        # Clicks while the label moves coalesce into the draw already chosen.
        tape.click()
        tape.click()
        self.wait_for_result()
        first_title = page.locator(".home-random-tape .vhs-spine-title").text_content()
        self.assertEqual(self.spine_state(), "available")
        self.assertEqual(page.locator(".spotlight-preview h3").text_content(), first_title)
        self.assertEqual(page.locator(".home-console-heading strong").text_content(), "Al azar")
        self.assertTrue(
            (page.locator(".home-consulted-poster").get_attribute("data-consulted-key") or "")
            .startswith("random:")
        )
        # The draw never opens the dossier and never reprograms the table.
        self.assertEqual(page.locator("dialog[open]").count(), 0)
        self.assertEqual(page.locator("[data-playlist-source]").text_content(), source_before)
        self.assertEqual(page.locator('[data-playlist-entry][aria-selected="true"]').count(), 0)
        self.assertEqual(
            page.locator("#homeSelectionAnnouncement").text_content(),
            f"Al azar: {first_title}, {'1995' if first_title == 'Heat' else '1988'}. Disponible.",
        )
        self.assertTrue(page.evaluate(
            "document.activeElement.classList.contains('home-random-tape')"
        ))

        # With two candidates the next draw never repeats the one on screen.
        tape.click()
        self.wait_for_result()
        second_title = page.locator(".home-random-tape .vhs-spine-title").text_content()
        self.assertNotEqual(second_title, first_title)
        self.assertEqual(page.locator(".spotlight-preview h3").text_content(), second_title)

        page.locator('.spotlight-preview [data-home-focus="consultation-view"]').click()
        page.wait_for_selector("#detailDrawer[open]")
        self.assertEqual(
            page.locator("#detailDrawerTitle").text_content(), f"Contratapa VHS // {second_title}"
        )

    def test_unavailable_result_scope_change_and_empty_pool(self) -> None:
        self.open_home(only_unavailable=True)
        page = self.page
        # "Solo disponibles" is on by default and nothing is available.
        self.assertEqual(self.spine_state(), "empty")
        self.assertEqual(page.locator(".home-random-note").get_by_text("Incluir no disponibles").count(), 1)

        page.locator(".home-random-note").get_by_text("Incluir no disponibles").click()
        self.assertEqual(self.spine_state(), "initial")
        page.emulate_media(reduced_motion="reduce")
        page.locator(".home-random-tape").click()
        # Reduced motion shows the result directly.
        self.assertEqual(self.spine_state(), "unavailable")
        tape = page.locator(".home-random-tape")
        self.assertIn("no disponible", tape.get_attribute("aria-label"))
        self.assertEqual(tape.locator(".home-random-mark").get_attribute("aria-hidden"), "true")
        self.assertEqual(tape.locator(".vhs-spine-title").text_content(), "Cinta perdida")
        self.assertEqual(page.locator(".spotlight-preview h3").text_content(), "Cinta perdida")

        # Narrowing the preference keeps the consultation and explains the scope.
        self.set_only_available(True)
        self.assertEqual(self.spine_state(), "out-of-scope")
        self.assertEqual(page.locator(".spotlight-preview h3").text_content(), "Cinta perdida")
        page.locator(".home-random-note").get_by_text("Elegir otra").click()
        self.assertEqual(self.spine_state(), "out-of-scope")
        self.assertIn(
            "No hay obras disponibles", page.locator("#homeSelectionAnnouncement").text_content()
        )

    def test_header_command_on_home_draws_without_opening_the_dossier(self) -> None:
        self.open_home()
        page = self.page
        page.emulate_media(reduced_motion="reduce")
        fixture.click_desktop_menu_action(page, "random")
        self.assertEqual(self.spine_state(), "available")
        self.assertEqual(page.locator("dialog[open]").count(), 0)
        spine_title = page.locator(".home-random-tape .vhs-spine-title").text_content()
        self.assertEqual(page.locator(".spotlight-preview h3").text_content(), spine_title)
        # The terminal bay is brought into the shelf's view.
        self.assertTrue(page.locator("[data-home-random]").evaluate(
            """bay => {
                const rail = document.querySelector('#homeSections').getBoundingClientRect();
                const box = bay.getBoundingClientRect();
                return box.left >= rail.left - 1 && box.right <= rail.right + 1;
            }"""
        ))

        # Outside Home the command keeps opening a random dossier.
        page.locator("#catalogButton").click()
        page.wait_for_selector("#collectionView:not([hidden])")
        fixture.click_desktop_menu_action(page, "random")
        page.wait_for_selector("#detailDrawer[open]")

    def test_collection_filters_without_results_leave_nothing_to_draw(self) -> None:
        self.open_home()
        page = self.page
        page.locator("#catalogButton").click()
        page.wait_for_selector("#collectionView:not([hidden])")
        counts = page.evaluate(
            """async () => {
                const grid = await import('/static/js/surfaces/catalog-grid.js');
                const before = grid.randomCandidates().length;
                grid.applyCollectionFilterDescriptor({year_from: '2150'});
                grid.render();
                return [before, grid.randomCandidates().length];
            }"""
        )
        # Before U8.1 an empty filter silently fell back to the whole catalogue.
        self.assertGreater(counts[0], 0)
        self.assertEqual(counts[1], 0)
        self.assertTrue(page.locator("#randomButton").is_disabled())


if __name__ == "__main__":
    unittest.main()
