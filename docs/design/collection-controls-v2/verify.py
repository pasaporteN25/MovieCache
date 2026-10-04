"""Verify the illustrative filter panel without loading any personal catalog."""

from pathlib import Path

from playwright.sync_api import sync_playwright


def verify():
    output = Path(__file__).parent
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto((output / "index.html").as_uri())
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 960})
            page.evaluate("document.fonts.ready")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"collection-{width}.png"), full_page=True)
            before = page.locator(".collection").bounding_box()
            page.locator("#open").click()
            page.get_by_role("button", name="Por ver", exact=True).click()
            assert page.locator("#rows li").count() == 6
            assert page.locator("#apply").inner_text() == "Mostrar 4 obras"
            assert page.locator(".collection").bounding_box() == before
            page.screenshot(path=str(output / f"panel-{width}.png"))
            page.locator("#cancel").click()
            assert page.locator("#rows li").count() == 6
            page.locator("#open").click()
            assert page.get_by_role("button", name="Por ver", exact=True).get_attribute(
                "aria-pressed"
            ) == "false"
            page.get_by_role("button", name="Por ver", exact=True).click()
            page.locator("#apply").click()
            assert page.locator("#rows li").count() == 4
            page.screenshot(path=str(output / f"applied-{width}.png"), full_page=True)
            page.locator("#open").click()
            page.locator("#reset").click()
            assert page.locator("#rows li").count() == 4
            page.keyboard.press("Escape")
            assert page.locator("#rows li").count() == 4
            page.get_by_role("button", name="Quitar filtro Por ver").click()
            assert page.locator("#rows li").count() == 6
        browser.close()
    print("Desktop/mobile: no overflow or collection reflow; draft/apply/cancel/reset/Escape verified.")


if __name__ == "__main__":
    verify()
