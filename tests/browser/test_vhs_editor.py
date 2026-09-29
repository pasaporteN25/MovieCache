"""VHS consultation and persistent editor drafts on disposable catalogues."""

import os
import unittest
from pathlib import Path
from typing import Any, cast

from tests.browser import test_collection_counter as collection_fixture
from tests.browser import test_ui_browser as fixture


class VhsEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.BrowserInterfaceTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        fixture.BrowserInterfaceTests.tearDownClass.__func__(cls)

    setUp = fixture.BrowserInterfaceTests.setUp
    tearDown = fixture.BrowserInterfaceTests.tearDown

    def open_case(self):
        self.page.goto(self.base_url + "?view=catalog")
        fixture.wait_for_app_ready(self.page)
        self.page.locator('#grid [data-id="heat"] .dvd-open-surface').click()
        self.page.wait_for_selector('[data-detail-mode="back-cover"] .vhs-edit-sticker')

    def test_drafts_survive_sections_save_and_guard_return(self):
        page = self.page
        self.open_case()
        page.locator(".vhs-edit-sticker").click()
        page.locator("[data-personal-review]").fill("Recuerdo de prueba VHS")
        page.locator('[data-section="data"]').click()
        page.locator('[data-metadata-field="directors"]').fill("Dirección de prueba")
        page.locator('[data-section="images"]').click()
        page.locator('[data-metadata-field="backdrop_image"]').fill(
            "https://example.test/frame.jpg"
        )
        page.locator('[data-section="personal"]').click()
        self.assertEqual(
            page.locator("[data-personal-review]").input_value(), "Recuerdo de prueba VHS"
        )
        page.locator("[data-editor-save]").click()
        page.wait_for_function(
            "document.querySelector('[data-editor-feedback]').textContent === 'Cambios guardados'"
        )
        headers = {"X-Movie-Inbox-Token": self.config.api_token}
        items = page.request.get(self.base_url + "/api/items", headers=headers).json()["items"]
        saved = next(item for item in items if item["id"] == "heat")
        self.assertEqual(saved["review"], "Recuerdo de prueba VHS")
        self.assertEqual(saved["directors"], ["Dirección de prueba"])
        self.assertEqual(saved["backdrop_image"], "https://example.test/frame.jpg")
        page.locator("[data-personal-review]").fill("Borrador pendiente")
        page.get_by_role("button", name="Volver a la contratapa").click()
        page.wait_for_selector("#unsavedDetailDialog[open]")
        page.locator("#keepEditingDetail").click()
        self.assertEqual(page.locator("[data-personal-review]").input_value(), "Borrador pendiente")
        page.get_by_role("button", name="Volver a la contratapa").click()
        page.locator("#discardDetailChanges").click()
        page.wait_for_selector('[data-detail-mode="back-cover"]')
        page.wait_for_function("document.activeElement.classList.contains('vhs-edit-sticker')")
        page.keyboard.press("Escape")
        page.wait_for_function("document.activeElement.dataset.id === 'heat'")

    def test_responsive_editor_and_case_evidence(self):
        page = self.page
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.emulate_media(reduced_motion="reduce")
        page.goto(self.base_url + "?view=catalog")
        fixture.wait_for_app_ready(page)
        page.evaluate("document.fonts.ready")
        output = Path("docs/design/vhs-case-v1")
        if os.environ.get("VHS_EVIDENCE"):
            page.screenshot(path=str(output / "collection-desktop.png"))
        card = page.locator('#grid article[data-id="heat"]')
        before = card.bounding_box()
        card.locator(".dvd-open-surface").evaluate("el => el.focus({preventScroll: true})")
        self.assertEqual(card.bounding_box(), before)
        if os.environ.get("VHS_EVIDENCE"):
            page.screenshot(path=str(output / "case-focus.png"))
        card.locator(".dvd-open-surface").click()
        page.wait_for_selector(".vhs-edit-sticker")
        if os.environ.get("VHS_EVIDENCE"):
            page.screenshot(path=str(output / "back-cover-desktop.png"))
        page.locator(".vhs-edit-sticker").click()
        for width in (1440, 1000, 390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            page.evaluate("document.fonts.ready")
            for section in ("personal", "data", "images", "availability", "advanced"):
                page.locator(f'[data-section="{section}"]').click()
                self.assertFalse(
                    page.locator(".vhs-editor-content").evaluate(
                        "el => el.scrollWidth > el.clientWidth + 1"
                    )
                )
                self.assertTrue(page.locator("[data-editor-save]").is_visible())
            page.locator('[data-section="personal"]').click()
            if os.environ.get("VHS_EVIDENCE"):
                page.screenshot(path=str(output / f"editor-{width}.png"))
        self.assertEqual(errors, [])

    def test_slow_save_blocks_switching_works_and_keeps_metadata_target(self):
        page = self.page
        self.open_case()
        page.locator(".vhs-edit-sticker").click()
        pending = []
        metadata = []
        page.route("**/api/personal", lambda route: pending.append(route))

        def save_metadata(route: Any) -> None:
            metadata.append(route.request.post_data_json)
            route.fulfill(json={"ok": True})

        page.route("**/api/metadata", save_metadata)
        page.locator("[data-personal-review]").fill("Guardado lento")
        page.locator('[data-section="data"]').click()
        page.locator('[data-metadata-field="directors"]').fill("Dirección lenta")
        with page.expect_request("**/api/personal"):
            page.locator("[data-editor-save]").click()
        self.assertTrue(page.locator('[data-click="detail-next"]').is_disabled())
        self.assertTrue(page.locator("#closeDetail").is_disabled())
        page.evaluate("""async () => {
            const detail = await import('/static/js/core/detail.js');
            detail.navigateDetail(1);
            detail.openDetail('akira');
            detail.closeDetail();
        }""")
        self.assertEqual(page.locator(".vhs-editor-heading h2").inner_text(), "Heat")
        self.assertFalse(page.locator("#unsavedDetailDialog").is_visible())
        pending[0].fulfill(json={"ok": True})
        page.wait_for_function(
            "document.querySelector('[data-editor-feedback]').textContent === 'Cambios guardados'"
        )
        self.assertEqual(metadata[0]["id"], "heat")
        self.assertFalse(page.locator("#closeDetail").is_disabled())

    def test_complete_artwork_and_missing_cover_in_pointer_and_keyboard_states(self):
        page = self.page
        page.set_viewport_size({"width": 1440, "height": 1100})
        page.emulate_media(reduced_motion="reduce")
        collection_fixture.CollectionCounterTests.open_collection(cast(Any, self), count=15)
        page.wait_for_selector(".collection-case-front img.is-loaded")
        page.evaluate("document.fonts.ready")
        card = page.locator('#grid article[data-id="counter-0"]')
        card.scroll_into_view_if_needed()
        photo = card.locator("img")
        self.assertEqual(photo.evaluate("el => getComputedStyle(el).objectFit"), "contain")
        self.assertEqual(
            card.locator(".collection-zoom-title").evaluate("el => getComputedStyle(el).opacity"),
            "0",
        )
        page.keyboard.press("Tab")
        card.locator(".dvd-open-surface").focus()
        card.hover()
        self.assertEqual(
            card.locator(".collection-zoom-title").evaluate("el => getComputedStyle(el).opacity"),
            "1",
        )
        self.assertEqual(
            card.locator(".collection-case-label").evaluate("el => getComputedStyle(el).opacity"),
            "0",
        )
        if os.environ.get("VHS_EVIDENCE"):
            card.screenshot(path="docs/design/vhs-case-v1/case-artwork-focus.png")
            page.mouse.move(0, 0)
            card.locator(".dvd-open-surface").blur()
            page.locator("#grid").screenshot(path="docs/design/vhs-case-v1/cases-with-artwork.png")
        page.mouse.move(0, 0)
        card.locator(".dvd-open-surface").blur()
        self.assertEqual(
            card.locator(".collection-case-label").evaluate("el => getComputedStyle(el).opacity"),
            "1",
        )
        broken = page.locator('#grid article[data-id="counter-1"]')
        self.assertTrue(broken.locator(".dvd-placeholder").is_visible())
        broken.locator(".dvd-open-surface").focus()
        self.assertEqual(
            broken.locator(".collection-zoom-title").evaluate("el => getComputedStyle(el).opacity"),
            "0",
        )
        # Packaged assets have the right MIME type and arrive under the existing CSP.
        for asset, mime in [
            ("img/brand/vhs-blank-512.webp", "image/webp"),
            ("fonts/permanent-marker-regular.ttf", "font/ttf"),
        ]:
            response = page.request.get(self.base_url + "/static/" + asset)
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["content-type"], mime)
        self.assertTrue(page.evaluate("document.fonts.check('20px \"VHS Marker\"')"))


if __name__ == "__main__":
    unittest.main()
