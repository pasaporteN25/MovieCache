"""Capture the P.6 console with complete and missing-image catalogue fixtures."""

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
    entries = []
    for index, (title, year) in enumerate(TITLES):
        item = {
            **base,
            "id": f"p6-{index}",
            "title": title,
            "year": year,
            "description": (
                "Una archivista sigue una señal nocturna que conecta una sala olvidada "
                "con las películas que todavía esperan ser vistas."
            ),
            "directors": ["Alejo Figueroa"],
            "writers": ["Alejo Figueroa", "Inés Vidal"],
            "cast": ["Mauro Beltrán", "Sofía Vargas", "Luciano Ríos"],
            "genres": ["Ciencia ficción"],
            "duration_minutes": 104,
            "backdrop_image": "https://fixture.invalid/p6-backdrop.png",
            "page_image": "https://fixture.invalid/p6-page.png",
        }
        entries.append(
            {
                "key": f"p6-{index}",
                "origin": {"kind": "catalog"},
                "item": item,
            }
        )
    home = payload.get("home") or {}
    home["featured"] = entries[:6]
    home["sections"] = [
        {
            "id": f"p6-bay-{index}",
            "title": label,
            "action": {"kind": "catalog", "label": "Ver colección", "filters": {}},
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
    output = ROOT / "docs/design/u2-p6-evidence"
    output.mkdir(exist_ok=True)
    image_assets = {
        "p6-backdrop.png": ROOT / "src/movie_inbox/web/static/img/night-videotheque-wall-v1.png",
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
                    """element => ({
                        frames: element.querySelectorAll('.home-furniture-frame').length,
                        visibleImages: [...element.querySelectorAll('.home-furniture-frame img')]
                            .filter(image => !image.hidden).length,
                        credits: element.querySelector('.home-furniture-credits')?.innerText,
                        pageOverflow: document.documentElement.scrollWidth - innerWidth,
                        panel: element.querySelector('.home-furniture-action-panel')
                            ?.getBoundingClientRect().toJSON(),
                        actions: element.querySelector('.home-shelf-preview-actions')
                            ?.getBoundingClientRect().toJSON(),
                    })"""
                )
                report.append({"viewport": width, **metrics})
                assert metrics["frames"] == 2
                assert metrics["visibleImages"] == 2
                assert metrics["pageOverflow"] <= 1

                if width >= 861:
                    page.locator("#homeFurniture").evaluate(
                        """element => {
                            const wrapper = document.createElement('div');
                            wrapper.id = 'p6CaptureFrame';
                            wrapper.style.height = '640px';
                            wrapper.style.overflow = 'hidden';
                            wrapper.style.position = 'relative';
                            wrapper.style.width = '100%';
                            element.before(wrapper);
                            wrapper.append(element);
                        }"""
                    )
                    page.locator("#p6CaptureFrame").screenshot(
                        path=str(output / f"console-{width}.png")
                    )
                else:
                    page.locator("#homeFurniture").scroll_into_view_if_needed()
                    page.locator("#homeFurniture").screenshot(
                        path=str(output / f"console-mobile-{width}.png")
                    )

                if width == 1440:
                    page.locator(".home-furniture-frame img").evaluate_all(
                        "images => images.forEach(image => image.dispatchEvent(new Event('error')))"
                    )
                    page.locator("#p6CaptureFrame").screenshot(
                        path=str(output / "console-missing-images-1440.png")
                    )
            finally:
                page.close()
    finally:
        BrowserInterfaceTests.tearDownClass()
    (output / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
