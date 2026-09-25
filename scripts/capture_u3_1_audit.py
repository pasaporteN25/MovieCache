"""Capture the current Collection surface for the U3.1 architecture audit."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402


def capture_metrics(page, state: str, width: int) -> dict[str, object]:
    return page.locator("#collectionView").evaluate(
        """(element, args) => ({
            state: args.state,
            viewport: args.width,
            pageOverflow: document.documentElement.scrollWidth - innerWidth,
            consoleHeight:
              element.querySelector('.search-console')?.getBoundingClientRect().height || 0,
            gridTop: element.querySelector('#grid')?.getBoundingClientRect().top || 0,
            activeMode: element.dataset.searchMode || 'browse',
            visibleQuickGroups: [...element.querySelectorAll('.quick-filter-group')]
              .filter(node => getComputedStyle(node).display !== 'none').length,
            visibleSearchSections: [...element.querySelectorAll('.search-section')]
              .filter(node => getComputedStyle(node).display !== 'none').length,
        })""",
        {"state": state, "width": width},
    )


def main() -> None:
    output = ROOT / "docs/design/u3-1-evidence"
    output.mkdir(exist_ok=True)
    report: list[dict[str, object]] = []
    BrowserInterfaceTests.setUpClass()
    try:
        for width, height in ((1440, 900), (390, 844)):
            page = BrowserInterfaceTests.context.new_page()
            try:
                page.set_viewport_size({"width": width, "height": height})
                page.emulate_media(reduced_motion="reduce")
                BrowserInterfaceTests._open_and_wait_for_catalog(page)
                page.locator("#catalogButton").click()
                page.wait_for_selector("#collectionView:not([hidden])")
                page.evaluate("document.fonts.ready")
                report.append(capture_metrics(page, "browse", width))
                page.screenshot(path=str(output / f"browse-{width}.png"), full_page=True)

                page.locator("#advancedFiltersMenu").evaluate("element => { element.open = true; }")
                report.append(capture_metrics(page, "filters-open", width))
                page.screenshot(path=str(output / f"filters-{width}.png"), full_page=True)
                page.locator("#advancedFiltersMenu").evaluate(
                    "element => { element.open = false; }"
                )

                page.locator("#query").fill("Heat")
                page.locator("#searchButton").click()
                page.wait_for_function(
                    "document.querySelector('#catalogSummary').textContent.includes('Heat')"
                )
                page.wait_for_function(
                    "document.querySelector('#searchButton').textContent === 'Buscar'"
                )
                report.append(capture_metrics(page, "local-search", width))
                page.screenshot(path=str(output / f"search-{width}.png"), full_page=True)

                page.locator("#query").fill("zzzzzz")
                page.locator("#searchButton").click()
                page.wait_for_function(
                    "document.querySelector('#empty').textContent.includes('zzzzzz')"
                )
                page.wait_for_function(
                    "document.querySelector('#searchButton').textContent === 'Buscar'"
                )
                report.append(capture_metrics(page, "empty-search", width))
                page.screenshot(path=str(output / f"empty-{width}.png"), full_page=True)
            finally:
                page.close()
    finally:
        BrowserInterfaceTests.tearDownClass()
    (output / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
