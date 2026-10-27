"""Capture the production search UI with disposable, illustrative search data."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests.browser.test_ui_browser import BrowserInterfaceTests


def capture() -> None:
    BrowserInterfaceTests.setUpClass()
    case = BrowserInterfaceTests(methodName="test_search_unifies_saved_and_external_results_by_relevance")
    case.setUp()
    try:
        page = case.page
        case._open_and_wait_for_catalog(page)

        def search(route) -> None:
            url = route.request.url
            body = {"results": []}
            if "external=false" in url:
                body = {"catalog": {"results": [{
                    "id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula",
                    "status": "pending", "en_catalogo": True,
                    "description": "Un detective y un ladrón profesional se enfrentan en Los Ángeles.",
                    "_search": {"score": 100},
                }]}}
            elif "source=imdb" in url:
                body = {"results": [{
                    "title": "Heat", "year": "1995", "kind": "pelicula", "source": "imdb",
                    "url": "https://www.imdb.com/title/tt0113277/", "_search": {"score": 100},
                    "description": "Referencia externa para comparar con tu archivo.",
                }]}
            elif "source=wikipedia" in url:
                body = {"results": [{
                    "title": "Heat", "year": "1986", "kind": "pelicula", "source": "wikipedia",
                    "url": "https://en.wikipedia.org/wiki/Heat_(1986_film)",
                    "description": "Una obra con el mismo título y otro año de estreno.",
                    "_search": {"score": 88},
                }] + [{
                    "title": f"Heat — referencia de prueba {number}", "year": "2020",
                    "kind": "documental", "source": "wikipedia",
                    "url": f"https://example.com/reference/{number}",
                    "description": "Datos ilustrativos para revisar la paginación común y la lectura.",
                    "_search": {"score": 60 - number},
                } for number in range(1, 7)]}
            elif "source=filmaffinity" in url:
                body = {"results": [{
                    "title": "The Heat", "year": "2013", "kind": "pelicula", "source": "filmaffinity",
                    "url": "https://www.filmaffinity.com/es/film000000.html",
                    "description": "Una coincidencia parcial de título, debajo de las coincidencias directas.",
                    "_search": {"score": 72},
                }]}
            route.fulfill(json=body)

        page.route("**/api/search?*", search)
        page.route("**/api/add", lambda route: route.fulfill(json={
            "ok": False, "reason": "possible_duplicate", "candidates": [{
                "id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula",
                "reason": "exact_title_year",
            }],
        }))
        page.locator("#catalogButton").click()
        page.locator("#externalSource").check()
        page.locator("#query").fill("Heat")
        page.locator("#searchButton").click()
        page.wait_for_function("!document.querySelector('#searchButton').disabled")
        page.evaluate("document.fonts.ready")
        base = Path(__file__).parent
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(base / "desktop-full.png"), full_page=True, animations="disabled")
        page.locator("#externalSearchSection").screenshot(path=str(base / "desktop.png"), animations="disabled")
        page.locator('.external-result[data-result-source="imdb"] [data-click="add-result"]').click()
        page.locator("#duplicateReview:not([hidden])").wait_for()
        page.locator("#externalSearchSection").screenshot(path=str(base / "desktop-duplicate.png"), animations="disabled")
        page.locator('[data-click="dismiss-duplicate"]').click()
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(base / f"mobile-{width}.png"), full_page=True, animations="disabled")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        print(json.dumps({"screenshots": 5, "overflow": False}))
    finally:
        case.tearDown()
        BrowserInterfaceTests.tearDownClass()


if __name__ == "__main__":
    capture()
