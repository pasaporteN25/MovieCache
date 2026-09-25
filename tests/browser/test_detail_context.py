"""Dossier context and concurrent personal edits, with disposable catalogues."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from tests.browser import test_ui_browser as fixture


class DetailContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture.BrowserInterfaceTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls) -> None:
        fixture.BrowserInterfaceTests.tearDownClass.__func__(cls)

    setUp = fixture.BrowserInterfaceTests.setUp
    tearDown = fixture.BrowserInterfaceTests.tearDown

    def open_detail(self) -> None:
        self.page.goto(self.base_url)
        fixture.wait_for_app_ready(self.page)
        self.page.evaluate("import('/static/js/core/detail.js').then(m => m.openDetail('heat'))")
        self.page.wait_for_selector("#detailDrawer[open]")

    def mock_context(self) -> None:
        self.page.route(
            "**/api/ratings?*",
            lambda route: route.fulfill(
                json={
                    "ratings": {
                        "heat": [
                            {
                                "source": "tmdb",
                                "average": 8,
                                "scale": 10,
                                "votes": 12,
                                "is_meaningful": False,
                            },
                            {
                                "source": "imdb",
                                "average": 8.3,
                                "scale": 10,
                                "votes": 750000,
                                "is_meaningful": True,
                            },
                        ]
                    },
                    "attribution": {
                        "imdb": "IMDb · datos de prueba",
                        "tmdb": "TMDb · datos de prueba",
                    },
                }
            ),
        )
        self.page.route(
            "**/api/streaming/preferences",
            lambda route: route.fulfill(
                json={
                    "preferences": {"region": "AR", "ignored_providers": ["99"]},
                    "effective_region": "AR",
                    "available_regions": ["AR", "UY"],
                    "may_choose": True,
                }
            ),
        )
        self.page.route(
            "**/api/streaming/availability?*",
            lambda route: route.fulfill(
                json={
                    "availability": {
                        "heat": {
                            "known": True,
                            "region_code": "AR",
                            "available_on": [
                                {
                                    "provider_id": "1",
                                    "provider_name": "Plataforma de prueba",
                                    "kind": "flatrate",
                                },
                            ],
                            "acquire_on": [
                                {
                                    "provider_id": "2",
                                    "provider_name": "Videoclub de prueba",
                                    "kind": "rent",
                                },
                            ],
                        }
                    },
                    "attribution": {
                        "justwatch": "Datos de disponibilidad provistos por JustWatch."
                    },
                }
            ),
        )

    def test_context_icons_ratings_offers_and_responsive(self) -> None:
        self.mock_context()
        self.open_detail()
        page = self.page
        page.wait_for_selector(".detail-public-scores")
        page.wait_for_selector(".detail-offer-group")
        self.assertEqual(
            page.locator(".detail-public-scores dt").all_text_contents(), ["IMDb", "TMDb"]
        )
        self.assertIn("Poco representativo", page.locator(".is-low-vote").inner_text())
        self.assertEqual(page.locator(".detail-access-signal.is-available").count(), 2)
        self.assertIn("Alquilar", page.locator(".detail-streaming-section").inner_text())
        self.assertIn("JustWatch", page.locator(".detail-streaming-section").inner_text())
        output = Path("docs/design/detail-context-evidence")
        output.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(output / "desktop.png"))
        page.locator(".detail-streaming-section").scroll_into_view_if_needed()
        page.screenshot(path=str(output / "desktop-context.png"))
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            page.locator(".detail-streaming-section").scroll_into_view_if_needed()
            self.assertFalse(
                page.evaluate(
                    "document.querySelector('#detailBody').scrollWidth > "
                    "document.querySelector('#detailBody').clientWidth + 1"
                )
            )
            page.screenshot(path=str(output / f"mobile-{width}.png"))

    def test_partial_save_and_noop_preserve_personal_fields(self) -> None:
        self.mock_context()
        self.open_detail()
        page = self.page
        personal: list[dict[str, Any]] = []
        privacy: list[dict[str, Any]] = []

        def save_personal(route: Any) -> None:
            personal.append(route.request.post_data_json)
            route.fulfill(json={"ok": True})

        def save_privacy(route: Any) -> None:
            privacy.append(route.request.post_data_json)
            route.fulfill(json={"ok": True})

        page.route("**/api/personal", save_personal)
        page.route("**/api/privacy/items/*", save_privacy)
        page.get_by_role("button", name="Editar registro", exact=True).click()
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        page.wait_for_selector(".personal-record-read")
        self.assertEqual(personal, [])
        self.assertEqual(privacy, [])
        page.get_by_role("button", name="Editar registro", exact=True).click()
        page.locator("[data-personal-review]").fill("Mi edición")
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        page.wait_for_selector(".personal-record-read")
        self.assertEqual(len(personal), 1)
        self.assertEqual(personal[0]["review"], "Mi edición")
        self.assertNotIn("rating", personal[0])
        self.assertNotIn("watched_at", personal[0])
        self.assertEqual(set(personal[0]["base"]), {"review", "rating", "watched_at"})
        self.assertEqual(privacy, [])

    def test_streaming_unknown_error_retry_and_country_preferences(self) -> None:
        self.mock_context()
        page = self.page
        selected = {"region": "AR", "ignored_providers": ["99"]}
        attempts = []

        def preferences(route: Any) -> None:
            if route.request.method == "POST":
                selected.update(route.request.post_data_json)
                route.fulfill(json={"preferences": selected})
            else:
                route.fulfill(
                    json={
                        "preferences": selected,
                        "effective_region": selected["region"],
                        "available_regions": ["AR", "UY"],
                        "may_choose": True,
                    }
                )

        def availability(route: Any) -> None:
            attempts.append(route.request.url)
            if len(attempts) == 1:
                route.fulfill(status=503, json={"reason": "streaming_unavailable"})
            else:
                route.fulfill(json={"availability": {}})

        page.route("**/api/streaming/preferences", preferences)
        page.route("**/api/streaming/availability?*", availability)
        self.open_detail()
        retry = page.locator(".detail-streaming-section").get_by_role("button", name="Reintentar")
        retry.click()
        page.wait_for_function(
            "document.querySelector('[data-streaming-offers]').textContent.includes('Todavía')"
        )
        self.assertIn(
            "Sin información", page.locator("[data-detail-streaming-signal]").inner_text()
        )
        self.assertEqual(page.locator("[data-detail-streaming-signal] .is-available").count(), 0)
        page.get_by_label("País para streaming").select_option("UY")
        page.wait_for_function(
            "document.querySelector('[data-streaming-offers]')"
            ".getAttribute('aria-busy') === 'false'"
        )
        self.assertEqual(selected, {"region": "UY", "ignored_providers": ["99"]})
        self.assertTrue(all("item_id=heat" in url for url in attempts))

    def test_conflict_keeps_text_and_requires_explicit_reconciliation(self) -> None:
        self.mock_context()
        self.open_detail()
        page = self.page
        page.get_by_role("button", name="Editar registro", exact=True).click()
        page.locator("[data-personal-review]").fill("Mi texto sin perder")
        calls: list[dict[str, Any]] = []

        def conflict(route: Any) -> None:
            calls.append(route.request.post_data_json)
            route.fulfill(status=409, json={"ok": False, "reason": "personal_conflict"})

        page.route("**/api/personal", conflict)
        page.route(
            "**/api/items",
            lambda route: route.fulfill(
                json={
                    "items": [
                        {"id": "heat", "title": "Heat", "rating": 9, "review": "Desde el teléfono"},
                    ]
                }
            ),
        )
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        page.wait_for_selector("[data-personal-conflict]")
        self.assertEqual(
            page.locator("[data-personal-review]").input_value(), "Mi texto sin perder"
        )
        self.assertIn("Desde el teléfono", page.locator("[data-personal-conflict]").inner_text())
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        self.assertEqual(len(calls), 1)
        page.get_by_role("button", name="Conservar mi edición", exact=True).click()
        self.assertEqual(page.locator("[data-personal-rating]").input_value(), "9")
        self.assertEqual(
            page.locator("[data-personal-review]").input_value(), "Mi texto sin perder"
        )
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        page.wait_for_selector("[data-personal-conflict]")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["base"]["review"], "Desde el teléfono")
        self.assertEqual(calls[1]["base"]["rating"], 9)
        page.get_by_role("button", name="Usar versión actual", exact=True).click()
        self.assertEqual(page.locator("[data-personal-review]").input_value(), "Desde el teléfono")

    def test_privacy_retry_does_not_repeat_an_already_saved_review(self) -> None:
        self.mock_context()
        self.open_detail()
        page = self.page
        personal = []
        privacy = []

        def save_personal(route: Any) -> None:
            personal.append(route.request.post_data_json)
            route.fulfill(json={"ok": True})

        def save_privacy(route: Any) -> None:
            privacy.append(route.request.post_data_json)
            route.fulfill(status=503 if len(privacy) == 1 else 200, json={"ok": len(privacy) > 1})

        page.route("**/api/personal", save_personal)
        page.route("**/api/privacy/items/*", save_privacy)
        page.get_by_role("button", name="Editar registro", exact=True).click()
        page.locator("[data-personal-review]").fill("Texto conservado")
        page.locator("[data-personal-rating-privacy]").select_option("shared")
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        page.wait_for_function(
            "document.querySelector('[data-personal-status]').textContent.includes('No se pudo')"
        )
        self.assertEqual(page.locator("[data-personal-review]").input_value(), "Texto conservado")
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        page.wait_for_selector(".personal-record-read")
        self.assertEqual(len(personal), 1)
        self.assertEqual(len(privacy), 2)

    def test_delayed_context_does_not_replace_the_next_work(self) -> None:
        self.mock_context()
        page = self.page
        pending = []
        page.route("**/api/ratings?item_id=heat", lambda route: pending.append(route))
        self.open_detail()
        page.get_by_role("button", name="Abrir ficha siguiente").click()
        page.wait_for_function("document.querySelector('.drawer-intro h2').textContent === 'Akira'")
        self.assertEqual(len(pending), 1)
        pending[0].fulfill(
            json={
                "ratings": {
                    "heat": [
                        {"source": "imdb", "average": 9, "scale": 10, "votes": 999},
                    ]
                }
            }
        )
        page.wait_for_function(
            "document.querySelector('[data-public-ratings]').getAttribute('aria-busy') === 'false'"
        )
        self.assertEqual(page.locator(".detail-public-scores").count(), 0)
        self.assertIn("Todavía", page.locator("[data-public-ratings]").inner_text())


if __name__ == "__main__":
    unittest.main()
