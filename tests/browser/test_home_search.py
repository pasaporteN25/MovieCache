"""IP2: el buscador del mostrador de Inicio, de punta a punta en el navegador.

Los resultados externos se simulan con rutas de Playwright (sin red real); el grupo
«En tu colección» usa el catálogo descartable del servidor de prueba (Heat y Akira).
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from tests.browser import test_ui_browser as fixture

COMBOBOX = "#homeSearchSlot input[role='combobox']"


def external_result(
    title: str,
    year: str,
    state: str,
    *,
    source: str = "wikipedia",
    score: float = 0.9,
    item_id: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "year": year,
        "kind": "pelicula",
        "source": source,
        "url": url or f"https://es.wikipedia.org/wiki/{title.replace(' ', '_')}",
        "_search": {"score": score},
        "_membership": {"state": state, "item_id": item_id},
    }


class HomeSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture.BrowserInterfaceTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        fixture.BrowserInterfaceTests.tearDownClass.__func__(cls)

    setUp = fixture.BrowserInterfaceTests.setUp
    tearDown = fixture.BrowserInterfaceTests.tearDown

    def mock_external(
        self,
        results: list[dict[str, Any]] | None = None,
        *,
        status: int = 200,
    ) -> list[str]:
        """Simula la parte externa de /api/search y deja pasar la local.

        Devuelve la lista (viva) de URLs externas pedidas."""
        requested: list[str] = []

        def handle(route: Any) -> None:
            url = route.request.url
            if "external=true" not in url:
                route.fallback()
                return
            requested.append(url)
            if status != 200:
                route.fulfill(status=status, json={"reason": "unavailable"})
                return
            route.fulfill(status=200, json={"results": results or [], "external": {"sources": {}}})

        self.page.route("**/api/search?*", handle)
        return requested

    def track_writes(self) -> list[tuple[str, str]]:
        writes: list[tuple[str, str]] = []
        self.page.on(
            "request",
            lambda request: (
                writes.append((request.method, request.url))
                if request.method in ("POST", "PATCH", "PUT", "DELETE") and "/api/" in request.url
                else None
            ),
        )
        return writes

    def open_home(self, *, with_featured: bool = False) -> None:
        if with_featured:

            def shape(route: Any) -> None:
                response = route.fetch()
                payload = response.json()
                payload["home"]["featured"] = [
                    {
                        "key": "daily-heat",
                        "origin": {"kind": "catalog"},
                        "item": payload["items"][0],
                    }
                ]
                route.fulfill(response=response, json=payload)

            self.page.route("**/api/items?*", shape)
        self.page.goto(self.base_url)
        fixture.wait_for_app_ready(self.page)
        self.page.wait_for_selector(COMBOBOX)

    def type_query(self, text: str) -> None:
        field = self.page.locator(COMBOBOX)
        field.focus()
        field.fill(text)

    def wait_for_external_rows(self, count: int) -> None:
        self.page.wait_for_function(
            "count => document.querySelectorAll('#homeSearchSlot .hs-external').length === count",
            arg=count,
        )

    def external_row(self, index: int = 0) -> Any:
        return self.page.locator("#homeSearchSlot .hs-external").nth(index)

    def test_enter_without_row_opens_collection_in_add_mode_and_back_returns_home(self) -> None:
        self.mock_external([])
        self.open_home()
        page = self.page
        self.type_query("Solaris")
        page.keyboard.press("Enter")

        page.wait_for_selector("#collectionView:not([hidden])")
        self.assertEqual(page.locator("#collectionView").get_attribute("data-search-mode"), "add")
        self.assertIn("mode=add", page.url)
        self.assertIn("q=Solaris", page.url)
        self.assertEqual(page.locator("#query").input_value(), "Solaris")

        page.go_back()
        page.wait_for_selector("#homeView:not([hidden])")
        self.assertTrue(page.locator("#collectionView").is_hidden())
        self.assertNotIn("mode=add", page.url)
        # La consulta quedó en recientes para la próxima vez.
        fixture.wait_for_app_ready(page)
        page.locator(COMBOBOX).fill("")
        page.locator(COMBOBOX).focus()
        self.assertIn(
            "Solaris", page.locator("#homeSearchSlot .hs-recent .hs-text").all_inner_texts()
        )

    def test_review_row_never_posts_to_add(self) -> None:
        self.mock_external([external_result("Heat", "1986", "review")])
        self.open_home()
        page = self.page
        writes = self.track_writes()
        self.type_query("Heat")
        self.wait_for_external_rows(1)
        row = self.external_row()
        self.assertEqual(row.locator(".hs-state").text_content(), "Revisar")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowDown")  # la primera fila es «En tu colección»
        self.assertEqual(row.get_attribute("aria-selected"), "true")
        page.keyboard.press("Enter")
        # «Revisar» lleva la decisión a Colección y no escribe nada.
        page.wait_for_selector("#collectionView:not([hidden])")
        self.assertEqual(page.locator("#collectionView").get_attribute("data-search-mode"), "add")
        self.assertEqual([w for w in writes if "/api/add" in w[1]], [])

        page.go_back()
        page.wait_for_selector("#homeView:not([hidden])")
        fixture.wait_for_app_ready(page)
        self.type_query("Heat")
        self.wait_for_external_rows(1)
        self.external_row().click()
        page.wait_for_selector("#collectionView:not([hidden])")
        self.assertEqual([w for w in writes if "/api/add" in w[1]], [])

    def test_pending_button_adds_and_the_row_changes(self) -> None:
        self.mock_external([external_result("Solaris", "1972", "missing")])
        page = self.page
        posted: list[dict[str, Any]] = []

        def handle_add(route: Any) -> None:
            posted.append(json.loads(route.request.post_data or "{}"))
            route.fulfill(
                status=200, json={"ok": True, "reason": "added", "item": {"id": "solaris"}}
            )

        page.route("**/api/add", handle_add)
        self.open_home()
        self.type_query("Solaris")
        self.wait_for_external_rows(1)
        row = self.external_row()
        self.assertEqual(row.locator(".hs-state").text_content(), "+ Pendiente")
        self.assertEqual(row.locator(".hs-source").text_content(), "Wikipedia")
        row.click()
        page.wait_for_function(
            "document.querySelector('#homeSearchSlot .hs-external .hs-state').textContent"
            " === 'Agregada'"
        )
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["title"], "Solaris")
        self.assertNotIn("action", posted[0])
        self.assertNotIn("target_id", posted[0])
        self.assertNotIn("_membership", posted[0])
        # Una fila ya agregada no vuelve a escribir.
        self.external_row().click()
        page.wait_for_timeout(200)
        self.assertEqual(len(posted), 1)
        # El campo y el panel siguen abiertos: se puede seguir buscando.
        self.assertEqual(page.locator(COMBOBOX).get_attribute("aria-expanded"), "true")

    def test_possible_duplicate_turns_the_row_into_review_without_retrying(self) -> None:
        self.mock_external([external_result("Solaris", "1972", "missing")])
        page = self.page
        posted: list[str] = []

        def handle_add(route: Any) -> None:
            posted.append(route.request.url)
            route.fulfill(
                status=409,
                json={"ok": False, "reason": "possible_duplicate", "candidates": [{"id": "x"}]},
            )

        page.route("**/api/add", handle_add)
        self.open_home()
        self.type_query("Solaris")
        self.wait_for_external_rows(1)
        self.external_row().click()
        page.wait_for_function(
            "document.querySelector('#homeSearchSlot .hs-external .hs-state').textContent"
            " === 'Revisar'"
        )
        self.assertEqual(len(posted), 1)
        # «Revisar» ya no escribe: el siguiente gesto amplía en Colección.
        self.external_row().click()
        page.wait_for_selector("#collectionView:not([hidden])")
        self.assertEqual(len(posted), 1)

    def test_pasting_a_link_shows_a_single_result_for_that_work(self) -> None:
        link = "https://www.imdb.com/title/tt0062622/"
        requested = self.mock_external(
            [
                external_result(
                    "2001: Odisea del espacio", "1968", "missing", source="imdb", url=link
                )
            ]
        )
        self.open_home()
        page = self.page
        self.type_query(link)
        self.wait_for_external_rows(1)
        self.assertEqual(page.locator("#homeSearchSlot .hs-external").count(), 1)
        self.assertEqual(
            page.locator("#homeSearchSlot .hs-group-label").all_text_contents(),
            ["Enlace de IMDb"],
        )
        self.assertEqual(self.external_row().locator(".hs-source").text_content(), "IMDb")
        self.assertEqual(len(requested), 1)
        self.assertIn("membership=true", requested[0])
        self.assertIn("catalog=false", requested[0])

    def test_escape_returns_the_poster_to_the_suggestion(self) -> None:
        self.mock_external([])
        self.open_home(with_featured=True)
        page = self.page
        poster = page.locator(".home-consulted-poster")
        suggested_key = poster.get_attribute("data-consulted-key")
        self.assertEqual(suggested_key, "daily-heat")
        self.assertEqual(poster.locator(".spotlight-selector-heading").text_content(), "Sugerencia")

        self.type_query("Akira")
        page.wait_for_selector("#homeSearchSlot .hs-local")
        page.keyboard.press("ArrowDown")
        self.assertEqual(poster.get_attribute("data-consulted-key"), "akira")
        self.assertEqual(poster.locator(".spotlight-selector-heading").text_content(), "Resultado")
        self.assertEqual(page.locator("#spotlight-selected-title").text_content(), "Akira")

        page.keyboard.press("Escape")
        self.assertEqual(poster.get_attribute("data-consulted-key"), suggested_key)
        self.assertEqual(poster.locator(".spotlight-selector-heading").text_content(), "Sugerencia")
        self.assertEqual(page.evaluate("window.getHomePlaybackState().selectionSource"), "daily")
        self.assertEqual(page.locator(COMBOBOX).get_attribute("aria-expanded"), "false")

    def test_slash_focuses_the_search_field_unless_typing_elsewhere(self) -> None:
        self.mock_external([])
        self.open_home()
        page = self.page
        page.locator("body").click(position={"x": 5, "y": 5})
        page.keyboard.press("/")
        self.assertEqual(page.evaluate("document.activeElement.getAttribute('role')"), "combobox")
        # La barra no se escribe dentro del campo que se acaba de enfocar.
        self.assertEqual(page.locator(COMBOBOX).input_value(), "")

        # Desde otra vista vuelve a Inicio.
        page.locator("#catalogButton").click()
        page.wait_for_selector("#collectionView:not([hidden])")
        page.locator("body").click(position={"x": 5, "y": 5})
        page.keyboard.press("/")
        page.wait_for_selector("#homeView:not([hidden])")
        self.assertEqual(page.evaluate("document.activeElement.getAttribute('role')"), "combobox")

        # Escribiendo en otro campo de texto, `/` es un carácter más.
        page.locator("#catalogButton").click()
        page.wait_for_selector("#collectionView:not([hidden])")
        # `press` sobre el locator enfoca el campo en el mismo paso, sin depender de que la
        # vista de Colección termine de mover el foco por su cuenta.
        page.locator("#query").press("/")
        self.assertEqual(page.locator("#query").input_value(), "/")
        self.assertTrue(page.locator("#collectionView").is_visible())

    def test_failed_source_does_not_break_the_local_group(self) -> None:
        self.mock_external(status=503)
        self.open_home()
        page = self.page
        self.type_query("Heat")
        page.wait_for_function(
            "document.querySelector('#homeSearchSlot .hs-warning')?.textContent"
            ".includes('fuente externa')"
        )
        self.assertEqual(
            page.locator("#homeSearchSlot .hs-group-label").all_text_contents(), ["En tu colección"]
        )
        local_rows = page.locator("#homeSearchSlot .hs-local")
        self.assertEqual(local_rows.count(), 1)
        self.assertIn("Heat", local_rows.first.inner_text())
        self.assertEqual(page.locator("#homeSearchSlot .hs-external").count(), 0)
        # Sigue siendo operable: Enter sobre la fila local abre la ficha.
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_selector("#detailDrawer[open]")


if __name__ == "__main__":
    unittest.main()
