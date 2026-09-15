"""Capture U2-P review evidence using the isolated browser-test catalogue.

Run from the repository root: .venv/Scripts/python.exe scripts/capture_u2_p_review.py
Does not read or modify the user's catalogue. Requires the browser-test dependencies.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/design/u2-p-evidence")
    output = parser.parse_args().output_dir
    output.mkdir(exist_ok=True)
    BrowserInterfaceTests.setUpClass()
    try:
        page = BrowserInterfaceTests.context.new_page()
        featured_entries = []

        def featured_fixture(route) -> None:
            response = route.fetch()
            payload = response.json()
            home = payload.get("home") or {}
            home["featured"] = [
                {"key": f"review-{index}", "item": item, "origin": {"kind": "catalog"}}
                for index, item in enumerate(payload.get("items") or [])
            ]
            featured_entries[:] = home["featured"]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", featured_fixture)
        BrowserInterfaceTests._open_and_wait_for_catalog(page)
        page.wait_for_selector(".spotlight-selector")

        def date_fixture(route) -> None:
            response = route.fetch()
            payload = response.json()
            payload["featured"] = featured_entries
            route.fulfill(response=response, json=payload)

        page.route("**/api/home?*", date_fixture)
        for width, height in ((1280, 720), (1440, 900), (1920, 1080), (390, 844), (320, 740)):
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(output / f"home-{width}x{height}.png"))
            assert page.locator(".spotlight-selector-option").count() == 0
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            if width > 860:
                page.locator(".spotlight-selector").screenshot(
                    path=str(output / f"marquee-{width}.png")
                )
                page.locator(
                    '.spotlight-date-control-desktop [data-click="home-date-yesterday"]'
                ).click()
                page.wait_for_function(
                    "document.querySelector('.spotlight-selector-heading span')"
                    "?.textContent.trim() === 'Ayer'"
                )
                page.locator(".spotlight-selector").screenshot(
                    path=str(output / f"marquee-ayer-{width}.png")
                )
                page.locator(
                    '.spotlight-date-control-desktop [data-click="home-date-today"]'
                ).click()
                page.wait_for_function(
                    "document.querySelector('.spotlight-selector-heading span')"
                    "?.textContent.trim() === 'Hoy'"
                )
        page.set_viewport_size({"width": 1440, "height": 1200})
        page.goto((ROOT / "docs/design/u2-p-font-comparison.html").as_uri())
        page.evaluate("document.fonts.ready")
        page.screenshot(path=str(output / "font-comparison.png"), full_page=True)
        session = page.context.new_cdp_session(page)
        session.send("DOM.enable")
        session.send("CSS.enable")
        root = session.send("DOM.getDocument")["root"]["nodeId"]
        for selector, expected in (
            ("#glyphs-oswald", "Oswald"),
            ("#glyphs-barlow", "Barlow Condensed"),
            ("#mono-oswald", "IBM Plex Mono"),
        ):
            node = session.send("DOM.querySelector", {"nodeId": root, "selector": selector})
            fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
            print(selector, fonts)
            assert all(font["isCustomFont"] for font in fonts["fonts"]), fonts
            assert any(expected in font["familyName"] for font in fonts["fonts"]), fonts
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
        page.close()
    finally:
        BrowserInterfaceTests.tearDownClass()


if __name__ == "__main__":
    main()
