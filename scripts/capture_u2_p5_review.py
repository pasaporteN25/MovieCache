"""Capture the visible P.5 cabinet crop with an isolated catalogue fixture."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.capture_u2_p3_review import TITLES  # noqa: E402
from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402


def fixture(route) -> None:
    response = route.fetch()
    payload = response.json()
    base = payload["items"][0]
    entries = [
        {
            "key": f"p5-{index}",
            "origin": {"kind": "catalog"},
            "item": {
                **base,
                "id": f"p5-{index}",
                "title": title,
                "year": year,
                "description": "",
                "wikipedia_extract": "",
                "directors": [],
                "genres": [],
            },
        }
        for index, (title, year) in enumerate(TITLES)
    ]
    home = payload.get("home") or {}
    home["featured"] = entries[:6]
    home["sections"] = [
        {
            "id": f"p5-bay-{index}",
            "title": label,
            "items": entries[index * 6 : (index + 1) * 6],
        }
        for index, label in enumerate(
            (
                "Disponible esta noche",
                "Tu archivo pide memoria",
                "Una ruta por cine de suspenso",
            )
        )
    ]
    payload["home"] = home
    route.fulfill(response=response, json=payload)


def main() -> None:
    output = ROOT / "docs/design/u2-p5-evidence"
    output.mkdir(exist_ok=True)
    report = []
    BrowserInterfaceTests.setUpClass()
    try:
        for width, height in ((1280, 720), (1440, 900), (1920, 1080)):
            page = BrowserInterfaceTests.context.new_page()
            try:
                page.set_viewport_size({"width": width, "height": height})
                page.emulate_media(reduced_motion="reduce")
                page.route("**/api/items?*", fixture)
                BrowserInterfaceTests._open_and_wait_for_catalog(page)
                page.locator(".vhs-spine-title").first.wait_for()
                page.evaluate("document.fonts.ready")
                geometry = page.locator("#homeFurniture").evaluate(
                    """element => {
                        const cabinet = element.getBoundingClientRect();
                        const home = element.closest('#homeView').getBoundingClientRect();
                        const shelfNode = element.querySelector('#homeSections');
                        const shelf = shelfNode.getBoundingClientRect();
                        return {
                            cabinetWidth: cabinet.width,
                            visibleWidth: home.width,
                            overrun: cabinet.right - home.right,
                            visibleFraction: (home.right - cabinet.left) / cabinet.width,
                            pageOverflow: document.documentElement.scrollWidth - innerWidth,
                            shelfRightInset: home.right - shelf.right,
                        };
                    }"""
                )
                report.append({"viewport": width, **geometry})
                assert geometry["overrun"] >= 71
                assert geometry["visibleFraction"] <= 0.95
                assert geometry["pageOverflow"] <= 1
                assert geometry["shelfRightInset"] >= 40

                page.locator("#homeFurniture").evaluate(
                    """element => {
                        const wrapper = document.createElement('div');
                        wrapper.id = 'p5CaptureFrame';
                        wrapper.style.height = '640px';
                        wrapper.style.overflow = 'hidden';
                        wrapper.style.position = 'relative';
                        wrapper.style.width = '100%';
                        element.before(wrapper);
                        wrapper.append(element);
                    }"""
                )
                frame = page.locator("#p5CaptureFrame")
                frame.screenshot(path=str(output / f"visible-{width}.png"))

                shelf = page.locator("#homeSections")
                shelf.evaluate("element => { element.scrollLeft = element.scrollWidth; }")
                frame.screenshot(path=str(output / f"end-{width}.png"))
            finally:
                page.close()
    finally:
        BrowserInterfaceTests.tearDownClass()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
