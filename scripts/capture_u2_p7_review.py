"""Capture the accepted U2-P.7 layout choices with an isolated fixture."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.capture_u2_p6_review import fixture  # noqa: E402
from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402


def main() -> None:
    output = ROOT / "docs/design/u2-p7-evidence"
    output.mkdir(exist_ok=True)
    image_assets = {
        "p6-backdrop.png": ROOT
        / "src/movie_inbox/web/static/img/night-videotheque-wall-v1.png",
        "p6-page.png": ROOT / "src/movie_inbox/web/static/img/night-cinema-ambient-v1.png",
    }
    report = []
    BrowserInterfaceTests.setUpClass()
    try:
        for width, height in ((1280, 720), (1440, 900), (1920, 1080), (390, 844), (320, 740)):
            page = BrowserInterfaceTests.context.new_page()
            try:
                page.set_viewport_size({"width": width, "height": height})
                page.emulate_media(reduced_motion="reduce")
                page.route("**/api/items?*", fixture)

                def images(route) -> None:
                    name = (
                        "p6-backdrop.png"
                        if "p6-backdrop.png" in route.request.url
                        else "p6-page.png"
                    )
                    route.fulfill(path=str(image_assets[name]), content_type="image/png")

                page.route("**/image-cache?*fixture.invalid*", images)
                BrowserInterfaceTests._open_and_wait_for_catalog(page)
                page.locator(".home-furniture-frame img").first.wait_for(state="visible")
                page.evaluate("document.fonts.ready")
                metrics = page.locator("#homeShelfPreview").evaluate(
                    """element => {
                        const display = element.querySelector('.home-furniture-display');
                        const facts = element.querySelector('.home-shelf-preview-facts dd');
                        return {
                            viewport: innerWidth,
                            parentId: element.parentElement?.id || '',
                            parentSection: element.parentElement?.dataset.homeSection || '',
                            displayHeight: display?.getBoundingClientRect().height || 0,
                            factsFontSize: facts ? parseFloat(getComputedStyle(facts).fontSize) : 0,
                            factsWhiteSpace: facts ? getComputedStyle(facts).whiteSpace : '',
                            pageOverflow: document.documentElement.scrollWidth - innerWidth,
                        };
                    }"""
                )
                report.append(metrics)
                assert metrics["pageOverflow"] <= 1

                if width >= 861:
                    assert metrics["parentId"] == "homeFurniture"
                    assert metrics["displayHeight"] >= 130
                    page.locator("#homeFurniture").evaluate(
                        """element => {
                            const wrapper = document.createElement('div');
                            wrapper.id = 'p7CaptureFrame';
                            wrapper.style.height = '640px';
                            wrapper.style.overflow = 'hidden';
                            wrapper.style.position = 'relative';
                            wrapper.style.width = '100%';
                            element.before(wrapper);
                            wrapper.append(element);
                        }"""
                    )
                    page.locator("#p7CaptureFrame").screenshot(
                        path=str(output / f"console-{width}.png")
                    )
                    if width == 1440:
                        page.locator("#homeView").screenshot(
                            path=str(output / "home-1440.png")
                        )
                else:
                    assert metrics["parentSection"] == "p6-bay-0"
                    assert metrics["factsFontSize"] >= 12
                    assert metrics["factsWhiteSpace"] == "normal"
                    page.locator('[data-home-section="p6-bay-0"]').evaluate(
                        """element => {
                            const header = document.querySelector('.app-header');
                            const offset = (header?.getBoundingClientRect().height || 0) + 12;
                            window.scrollTo({
                                top: element.getBoundingClientRect().top + scrollY - offset,
                                behavior: 'instant',
                            });
                        }"""
                    )
                    page.screenshot(path=str(output / f"active-category-{width}.png"))
                    page.locator("#homeShelfPreview").evaluate(
                        """element => {
                            const header = document.querySelector('.app-header');
                            const offset = (header?.getBoundingClientRect().height || 0) + 12;
                            window.scrollTo({
                                top: element.getBoundingClientRect().top + scrollY - offset,
                                behavior: 'instant',
                            });
                        }"""
                    )
                    page.screenshot(path=str(output / f"preview-{width}.png"))
            finally:
                page.close()
    finally:
        BrowserInterfaceTests.tearDownClass()
    (output / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
