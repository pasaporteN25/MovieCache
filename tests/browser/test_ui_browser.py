from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import uvicorn
from playwright.sync_api import sync_playwright

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.models import CatalogItem
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def wait_until_healthy(base_url: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}/healthz", timeout=0.5) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("Server did not become healthy in time")


def run_library_scan(page, base_url: str, headers: dict[str, str], library_id: str) -> None:
    """Run a dry_run then an apply pass, polling between and after each --
    under a real uvicorn server (unlike TestClient) the scan itself runs in a
    FastAPI BackgroundTask after the response is already sent."""
    for mode in ("dry_run", "apply"):
        run_id = page.request.post(
            f"{base_url}/api/libraries/{library_id}/runs",
            data=json.dumps({"mode": mode}),
            headers=headers,
        ).json()["run"]["id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            run = page.request.get(f"{base_url}/api/library-runs/{run_id}", headers=headers).json()[
                "run"
            ]
            if run["status"] == "completed":
                break
            if run["status"] in ("failed", "blocked"):
                raise RuntimeError(f"Library {mode} run ended as {run['status']}: {run}")
            time.sleep(0.1)
        else:
            raise RuntimeError(f"Library {mode} run did not finish in time")


def wait_for_app_ready(page) -> None:
    """Wait for the first catalog load to finish rendering.

    #homeView is aria-busy until then, and `#homeView` being visible says nothing
    about it. The router closes the system menu when it restores the route, in the
    same task that ends the busy state, so a menu opened before that is closed again
    under the click that follows. It only shows on a slow machine, where the load
    loses the race against the test."""
    page.wait_for_function(
        "document.querySelector('#homeView').getAttribute('aria-busy') === 'false'"
    )


def open_desktop_menu(page) -> None:
    wait_for_app_ready(page)
    page.locator("#systemMenu > summary").click()


def click_desktop_menu_action(page, action: str) -> None:
    open_desktop_menu(page)
    page.locator(f'[data-click="menu-{action}"]').click()


class BrowserInterfaceTests(unittest.TestCase):
    """Colección, Ficha and structural-markup coverage on a shared, read-only
    catalog. No test here writes to the catalog, so they can safely share one
    server/session regardless of execution order."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        cls.catalog_path = root / "catalog.json"
        JsonCatalogRepository(cls.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "description": (
                            "Un detective y un ladrón profesional se enfrentan en Los Ángeles."
                        ),
                        "en_catalogo": True,
                    }
                ),
                normalize_item(
                    {
                        "id": "akira",
                        "title": "Akira",
                        "year": "1988",
                        "status": "watched",
                    }
                ),
            ]
        )
        cls.owner_password = "a-long-browser-test-password"
        cls.instance_path = root / "instance.db"
        cls.media_path = root / "media"
        cls.media_path.mkdir()
        AuthService(SqliteIdentityRepository(cls.instance_path)).bootstrap_owner(
            "lucas",
            cls.owner_password,
            catalog_name="Catálogo de Lucas",
            source_paths=[str(cls.catalog_path)],
            write_path=str(cls.catalog_path),
        )
        cls.port = available_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.config = ViewerConfig(
            patterns=[str(cls.catalog_path)],
            title="Movie Inbox Browser Test",
            write_json=str(cls.catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=cls.port,
            api_token="browser-test-token",
            instance_db=str(cls.instance_path),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(cls.media_path),),
            library_scheduler_poll_seconds=3600,
        )
        cls.server = uvicorn.Server(
            uvicorn.Config(
                create_app(cls.config), host="127.0.0.1", port=cls.port, log_level="error"
            )
        )
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        wait_until_healthy(cls.base_url)

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        # bypass_csp: without it, Page.evaluate/wait_for_function on any page
        # after the first one opened in a context hits the app's strict CSP
        # ("script-src 'self'", no 'unsafe-eval') and raises EvalError -- a
        # Playwright/Chromium quirk unrelated to the app itself, only visible
        # to test automation.
        cls.context = cls.browser.new_context(
            viewport={"width": 1280, "height": 900}, bypass_csp=True
        )
        setup_page = cls.context.new_page()
        setup_page.goto(cls.base_url)
        setup_page.get_by_label("Usuario").fill("lucas")
        setup_page.get_by_label("Contraseña", exact=True).fill(cls.owner_password)
        setup_page.get_by_role("button", name="Entrar").click()
        setup_page.wait_for_selector("#homeView:not([hidden])")

        # Give "Akira" server-verified availability via a real library scan, so
        # test_ficha_availability_panel_separates_manual_from_server_provenance
        # can show manual vs. server provenance without a second server.
        headers = {
            "X-Movie-Inbox-Token": cls.config.api_token,
            "Origin": cls.base_url,
            "Content-Type": "application/json",
        }
        (cls.media_path / "Akira.1988.mkv").write_bytes(b"akira-video")
        library = setup_page.request.post(
            f"{cls.base_url}/api/libraries",
            data=json.dumps(
                {"name": "Anime", "root_path": str(cls.media_path), "schedule": "manual"}
            ),
            headers=headers,
        ).json()["library"]
        run_library_scan(setup_page, cls.base_url, headers, library["id"])
        items = setup_page.request.get(f"{cls.base_url}/api/items", headers=headers).json()["items"]
        akira = next(item for item in items if item["id"] == "akira")
        if not akira["_availability"]["server"]:
            raise RuntimeError(f"Library scan did not link Akira: {akira['_availability']}")
        setup_page.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()
        cls.server.should_exit = True
        cls.server_thread.join(timeout=10)
        cls.temporary.cleanup()

    def setUp(self) -> None:
        self.page = self.context.new_page()

    def tearDown(self) -> None:
        self.page.close()

    @staticmethod
    def _open_and_wait_for_catalog(page) -> None:
        """openDetail/openSearchDescription read the app's in-memory catalog,
        which is still empty right when #homeView first becomes visible."""
        page.goto(BrowserInterfaceTests.base_url)
        page.wait_for_selector("#homeView:not([hidden])")
        page.wait_for_function("document.querySelector('#stats').textContent.includes('2 obras')")

    def test_collection_navigation_and_responsive_layout(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        self.assertEqual(page.locator(".primary-nav > .nav-action").count(), 4)
        self.assertEqual(page.locator(".primary-nav #randomButton").count(), 0)
        self.assertEqual(page.locator(".header-utilities #randomButton").count(), 1)
        self.assertEqual(page.locator(".header-utilities #headerSearchButton").count(), 1)
        self.assertEqual(page.locator(".header-utilities #headerAddButton").count(), 1)
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )

        page.locator(".brand-home").focus()
        page.keyboard.press("Tab")
        self.assertEqual(page.evaluate("document.activeElement.id"), "catalogButton")

        page.locator("#catalogButton").focus()
        page.keyboard.press("Tab")
        self.assertEqual(
            page.evaluate("document.activeElement.closest('#systemMenu')?.id"), "systemMenu"
        )

        page.set_viewport_size({"width": 390, "height": 844})
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )
        self.assertEqual(page.locator(".primary-nav > .nav-action").count(), 4)
        for selector in (
            "#homeButton",
            "#catalogButton",
            "#inboxButton",
            "#clubButton",
            "#headerSearchButton",
            "#headerAddButton",
            "#randomButton",
        ):
            box = page.locator(selector).bounding_box()
            self.assertIsNotNone(box, selector)
            self.assertGreaterEqual(box["height"], 44, selector)

    def test_mobile_home_restores_header_preview_and_broken_poster_flow(self) -> None:
        page = self.page

        def add_mobile_recovery_fixture(route) -> None:
            response = route.fetch()
            payload = response.json()
            item = dict(payload["items"][0])
            item.update(
                {
                    "title": "La insoportable levedad del ser y otras historias de medianoche",
                    "year": "1988",
                    "kind": "pelicula",
                    "description": (
                        "Una historia extensa para verificar que la sinopsis conserve una "
                        "lectura cómoda, visible y ordenada en una pantalla móvil angosta."
                    ),
                    "backdrop_image": "https://example.invalid/u2-p6-broken-backdrop.jpg",
                    "page_image": "https://example.invalid/u2-r6-broken-poster.jpg",
                    "directors": ["Philip Kaufman"],
                    "writers": ["Milan Kundera", "Jean-Claude Carrière"],
                    "cast": ["Daniel Day-Lewis", "Juliette Binoche"],
                }
            )
            payload["home"]["sections"] = [
                {
                    "id": "available",
                    "title": "Disponible esta noche",
                    "action": {"kind": "catalog", "label": "Ver colección", "filters": {}},
                    "items": [
                        {
                            "key": "available-long-title",
                            "origin": {"kind": "catalog"},
                            "item": item,
                            "reason": {"label": "Lista para ver", "detail": "Disponible."},
                        }
                    ],
                }
            ]
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_mobile_recovery_fixture)
        page.set_viewport_size({"width": 390, "height": 844})
        self._open_and_wait_for_catalog(page)
        # U4.6b: choosing the shelf's spine fills the single console above the shelves,
        # which replaced each shelf's own preview.
        page.locator('[data-home-section="available"] .home-shelf-tape').first.click()
        preview = page.locator('.spotlight-preview[data-selection-source="shelf:available"]')
        preview.wait_for()
        self.assertEqual(preview.get_attribute("data-selected-entry-key"), "available-long-title")
        # The console carries no images of its own: the "En consulta" frame shows the
        # poster, so the console never repeats it.
        self.assertEqual(preview.locator("img").count(), 0)

        geometry = page.evaluate(
            """() => {
                const box = selector => document.querySelector(selector).getBoundingClientRect();
                const header = box('.app-header');
                const brand = box('.brand-lockup');
                const title = box('h1');
                const consoleBox = box('.spotlight-preview');
                const credits = box('.spotlight-preview .home-furniture-credits');
                const summary = document.querySelector('.spotlight-preview .spotlight-copy p');
                const summaryStyle = getComputedStyle(summary);
                return {
                    overflow: document.documentElement.scrollWidth - innerWidth,
                    headerHeight: header.height,
                    brandWidth: brand.width,
                    titleWidth: title.width,
                    titleHeight: title.height,
                    consoleWidth: consoleBox.width,
                    consoleInside: consoleBox.left >= 0 && consoleBox.right <= innerWidth,
                    creditsWidth: credits.width,
                    summaryFontSize: Number.parseFloat(summaryStyle.fontSize),
                    summaryLineHeight: Number.parseFloat(summaryStyle.lineHeight),
                    summaryFits: summary.scrollWidth <= summary.clientWidth + 1,
                };
            }"""
        )
        self.assertLessEqual(geometry["overflow"], 1)
        self.assertLess(geometry["headerHeight"], 230)
        self.assertGreater(geometry["brandWidth"], 320)
        self.assertGreater(geometry["titleWidth"], 300)
        self.assertLess(geometry["titleHeight"], 90)
        self.assertGreater(geometry["consoleWidth"], 300)
        self.assertTrue(geometry["consoleInside"])
        self.assertGreater(geometry["creditsWidth"], 300)
        # The compact console sets the floor: 12px text on an 18px line, never clipped.
        self.assertGreaterEqual(geometry["summaryFontSize"], 12)
        self.assertGreaterEqual(geometry["summaryLineHeight"], 18)
        self.assertTrue(geometry["summaryFits"])
        self.assertEqual(preview.locator(".home-console-details").count(), 1)
        self.assertEqual(page.locator(".home-shelf-preview, #homeShelfPreview").count(), 0)
        self.assertEqual(preview.locator(".home-furniture-format-panel").count(), 0)
        self.assertEqual(preview.locator(".spotlight-preview-action").count(), 2)
        for action in preview.locator(".spotlight-preview-action").all():
            action_box = action.bounding_box()
            self.assertIsNotNone(action_box)
            self.assertGreaterEqual(action_box["height"], 44)

        # The fixed bottom navigation may overlap an action until the page scrolls, but it
        # must never cover one once it is brought to the middle of the screen.
        for action in preview.locator(".spotlight-preview-action").all():
            action.evaluate("element => element.scrollIntoView({block: 'center'})")
            self.assertTrue(
                action.evaluate(
                    """element => {
                        const box = element.getBoundingClientRect();
                        const hit = document.elementFromPoint(
                            box.left + box.width / 2, box.top + box.height / 2
                        );
                        return element === hit || element.contains(hit);
                    }"""
                )
            )

        page.set_viewport_size({"width": 320, "height": 720})
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )

    def test_mobile_touch_accessible_names_and_reduced_motion_survive_reflow(self) -> None:
        touch_context = self.browser.new_context(
            viewport={"width": 390, "height": 844},
            bypass_csp=True,
            has_touch=True,
            is_mobile=True,
            reduced_motion="reduce",
            storage_state=self.context.storage_state(),
        )
        touch_page = touch_context.new_page()

        def add_touch_gate_fixture(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 2:
                home["featured"] = [
                    {
                        "key": f"touch-featured-{index}",
                        "origin": {"kind": "catalog"},
                        "item": {
                            **items[index],
                            "id": f"touch-featured-item-{index}",
                            "title": f"Función táctil {index + 1}",
                        },
                        "reason": {"label": "Selección táctil", "detail": "Disponible."},
                    }
                    for index in range(2)
                ]
                home["hero"] = home["featured"][0]

                def shelf_entry(section_id: str, index: int) -> dict[str, Any]:
                    item = items[index % len(items)]
                    return {
                        "key": f"{section_id}-touch-{index}",
                        "origin": {"kind": "catalog"},
                        "item": {
                            **item,
                            "id": f"{section_id}-touch-item-{index}",
                            "title": f"{section_id.title()} obra {index + 1}",
                        },
                        "reason": {
                            "label": "Selección del archivo",
                            "detail": "Disponible para el gate táctil.",
                        },
                    }

                home["sections"] = [
                    {
                        "id": section_id,
                        "title": title,
                        "items": [shelf_entry(section_id, index) for index in range(6)],
                    }
                    for section_id, title in (
                        ("available", "Disponible esta noche"),
                        ("memory", "Tu archivo pide memoria"),
                    )
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        try:
            touch_page.route("**/api/items?*", add_touch_gate_fixture)
            self._open_and_wait_for_catalog(touch_page)
            self.assertTrue(
                touch_page.evaluate("window.matchMedia('(prefers-reduced-motion: reduce)').matches")
            )

            playback_before = touch_page.evaluate("window.getHomePlaybackState()")
            self.assertFalse(touch_page.evaluate("window.tickHomeAutoplay()"))
            self.assertEqual(
                touch_page.evaluate("window.getHomePlaybackState().carouselItemId"),
                playback_before["carouselItemId"],
            )

            furniture = touch_page.get_by_role("region", name="Videoteca")
            self.assertTrue(furniture.is_visible())
            memory_spine = touch_page.locator('[data-home-section="memory"] .home-shelf-tape').nth(
                2
            )
            accessible_name = memory_spine.get_attribute("aria-label") or ""
            self.assertIn("Memory obra 3", accessible_name)
            self.assertIn("Opción 3", accessible_name)

            memory_spine.tap()
            # U4.6b: each shelf's own preview became the single console above the shelves,
            # which names the shelf and the entry it shows.
            console = touch_page.locator(".spotlight-preview")
            self.assertEqual(console.get_attribute("data-selection-source"), "shelf:memory")
            self.assertEqual(memory_spine.get_attribute("aria-pressed"), "true")
            self.assertEqual(console.get_attribute("data-selected-entry-key"), "memory-touch-2")
            self.assertEqual(
                touch_page.locator("#spotlight-selected-title").text_content(),
                "Memory obra 3",
            )

            view_more = console.get_by_role("button", name="Ver más")
            view_more.tap()
            touch_page.wait_for_selector("#detailDrawer[open]")
            self.assertEqual(touch_page.evaluate("document.activeElement.id"), "closeDetail")
            touch_page.locator("#closeDetail").tap()
            touch_page.wait_for_selector("#detailDrawer:not([open])", state="hidden")

            for width, height in ((390, 844), (320, 720)):
                touch_page.set_viewport_size({"width": width, "height": height})
                self.assertFalse(
                    touch_page.evaluate(
                        "document.documentElement.scrollWidth > window.innerWidth + 1"
                    ),
                    width,
                )
                self.assertTrue(
                    touch_page.get_by_role("region", name="Videoteca").is_visible(),
                    width,
                )
                target_size = touch_page.locator(
                    '[data-home-section="memory"] .home-shelf-tape[aria-pressed="true"]'
                ).bounding_box()
                self.assertIsNotNone(target_size, width)
                self.assertGreaterEqual(target_size["width"], 44, width)
                self.assertGreaterEqual(target_size["height"], 44, width)
        finally:
            touch_context.close()

    def test_home_empty_payload_exposes_recovery_without_empty_furniture(self) -> None:
        page = self.page

        def empty_home(route) -> None:
            response = route.fetch()
            payload = response.json()
            home = payload.get("home") or {}
            home["featured"] = []
            home["sections"] = []
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", empty_home)
        self._open_and_wait_for_catalog(page)

        self.assertTrue(page.locator(".spotlight-stage.is-empty").is_visible())
        self.assertIn(
            "la pantalla espera una obra disponible",
            page.locator(".spotlight-stage.is-empty").inner_text().casefold(),
        )
        self.assertEqual(page.locator("[data-playlist-entry]").count(), 0)
        self.assertTrue(page.locator("#homeEmpty").is_visible())
        self.assertTrue(page.locator("#homeFurniture").is_hidden())
        self.assertTrue(page.locator("#homeShelfCategories").is_hidden())
        self.assertEqual(page.locator("#homeEmpty button").count(), 3)

    def test_home_single_category_long_content_and_broken_posters_remain_contained(
        self,
    ) -> None:
        page = self.page
        long_title = (
            "La extraordinaria e interminable historia del archivo que volvió de medianoche"
        )
        long_genre = "Ciencia ficción especulativa y memoria cinematográfica latinoamericana"

        def extreme_home(route) -> None:
            response = route.fetch()
            payload = response.json()
            item = {
                **payload["items"][0],
                "title": long_title,
                "genres": [long_genre, "Drama psicológico de expansión internacional"],
                "page_image": "https://example.invalid/r7b-broken-poster.jpg",
            }
            entry = {
                "key": "r7b-extreme-entry",
                "origin": {"kind": "catalog"},
                "item": item,
                "reason": {"label": "Selección del archivo", "detail": "Disponible."},
            }
            payload["home"]["featured"] = [entry]
            payload["home"]["sections"] = [
                {
                    "id": "r7b-single",
                    "title": "Una sola categoría con un nombre deliberadamente extenso",
                    "items": [entry],
                }
            ]
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", extreme_home)
        page.set_viewport_size({"width": 1280, "height": 720})
        self._open_and_wait_for_catalog(page)

        self.assertEqual(page.locator(".home-shelf-bay").count(), 1)
        self.assertEqual(page.locator("#homeSections").get_attribute("data-bay-count"), "1")
        self.assertTrue(page.locator("#homeShelfCategories").is_hidden())
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )
        brand_metrics = page.locator("h1").evaluate(
            """element => ({
                clientWidth: element.clientWidth,
                scrollWidth: element.scrollWidth,
                lockupWidth: element.closest('.brand-lockup').clientWidth,
            })"""
        )
        self.assertLessEqual(
            brand_metrics["scrollWidth"],
            brand_metrics["clientWidth"] + 1,
            brand_metrics,
        )

        selected_row = page.locator("[data-playlist-entry]")
        self.assertIn(long_title, selected_row.get_attribute("aria-label"))
        self.assertIn(long_genre, selected_row.get_attribute("aria-label"))
        self.assertIn(
            long_title,
            page.locator("[data-home-section] .home-shelf-tape").get_attribute("aria-label"),
        )

        # U4.6b: the console and the consulted poster exist once a spine is chosen.
        page.locator(".home-shelf-tape").first.click()
        console = page.locator('.spotlight-preview[data-selection-source="shelf:r7b-single"]')
        console.wait_for()

        # Let the browser's real network failures settle before replaying load/error
        # events. Otherwise a late error from example.invalid can race the synthetic
        # load below when this case runs as part of the complete browser suite.
        page.wait_for_function(
            """() => {
                const images = [...document.querySelectorAll('img')].filter(
                    image => (image.getAttribute('src') || '').includes('r7b-broken-poster')
                );
                return images.length >= 2 && images.every(image => image.hidden === true);
            }"""
        )

        marquee = page.locator(".spotlight-selector:not(.home-consulted-poster)")
        marquee_image = marquee.locator("[data-spotlight-image]")
        marquee_fallback = marquee.locator(".spotlight-poster-trigger > .spotlight-poster-fallback")
        marquee_image.dispatch_event("load")
        self.assertTrue(marquee_fallback.is_hidden())
        marquee_image.dispatch_event("error")
        self.assertTrue(marquee_image.is_hidden())
        self.assertTrue(marquee_fallback.is_visible())
        self.assertIn("sin portada", marquee_fallback.inner_text().casefold())

        consulted = page.locator(".home-consulted-poster")
        consulted_image = consulted.locator("[data-spotlight-image]")
        consulted_fallback = consulted.locator(".spotlight-poster-fallback")
        consulted_image.dispatch_event("load")
        self.assertTrue(consulted_fallback.is_hidden())
        consulted_image.dispatch_event("error")
        self.assertTrue(consulted_image.is_hidden())
        self.assertTrue(consulted_fallback.is_visible())

        self.assertEqual(console.locator("img").count(), 0)

        for width, height in ((1440, 900), (1920, 1080)):
            page.set_viewport_size({"width": width, "height": height})
            self.assertFalse(
                page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"),
                (width, height),
            )
            self.assertTrue(
                page.locator("h1").evaluate(
                    "element => element.scrollWidth <= element.clientWidth + 1"
                ),
                (width, height),
            )

    def test_header_utilities_open_collection_search_and_add(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        click_desktop_menu_action(page, "search")
        page.wait_for_selector("#collectionView:not([hidden])")
        page.wait_for_function("document.activeElement.id === 'query'")

        page.locator(".brand-home").click()
        page.wait_for_selector("#homeView:not([hidden])")
        page.wait_for_function("document.querySelector('#stats').textContent.includes('2 obras')")

        click_desktop_menu_action(page, "add")
        page.wait_for_selector("#collectionView:not([hidden])")
        page.wait_for_function("document.activeElement.id === 'query'")
        self.assertEqual(page.locator("#collectionView").get_attribute("data-search-mode"), "add")

    def test_collection_task_modes_and_history(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)
        page.locator("#catalogButton").click()
        collection = page.locator("#collectionView")
        self.assertEqual(collection.get_attribute("data-search-mode"), "browse")
        self.assertTrue(page.locator(".search-main").is_hidden())
        self.assertNotIn("mode=", page.url)

        first_status = page.locator("#statusQuickFilters button").first
        first_status.click()
        selected_status = first_status.get_attribute("data-value")
        self.assertIn(f"status={selected_status}", page.url)

        page.locator('[data-mode="search"]').click()
        page.wait_for_function("document.activeElement.id === 'query'")
        self.assertIn("mode=search", page.url)
        page.locator("#query").fill("Heat")
        page.evaluate("window.scrollTo(0, 180)")
        page.locator("#searchButton").click()
        page.wait_for_function("new URL(location.href).searchParams.get('q') === 'Heat'")
        search_scroll = page.evaluate("window.scrollY")

        page.locator('#collectionModeTabs [data-mode="add"]').click()
        self.assertEqual(collection.get_attribute("data-search-mode"), "add")
        self.assertIn("mode=add", page.url)
        self.assertNotIn("status=", page.url)
        page.wait_for_function("document.activeElement.id === 'query'")

        page.go_back()
        page.wait_for_function(
            "document.querySelector('#collectionView').dataset.searchMode === 'search'"
        )
        self.assertEqual(page.locator("#query").input_value(), "Heat")
        self.assertIn(f"status={selected_status}", page.url)
        page.wait_for_function("document.activeElement.id === 'searchButton'")
        self.assertAlmostEqual(page.evaluate("window.scrollY"), search_scroll, delta=2)

    def test_home_marquee_shows_the_available_billboard_label_and_decorative_ambience(
        self,
    ) -> None:
        page = self.page
        marquee_featured: list[dict[str, Any]] = []

        def add_marquee_items(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if items:
                home["featured"] = [
                    {
                        "key": f"marquee-{index}",
                        "origin": {"kind": "catalog"},
                        "item": {
                            **items[index % len(items)],
                            "id": f"marquee-item-{index}",
                            "title": f"Cartelera {index + 1}",
                            "page_image": "https://example.invalid/marquee-test-poster.svg",
                        },
                    }
                    for index in range(6)
                ]
                home["limits"] = {**(home.get("limits") or {}), "featured_items": 6}
                marquee_featured[:] = home["featured"]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        def serve_marquee_date(route) -> None:
            response = route.fetch()
            payload = response.json()
            requested_date = route.request.url.split("date=", 1)[1].split("&", 1)[0]
            payload["generated_for"] = requested_date
            payload["featured"] = marquee_featured
            payload["limits"] = {**(payload.get("limits") or {}), "featured_items": 6}
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_marquee_items)
        page.route("**/api/home?*", serve_marquee_date)
        page.route(
            "**/image-cache?*",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body=(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" '
                    'viewBox="0 0 600 900"><rect width="600" height="900" fill="#101727"/>'
                    '<rect x="12" y="12" width="576" height="876" fill="none" '
                    'stroke="#efb83e" stroke-width="24"/><path d="M0 0L600 900M600 0L0 900" '
                    'stroke="#20d7df" stroke-width="18"/><circle cx="300" cy="420" '
                    'r="130" fill="#ff2e95"/><text x="300" y="760" text-anchor="middle" '
                    'fill="white" font-size="54">POSTER</text></svg>'
                ),
            ),
        )
        self._open_and_wait_for_catalog(page)
        probe = Path(__file__).with_name("home_visual_metrics.js").read_text(encoding="utf-8")
        for width, height in ((1280, 720), (1440, 900), (1920, 1080)):
            page.set_viewport_size({"width": width, "height": height})
            metrics = page.evaluate(probe)
            self.assertEqual(metrics["rowCount"], 6)
            self.assertLessEqual(metrics["localTableScroll"], 1)
            self.assertFalse(metrics["rowsOverlapConsole"])
            self.assertLessEqual(metrics["overflow"], 1)
            self.assertEqual(metrics["posterCount"], 2)
            self.assertAlmostEqual(metrics["posterWidthDifference"], 0, delta=1)
            self.assertAlmostEqual(metrics["consoleWidthDifference"], 0, delta=1)
        self.assertEqual(
            page.locator("#spotlightTitle").inner_text().strip().casefold(), "cartelera disponible"
        )
        self.assertTrue(page.locator(".spotlight-ambience").is_hidden())
        self.assertEqual(page.locator(".spotlight-preview-signal").count(), 0)
        self.assertEqual(page.locator(".spotlight-selector-options").count(), 0)
        for selector in page.locator(".spotlight-selector").all():
            heading = selector.locator(".spotlight-selector-heading")
            bounds = selector.bounding_box()
            label = heading.bounding_box()
            self.assertAlmostEqual(
                label["x"] + label["width"] / 2, bounds["x"] + bounds["width"] / 2, delta=1
            )
            self.assertEqual(
                selector.locator(".spotlight-poster").evaluate(
                    "node => getComputedStyle(node).objectFit"
                ),
                "contain",
            )
        date_control = page.locator(".spotlight-playlist-head")
        date_control.locator('[data-click="home-date-yesterday"]').click()
        page.wait_for_function(
            "document.querySelector('.spotlight-selector-heading span')?.textContent.trim() "
            "=== 'Ayer'"
        )
        # CSS uppercases the label, so read the page text like the date above.
        consulted_poster = page.locator(".home-consulted-poster")
        self.assertEqual(
            consulted_poster.locator(".spotlight-selector-heading").text_content(),
            "En consulta",
        )

    def test_home_typography_is_local_scoped_and_works_with_csp(self) -> None:
        # Fresh context: exercise the real CSP, not the shared bypass used by other tests.
        context = self.browser.new_context(storage_state=self.context.storage_state())
        try:
            page = context.new_page()
            page.goto(self.base_url)
            page.locator('#stats:has-text("2 obras")').wait_for()
            page.locator(".vhs-spine-title").first.wait_for()
            page.evaluate("document.fonts.ready")
            for name in (
                "barlow-condensed-600-latin",
                "ibm-plex-mono-400-latin",
                "oswald-400-latin",
            ):
                response = page.request.get(f"{self.base_url}/static/fonts/{name}.woff2")
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["content-type"], "font/woff2")
            # U4.6b: the console that replaced the shelf preview appears once a spine is chosen.
            page.locator(".home-shelf-tape").first.click()
            page.locator("#spotlight-selected-title").wait_for()
            session = context.new_cdp_session(page)
            session.send("DOM.enable")
            session.send("CSS.enable")
            root = session.send("DOM.getDocument")["root"]["nodeId"]
            for selector, family, weight in (
                (".vhs-spine-title", "Barlow Condensed", "600"),
                (".home-shelf-bay-plaque > span", "Oswald", "400"),
                (".home-shelf-bay-plaque > small", "IBM Plex Mono", "400"),
                ("#spotlight-selected-title", "Oswald", "400"),
                (".spotlight-preview .spotlight-preview-facts dd", "IBM Plex Mono", "400"),
            ):
                element = page.locator(selector).first
                element.evaluate("el => el.textContent = 'ÁÉÍÓÚÜÑ áéíóúüñ ¿Año? 2026 Łódź'")
                page.evaluate("document.fonts.ready")
                node = session.send("DOM.querySelector", {"nodeId": root, "selector": selector})
                fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
                self.assertTrue(fonts["fonts"])
                self.assertTrue(all(font["isCustomFont"] for font in fonts["fonts"]), fonts)
                self.assertTrue(all(family in font["familyName"] for font in fonts["fonts"]))
                self.assertEqual(element.evaluate("el => getComputedStyle(el).fontWeight"), weight)
                self.assertEqual(element.evaluate("el => getComputedStyle(el).fontStyle"), "normal")
            self.assertNotIn(
                "Barlow", page.locator("h1").evaluate("el => getComputedStyle(el).fontFamily")
            )
            font_urls = page.evaluate(
                "performance.getEntriesByType('resource').filter(e => e.name.endsWith('.woff2'))"
                ".map(e => e.name)"
            )
            self.assertTrue(font_urls)
            self.assertTrue(
                all(url.startswith(self.base_url + "/static/fonts/") for url in font_urls)
            )
            for width in (1920, 1440, 1280, 720, 390, 320):
                page.set_viewport_size({"width": width, "height": 900})
                self.assertFalse(
                    page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                )
        finally:
            context.close()

    def test_home_font_failure_keeps_text_and_navigation_usable(self) -> None:
        page = self.page
        page.route("**/*.woff2", lambda route: route.abort())
        self._open_and_wait_for_catalog(page)
        page.evaluate("document.fonts.ready")
        self.assertFalse(page.evaluate("document.fonts.check('600 16px \"Barlow Condensed\"')"))
        self.assertFalse(page.evaluate("document.fonts.check('400 16px \"Oswald\"')"))
        for width in (1280, 390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            title = page.locator(".vhs-spine-title").first
            self.assertTrue(title.is_visible())
            self.assertTrue(title.inner_text())
            plaque = page.locator(".home-shelf-bay-plaque").first
            self.assertTrue(plaque.is_visible())
            self.assertTrue(plaque.inner_text())
            self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"))
        page.locator(".home-shelf-tape").first.focus()
        page.keyboard.press("Enter")
        self.assertTrue(
            page.locator(".spotlight-preview")
            .get_attribute("data-selection-source")
            .startswith("shelf:")
        )
        self.assertTrue(page.locator("#spotlight-selected-title").is_visible())

    def test_home_material_plaques_and_inset_spines_keep_geometry_on_desktop_and_mobile(
        self,
    ) -> None:
        page = self.page
        label = 'Colección "Noches del archivo" & otras historias para volver a descubrir'

        def add_long_category(route) -> None:
            response = route.fetch()
            payload = response.json()
            payload["home"]["sections"] = [
                {
                    "id": "plaque-review",
                    "title": label,
                    "items": [
                        {
                            "key": "plaque-item",
                            "origin": {"kind": "catalog"},
                            "item": payload["items"][0],
                        }
                    ],
                }
            ]
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_long_category)
        page.set_viewport_size({"width": 1440, "height": 900})
        self._open_and_wait_for_catalog(page)
        page.evaluate("document.fonts.ready")
        plaque = page.locator(".home-shelf-bay-plaque").first
        self.assertEqual(plaque.get_attribute("title"), label)
        self.assertEqual(plaque.locator("span").text_content(), label)
        self.assertIn(
            "home-category-plaque-inset-v1.png",
            plaque.evaluate("node => getComputedStyle(node, '::before').backgroundImage"),
        )
        self.assertIn(
            "Oswald", plaque.locator("span").evaluate("node => getComputedStyle(node).fontFamily")
        )
        self.assertEqual(
            plaque.locator("span").evaluate("node => getComputedStyle(node).fontWeight"), "400"
        )
        probe = Path(__file__).with_name("home_visual_metrics.js").read_text(encoding="utf-8")
        for width in (1280, 1440, 1920, 390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            metrics = page.evaluate(probe)
            self.assertLessEqual(metrics["overflow"], 1, metrics)
            # Desktop gives the space of the retired Videoteca row to the spines.
            self.assertAlmostEqual(metrics["spineHeight"], 348 if width > 860 else 308, delta=1)
            self.assertAlmostEqual(metrics["plateHeight"], 54, delta=1)
            self.assertGreaterEqual(metrics["plateGap"], 0, metrics)
            self.assertEqual(metrics["spineTransform"], "none", metrics)
            if width > 860:
                self.assertAlmostEqual(metrics["contactGap"], 2, delta=1)
            self.assertEqual(plaque.locator("span").text_content(), label)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator(".home-shelf-tape").first.click()
        metrics = page.evaluate(probe)
        self.assertEqual(metrics["spineTransform"], "none")
        self.assertAlmostEqual(metrics["contactGap"], 2, delta=1)

    def test_home_poster_replaces_dots_and_keeps_keyboard_navigation(self) -> None:
        page = self.page

        def add_second_featured(route) -> None:
            response = route.fetch()
            payload = response.json()
            home = payload.get("home") or {}
            items = payload.get("items") or []
            if len(items) >= 2:
                home["featured"] = [
                    {
                        "key": "browser-selector-heat",
                        "item": items[0],
                        "origin": {"kind": "catalog"},
                        "reason": {
                            "label": "Función destacada",
                            "detail": "Disponible para la prueba del selector.",
                        },
                    },
                    {
                        "key": "browser-selector-alternate",
                        "item": items[1],
                        "origin": {"kind": "catalog"},
                        "reason": {
                            "label": "Otra función disponible",
                            "detail": "Alternativa para la prueba del selector.",
                        },
                    },
                ]
                home["hero"] = home["featured"][0]
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_second_featured)
        self._open_and_wait_for_catalog(page)
        selector = page.locator('[data-click="spotlight-select"]')
        self.assertEqual(page.locator(".spotlight-selector-option").count(), 0)
        self.assertEqual(page.locator(".spotlight-selector button").count(), 2)
        self.assertEqual(selector.get_attribute("aria-describedby"), "spotlight-navigation-help")
        self.assertEqual(page.locator(".spotlight-signal-wave").count(), 0)

        selector.focus()
        selected_before = page.evaluate("window.getHomePlaybackState().selectedEntryKey")
        page.keyboard.press("ArrowDown")

        self.assertEqual(page.evaluate("document.activeElement.dataset.index"), "1")
        self.assertEqual(page.evaluate("document.activeElement.dataset.click"), "spotlight-select")
        self.assertIn(
            "Recomendación 2 de 2", page.locator("#spotlight-navigation-help").inner_text()
        )
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), selected_before
        )
        self.assertFalse(page.evaluate("window.tickHomeAutoplay()"))
        self.assertEqual(selector.get_attribute("data-index"), "1")
        for key, expected in (
            ("ArrowRight", "0"),
            ("ArrowLeft", "1"),
            ("Home", "0"),
            ("End", "1"),
            ("ArrowUp", "0"),
        ):
            page.keyboard.press(key)
            self.assertEqual(page.evaluate("document.activeElement.dataset.index"), expected)
        page.keyboard.press("End")
        page.keyboard.press("Enter")
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"),
            "browser-selector-alternate",
        )

        page.keyboard.press("Tab")
        self.assertIn(
            page.evaluate("document.activeElement.dataset.click"),
            {
                "spotlight-select",
                "playlist-select",
                "home-date-today",
                "home-date-yesterday",
            },
        )
        self.assertTrue(page.evaluate("window.tickHomeAutoplay()"))
        page.locator("[data-playlist-entry]").nth(1).click()
        self.assertEqual(
            page.locator(".home-consulted-poster").get_attribute("data-consulted-key"),
            "browser-selector-alternate",
        )
        page.locator("[data-playlist-entry]").nth(0).click()
        self.assertEqual(
            page.locator(".home-consulted-poster").get_attribute("data-consulted-key"),
            "browser-selector-heat",
        )
        page.set_viewport_size({"width": 390, "height": 844})
        self.assertFalse(page.locator(".spotlight-date-control-mobile").is_visible())
        self.assertTrue(page.locator(".spotlight-date-control-desktop").is_visible())
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )

    def test_home_playlist_columns_and_autoplay_keep_manual_selection_and_focus(self) -> None:
        page = self.page

        def add_playlist_features(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 2:
                titles = ("Heat", "Akira", "Videodrome", "Paris, Texas", "Possession", "Cure")
                home["featured"] = [
                    {
                        "key": f"playlist-{index}",
                        "origin": {"kind": "catalog"},
                        "item": {
                            **items[index % 2],
                            "id": f"playlist-item-{index}",
                            "title": title,
                            "directors": [f"Director {index + 1}"],
                            "year": str(1981 + index),
                            "duration_minutes": 96 + index,
                        },
                    }
                    for index, title in enumerate(titles)
                ]
                home["limits"] = {**(home.get("limits") or {}), "featured_items": 6}
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_playlist_features)
        self._open_and_wait_for_catalog(page)

        self.assertEqual(
            [
                value.casefold()
                for value in page.locator(".spotlight-playlist thead th").all_inner_texts()
            ],
            ["#", "título", "director", "año", "tipo", "géneros", "duración"],
        )
        rows = page.locator("[data-playlist-entry]")
        self.assertEqual(rows.count(), 6)
        self.assertEqual(rows.nth(0).locator(".playlist-director").inner_text(), "Director 1")
        self.assertEqual(rows.nth(0).locator(".playlist-index").inner_text(), "")
        self.assertEqual(rows.nth(1).locator(".playlist-index").inner_text(), "02")
        self.assertEqual(
            rows.nth(0)
            .locator(".playlist-index")
            .evaluate("element => getComputedStyle(element, '::before').content"),
            '"▸"',
        )
        rows.nth(1).click()
        selected_key = rows.nth(1).get_attribute("data-entry-key")
        rows.nth(1).focus()
        before = page.evaluate("window.getHomePlaybackState()")
        self.assertEqual(before["selectedEntryKey"], selected_key)
        page.evaluate("window.tickHomeAutoplay()")
        after = page.evaluate("window.getHomePlaybackState()")
        self.assertEqual(after["selectedEntryKey"], selected_key)
        self.assertEqual(page.evaluate("document.activeElement.dataset.entryKey"), selected_key)
        self.assertEqual(
            page.locator("[data-playlist-entry].is-selected").get_attribute("data-entry-key"),
            selected_key,
        )
        self.assertEqual(page.locator("[data-playlist-entry].is-on-air").count(), 1)

        page.keyboard.press("Enter")
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.click"),
            "open-detail-with-case-transition",
        )

        self.assertEqual(
            page.locator('[data-click="spotlight-prev"], [data-click="spotlight-next"]').count(), 0
        )
        page.locator('[data-click="spotlight-select"]').focus()
        page.keyboard.press("End")
        self.assertEqual(page.evaluate("window.getHomePlaybackState().spotlightIndex"), 5)
        self.assertEqual(page.evaluate("document.activeElement.dataset.click"), "spotlight-select")
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), selected_key
        )

        page.locator("#catalogButton").click()
        page.wait_for_selector("#collectionView:not([hidden])")
        hidden_before = page.evaluate("window.getHomePlaybackState().carouselItemId")
        self.assertFalse(page.evaluate("window.tickHomeAutoplay()"))
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().carouselItemId"), hidden_before
        )

        page.goto(BrowserInterfaceTests.base_url)
        page.wait_for_selector("#homeView:not([hidden])")
        page.set_viewport_size({"width": 1280, "height": 720})
        # U4.6b: measure Home once it is drawn. Right after it shows, the playlist rows and
        # the console are still missing and the page reads 218 px shorter than it is.
        page.wait_for_selector("[data-playlist-entry]")
        page.wait_for_selector(".spotlight-preview")
        home_metrics = """() => ({
            viewport: window.innerHeight,
            page: document.documentElement.scrollHeight,
            header: document.querySelector('.app-header')?.getBoundingClientRect().height || 0,
            spotlight: document.querySelector('#spotlight')?.getBoundingClientRect().height || 0,
            categories: document.querySelector(
                '#homeShelfCategories'
            )?.getBoundingClientRect().height || 0,
            sections: document.querySelector('#homeSections')?.getBoundingClientRect().height || 0
        })"""
        viewport_metrics = page.evaluate(home_metrics)
        # DESIGN.md (U4.2c) replaced U2-R.6's "viewport + 320" budget: the upper opening
        # keeps at least 484 px and Home is not compressed to fit 720 px of height, so part
        # of the console sits below the fold.
        self.assertGreater(viewport_metrics["page"], viewport_metrics["viewport"])
        self.assertGreaterEqual(viewport_metrics["spotlight"], 484, viewport_metrics)
        blocks = sum(
            viewport_metrics[name] for name in ("header", "spotlight", "categories", "sections")
        )
        # Beyond those four blocks the page only adds the videotheque heading and the
        # spacing around them, 90 px when this was written.
        self.assertLessEqual(viewport_metrics["page"], blocks + 120, viewport_metrics)
        page.set_viewport_size({"width": 1280, "height": 1000})
        page.wait_for_timeout(150)
        taller_metrics = page.evaluate(home_metrics)
        self.assertGreaterEqual(
            viewport_metrics["spotlight"],
            taller_metrics["spotlight"] - 1,
            (viewport_metrics, taller_metrics),
        )

    def test_desktop_menu_duplicate_commands_close_details_and_navigate(self) -> None:
        page = self.page

        def open_menu() -> None:
            open_desktop_menu(page)
            self.assertTrue(page.locator("#systemMenu").get_attribute("open") is not None)

        self._open_and_wait_for_catalog(page)
        open_menu()
        page.locator('[data-click="menu-inbox"]').click()
        page.wait_for_selector("#inboxView:not([hidden])")
        self.assertIsNone(page.locator("#systemMenu").get_attribute("open"))

        page.goto(BrowserInterfaceTests.base_url)
        page.wait_for_selector("#homeView:not([hidden])")
        open_menu()
        page.locator('[data-click="menu-club"]').click()
        page.wait_for_selector("#clubView:not([hidden])")
        self.assertIsNone(page.locator("#systemMenu").get_attribute("open"))

        page.goto(BrowserInterfaceTests.base_url)
        page.wait_for_selector("#homeView:not([hidden])")
        open_menu()
        page.locator('[data-click="menu-search"]').click()
        page.wait_for_selector("#collectionView:not([hidden])")
        self.assertIsNone(page.locator("#systemMenu").get_attribute("open"))

        page.goto(BrowserInterfaceTests.base_url)
        page.wait_for_selector("#homeView:not([hidden])")
        open_menu()
        page.locator('[data-click="menu-add"]').click()
        page.wait_for_selector("#collectionView:not([hidden])")
        self.assertIsNone(page.locator("#systemMenu").get_attribute("open"))

    def test_opening_the_menu_waits_for_a_slow_first_load(self) -> None:
        # The router closes the system menu when it restores the route after the
        # first catalog load. A menu opened before that closes under the next
        # click -- which used to fail the tests above whenever the machine was slow
        # enough for the load to lose the race. Delaying the load makes the race
        # certain, so the helpers cannot quietly stop waiting.
        page = self.page

        def slow_catalog(route) -> None:
            time.sleep(1.5)
            route.continue_()

        page.route("**/api/items*", slow_catalog)
        page.goto(BrowserInterfaceTests.base_url)
        page.wait_for_selector("#homeView:not([hidden])")

        click_desktop_menu_action(page, "club")

        page.wait_for_selector("#clubView:not([hidden])")

    def test_home_shelves_use_existing_sections_with_keyboard_preview_and_touch_scroll(
        self,
    ) -> None:
        page = self.page

        def add_home_shelves(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 2:
                home["sections"] = [
                    {
                        "id": "available",
                        "eyebrow": "Para ver ahora",
                        "title": "Disponible esta noche",
                        "description": (
                            "Pendientes que tu biblioteca física confirma como disponibles."
                        ),
                        "action": {
                            "kind": "catalog",
                            "label": "Ver colección",
                            "filters": {
                                "status": ["to_watch"],
                                "availability": ["available"],
                            },
                        },
                        "items": [
                            {
                                "key": "available-heat",
                                "origin": {"kind": "catalog"},
                                "item": items[0],
                                "reason": {
                                    "label": "Lista para ver",
                                    "detail": "El inventario confirma que está disponible.",
                                },
                            },
                            {
                                "key": "available-akira",
                                "origin": {"kind": "catalog"},
                                "item": items[1],
                                "reason": {
                                    "label": "Lista para ver",
                                    "detail": "El inventario confirma que está disponible.",
                                },
                            },
                            # Padding entries: real spines are narrow, so a couple
                            # of them may not overflow a mobile viewport on their
                            # own. More entries make the horizontal-scroll
                            # assertion below meaningful regardless of width.
                            *(
                                {
                                    "key": f"available-padding-{padding_index}",
                                    "origin": {"kind": "catalog"},
                                    "item": items[padding_index % 2],
                                    "reason": {
                                        "label": "Lista para ver",
                                        "detail": "El inventario confirma que está disponible.",
                                    },
                                }
                                for padding_index in range(6)
                            ),
                        ],
                    }
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_home_shelves)
        self._open_and_wait_for_catalog(page)
        self.assertEqual(page.locator(".home-shelf-bay").count(), 1)
        self.assertEqual(page.locator(".home-shelf-scroll-control").count(), 0)
        shelf = page.locator('[data-home-section="available"] .home-shelf-tape')
        self.assertEqual(shelf.count(), 8)
        self.assertEqual(shelf.nth(0).get_attribute("tabindex"), "0")
        self.assertEqual(shelf.nth(1).get_attribute("tabindex"), "-1")
        self.assertEqual(shelf.nth(0).get_attribute("data-vhs-state"), "closed")
        self.assertEqual(shelf.nth(1).get_attribute("data-vhs-state"), "closed")
        # U5 selects only on deliberate input, never by initial roving tabindex.
        self.assertEqual(page.locator("[data-home-shelf-preview]").count(), 0)
        self.assertEqual(page.locator(".home-shelf-preview-frame").count(), 0)

        shelf.nth(0).focus()
        page.keyboard.press("ArrowRight")

        self.assertEqual(
            page.evaluate("document.activeElement.dataset.entryKey"), "available-akira"
        )
        self.assertEqual(shelf.nth(1).get_attribute("aria-pressed"), "true")
        self.assertEqual(shelf.nth(1).get_attribute("data-vhs-state"), "selected")
        self.assertEqual(
            page.locator("#spotlight-selected-title").text_content(),
            "Akira",
        )
        self.assertEqual(
            page.locator(".spotlight-preview").get_attribute("data-selection-source"),
            "shelf:available",
        )
        state_before_tab = page.evaluate("window.getHomePlaybackState()")
        page.keyboard.press("Tab")
        self.assertEqual(page.evaluate("window.getHomePlaybackState()"), state_before_tab)

        shelf.nth(0).click()
        self.assertEqual(
            page.locator("#spotlight-selected-title").text_content(),
            "Heat",
        )
        page.set_viewport_size({"width": 390, "height": 844})
        self.assertEqual(
            page.locator(".home-shelf-rail").evaluate(
                "element => getComputedStyle(element).overflowX"
            ),
            "auto",
        )
        self.assertTrue(
            page.locator(".home-shelf-rail").evaluate(
                "element => element.scrollWidth > element.clientWidth"
            )
        )
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )
        page.emulate_media(reduced_motion="reduce")
        self.assertEqual(
            shelf.nth(0).evaluate("element => getComputedStyle(element).transitionDuration"),
            "0s",
        )

    def test_home_spines_keep_vhs_signature_and_accessible_real_type_and_title(self) -> None:
        page = self.page
        titles = [
            "Heat",
            "Ñ" * 22,
            "Ó" * 23,
            "A" * 36,
            "B" * 37,
            'Una noche "especial" <img src=x onerror="alert(1)"> & otra historia',
        ]
        kinds = ["pelicula", "serie", "anime", "documental", "obra", "serie"]

        def add_spine_variants(route) -> None:
            response = route.fetch()
            payload = response.json()
            item = next(item for item in payload["items"] if item["id"] == "heat")
            payload["home"]["sections"] = [
                {
                    "id": "spine-variants",
                    "title": "Lomos de prueba",
                    "items": [
                        {
                            "key": f"spine-variant-{index}",
                            "origin": {"kind": "catalog"},
                            "item": {**item, "title": title, "kind": kinds[index]},
                        }
                        for index, title in enumerate(titles)
                    ],
                }
            ]
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_spine_variants)
        self._open_and_wait_for_catalog(page)
        spines = page.locator('[data-home-section="spine-variants"] .home-shelf-tape')
        self.assertEqual(spines.count(), len(titles))
        self.assertEqual(
            spines.evaluate_all("elements => elements.map(node => node.dataset.titleLength)"),
            ["short", "short", "long", "long", "xlong", "xlong"],
        )
        for index, title in enumerate(titles):
            with self.subTest(title=title):
                spine = spines.nth(index)
                self.assertEqual(spine.get_attribute("title"), title)
                self.assertEqual(spine.locator(".vhs-spine-title").text_content(), title)
                self.assertIn(
                    f"{title}. 1995. Tipo: {kinds[index]}.", spine.get_attribute("aria-label")
                )
                self.assertEqual(spine.locator(".vhs-spine-year").text_content(), "1995")
                self.assertEqual(spine.locator(".vhs-spine-format").text_content(), "VHS")
                self.assertEqual(
                    spine.locator(".vhs-spine-meta").get_attribute("aria-hidden"), "true"
                )
                self.assertEqual(spine.locator("img").count(), 0)
                self.assertIsNone(spine.get_attribute("onerror"))
        spines.first.click()
        console = page.locator('.spotlight-preview[data-selection-source="shelf:spine-variants"]')
        console.get_by_role("button", name="Ver más").click()
        page.wait_for_selector("#detailDrawer[open]")
        self.assertIn("pelicula", page.locator("#detailDrawer").inner_text().lower())

    def test_home_shelf_furniture_has_four_bays_real_overflow_and_wheel_limits(self) -> None:
        page = self.page

        def add_four_home_sections(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if items:
                home["sections"] = [
                    {
                        "id": f"bay-{index}",
                        "title": f"Módulo {index + 1}",
                        "description": "Una selección continua del archivo.",
                        "items": [
                            {
                                "key": f"bay-{index}-item-{item_index}",
                                "origin": {"kind": "catalog"},
                                "item": {
                                    **items[(index + item_index) % len(items)],
                                    "id": f"bay-{index}-item-{item_index}",
                                    "title": (
                                        "La insoportable levedad del ser"
                                        if index == 0 and item_index == 0
                                        else items[(index + item_index) % len(items)]["title"]
                                    ),
                                },
                                "reason": {"label": "Selección", "detail": "Disponible."},
                            }
                            for item_index in range(4)
                        ],
                    }
                    for index in range(4)
                ]
                home["featured"] = [
                    {
                        "key": f"four-bay-featured-{index}",
                        "origin": {"kind": "catalog"},
                        "item": {
                            **items[index % len(items)],
                            "id": f"four-bay-featured-item-{index}",
                            "title": f"Función {index + 1}",
                        },
                    }
                    for index in range(6)
                ]
                home["limits"] = {**(home.get("limits") or {}), "featured_items": 6}
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_four_home_sections)
        self._open_and_wait_for_catalog(page)
        page.set_viewport_size({"width": 1280, "height": 720})

        bays = page.locator(".home-shelf-bay")
        self.assertEqual(bays.count(), 4)
        self.assertTrue(all(bays.nth(index).is_visible() for index in range(4)))
        cabinet = page.locator("#homeFurniture")
        furniture = page.locator("#homeSections")
        self.assertTrue(page.locator(".home-service-spine").is_hidden())
        self.assertEqual(
            page.locator(".home-machine-shell").evaluate(
                "element => getComputedStyle(element).display"
            ),
            "contents",
        )
        self.assertEqual(page.locator("#homeShelfPreview").count(), 0)
        self.assertTrue(furniture.evaluate("element => element.scrollWidth > element.clientWidth"))
        navigation = page.locator("#homeShelfCategories")
        controls = navigation.locator(".home-shelf-scroll-control")
        self.assertTrue(navigation.is_visible())
        self.assertTrue(controls.nth(0).is_disabled())
        self.assertFalse(controls.nth(1).is_disabled())
        # Each bay keeps a real heading; its hidden plaque is now a native button inside it.
        self.assertEqual(page.locator(".home-shelf-bay > h2.home-shelf-heading").count(), 4)
        self.assertEqual(
            page.locator(".home-shelf-bay > h2 > .home-shelf-bay-plaque.sr-only").count(), 4
        )
        self.assertEqual(
            furniture.evaluate("element => getComputedStyle(element).scrollbarWidth"), "thin"
        )
        probe = Path(__file__).with_name("home_visual_metrics.js").read_text(encoding="utf-8")
        geometry = page.evaluate(probe)
        self.assertLessEqual(geometry["overflow"], 1)
        self.assertAlmostEqual(geometry["contactGap"], 2, delta=1)
        bounds = cabinet.evaluate("""element => {
            const cabinet = element.getBoundingClientRect();
            const home = element.closest('#homeView').getBoundingClientRect();
            return {left: cabinet.left - home.left, right: home.right - cabinet.right};
        }""")
        self.assertAlmostEqual(bounds["left"], bounds["right"], delta=1)
        first_spine = page.locator('[data-home-section="bay-0"] .home-shelf-tape').nth(0)
        spine_readability = first_spine.evaluate(
            """element => {
                const spine = element.getBoundingClientRect();
                const titleNode = element.querySelector('.vhs-spine-title');
                const title = titleNode.getBoundingClientRect();
                const titleStyle = getComputedStyle(titleNode);
                const meta = element.querySelector('.vhs-spine-meta');
                const metaRect = meta.getBoundingClientRect();
                const year = element.querySelector('.vhs-spine-year').getBoundingClientRect();
                const format = element.querySelector('.vhs-spine-format').getBoundingClientRect();
                return {
                    titleHeightRatio: title.height / spine.height,
                    footerStacked: year.bottom <= format.top,
                    metaContained: metaRect.bottom <= spine.bottom,
                    titleWritingMode: titleStyle.writingMode,
                    titleTransform: titleStyle.transform,
                    titleStyle: titleStyle.fontStyle,
                    metaWritingMode: getComputedStyle(meta).writingMode,
                };
            }"""
        )
        self.assertGreaterEqual(spine_readability["titleHeightRatio"], 0.5)
        self.assertTrue(spine_readability["footerStacked"])
        self.assertTrue(spine_readability["metaContained"])
        self.assertEqual(spine_readability["titleWritingMode"], "vertical-rl")
        self.assertEqual(spine_readability["titleTransform"], "matrix(-1, 0, 0, -1, 0, 0)")
        self.assertEqual(spine_readability["titleStyle"], "normal")
        self.assertEqual(spine_readability["metaWritingMode"], "horizontal-tb")
        self.assertEqual(
            first_spine.locator(".vhs-spine-meta > span").all_text_contents(),
            ["1995", "VHS"],
        )
        self.assertIn(
            "La insoportable levedad del ser. 1995. Tipo: pelicula.",
            first_spine.get_attribute("aria-label"),
        )
        self.assertGreater(
            page.evaluate("document.documentElement.scrollHeight"),
            page.evaluate("window.innerHeight") + 1,
        )

        start = furniture.evaluate("element => element.scrollLeft")
        page.locator('[data-click="home-shelf-scroll"][data-direction="next"]').click()
        page.wait_for_timeout(350)
        moved = furniture.evaluate("element => element.scrollLeft")
        self.assertGreater(moved, start)

        page.locator('[data-click="home-shelf-scroll"][data-direction="prev"]').click()
        page.wait_for_timeout(350)
        self.assertLessEqual(furniture.evaluate("element => element.scrollLeft"), moved)

        furniture.evaluate(
            "element => element.dispatchEvent(new WheelEvent('wheel', "
            "{deltaY: 420, bubbles: true, cancelable: true}))"
        )
        page.wait_for_timeout(100)
        self.assertGreater(furniture.evaluate("element => element.scrollLeft"), start)

        furniture.evaluate("element => { element.scrollLeft = element.scrollWidth; }")
        page.wait_for_timeout(350)
        final_spine = page.locator('[data-home-section="bay-3"] .home-shelf-tape').last
        end_geometry = final_spine.evaluate(
            """element => {
                const spine = element.getBoundingClientRect();
                const shelf = element.closest('#homeSections').getBoundingClientRect();
                const home = element.closest('#homeView').getBoundingClientRect();
                return {
                    completelyVisible: spine.left >= shelf.left - 1
                        && spine.right <= shelf.right + 1
                        && spine.right <= home.right + 1,
                };
            }"""
        )
        self.assertTrue(end_geometry["completelyVisible"])

        page.emulate_media(reduced_motion="reduce")
        self.assertEqual(
            furniture.evaluate("element => getComputedStyle(element).scrollBehavior"), "auto"
        )

    def test_home_furniture_console_keeps_primary_copy_legible_at_desktop_sizes(self) -> None:
        """U4 B: one shared console; no lower percentage-positioned cabinet."""
        page = self.page
        self._open_and_wait_for_catalog(page)
        page.locator(".home-shelf-tape").first.click()
        probe = Path(__file__).with_name("home_visual_metrics.js").read_text(encoding="utf-8")
        for width, height in ((1280, 720), (1440, 900), (1920, 1080)):
            with self.subTest(viewport=(width, height)):
                page.set_viewport_size({"width": width, "height": height})
                metrics = page.evaluate(probe)
                self.assertLessEqual(metrics["overflow"], 1, metrics)
                self.assertEqual(metrics["consoleCount"], 1, metrics)
                self.assertEqual(metrics["retiredConsoleCount"], 0, metrics)
                self.assertEqual(metrics["posterCount"], 2, metrics)
                self.assertLessEqual(metrics["posterWidthDifference"], 1, metrics)
                self.assertLessEqual(metrics["consoleWidthDifference"], 1, metrics)
                self.assertFalse(metrics["rowsOverlapConsole"], metrics)
                self.assertLessEqual(metrics["localTableScroll"], 1, metrics)
                self.assertEqual(metrics["imageCount"], 0, metrics)
        preview = page.locator(".spotlight-preview")
        self.assertEqual(preview.locator(".spotlight-preview-actions button").count(), 2)
        self.assertEqual(preview.locator(".home-console-details").count(), 1)
        self.assertTrue(preview.locator(".spotlight-copy h3").is_visible())

    def test_home_shelf_furniture_handles_zero_categories_without_empty_controls(self) -> None:
        page = self.page

        def remove_home_sections(route) -> None:
            response = route.fetch()
            payload = response.json()
            home = payload.get("home") or {}
            home["sections"] = []
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", remove_home_sections)
        self._open_and_wait_for_catalog(page)
        self.assertEqual(page.locator(".home-shelf-bay").count(), 0)
        self.assertEqual(page.locator(".home-shelf-scroll-control").count(), 0)
        self.assertTrue(page.locator(".home-videotheque-heading").is_hidden())
        self.assertEqual(page.locator("#homeSections").get_attribute("data-bay-count"), "0")
        self.assertEqual(page.locator("#homeSections").get_attribute("tabindex"), "-1")

    def test_direct_spine_choice_synchronizes_playlist_and_shared_console(
        self,
    ) -> None:
        page = self.page

        def add_sync_sections(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 2:

                def entry(key: str, item_index: int, title: str) -> dict[str, Any]:
                    item = {**items[item_index], "id": f"{key}-item", "title": title}
                    return {
                        "key": key,
                        "origin": {"kind": "catalog"},
                        "item": item,
                        "reason": {"label": "Selección del archivo", "detail": "Disponible."},
                    }

                home["sections"] = [
                    {
                        "id": "available",
                        "title": "Disponible esta noche",
                        "items": [
                            entry("available-heat", 0, "Heat en VHS"),
                            entry("available-akira", 1, "Akira en VHS"),
                        ],
                    },
                    {
                        "id": "memory",
                        "title": "Tu archivo pide memoria",
                        "items": [
                            entry("memory-akira", 1, "Akira recordada"),
                            entry("memory-heat", 0, "Heat recordada"),
                            *[
                                entry(
                                    f"memory-extra-{index}",
                                    index % 2,
                                    f"Recuerdo extra {index + 1}",
                                )
                                for index in range(12)
                            ],
                        ],
                    },
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_sync_sections)
        self._open_and_wait_for_catalog(page)
        self.assertEqual(page.locator("#homeShelfPreview, .home-shelf-preview").count(), 0)

        initial_state = page.evaluate("window.getHomePlaybackState()")
        # Clicking a spine in another visible bay activates that bay and its
        # playlist/consultation. Only the daily poster stays independent (U5).
        memory_spines = page.locator('[data-home-section="memory"] .home-shelf-tape')
        memory_spines.nth(1).click()
        self.assertEqual(page.locator(".spotlight-preview").count(), 1)
        state = page.evaluate("window.getHomePlaybackState()")
        self.assertEqual(state["activeShelfId"], "memory")
        self.assertEqual(state["playlistSource"], "shelf:memory")
        self.assertEqual(state["selectedEntryKey"], "memory-heat")
        self.assertEqual(state["selectedItemId"], "memory-heat-item")
        self.assertEqual(state["selectionSource"], "shelf:memory")
        self.assertEqual(state["carouselItemId"], initial_state["carouselItemId"])
        self.assertEqual(page.locator("#spotlight-selected-title").text_content(), "Heat recordada")
        self.assertEqual(
            page.locator('[data-home-section="memory"]').get_attribute("data-active"),
            "true",
        )
        self.assertEqual(
            page.locator('[data-home-section="available"]').get_attribute("data-active"),
            "false",
        )
        self.assertEqual(
            page.locator(".spotlight-preview").get_attribute("data-selection-source"),
            "shelf:memory",
        )
        self.assertEqual(
            page.locator(".spotlight-preview").get_attribute("data-selected-entry-key"),
            "memory-heat",
        )
        self.assertEqual(
            page.locator(".home-console-heading strong").text_content(),
            "Tu archivo pide memoria",
        )
        self.assertEqual(
            page.locator(
                '[data-home-section="memory"] .home-shelf-tape[aria-pressed="true"]'
            ).get_attribute("data-entry-key"),
            "memory-heat",
        )
        self.assertEqual(
            page.locator("[data-playlist-entry]").evaluate_all(
                "elements => elements.map(element => element.dataset.entryKey)"
            ),
            ["memory-akira", "memory-heat", *[f"memory-extra-{i}" for i in range(12)]],
        )
        self.assertEqual(page.locator('[data-playlist-entry][aria-selected="true"]').count(), 1)
        self.assertEqual(page.locator('[data-playlist-entry][tabindex="0"]').count(), 1)
        self.assertEqual(page.evaluate("document.activeElement.dataset.entryKey"), "memory-heat")

        # Enter on a spine in a different bay follows the same state transition.
        available_spines = page.locator('[data-home-section="available"] .home-shelf-tape')
        available_spines.nth(1).focus()
        page.keyboard.press("Enter")
        state = page.evaluate("window.getHomePlaybackState()")
        self.assertEqual(state["activeShelfId"], "available")
        self.assertEqual(state["playlistSource"], "shelf:available")
        self.assertEqual(state["selectedEntryKey"], "available-akira")
        self.assertEqual(state["selectionSource"], "shelf:available")
        self.assertEqual(
            page.locator(".spotlight-preview").get_attribute("data-selected-entry-key"),
            "available-akira",
        )
        self.assertEqual(
            page.locator(
                '[data-home-section="available"] .home-shelf-tape[aria-pressed="true"]'
            ).get_attribute("data-entry-key"),
            "available-akira",
        )
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.entryKey"), "available-akira"
        )
        focus_ring = available_spines.nth(1).evaluate(
            """element => {
                const style = getComputedStyle(element);
                return { style: style.outlineStyle, width: parseFloat(style.outlineWidth) };
            }"""
        )
        self.assertNotEqual(focus_ring["style"], "none")
        self.assertGreaterEqual(focus_ring["width"], 2)

        # The native plaque button restores that shelf's remembered spine.
        memory_bay = page.locator('[data-click="home-shelf-activate"][data-section-id="memory"]')
        memory_bay.click()
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().playlistSource"), "shelf:memory"
        )
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), "memory-heat"
        )
        self.assertEqual(
            page.locator(".spotlight-preview").get_attribute("data-selected-entry-key"),
            "memory-heat",
        )

        selected_row = page.locator("[data-playlist-entry].is-selected")
        selected_row.focus()
        page_scroll_before = page.evaluate("window.scrollY")
        page.keyboard.press("Home")
        self.assertEqual(page.evaluate("document.activeElement.dataset.entryKey"), "memory-akira")
        self.assertEqual(
            page.locator(
                '[data-home-section="memory"] .home-shelf-tape[data-vhs-state="selected"]'
            ).get_attribute("data-entry-key"),
            "memory-akira",
        )
        page.keyboard.press("End")
        page.wait_for_timeout(350)
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.entryKey"), "memory-extra-11"
        )
        self.assertEqual(
            page.locator("[data-playlist-entry].is-selected").get_attribute("data-entry-key"),
            "memory-extra-11",
        )
        selected_spine = page.locator(
            '[data-home-section="memory"] .home-shelf-tape[data-vhs-state="selected"]'
        )
        self.assertEqual(selected_spine.get_attribute("data-entry-key"), "memory-extra-11")
        self.assertTrue(
            selected_spine.evaluate(
                """element => {
                    const spine = element.getBoundingClientRect();
                    const rail = document.querySelector('#homeSections').getBoundingClientRect();
                    return spine.left >= rail.left - 1 && spine.right <= rail.right + 1;
                }"""
            )
        )
        self.assertGreater(
            page.locator("#homeSections").evaluate("element => element.scrollLeft"),
            0,
        )
        self.assertEqual(page.evaluate("window.scrollY"), page_scroll_before)
        self.assertEqual(
            page.locator(".spotlight-preview").get_attribute("data-selected-entry-key"),
            "memory-extra-11",
        )

        self.assertEqual(page.locator(".spotlight-preview").count(), 1)
        self.assertEqual(page.locator(".spotlight-preview-actions button").count(), 2)

    def _install_u5_source_fixture(self, count: int = 6) -> None:
        """Extended lists are test-only; no production section limit is changed."""

        def fixture(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload["items"]
            daily = [
                {"key": f"shared-{index}", "origin": {"kind": "catalog"}, "item": item}
                for index, item in enumerate(items)
            ]
            payload["home"].update(
                {
                    "featured": daily,
                    "sections": [
                        {
                            "id": "sample",
                            "title": "Memoria del archivo",
                            "items": [
                                {
                                    "key": f"sample-{index}",
                                    "origin": {"kind": "catalog"},
                                    "item": {
                                        **items[index % len(items)],
                                        "title": f"Obra {index + 1:03d} del archivo",
                                    },
                                }
                                for index in range(count)
                            ],
                        },
                        {
                            "id": "club",
                            "title": "Colección seguida",
                            "items": [
                                {
                                    "key": "shared-0",
                                    "origin": {
                                        "kind": "collection",
                                        "collection_id": "club-test",
                                        "collection_title": "Archivo del Club",
                                        "collection_item_id": items[0]["id"],
                                    },
                                    "item": {
                                        **items[0],
                                        "title": "Obra ajena con el mismo identificador",
                                    },
                                }
                            ],
                        },
                    ],
                }
            )
            route.fulfill(response=response, json=payload)

        self.page.route("**/api/items?*", fixture)

    def test_u5_source_counts_keyboard_alignment_and_removal(self) -> None:
        page = self.page
        for count in (0, 1, 6, 20, 100):
            with self.subTest(count=count):
                page.unroute("**/api/items?*")
                self._install_u5_source_fixture(count)
                self._open_and_wait_for_catalog(page)
                if not count:
                    self.assertEqual(page.locator('[data-home-section="sample"]').count(), 0)
                    self.assertEqual(page.locator("[data-playlist-entry]").count(), 2)
                    continue
                plaque = page.locator(
                    '[data-click="home-shelf-activate"][data-section-id="sample"]'
                )
                before = page.evaluate("window.getHomePlaybackState()")
                plaque.focus()
                page.keyboard.press("Tab")
                self.assertEqual(page.evaluate("window.getHomePlaybackState()"), before)
                self.assertEqual(
                    page.evaluate("document.activeElement.dataset.click"), "home-shelf-select"
                )
                page.keyboard.press("Space")
                self.assertEqual(page.locator("[data-playlist-entry]").count(), count)
                self.assertEqual(
                    page.evaluate("document.activeElement.dataset.entryKey"), "sample-0"
                )
                page.locator('[data-playlist-entry][aria-selected="true"]').focus()
                scroll_before = page.evaluate("window.scrollY")
                page.keyboard.press("End")
                self.assertEqual(
                    page.evaluate("document.activeElement.dataset.entryKey"), f"sample-{count - 1}"
                )
                self.assertEqual(page.evaluate("window.scrollY"), scroll_before)
                metrics = page.evaluate(
                    Path(__file__).with_name("home_list_metrics.js").read_text(encoding="utf-8")
                )
                self.assertTrue(metrics["selectedVisible"], metrics)
                self.assertEqual(metrics["extended"], str(count > 6).lower())
                self.assertFalse(metrics["windowOverlapsConsole"], metrics)
                self.assertLessEqual(metrics["overflow"], 1, metrics)
                announcement = page.locator("#homeSelectionAnnouncement").inner_text()
                selected = page.evaluate("window.getHomePlaybackState().selectedEntryKey")
                page.evaluate("window.tickHomeAutoplay()")
                self.assertEqual(
                    page.locator("#homeSelectionAnnouncement").inner_text(), announcement
                )
                self.assertEqual(page.evaluate("document.activeElement.dataset.entryKey"), selected)
                self.assertEqual(
                    page.evaluate("window.getHomePlaybackState().selectedEntryKey"), selected
                )
                # Live data changes use the real renderer; no stale console actions.
                page.evaluate("""async () => {
                    const home = await import('/static/js/surfaces/home.js');
                    home.editorialHome.sections[0].items = [];
                    home.renderEditorialHome();
                }""")
                self.assertEqual(page.locator("[data-playlist-count]").inner_text(), "0 obras")
                self.assertEqual(page.locator(".spotlight-preview").count(), 0)
                self.assertEqual(
                    page.evaluate("document.activeElement.dataset.click"), "home-programming-return"
                )
                page.evaluate("""async () => {
                    const home = await import('/static/js/surfaces/home.js');
                    home.editorialHome.sections.shift();
                    home.renderEditorialHome();
                }""")
                self.assertEqual(
                    page.evaluate("window.getHomePlaybackState().playlistSource"), "daily"
                )
                self.assertEqual(page.locator("[data-playlist-entry]").count(), 2)
                self.assertIn(
                    "Volvimos a programación",
                    page.locator("#homeSelectionAnnouncement").inner_text(),
                )
                self.assertEqual(
                    page.evaluate("document.activeElement.dataset.click"), "home-date-today"
                )

    def test_u5_club_collision_dialog_focus_and_single_announcement(self) -> None:
        page = self.page
        self._install_u5_source_fixture()
        self._open_and_wait_for_catalog(page)
        writes = []
        page.on(
            "request",
            lambda request: (
                writes.append(request.url)
                if request.method in ("POST", "PATCH", "PUT", "DELETE") and "/api/" in request.url
                else None
            ),
        )
        page.evaluate("""() => {
            window.u5Announcements = [];
            new MutationObserver(records => window.u5Announcements.push(...records.map(() =>
                document.querySelector('#homeSelectionAnnouncement').textContent)))
                .observe(document.querySelector('#homeSelectionAnnouncement'), {childList: true});
        }""")
        page.locator('[data-home-section="club"] .home-shelf-tape').click()
        self.assertEqual(len(page.evaluate("window.u5Announcements")), 1)
        page.locator('[data-home-section="club"] .home-shelf-tape').click()
        self.assertEqual(len(page.evaluate("window.u5Announcements")), 1)
        self.assertEqual(
            page.locator('.spotlight-preview [data-click="edit-home-shelf-entry"]').count(), 0
        )
        self.assertEqual(
            page.locator(".home-consulted-poster").get_attribute("data-consulted-source"),
            "shelf:club",
        )
        for surface in ("consultation-view", "consultation-poster"):
            opener = page.locator(f'[data-home-focus="{surface}"]')
            opener.click()
            page.locator("#sharedDetailDialog").wait_for(state="visible")
            self.assertIn(
                "obra ajena con el mismo identificador",
                page.locator("#sharedDetailBody").inner_text().casefold(),
            )
            self.assertEqual(
                page.locator("#sharedDetailDialog").get_by_text("Editar mi ficha").count(), 0
            )
            self.assertFalse(page.evaluate("window.tickHomeAutoplay()"))
            page.keyboard.press("Escape")
            page.locator("#sharedDetailDialog").wait_for(state="hidden")
            self.assertEqual(page.evaluate("document.activeElement.dataset.homeFocus"), surface)
        page.locator('[data-click="home-programming-return"]').click()
        self.assertEqual(page.evaluate("document.activeElement.dataset.click"), "home-date-today")
        self.assertEqual(
            page.locator('.spotlight-preview [data-click="edit-home-shelf-entry"]').count(), 1
        )
        self.assertEqual(writes, [])

    def test_u5_removed_focused_spine_recovers_without_focusing_a_different_origin(self) -> None:
        page = self.page
        self._install_u5_source_fixture()
        self._open_and_wait_for_catalog(page)
        page.locator('[data-home-section="sample"] .home-shelf-tape').nth(1).click()
        page.evaluate("""async () => {
            const home = await import('/static/js/surfaces/home.js');
            home.editorialHome.sections[0].items.splice(1, 1);
            home.renderEditorialHome();
        }""")
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.click"), "home-shelf-activate"
        )
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), "sample-0"
        )
        page.locator('[data-home-section="club"] .home-shelf-tape').click()
        page.locator('[data-playlist-entry][aria-selected="true"]').focus()
        page.evaluate("""async () => {
            const home = await import('/static/js/surfaces/home.js');
            home.editorialHome.sections.pop();
            home.renderEditorialHome();
        }""")
        self.assertEqual(page.evaluate("document.activeElement.dataset.click"), "home-date-today")
        self.assertEqual(page.evaluate("window.getHomePlaybackState().selectionSource"), "daily")

    def test_u5_day_failure_retry_focus_and_cached_return(self) -> None:
        page = self.page
        self._install_u5_source_fixture()
        self._open_and_wait_for_catalog(page)
        page.locator('[data-home-section="sample"] .home-shelf-tape').nth(1).click()
        page.route(
            "**/api/home?*", lambda route: route.fulfill(status=503, json={"reason": "offline"})
        )
        yesterday = page.locator(
            '#spotlightStage .spotlight-date-tabs [data-click="home-date-yesterday"]'
        )
        yesterday.click()
        page.locator("#homeFeedback button").wait_for(state="visible")
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), "sample-1"
        )
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.click"), "home-date-yesterday"
        )
        page.unroute("**/api/home?*")
        page.locator("#homeFeedback button").click()
        page.wait_for_function(
            "document.querySelector('#spotlight').getAttribute('aria-busy') === 'false' "
            "&& document.querySelector('#homeFeedback').hidden"
        )
        self.assertEqual(page.evaluate("window.getHomePlaybackState().playlistSource"), "daily")
        self.assertEqual(yesterday.get_attribute("aria-pressed"), "true")
        page.locator('[data-home-section="sample"] .home-shelf-tape').nth(1).click()
        yesterday.click()
        self.assertEqual(page.evaluate("window.getHomePlaybackState().playlistSource"), "daily")
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.click"), "home-date-yesterday"
        )

    def test_home_shelf_furniture_compacts_and_labels_short_categories(
        self,
    ) -> None:
        page = self.page

        def add_two_home_sections(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 2:
                home["sections"] = [
                    {
                        "id": "available",
                        "eyebrow": "Para ver ahora",
                        "title": "Disponible esta noche",
                        "description": "Pendientes que confirma tu biblioteca física.",
                        "items": [
                            {
                                "key": "available-heat",
                                "origin": {"kind": "catalog"},
                                "item": items[0],
                                "reason": {"label": "Lista para ver", "detail": "Disponible."},
                            }
                        ],
                    },
                    {
                        "id": "memory",
                        "eyebrow": "Tu archivo pide memoria",
                        "title": "Volvé a esto",
                        "description": "Obras que ya viste y podrían volver a la cartelera.",
                        "items": [
                            {
                                "key": "memory-akira",
                                "origin": {"kind": "catalog"},
                                "item": items[1],
                                "reason": {"label": "Ya la viste", "detail": "Hace tiempo."},
                            }
                        ],
                    },
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_two_home_sections)
        self._open_and_wait_for_catalog(page)

        categories = page.locator(".home-shelf-category")
        self.assertEqual(categories.count(), 0)
        controls = page.locator(".home-shelf-scroll-control")
        self.assertEqual(controls.count(), 2)
        self.assertFalse(page.locator("#homeShelfCategories").is_visible())
        self.assertTrue(all(controls.nth(index).is_disabled() for index in range(2)))
        plaques = page.locator(".home-shelf-bay-plaque")
        self.assertEqual(plaques.count(), 2)
        self.assertTrue(all(plaques.nth(index).is_visible() for index in range(2)))
        self.assertEqual(
            plaques.all_text_contents(),
            ["Disponible esta noche1 título", "Volvé a esto1 título"],
        )
        # One material family; active state belongs to the selected VHS, not a new plaque color.
        self.assertEqual(
            plaques.nth(0).evaluate("element => getComputedStyle(element).color"),
            plaques.nth(1).evaluate("element => getComputedStyle(element).color"),
        )
        self.assertEqual(
            page.locator('.home-program[data-home-section="available"]').get_attribute(
                "data-active"
            ),
            "true",
        )
        self.assertEqual(
            page.locator('.home-program[data-home-section="memory"]').get_attribute("data-active"),
            "false",
        )
        self.assertTrue(page.locator('.home-program[data-home-section="memory"]').is_visible())

        geometry = page.locator("#homeSections").evaluate(
            """element => {
                const bays = [...element.querySelectorAll('.home-shelf-bay')]
                    .map(bay => bay.getBoundingClientRect());
                return {
                    widths: bays.map(bay => bay.width),
                    gap: bays[1].left - bays[0].right,
                    overflows: element.scrollWidth > element.clientWidth + 1,
                };
            }"""
        )
        self.assertTrue(all(width >= 360 for width in geometry["widths"]))
        self.assertGreaterEqual(geometry["gap"], 24)
        self.assertFalse(geometry["overflows"])

        page.locator("#homeSections").focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(350)
        self.assertTrue(page.locator('.home-program[data-home-section="memory"]').is_visible())
        self.assertEqual(page.locator("#homeSections").evaluate("element => element.scrollLeft"), 0)

        page.set_viewport_size({"width": 390, "height": 844})
        self.assertFalse(page.locator("#homeShelfCategories").is_visible())
        self.assertTrue(page.locator('.home-program[data-home-section="available"]').is_visible())
        self.assertTrue(page.locator('.home-program[data-home-section="memory"]').is_visible())
        self.assertTrue(
            all(
                plaques.nth(index).evaluate(
                    "element => element.getBoundingClientRect().width <= innerWidth "
                    "&& element.getBoundingClientRect().height >= 48"
                )
                for index in range(2)
            )
        )
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )

    def test_home_shelf_preview_shows_edit_action_only_for_personal_entries(self) -> None:
        page = self.page

        def add_mixed_origin_section(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 1:
                home["sections"] = [
                    {
                        "id": "available",
                        "eyebrow": "Para ver ahora",
                        "title": "Disponible esta noche",
                        "description": "Pendientes que confirma tu biblioteca física.",
                        "items": [
                            {
                                "key": "available-heat",
                                "origin": {"kind": "catalog"},
                                "item": items[0],
                                "reason": {"label": "Lista para ver", "detail": "Disponible."},
                            }
                        ],
                    }
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_mixed_origin_section)
        self._open_and_wait_for_catalog(page)

        page.locator('[data-home-section="available"] .home-shelf-tape').first.click()
        preview = page.locator(".spotlight-preview")
        self.assertEqual(preview.get_by_text("Ver más").count(), 1)
        self.assertEqual(preview.locator(".home-console-media").count(), 0)
        edit_button = preview.get_by_text("Editar mi ficha")
        self.assertEqual(edit_button.count(), 1)

        edit_button.click()
        page.wait_for_selector("#detailDrawer[open]")
        page.wait_for_selector("[data-detail-form='personal']")
        self.assertEqual(page.locator("#detailDrawer").get_attribute("data-detail-mode"), "dossier")
        self.assertEqual(page.locator("#detailDrawer .vhs-back-cover").count(), 0)
        self.assertEqual(
            page.evaluate("document.activeElement.hasAttribute('data-personal-watched-at')"),
            True,
        )

    def test_home_shelf_collection_entries_never_show_an_edit_action(self) -> None:
        page = self.page

        def add_collection_origin_section(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 1:
                club_item = dict(items[0])
                club_item["id"] = "club-heat"
                home["sections"] = [
                    {
                        "id": "followed",
                        "eyebrow": "Seguís esto",
                        "title": "De tus colecciones",
                        "description": "Recomendaciones de colecciones que seguís.",
                        "items": [
                            {
                                "key": "followed-heat",
                                "origin": {
                                    "kind": "collection",
                                    "collection_id": "collection-1",
                                    "collection_title": "Noir esencial",
                                    "collection_item_id": "club-heat",
                                },
                                "item": club_item,
                                "reason": {
                                    "label": "En una colección seguida",
                                    "detail": "Todavía no está en tu catálogo.",
                                },
                            }
                        ],
                    }
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_collection_origin_section)
        page.set_viewport_size({"width": 390, "height": 844})
        self._open_and_wait_for_catalog(page)

        page.locator('[data-home-section="followed"] .home-shelf-tape').first.click()
        preview = page.locator(".spotlight-preview")
        self.assertEqual(preview.get_by_text("Ver ficha del Club").count(), 1)
        # The whole point: a not-yet-personal recommendation never offers to
        # "edit my record" for a record that doesn't exist yet.
        self.assertEqual(preview.get_by_text("Editar mi ficha").count(), 0)
        collection_action_box = preview.get_by_text("Ver ficha del Club").bounding_box()
        self.assertIsNotNone(collection_action_box)
        self.assertGreater(collection_action_box["width"], 100)
        self.assertGreaterEqual(collection_action_box["height"], 44)

        preview.get_by_text("Ver ficha del Club").click()
        shared_dialog = page.locator("#sharedDetailDialog")
        shared_dialog.wait_for(state="visible")
        self.assertEqual(shared_dialog.get_by_text("Editar mi ficha").count(), 0)
        self.assertEqual(shared_dialog.get_by_text("Agregar a mi catálogo").count(), 1)

    def test_selecting_and_previewing_a_shelf_entry_never_mutates_the_catalog(
        self,
    ) -> None:
        page = self.page

        def add_home_section(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 2:
                home["sections"] = [
                    {
                        "id": "available",
                        "eyebrow": "Para ver ahora",
                        "title": "Disponible esta noche",
                        "description": "Pendientes que confirma tu biblioteca física.",
                        "items": [
                            {
                                "key": "available-heat",
                                "origin": {"kind": "catalog"},
                                "item": items[0],
                                "reason": {"label": "Lista para ver", "detail": "Disponible."},
                            },
                            {
                                "key": "available-akira",
                                "origin": {"kind": "catalog"},
                                "item": items[1],
                                "reason": {"label": "Lista para ver", "detail": "Disponible."},
                            },
                        ],
                    }
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_home_section)
        self._open_and_wait_for_catalog(page)

        write_requests: list[str] = []

        def record_write(request) -> None:
            if request.method in ("POST", "PATCH", "PUT", "DELETE") and "/api/" in request.url:
                write_requests.append(f"{request.method} {request.url}")

        page.on("request", record_write)
        try:
            shelf = page.locator('[data-home-section="available"] .home-shelf-tape')
            shelf.nth(0).focus()
            page.keyboard.press("ArrowRight")
            page.keyboard.press("Home")
            page.keyboard.press("End")
            shelf.nth(0).click()
            page.locator(".spotlight-preview").get_by_text("Ver más", exact=True).click()
            page.wait_for_selector("#detailDrawer[open]")
            page.keyboard.press("Escape")
            page.wait_for_selector("#detailDrawer:not([open])", state="hidden")
        finally:
            page.remove_listener("request", record_write)
        self.assertEqual(write_requests, [])

    def test_back_cover_template_mapper_is_stable_for_opaque_ids(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        result = page.evaluate(
            """async () => {
                const module = await import('/static/js/core/back-cover.js');
                const ids = ['heat', 'akira', 'movie-42', 'opaque:999', 'opaque-2'];
                const templates = ids.map((id) => [id, module.backCoverTemplateForId(id)]);
                const rendered = ids.map((id) => {
                    const host = document.createElement('div');
                    host.innerHTML = module.renderBackCover({ id, title: id });
                    return {
                        template: host.firstElementChild.dataset.backCoverTemplate,
                        frames: host.querySelectorAll('.vhs-back-cover-frame[role="img"]').length,
                    };
                });
                return { templates, rendered };
            }"""
        )
        self.assertEqual(
            result["templates"],
            [
                ["heat", "episode-collage"],
                ["akira", "rental-classic"],
                ["movie-42", "studio-triptych"],
                ["opaque:999", "midnight-noir"],
                ["opaque-2", "archive-grid"],
            ],
        )
        self.assertEqual([entry["frames"] for entry in result["rendered"]], [2] * 5)
        self.assertEqual(
            [entry["template"] for entry in result["rendered"]],
            [entry[1] for entry in result["templates"]],
        )

    def test_home_shelf_view_more_opens_deterministic_back_cover_with_reversible_transition(
        self,
    ) -> None:
        page = self.page

        def add_home_section(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if len(items) >= 1:
                items[0].update(
                    {
                        "directors": ["Michael Mann"],
                        "writers": ["Michael Mann"],
                        "cast": ["Al Pacino", "Robert De Niro"],
                        "duration_minutes": 170,
                        "genres": ["Crimen", "Drama"],
                        "rating": 9,
                        "review": "Una memoria personal de prueba.",
                        "notes": "Esta nota no debe aparecer como sinopsis.",
                    }
                )
                home["sections"] = [
                    {
                        "id": "available",
                        "eyebrow": "Para ver ahora",
                        "title": "Disponible esta noche",
                        "description": "Pendientes que confirma tu biblioteca física.",
                        "items": [
                            {
                                "key": "available-heat",
                                "origin": {"kind": "catalog"},
                                "item": items[0],
                                "reason": {"label": "Lista para ver", "detail": "Disponible."},
                            }
                        ],
                    }
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_home_section)
        self._open_and_wait_for_catalog(page)
        page.set_viewport_size({"width": 1280, "height": 720})

        # document.startViewTransition support is exercised for real here (this
        # Playwright build ships a Chromium new enough to have it); we assert on
        # end-to-end behavior rather than instrumenting the API itself, since
        # wrapping it changes timing enough to throw off focus restoration.
        page.locator('[data-home-section="available"] .home-shelf-tape').first.click()
        view_more = page.locator(".spotlight-preview").get_by_text("Ver más", exact=True)
        view_more.click()
        page.wait_for_selector("#detailDrawer[open]")

        drawer = page.locator("#detailDrawer")
        self.assertEqual(drawer.get_attribute("data-detail-mode"), "back-cover")
        self.assertEqual(
            page.locator("#detailDrawerTitle").text_content(), "Contratapa VHS // Heat"
        )
        case = page.locator("#detailDrawer .vhs-back-cover-shell")
        self.assertEqual(
            page.locator("#detailDrawer .vhs-back-cover").get_attribute("data-back-cover-template"),
            "episode-collage",
        )
        self.assertIn(
            "vhs-back-cover-shell-v1.png",
            case.evaluate("element => getComputedStyle(element).backgroundImage"),
        )
        self.assertEqual(page.locator("#detailDrawer .vhs-back-cover-frame").count(), 2)
        self.assertEqual(page.locator("#detailDrawer .vhs-back-cover-frame[role='img']").count(), 2)
        self.assertEqual(page.locator("#detailDrawer .vhs-back-cover-credits").count(), 1)
        self.assertIn("Michael Mann", page.locator("#detailDrawer").inner_text())
        self.assertIn("Una memoria personal de prueba.", page.locator("#detailDrawer").inner_text())
        self.assertNotIn(
            "Esta nota no debe aparecer como sinopsis.",
            page.locator("#detailDrawer .vhs-back-cover-synopsis").inner_text(),
        )
        content_region = page.locator("#detailDrawer .vhs-back-cover-content")
        self.assertEqual(content_region.get_attribute("tabindex"), "0")
        self.assertEqual(content_region.get_attribute("role"), "region")
        self.assertGreaterEqual(
            float(content_region.evaluate("element => getComputedStyle(element).fontSize")[:-2]),
            11,
        )
        self.assertGreaterEqual(case.bounding_box()["width"], 460)
        geometry = page.locator("#detailDrawer .vhs-back-cover").evaluate(
            """element => {
                const shell = element.querySelector(
                    '.vhs-back-cover-shell'
                ).getBoundingClientRect();
                const content = element.querySelector('.vhs-back-cover-content');
                const box = content.getBoundingClientRect();
                return {
                    inside: box.left >= shell.left && box.right <= shell.right
                        && box.top >= shell.top && box.bottom <= shell.bottom,
                    contentOverflow: content.scrollHeight - content.clientHeight,
                };
            }"""
        )
        self.assertTrue(geometry["inside"])
        self.assertLessEqual(geometry["contentOverflow"], 1)
        template_overflows = page.locator("#detailDrawer .vhs-back-cover").evaluate(
            """element => {
                const original = element.dataset.backCoverTemplate;
                const overflows = [
                    'rental-classic',
                    'episode-collage',
                    'studio-triptych',
                    'midnight-noir',
                    'archive-grid',
                ].map((template) => {
                element.className = `vhs-back-cover vhs-back-cover--${template}`;
                const content = element.querySelector('.vhs-back-cover-content');
                return content.scrollHeight - content.clientHeight;
                });
                element.className = `vhs-back-cover vhs-back-cover--${original}`;
                return overflows;
            }"""
        )
        self.assertTrue(all(overflow <= 1 for overflow in template_overflows))

        page.locator("#detailDrawer .vhs-back-cover-synopsis p").evaluate(
            "element => { element.textContent = `${element.textContent} `.repeat(80); }"
        )
        content_region.focus()
        self.assertEqual(
            page.evaluate("document.activeElement.classList.contains('vhs-back-cover-content')"),
            True,
        )
        self.assertGreater(
            content_region.evaluate("element => element.scrollHeight - element.clientHeight"), 0
        )
        page.keyboard.press("End")
        page.wait_for_function("document.querySelector('.vhs-back-cover-content').scrollTop > 0")

        # Reversible + doesn't block Escape/focus.
        page.keyboard.press("Escape")
        page.wait_for_selector("#detailDrawer:not([open])", state="hidden")
        # The view transition's callback runs synchronously, but Chromium settles
        # the actual focus move a tick later while the transition is captured, so
        # poll instead of asserting on a single synchronous read.
        page.wait_for_function("document.activeElement.textContent === 'Ver más'")

        # prefers-reduced-motion: the same open/close still works (the JS gate
        # skips document.startViewTransition before CSS ever enters the picture).
        page.emulate_media(reduced_motion="reduce")
        view_more.click()
        page.wait_for_selector("#detailDrawer[open]")
        page.keyboard.press("Escape")
        page.wait_for_selector("#detailDrawer:not([open])", state="hidden")
        # The view transition's callback runs synchronously, but Chromium settles
        # the actual focus move a tick later while the transition is captured, so
        # poll instead of asserting on a single synchronous read.
        page.wait_for_function("document.activeElement.textContent === 'Ver más'")

        # The back cover has no visible frame or close button for pointer users: the
        # button keeps its accessible name, and a click beside the case closes it.
        view_more.click()
        page.wait_for_selector("#detailDrawer[open]")
        close = page.locator("#closeDetail")
        self.assertEqual(close.get_attribute("aria-label") or close.text_content(), "Cerrar")
        self.assertEqual(close.evaluate("element => getComputedStyle(element).opacity"), "0")
        case_box = page.locator("#detailDrawer .vhs-back-cover-shell").bounding_box()
        page.mouse.click(case_box["x"] + case_box["width"] + 40, case_box["y"] + 200)
        page.wait_for_selector("#detailDrawer:not([open])", state="hidden")

    def test_ficha_description_dialog_focus_and_naming(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        page.locator("#systemMenu > summary").click()
        page.locator('[data-click="menu-random"]').focus()
        # openSearchDescription(collection, itemId): "" looks the id up in the
        # loaded catalog items rather than in an external-search results list.
        page.evaluate("openSearchDescription('', 'heat')")

        self.assertTrue(page.get_by_role("dialog", name="Heat").is_visible())
        # Accessible name comes from aria-labelledby -> #descriptionDialogTitle;
        # the accessible description (aria-describedby) has to resolve to real,
        # non-empty content too, not just point at an empty element.
        self.assertEqual(page.evaluate("document.activeElement.id"), "closeDescriptionDialog")
        self.assertEqual(
            page.locator("#descriptionDialogText").inner_text(),
            "Un detective y un ladrón profesional se enfrentan en Los Ángeles.",
        )

        page.get_by_role("button", name="Cerrar", exact=True).click()
        self.assertEqual(page.evaluate("document.activeElement.dataset.click"), "menu-random")

    def test_structural_regions_are_not_live_announcements(self) -> None:
        page = self.page
        page.goto(self.base_url)
        page.wait_for_selector("#homeView:not([hidden])")

        structural_ids = (
            "clubCatalogPanel",
            "collectionList",
            "collectionDetailPanel",
            "curationDetail",
            "importDraftList",
            "importReviewPanel",
            "scannerQueue",
            "scannerQueueDetail",
            "libraryList",
            "memberList",
        )
        selector = ", ".join(f"#{element_id}[aria-live]" for element_id in structural_ids)
        self.assertEqual(page.locator(selector).count(), 0)

    def test_ficha_availability_panel_separates_manual_from_server_provenance(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        page.evaluate("openDetail('heat')")
        page.wait_for_selector("#detailDrawer[open]")
        # The panel lives inside a collapsed <details> accordion; expand it
        # before reading, the same way a person would need to.
        page.locator("summary", has_text="Disponibilidad y fuentes").click()
        heat_panel = page.locator(".availability-panel").inner_text()
        page.evaluate("closeDetail()")

        page.evaluate("openDetail('akira')")
        page.wait_for_selector("#detailDrawer[open]")
        page.locator("summary", has_text="Disponibilidad y fuentes").click()
        akira_panel = page.locator(".availability-panel").inner_text()
        page.evaluate("closeDetail()")

        # "Heat" only has a manual declaration; "Akira" only has a real library
        # scan behind it. Their panels must not read the same way.
        self.assertIn("Disponible · Declaración manual", heat_panel)
        self.assertIn("Activa", heat_panel)
        self.assertIn("Sin archivos vinculados", heat_panel)

        self.assertIn("Disponible · Inventario verificado", akira_panel)
        self.assertIn("Inactiva", akira_panel)
        self.assertNotIn("Sin archivos vinculados", akira_panel)

    def test_curation_queue_shows_the_unified_availability_pill(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        # Both fixture items are pending Curaduria cases; the shared library
        # scan in setUpClass gives Akira server availability but leaves no
        # Scanner queue item, so the scanner badge must stay hidden.
        page.locator("#systemMenu > summary").click()
        page.locator("[data-menu-inbox-badge]").wait_for(state="visible")
        self.assertEqual(page.locator("[data-menu-inbox-badge]").inner_text(), "2")
        self.assertFalse(page.locator("[data-menu-scanner-badge]").is_visible())

        page.locator('[data-click="menu-inbox"]').click()
        self.assertEqual(page.locator("#inboxCurationMode").inner_text(), "Tu catálogo")
        self.assertIn(
            "Inventario de la instancia",
            page.locator("#inboxScannerMode").get_attribute("title") or "",
        )
        page.locator("#inboxCurationMode").click()

        # "Heat" (manual declaration only) and "Akira" (real library scan only)
        # are the same two items test_ficha_availability_panel_... uses --
        # Curaduria's queue must show the same unified pill, not "manual: si/no".
        page.locator(".curation-queue-item", has_text="Heat").click()
        heat_record = page.locator(".curation-record").inner_text()
        self.assertIn("Disponible · Declaración manual", heat_record)
        self.assertNotIn("manual:", heat_record)
        # Curaduria only ever touches the personal catalog -- the "catalog"
        # scope chip must be active regardless of which case is selected.
        self.assertEqual(
            page.locator('[data-scope-chip="catalog"]').get_attribute("data-active"), "true"
        )
        self.assertEqual(
            page.locator('[data-scope-chip="physical"]').get_attribute("data-active"), "false"
        )

        page.locator(".curation-queue-item", has_text="Akira").click()
        akira_record = page.locator(".curation-record").inner_text()
        self.assertIn("Disponible · Inventario verificado", akira_record)
        self.assertNotIn("manual:", akira_record)

    def test_public_landing_renders_a_revocable_snapshot_without_a_session(self) -> None:
        page = self.page
        headers = {
            "X-Movie-Inbox-Token": self.config.api_token,
            "Origin": self.base_url,
            "Content-Type": "application/json",
        }
        collections = page.request.get(f"{self.base_url}/api/collections", headers=headers).json()
        collection = collections["collections"][0]
        created = page.request.post(
            f"{self.base_url}/api/public-presentations",
            data=json.dumps(
                {
                    "collection_id": collection["id"],
                    "title": "Funciones de prueba",
                    "description": "Sólo disponibilidad verificada.",
                }
            ),
            headers=headers,
        )
        self.assertEqual(created.status, 201)
        public_url = f"{self.base_url}{created.json()['url']}"

        anonymous = self.browser.new_context(viewport={"width": 390, "height": 844})
        try:
            public_page = anonymous.new_page()
            public_page.goto(public_url)
            public_page.locator("h1").filter(has_text="Funciones de prueba").wait_for()
            self.assertIn(
                "Sólo disponibilidad verificada.", public_page.locator("body").inner_text()
            )
            self.assertIn("FUNCIONES", public_page.locator("#publicPresentationCount").inner_text())
            self.assertFalse(public_page.locator("#currentUserName").count())
            self.assertEqual(public_page.locator(".public-presentation__item").count(), 31)
        finally:
            anonymous.close()

    def test_curation_search_keyboard_and_three_member_duplicate_group(self) -> None:
        page = self.page
        availability = {"effective": False, "manual": False, "server": False, "file_count": 0}
        heat_a: dict[str, Any] = {
            "id": "heat-a",
            "ref": "heat-a::catalog.json",
            "source_file": "catalog.json",
            "title": "Heat",
            "year": "1995",
            "kind": "pelicula",
            "source": "imdb",
            "added_at": "2026-08-24T01:00:00Z",
            "local_files": [],
            "status": "to_watch",
            "_availability": availability,
        }
        heat_a["rating"] = 9
        heat_b = {**heat_a, "id": "heat-b", "ref": "heat-b::catalog.json", "rating": 4}
        heat_c = {**heat_a, "id": "heat-c", "ref": "heat-c::catalog.json", "rating": 0}
        akira = {
            **heat_a,
            "id": "akira",
            "ref": "akira::catalog.json",
            "title": "Ákira",
            "year": "1988",
            "source": "wikipedia",
        }
        cases = [
            {
                "id": "duplicate-heat",
                "type": "duplicate",
                "status": "pending",
                "members": [heat_a, heat_b, heat_c],
                "evidence": ["Mismo título y año"],
            },
            {
                "id": "missing-akira",
                "type": "missing_link",
                "status": "pending",
                "primary": akira,
                "secondary": None,
                "evidence": ["Sin referencia externa"],
            },
        ]
        history = [
            {
                "id": "operation-1",
                "action": "merge",
                "label": "Primera combinación",
                "created_at": "2026-08-24T02:00:00Z",
                "status": "applied",
                "can_undo": True,
                "mode": "session",
                "summary": {},
            },
            {
                "id": "operation-2",
                "action": "link_curation",
                "label": "Segunda decisión",
                "created_at": "2026-08-24T03:00:00Z",
                "status": "applied",
                "can_undo": True,
                "mode": "session",
                "summary": {},
            },
        ]
        compare_payload = {
            "group": True,
            "members": [
                {
                    **member,
                    "local_files_count": 0,
                    "reference": {"id": member["id"], "source_file": member["source_file"]},
                }
                for member in (heat_a, heat_b, heat_c)
            ],
            "fields": [
                {
                    "key": "rating",
                    "label": "Puntaje",
                    "group": "personal",
                    "strategy": "scalar",
                    "protected": True,
                    "locked": False,
                    "different": True,
                    "allowed": [heat_a["ref"], heat_b["ref"], heat_c["ref"]],
                    "default_choice": "",
                    "required": True,
                    "values": [
                        {"member_ref": heat_a["ref"], "value": 9},
                        {"member_ref": heat_b["ref"], "value": 4},
                        {"member_ref": heat_c["ref"], "value": 0},
                    ],
                }
            ],
            "groups": [{"key": "personal", "label": "Registro personal"}],
            "survivor_ref": heat_a["ref"],
            "can_select_survivor": True,
            "different_count": 1,
            "review_id": "browser-position-fallback",
        }

        page.route(
            "**/api/curation/history?*",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"operations": history, "count": len(history)}),
            ),
        )

        def compare_group(route) -> None:
            request_body = route.request.post_data_json
            survivor_id = str((request_body.get("survivor") or {}).get("id") or "heat-a")
            payload = {
                **compare_payload,
                "survivor_ref": f"{survivor_id}::catalog.json",
            }
            route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

        merge_requests: list[dict[str, Any]] = []

        def merge_group(route) -> None:
            merge_requests.append(route.request.post_data_json)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "reason": "merged",
                        "item": heat_c,
                        "operation": {
                            "id": "merge-group-1",
                            "action": "merge_group",
                            "can_undo": True,
                        },
                    }
                ),
            )

        page.route("**/api/curation/compare", compare_group)
        page.route("**/api/curation/merge", merge_group)
        page.route(
            "**/api/curation",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "cases": cases,
                        "counts": {
                            "pending": 2,
                            "duplicates": 1,
                            "missing_link": 1,
                            "deferred": 0,
                        },
                    }
                ),
            ),
        )

        self._open_and_wait_for_catalog(page)
        click_desktop_menu_action(page, "inbox")
        page.wait_for_selector("#inboxView:not([hidden])")

        search = page.locator("#curationQueueSearch")
        search.fill("akira")
        self.assertEqual(page.locator(".curation-queue-item").count(), 1)
        self.assertIn("Ákira", page.locator(".curation-queue-item").inner_text())

        search.fill("")
        self.assertEqual(page.locator(".curation-queue-item").count(), 2)
        selected_before = page.locator(".curation-queue-item.selected").get_attribute(
            "data-curation-case"
        )
        page.locator(".curation-queue-item.selected").focus()
        page.keyboard.press("ArrowDown")
        page.wait_for_function("document.activeElement.matches('.curation-queue-item.selected')")
        self.assertNotEqual(
            page.locator(".curation-queue-item.selected").get_attribute("data-curation-case"),
            selected_before,
        )

        duplicate = page.locator('[data-curation-case="duplicate-heat"]')
        self.assertIn("3 entradas conectadas", duplicate.inner_text())
        duplicate.click()
        detail_text = page.locator("#curationDetail").text_content() or ""
        self.assertIn("Entrada 1 de 3", detail_text)
        self.assertIn("Entrada 2 de 3", detail_text)
        self.assertIn("Entrada 3 de 3", detail_text)

        page.get_by_role("button", name="Comparar 3 entradas").click()
        page.wait_for_selector("#mergeComparatorDialog[open]")
        page.wait_for_function(
            "document.querySelector('#mergeComparatorDialog').dataset.loading === 'false'"
        )
        self.assertEqual(
            page.locator("#mergeComparatorTitle").text_content(),
            "Heat · 3 entradas",
        )
        summary_text = page.locator("#mergeComparatorSummary").text_content() or ""
        self.assertIn("Entrada 1 de 3", summary_text)
        self.assertIn("Entrada 2 de 3", summary_text)
        self.assertIn("Entrada 3 de 3", summary_text)
        self.assertEqual(
            page.locator('#mergeSurvivorControl input[name="merge-survivor"]').count(), 3
        )
        self.assertEqual(
            page.locator("#confirmReviewedMerge").text_content(), "Combinar 3 entradas"
        )
        self.assertEqual(
            page.locator("#confirmReviewedMerge").get_attribute("aria-describedby"),
            "mergeDecisionStatus",
        )
        self.assertEqual(
            page.locator("#mergeDecisionStatus").locator("xpath=..").get_attribute("aria-live"),
            "polite",
        )
        page.locator('input[name="merge-survivor"][value="heat-c::catalog.json"]').check()
        page.wait_for_function(
            "document.querySelector('#mergeComparatorDialog').dataset.loading === 'false'"
        )
        self.assertTrue(page.locator("#confirmReviewedMerge").is_disabled())
        page.locator('[data-merge-choice="rating"][value="heat-a::catalog.json"]').check()
        page.locator("#confirmReviewedMerge").click()
        page.wait_for_function("!document.querySelector('#mergeComparatorDialog').open")
        self.assertEqual(len(merge_requests), 1)
        self.assertEqual(len(merge_requests[0]["members"]), 3)
        self.assertEqual(merge_requests[0]["survivor"]["id"], "heat-c")
        self.assertEqual(merge_requests[0]["choices"]["rating"], "heat-a::catalog.json")

        page.locator('[data-curation-filter="history"]').click()
        first_history = page.locator(".curation-queue-item.selected")
        self.assertEqual(first_history.get_attribute("data-curation-case"), "operation-1")
        first_history.focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_function("document.activeElement.matches('.curation-queue-item.selected')")
        self.assertEqual(
            page.locator(".curation-queue-item.selected").get_attribute("data-curation-case"),
            "operation-2",
        )

    def test_catalog_compare_mode_refine_keeps_external_pick_and_searches_local_only(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        def handle_search(route) -> None:
            url = route.request.url
            body: dict[str, Any]
            if "external=true" in url:
                body = {"results": []}
                if "source=wikipedia" in url:
                    body = {
                        "results": [
                            {
                                "title": "Heat",
                                "year": "1995",
                                "source": "wikipedia",
                                "url": "https://es.wikipedia.org/wiki/Heat",
                            }
                        ]
                    }
            else:
                body = {"catalog": {"results": []}}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        page.route("**/api/search?*", handle_search)
        candidate = {"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}
        page.route(
            "**/api/search/catalog-candidates",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"results": [candidate]}),
            ),
        )

        page.locator("#catalogButton").click()
        page.locator('[data-mode="search"]').click()
        page.locator("#externalSource").check()
        page.locator("#query").fill("Heat")
        page.locator("#searchButton").click()
        page.wait_for_selector('[data-click="prepare-merge"][data-index="0"]')

        page.locator('[data-click="prepare-merge"][data-index="0"]').click()
        page.wait_for_function(
            "(document.querySelector('#catalogMergeResults').textContent || '').includes('Heat')"
        )
        self.assertIn("mode=compare", page.url)
        self.assertIn("candidate_source=wikipedia", page.url)
        self.assertIn("candidate_ref=", page.url)
        self.assertIn("Heat", page.locator("#collectionAnchor").inner_text())
        external_before = page.locator("#manualSearchResults").inner_text()
        self.assertIn("Heat", external_before)

        page.route(
            "**/api/search?*",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"catalog": {"results": []}}),
            ),
        )
        page.locator("#query").fill("Heat edición restaurada")
        page.locator("#searchButton").click()
        page.wait_for_function(
            "document.querySelector('#catalogMergeStatus').textContent.includes('0 entradas')"
        )

        # El lado externo (ya fijo) no debe haberse vuelto a pedir ni a perder.
        self.assertEqual(page.locator("#manualSearchResults").inner_text(), external_before)
        self.assertFalse(page.locator("#backToCollection").is_hidden())
        merge_section_class = page.locator("#catalogMergeSection").get_attribute("class") or ""
        self.assertIn("active", merge_section_class)

        page.reload()
        page.wait_for_function(
            "document.querySelector('#collectionView').dataset.searchMode === 'compare'"
        )
        self.assertIn("Heat", page.locator("#collectionAnchor").inner_text())
        self.assertFalse(page.locator("#collectionAnchor").is_hidden())

    def test_catalog_can_search_and_add_a_jikan_result(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)
        submitted: list[dict[str, Any]] = []

        def handle_search(route) -> None:
            url = route.request.url
            body: dict[str, Any]
            if "external=true" not in url:
                body = {"catalog": {"results": []}}
            elif "source=jikan" in url:
                body = {
                    "results": [
                        {
                            "title": "Kimi no Na wa.",
                            "english_title": "Your Name.",
                            "year": "2016",
                            "kind": "anime",
                            "source": "jikan",
                            "url": "https://myanimelist.net/anime/32281",
                            "myanimelist_url": "https://myanimelist.net/anime/32281",
                            "mal_id": "32281",
                        }
                    ]
                }
            else:
                body = {"results": []}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        def handle_add(route) -> None:
            submitted.append(route.request.post_data_json)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"ok": True, "reason": "added"}),
            )

        page.route("**/api/search?*", handle_search)
        page.route("**/api/add", handle_add)
        page.locator("#catalogButton").click()
        page.locator('[data-mode="search"]').click()
        page.locator("#externalSource").check()
        page.locator("#query").fill("Your Name")
        page.locator("#searchButton").click()

        jikan_group = page.locator('[data-source-group="jikan"]')
        jikan_group.get_by_role("heading", name="Kimi no Na wa.", exact=True).wait_for()
        self.assertIn("no está afiliada a MyAnimeList", jikan_group.inner_text())
        jikan_group.get_by_role("button", name="Agregar").click()
        page.wait_for_function(
            "[...document.querySelectorAll('[data-source-group=\"jikan\"] button')]"
            ".some((button) => button.textContent === 'Agregado')"
        )

        self.assertEqual(len(submitted), 1)
        self.assertEqual(submitted[0]["source"], "jikan")
        self.assertEqual(submitted[0]["mal_id"], "32281")
        self.assertEqual(submitted[0]["myanimelist_url"], "https://myanimelist.net/anime/32281")

    def test_jikan_cooldown_shows_labeled_offline_fallback_and_attribution(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        def handle_search(route) -> None:
            url = route.request.url
            body: dict[str, Any] = {"results": []}
            if "source=jikan" in url:
                body = {
                    "results": [
                        {
                            "title": "Death Note",
                            "year": "2006",
                            "kind": "anime",
                            "source": "anime_offline_database",
                            "_search_shelf": "jikan",
                            "fallback_reason": "rate_limited",
                            "offline": True,
                            "url": "https://myanimelist.net/anime/1535",
                            "myanimelist_url": "https://myanimelist.net/anime/1535",
                            "mal_id": "1535",
                            "snapshot_date": "2026-07-04",
                        }
                    ],
                    "external": {
                        "sources": {
                            "jikan": {
                                "status": "cooldown",
                                "error": "HTTP Error 429",
                                "retry_after_seconds": 90,
                            },
                            "anime_offline_database": {
                                "status": "ok",
                                "snapshot_date": "2026-07-04",
                                "result_count": 1,
                            },
                        }
                    },
                }
            route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        page.route("**/api/search?*", handle_search)
        page.locator("#catalogButton").click()
        page.locator('[data-mode="search"]').click()
        page.locator("#externalSource").check()
        page.locator("#query").fill("Death Note")
        page.locator("#searchButton").click()

        jikan_group = page.locator('[data-source-group="jikan"]')
        jikan_group.get_by_role("heading", name="Death Note", exact=True).wait_for()
        text = jikan_group.inner_text()
        self.assertIn("Respaldo local", text)
        self.assertIn("Anime DB offline", text)
        self.assertIn("ODbL/DbCL", text)
        self.assertIn("Jikan alcanzó su límite temporal", text)

    def test_catalog_link_mode_refine_keeps_local_item_and_searches_external_only(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        def handle_search(route) -> None:
            url = route.request.url
            body: dict[str, Any] = {"results": []}
            if "source=wikipedia" in url and "restaurada" in url:
                body = {
                    "results": [
                        {
                            "title": "Heat (edición restaurada)",
                            "year": "1995",
                            "source": "wikipedia",
                            "url": "https://es.wikipedia.org/wiki/Heat_restaurada",
                        }
                    ]
                }
            route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

        page.route("**/api/search?*", handle_search)

        page.evaluate("openDetail('heat')")
        page.wait_for_selector("#detailDrawer[open]")
        page.get_by_text("Disponibilidad y fuentes").click()
        page.locator('[data-click="find-link"]').click()
        page.wait_for_selector("#catalogMergeSection.active")
        self.assertIn("mode=link", page.url)
        self.assertIn("link_id=heat", page.url)
        self.assertIn("Heat", page.locator("#collectionAnchor").inner_text())
        local_before = page.locator("#catalogMergeResults").inner_text()
        self.assertIn("Heat", local_before)

        page.locator("#query").fill("Heat edición restaurada")
        page.locator("#searchButton").click()
        page.wait_for_function(
            "document.querySelector('#manualSearchResults').textContent.includes('restaurada')"
        )

        # El lado local (ya fijo) no debe haberse alterado por refinar la query.
        self.assertEqual(page.locator("#catalogMergeResults").inner_text(), local_before)
        self.assertFalse(page.locator("#backToCollection").is_hidden())

        page.go_back()
        page.wait_for_function(
            "document.querySelector('#catalogMergeSection').classList.contains('active')"
        )
        self.assertIn("Heat", page.locator("#catalogMergeResults").inner_text())
        self.assertFalse(page.locator("#backToCollection").is_hidden())


class ScannerBrowserTests(unittest.TestCase):
    """Bandeja > Scanner coverage. Isolated from BrowserInterfaceTests because
    confirming "Conservar ambas" writes a new catalog item -- sharing that
    mutation with read-only assertions elsewhere would make test order
    matter."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        cls.catalog_path = root / "catalog.json"
        JsonCatalogRepository(cls.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "legacy-1917",
                        "title": "1917",
                        "year": "1917",
                        "kind": "pelicula",
                        "source": "imdb",
                        "url": "https://www.imdb.com/title/tt8579674/",
                        "imdb_url": "https://www.imdb.com/title/tt8579674/",
                    }
                ),
            ]
        )
        cls.owner_password = "a-long-scanner-browser-test-password"
        cls.instance_path = root / "instance.db"
        cls.media_path = root / "media"
        cls.media_path.mkdir()
        (cls.media_path / "1917.2019.1080p.BluRay.mkv").write_bytes(b"numeric-title")
        AuthService(SqliteIdentityRepository(cls.instance_path)).bootstrap_owner(
            "lucas",
            cls.owner_password,
            catalog_name="Catálogo de Lucas",
            source_paths=[str(cls.catalog_path)],
            write_path=str(cls.catalog_path),
        )
        cls.port = available_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.config = ViewerConfig(
            patterns=[str(cls.catalog_path)],
            title="Movie Inbox Scanner Test",
            write_json=str(cls.catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=cls.port,
            api_token="scanner-browser-test-token",
            instance_db=str(cls.instance_path),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(cls.media_path),),
            library_scheduler_poll_seconds=3600,
        )
        cls.server = uvicorn.Server(
            uvicorn.Config(
                create_app(cls.config), host="127.0.0.1", port=cls.port, log_level="error"
            )
        )
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        wait_until_healthy(cls.base_url)

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()
        # bypass_csp: without it, Page.evaluate/wait_for_function on any page
        # after the first one opened in a context hits the app's strict CSP
        # ("script-src 'self'", no 'unsafe-eval') and raises EvalError -- a
        # Playwright/Chromium quirk unrelated to the app itself, only visible
        # to test automation.
        cls.context = cls.browser.new_context(
            viewport={"width": 1280, "height": 900}, bypass_csp=True
        )
        setup_page = cls.context.new_page()
        setup_page.goto(cls.base_url)
        setup_page.get_by_label("Usuario").fill("lucas")
        setup_page.get_by_label("Contraseña", exact=True).fill(cls.owner_password)
        setup_page.get_by_role("button", name="Entrar").click()
        setup_page.wait_for_selector("#homeView:not([hidden])")

        cls.headers = {
            "X-Movie-Inbox-Token": cls.config.api_token,
            "Origin": cls.base_url,
            "Content-Type": "application/json",
        }
        library = setup_page.request.post(
            f"{cls.base_url}/api/libraries",
            data=json.dumps(
                {"name": "Peliculas", "root_path": str(cls.media_path), "schedule": "manual"}
            ),
            headers=cls.headers,
        ).json()["library"]
        cls.library_id = library["id"]
        run_library_scan(setup_page, cls.base_url, cls.headers, library["id"])
        deadline = time.monotonic() + 10
        queue: dict[str, object] = {}
        while time.monotonic() < deadline:
            queue = setup_page.request.get(
                f"{cls.base_url}/api/scanner/queue", headers=cls.headers
            ).json()
            if queue.get("count"):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Scanner queue was not populated in time")
        queue_items = queue.get("items")
        if not isinstance(queue_items, list) or not queue_items:
            raise RuntimeError("Scanner queue did not include any items")
        queue_item = queue_items[0]
        if not isinstance(queue_item, dict) or not isinstance(queue_item.get("id"), str):
            raise RuntimeError("Scanner queue item did not include an id")
        cls.queue_item_id = queue_item["id"]
        setup_page.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.context.close()
        cls.browser.close()
        cls.playwright.stop()
        cls.server.should_exit = True
        cls.server_thread.join(timeout=10)
        cls.temporary.cleanup()

    def test_bandeja_scanner_confirms_a_distinct_work_behind_a_review_step(self) -> None:
        page = self.context.new_page()
        page.goto(self.base_url)
        page.wait_for_selector("#homeView:not([hidden])")

        click_desktop_menu_action(page, "inbox")
        page.locator("#inboxScannerMode").click()
        page.locator(f'[data-scanner-item="{self.queue_item_id}"]').click()

        # Step 1: the guard renders as "review-distinct" and is not yet
        # confirming. Title/year/kind fields are pre-filled from the scanned
        # filename, so no form input is needed for either step to submit.
        page.wait_for_selector('[data-scanner-review="review-distinct"]')
        self.assertEqual(page.locator("section.scanner-create-guard.is-confirming").count(), 0)
        page.locator('[data-scanner-review="review-distinct"]').click()

        # Step 2: the same section now carries "is-confirming" and the button
        # flips to "create-distinct" -- the server-issued review token that
        # gates this, not copy, is what makes the second click succeed.
        page.wait_for_selector('[data-scanner-review="create-distinct"]')
        self.assertGreater(page.locator("section.scanner-create-guard.is-confirming").count(), 0)
        page.locator('[data-scanner-review="create-distinct"]').click()

        page.wait_for_function(
            f"""
            () => fetch('/api/scanner/queue', {{
                headers: {{'X-Movie-Inbox-Token': '{self.config.api_token}'}}
            }}).then((response) => response.json()).then((data) => data.count === 0)
            """,
            timeout=10000,
        )

        # Regression: #curationFeedback used to be nested inside
        # #curationInboxPanel, which goes `hidden` in Scanner mode -- every
        # Scanner success message rendered into a display:none element. It
        # now lives as a sibling of the mode tabs, so it must be visible here.
        # The queue-count wait above only proves the server finished; give the
        # frontend's own re-render (loadScannerQueue + setCurationFeedback)
        # a moment to catch up before reading the feedback text.
        page.wait_for_function(
            "() => (document.querySelector('#curationFeedback')?.textContent"
            " || '').includes('cambió')"
        )
        self.assertTrue(page.locator("#curationFeedback").is_visible())
        self.assertIn("Tu catálogo cambió", page.locator("#curationFeedback").inner_text())

        page.close()

    def test_badge_and_scope_strip_separate_scanner_from_personal_scope(self) -> None:
        page = self.context.new_page()
        page.goto(self.base_url)
        page.wait_for_selector("#homeView:not([hidden])")

        # This fixture's only catalog item ("legacy-1917") already has an
        # imdb_url, so it never shows up as a pending Curaduria case -- the
        # personal badge must stay hidden while the scanner one is not.
        # loadCatalog() populates both counts asynchronously after the home
        # view is already visible, so wait for the scanner badge specifically
        # rather than reading a snapshot right after page load.
        open_desktop_menu(page)
        page.locator("[data-menu-scanner-badge]").wait_for(state="visible")
        self.assertFalse(page.locator("[data-menu-inbox-badge]").is_visible())
        self.assertEqual(page.locator("[data-menu-scanner-badge]").inner_text(), "1")

        page.locator('[data-click="menu-inbox"]').click()
        self.assertEqual(page.locator("#inboxCurationMode").inner_text(), "Tu catálogo")
        self.assertIn(
            "Inventario de la instancia",
            page.locator("#inboxScannerMode").get_attribute("title") or "",
        )

        page.locator("#inboxScannerMode").click()
        page.locator(f'[data-scanner-item="{self.queue_item_id}"]').click()
        page.wait_for_selector('[data-scope-chip="identity"][data-active="true"]')
        summary = page.locator("#scopeStripSummary").inner_text()
        self.assertIn("archivo físico", summary)
        self.assertIn("identidad compartida", summary)

        page.close()

    def test_bandeja_scanner_candidate_shows_your_catalog_origin(self) -> None:
        # Runs before test_bandeja_scanner_confirms_a_distinct_work_behind_a_review_step
        # (alphabetical "candidate" < "confirms"): that test consumes the only
        # queue item, so this read-only assertion has to observe it first.
        page = self.context.new_page()
        page.goto(self.base_url)
        page.wait_for_selector("#homeView:not([hidden])")

        click_desktop_menu_action(page, "inbox")
        page.locator("#inboxScannerMode").click()
        page.locator(f'[data-scanner-item="{self.queue_item_id}"]').click()

        origin = page.locator(".scanner-candidate-origin").first
        origin.wait_for(state="visible")
        # text-transform: uppercase (same styling as .scanner-candidate-index)
        # means inner_text() reflects the rendered case, not the DOM string.
        self.assertEqual(origin.inner_text(), "EN TU CATÁLOGO")

        page.close()

    def test_bandeja_scanner_cause_bucket_badges_and_filters_the_queue(self) -> None:
        # Runs before ..._confirms_... (alphabetical "cause" < "confirms"):
        # read-only, but the queue item needs to still be pending.
        page = self.context.new_page()
        page.goto(self.base_url)
        page.wait_for_selector("#homeView:not([hidden])")

        click_desktop_menu_action(page, "inbox")
        page.locator("#inboxScannerMode").click()
        page.wait_for_selector(f'[data-scanner-item="{self.queue_item_id}"]')

        # "1917" detected as title="1917"/year="2019" against a catalog item
        # year="1917" -- exact title, year conflict -- lands in year_type_conflict.
        self.assertEqual(page.locator("#scannerAllCount").inner_text(), "1")
        self.assertEqual(page.locator("#scannerYearTypeConflictCount").inner_text(), "1")
        self.assertEqual(page.locator("#scannerMissingIdentityCount").inner_text(), "0")
        self.assertEqual(page.locator("#scannerLikelyExistingCount").inner_text(), "0")
        self.assertEqual(page.locator("#scannerNoSignalCount").inner_text(), "0")

        row = page.locator(f'[data-scanner-item="{self.queue_item_id}"]')
        # .member-state is text-transform: uppercase; inner_text() reflects
        # the rendered case, not the DOM string (same as P1-b's origin chip).
        self.assertIn("CONFLICTO DE AÑO/TIPO", row.inner_text())
        self.assertGreater(row.locator(".member-state-attention").count(), 0)

        page.locator('[data-scanner-filter="missing_identity"]').click()
        page.wait_for_selector(".curation-empty.compact")

        page.locator('[data-scanner-filter="year_type_conflict"]').click()
        page.wait_for_selector(f'[data-scanner-item="{self.queue_item_id}"]')

        page.close()

    def test_bandeja_scanner_candidates_beyond_three_stay_collapsed(self) -> None:
        # Independent of the alphabetical-order convention the other tests in
        # this class rely on: this one cleans up its own queue item via
        # addCleanup, so it can't leak state into ..._confirms_... regardless
        # of when it runs.
        (self.media_path / "Quartz Lantern Meridian.2010.1080p.mkv").write_bytes(
            b"collapsed-candidates"
        )

        def add_items(items: list[CatalogItem]) -> tuple[bool, None]:
            items.extend(
                normalize_item(row)
                for row in [
                    {
                        "id": "quartz-a",
                        "title": "Quartz Lantern Meridian",
                        "year": "2010",
                        "kind": "documental",
                    },
                    {
                        "id": "quartz-b",
                        "title": "Quartz Lantern Meridian",
                        "kind": "pelicula",
                    },
                    {
                        "id": "quartz-c",
                        "title": "Quartz Lantern Meridian",
                        "year": "2010",
                        "kind": "serie",
                    },
                    {
                        "id": "quartz-d",
                        "title": "Quartz Lantern Meridian",
                        "year": "1975",
                        "kind": "pelicula",
                    },
                    {
                        "id": "quartz-e",
                        "title": "Quartz Lantern Meridian",
                        "year": "1980",
                        "kind": "pelicula",
                    },
                ]
            )
            return True, None

        JsonCatalogRepository(self.catalog_path, normalize_item).mutate(add_items)

        page = self.context.new_page()
        page.goto(self.base_url)
        page.wait_for_selector("#homeView:not([hidden])")
        run_library_scan(page, self.base_url, self.headers, self.library_id)

        deadline = time.monotonic() + 10
        queue_item_id = ""
        while time.monotonic() < deadline:
            queue = page.request.get(
                f"{self.base_url}/api/scanner/queue", headers=self.headers
            ).json()
            match = next(
                (
                    item
                    for item in queue["items"]
                    if item["detected_title"] == "Quartz Lantern Meridian"
                ),
                None,
            )
            if match:
                queue_item_id = match["id"]
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("New scanner item was not found in time")

        self.addCleanup(
            lambda: self.context.request.post(
                f"{self.base_url}/api/scanner/queue/{queue_item_id}",
                data=json.dumps({"action": "ignore"}),
                headers=self.headers,
            )
        )

        click_desktop_menu_action(page, "inbox")
        page.locator("#inboxScannerMode").click()
        page.locator(f'[data-scanner-item="{queue_item_id}"]').click()
        page.wait_for_selector(".scanner-candidate-card")

        # All 5 fixture items must surface as candidates -- if the legacy
        # silent-auto-match path swallowed one, this catches it directly.
        self.assertEqual(page.locator(".scanner-candidate-card").count(), 5)
        self.assertEqual(page.locator(".scanner-candidates > .scanner-candidate-card").count(), 3)
        hidden_cards = page.locator("details.scanner-candidates-more .scanner-candidate-card")
        self.assertEqual(hidden_cards.count(), 2)
        self.assertFalse(hidden_cards.first.is_visible())

        page.locator("details.scanner-candidates-more summary").click()
        self.assertTrue(hidden_cards.first.is_visible())

        page.close()


class LoginAccessibilityTests(unittest.TestCase):
    """Login page coverage. Only needs the server up, not an authenticated
    session, so it gets its own minimal fixture."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        catalog_path = root / "catalog.json"
        JsonCatalogRepository(catalog_path, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995"})]
        )
        instance_path = root / "instance.db"
        AuthService(SqliteIdentityRepository(instance_path)).bootstrap_owner(
            "lucas",
            "a-long-login-browser-test-password",
            catalog_name="Catálogo de Lucas",
            source_paths=[str(catalog_path)],
            write_path=str(catalog_path),
        )
        cls.port = available_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        config = ViewerConfig(
            patterns=[str(catalog_path)],
            title="Movie Inbox Login Test",
            write_json=str(catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=cls.port,
            api_token="login-browser-test-token",
            instance_db=str(instance_path),
            member_catalog_dir=str(root / "member-catalogs"),
        )
        cls.server = uvicorn.Server(
            uvicorn.Config(create_app(config), host="127.0.0.1", port=cls.port, log_level="error")
        )
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        wait_until_healthy(cls.base_url)
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()
        cls.server.should_exit = True
        cls.server_thread.join(timeout=10)
        cls.temporary.cleanup()

    def test_decorative_member_photo_is_not_an_empty_landmark(self) -> None:
        page = self.browser.new_page()
        page.goto(f"{self.base_url}/login")
        page.wait_for_selector("#loginForm")

        # A decorative image wrapped only in `aria-hidden="true"` produces no
        # landmark at all; the old markup used a bare <aside>, which browsers
        # expose as an (empty, unlabelled) "complementary" landmark region.
        snapshot = page.locator("body").aria_snapshot()
        self.assertNotIn("complementary", snapshot)
        page.close()

    def test_login_password_eye_and_compact_submit_fit_the_membership_card(self) -> None:
        page = self.browser.new_page(viewport={"width": 480, "height": 900})
        page.goto(f"{self.base_url}/login")
        page.wait_for_selector("#loginForm")

        password_box = page.locator("#loginPassword").bounding_box()
        visibility = page.locator("#showPassword")
        visibility_box = visibility.bounding_box()
        submit_box = page.locator("#loginSubmit").bounding_box()
        pass_box = page.locator(".member-login-pass").bounding_box()
        self.assertIsNotNone(password_box)
        self.assertIsNotNone(visibility_box)
        self.assertIsNotNone(submit_box)
        self.assertIsNotNone(pass_box)
        self.assertGreaterEqual(visibility_box["height"], 44)
        self.assertGreaterEqual(visibility_box["x"], password_box["x"] + password_box["width"] - 48)
        self.assertLessEqual(
            visibility_box["y"] + visibility_box["height"],
            password_box["y"] + password_box["height"] + 1,
        )
        self.assertGreaterEqual(submit_box["y"], password_box["y"] + password_box["height"])
        self.assertGreaterEqual(submit_box["width"], 132)
        self.assertLess(submit_box["width"], password_box["width"])
        self.assertAlmostEqual(
            submit_box["x"] + submit_box["width"] / 2,
            password_box["x"] + password_box["width"] / 2,
            delta=1,
        )
        self.assertLess(pass_box["height"], pass_box["width"])
        self.assertEqual(page.locator("#loginForm input[type='checkbox']").count(), 0)
        self.assertEqual(page.get_by_role("button", name="Entrar", exact=True).count(), 1)
        self.assertEqual(page.locator("#loginPassword").get_attribute("type"), "password")
        self.assertEqual(visibility.get_attribute("aria-label"), "Mostrar contraseña")
        visibility.click()
        self.assertEqual(page.locator("#loginPassword").get_attribute("type"), "text")
        self.assertEqual(visibility.get_attribute("aria-pressed"), "true")
        self.assertEqual(visibility.get_attribute("aria-label"), "Ocultar contraseña")
        visibility.click()
        self.assertEqual(page.locator("#loginPassword").get_attribute("type"), "password")

        page.evaluate("setFeedback('Usuario o contraseña incorrectos.')")
        feedback_box = page.locator("#loginFeedback").bounding_box()
        footer_box = page.locator(".login-pass-footer").bounding_box()
        self.assertIsNotNone(feedback_box)
        self.assertIsNotNone(footer_box)
        self.assertLessEqual(feedback_box["y"] + feedback_box["height"], footer_box["y"])
        page.close()


if __name__ == "__main__":
    unittest.main()
