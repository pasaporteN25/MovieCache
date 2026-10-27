"""Captura el mostrador de Inicio (IP1/IP2) con datos descartables e ilustrativos.

Uso, desde la raíz del repositorio y con `.[browser-test]` instalado:
    python docs/design/home-search-desk-v1/capture.py
"""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests.browser.test_ui_browser import BrowserInterfaceTests, wait_for_app_ready

WIDTHS = ((390, 844), (1280, 800), (1440, 900), (1920, 1080))
TITLES = ("Heat", "Akira", "Solaris", "Stalker", "Cure", "Vértigo", "Paris, Texas", "Ran")

POSTER = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900">'
    '<rect width="600" height="900" fill="#101727"/>'
    '<rect x="12" y="12" width="576" height="876" fill="none" stroke="#efb83e" stroke-width="24"/>'
    '<circle cx="300" cy="420" r="130" fill="#ff2e95"/>'
    '<text x="300" y="760" text-anchor="middle" fill="white" font-size="54">AFICHE DE PRUEBA</text>'
    "</svg>"
)


def external(title: str, year: str, state: str, score: int, source: str, item_id: str | None = None) -> dict[str, Any]:
    return {
        "title": title, "year": year, "kind": "pelicula", "source": source,
        "url": f"https://example.com/{source}/{title.replace(' ', '_')}",
        "page_image": "https://example.invalid/poster.svg", "_search": {"score": score},
        "_membership": {"state": state, "item_id": item_id},
    }


def capture() -> None:
    BrowserInterfaceTests.setUpClass()
    case = BrowserInterfaceTests(methodName="test_home_loading_failure_can_retry")
    case.setUp()
    base = Path(__file__).parent
    try:
        page = case.page

        def items(route) -> None:
            response = route.fetch()
            payload = response.json()
            seed = payload["items"]

            def entry(index: int, prefix: str) -> dict[str, Any]:
                item = {**seed[index % len(seed)], "id": f"{prefix}-{index}", "title": TITLES[index % len(TITLES)],
                        "page_image": "https://example.invalid/poster.svg", "en_catalogo": True}
                return {"key": f"{prefix}-{index}", "origin": {"kind": "catalog"}, "item": item,
                        "reason": {"label": "Selección del archivo", "detail": "Disponible."}}

            payload["home"]["featured"] = [entry(index, "daily") for index in range(4)]
            payload["home"]["sections"] = [
                {"id": "available", "title": "Disponible esta noche", "items": [entry(i, "disp") for i in range(8)]},
                {"id": "memory", "title": "Tu archivo pide memoria", "items": [entry(i + 2, "mem") for i in range(6)]},
            ]
            route.fulfill(response=response, json=payload)

        def search(route) -> None:
            url = route.request.url
            if "external=true" in url:
                body = {"results": [
                    external("Heat", "1995", "present", 100, "imdb", "heat"),
                    external("Heat", "1986", "review", 88, "wikipedia"),
                    external("The Heat", "2013", "missing", 72, "filmaffinity"),
                    external("Heat — referencia", "2020", "missing", 60, "wikipedia"),
                ]}
            else:
                body = {"catalog": {"results": [{
                    "id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula",
                    "status": "to_watch", "en_catalogo": True, "_search": {"score": 100},
                }]}}
            route.fulfill(json=body)

        page.route("**/api/items?*", items)
        page.route("**/api/search?*", search)
        page.route("**/image-cache?*", lambda route: route.fulfill(content_type="image/svg+xml", body=POSTER))
        shots = 0
        for width, height in WIDTHS:
            page.set_viewport_size({"width": width, "height": height})
            page.goto(case.base_url)
            wait_for_app_ready(page)
            page.evaluate("document.fonts.ready")
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(base / f"home-{width}.png"), animations="disabled")
            field = page.locator("#homeSearchSlot input[role='combobox']")
            field.focus()
            field.fill("Heat")
            page.wait_for_function("document.querySelectorAll('#homeSearchSlot .hs-external').length === 3")
            page.keyboard.press("ArrowDown")
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(base / f"search-{width}.png"), animations="disabled")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            shots += 2
        print(json.dumps({"screenshots": shots, "overflow": False}))
    finally:
        case.tearDown()
        BrowserInterfaceTests.tearDownClass()


if __name__ == "__main__":
    capture()
