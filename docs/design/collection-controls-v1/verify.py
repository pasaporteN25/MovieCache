"""Render the disposable design options and the real Home with synthetic fixtures."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402


def verify() -> None:
    BrowserInterfaceTests.setUpClass()
    case = BrowserInterfaceTests(
        methodName="test_home_marquee_shows_the_available_billboard_label_and_decorative_ambience"
    )
    case.setUp()
    output = Path(__file__).parent
    report = {"home": [], "options": []}
    try:
        page = case.page
        case.test_home_marquee_shows_the_available_billboard_label_and_decorative_ambience()
        page.evaluate("document.fonts.ready")
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 900})
            page.screenshot(
                path=str(output / f"home-{width}.png"), full_page=True, animations="disabled"
            )
            metrics = page.locator(".spotlight-selector-heading").evaluate_all(
                """nodes => nodes.map(node => {
                    const box = node.getBoundingClientRect();
                    const frame = node.closest('.spotlight-selector').getBoundingClientRect();
                    const text = node.querySelector('span');
                    const range = document.createRange();
                    range.selectNodeContents(text);
                    const ink = range.getBoundingClientRect();
                    return {text: text.textContent.trim(),
                        centerDelta: Math.abs(box.x + box.width/2 - frame.x - frame.width/2),
                        textCenterDelta: Math.abs(ink.x + ink.width/2 - box.x - box.width/2),
                        textFits: ink.width <= box.width,
                        verticalCenterDelta: Math.abs(ink.y + ink.height/2 - box.y - box.height/2)};
                })"""
            )
            assert metrics and all(row["textFits"] for row in metrics), metrics
            assert all(row["centerDelta"] < 1 for row in metrics), metrics
            assert all(row["textCenterDelta"] < 1 for row in metrics), metrics
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            report["home"].append({"width": width, "labels": metrics})

        page.goto("http://127.0.0.1:8765/docs/design/collection-controls-v1/index.html")
        for layout in ("compact", "visible", "sidebar"):
            page.locator(f'[data-layout="{layout}"]').click()
            for width in (1440, 390, 320):
                page.set_viewport_size({"width": width, "height": 1000})
                page.evaluate("document.fonts.ready")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(
                    path=str(output / f"{layout}-{width}.png"),
                    full_page=True,
                    animations="disabled",
                )
                report["options"].append({"layout": layout, "width": width, "overflow": False})
            page.locator("#broaden").click()
            assert page.locator("#example").is_visible()
            assert "Ninguna obra se agregó" in page.locator("#feedback").inner_text()
            page.locator("#query").fill("pretsel")
        (output / "verification.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False))
    finally:
        case.tearDown()
        BrowserInterfaceTests.tearDownClass()


if __name__ == "__main__":
    verify()
