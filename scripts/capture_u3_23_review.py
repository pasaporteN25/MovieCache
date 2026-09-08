"""Capture the implemented U3.2/U3.3 Collection modes for visual review."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402


def metrics(page, mode: str, width: int) -> dict[str, object]:
    return page.locator("#collectionView").evaluate(
        """(element, args) => ({
            mode: args.mode,
            viewport: args.width,
            pageOverflow: Math.max(0, document.documentElement.scrollWidth - innerWidth),
            headerHeight:
              element.querySelector('.collection-task-header')?.getBoundingClientRect().height || 0,
            consoleHeight:
              element.querySelector('.search-console')?.getBoundingClientRect().height || 0,
            gridTop: element.querySelector('#grid')?.getBoundingClientRect().top || 0,
            taskTabsVisible: [...element.querySelectorAll('#collectionModeTabs button')]
              .filter(node => getComputedStyle(node).display !== 'none').length,
            quickGroupsVisible: [...element.querySelectorAll('.quick-filter-group')]
              .filter(node => getComputedStyle(node).display !== 'none').length,
        })""",
        {"mode": mode, "width": width},
    )


def main() -> None:
    output = ROOT / "docs/design/u3-23-evidence"
    output.mkdir(exist_ok=True)
    report: list[dict[str, object]] = []
    BrowserInterfaceTests.setUpClass()
    try:
        for width, height in ((1440, 900), (390, 844), (320, 740)):
            page = BrowserInterfaceTests.context.new_page()
            try:
                page.set_viewport_size({"width": width, "height": height})
                page.emulate_media(reduced_motion="reduce")
                BrowserInterfaceTests._open_and_wait_for_catalog(page)
                page.locator("#catalogButton").click()
                page.wait_for_selector("#collectionView:not([hidden])")
                page.evaluate("document.fonts.ready")

                report.append(metrics(page, "browse", width))
                page.screenshot(path=str(output / f"browse-{width}.png"), full_page=True)

                page.locator('#collectionModeTabs [data-mode="search"]').click()
                page.locator("#query").fill("Heat")
                page.locator("#searchButton").click()
                page.wait_for_function(
                    "document.querySelector('#catalogSummary').textContent.includes('Heat')"
                )
                report.append(metrics(page, "search", width))
                page.screenshot(path=str(output / f"search-{width}.png"), full_page=True)

                page.locator('#collectionModeTabs [data-mode="add"]').click()
                report.append(metrics(page, "add", width))
                page.screenshot(path=str(output / f"add-{width}.png"), full_page=True)
            finally:
                page.close()
    finally:
        BrowserInterfaceTests.tearDownClass()
    (output / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
