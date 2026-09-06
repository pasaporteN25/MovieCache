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


def click_desktop_menu_action(page, action: str) -> None:
    page.locator("#systemMenu > summary").click()
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
                    "page_image": "https://example.invalid/u2-r6-broken-poster.jpg",
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
        preview = page.locator('[data-home-shelf-preview="available"]')
        preview.wait_for()
        page.wait_for_function(
            "document.querySelector('.home-shelf-preview-art img')?.hidden === true"
        )
        poster = preview.locator(".home-shelf-preview-art img")
        fallback = preview.locator(".home-shelf-preview-placeholder")
        poster.dispatch_event("load")
        self.assertFalse(poster.is_hidden())
        self.assertFalse(fallback.is_visible())
        poster.dispatch_event("error")
        self.assertTrue(poster.is_hidden())
        self.assertTrue(fallback.is_visible())

        geometry = page.evaluate(
            """() => {
                const box = selector => document.querySelector(selector).getBoundingClientRect();
                const header = box('.app-header');
                const brand = box('.brand-lockup');
                const title = box('h1');
                const display = box('.home-furniture-display');
                const body = box('.home-furniture-display-body');
                const art = box('.home-shelf-preview-art');
                const copy = box('.home-shelf-preview-copy');
                const panel = box('.home-furniture-action-panel');
                const summaryStyle = getComputedStyle(
                    document.querySelector('.home-shelf-preview-summary')
                );
                return {
                    overflow: document.documentElement.scrollWidth - innerWidth,
                    headerHeight: header.height,
                    brandWidth: brand.width,
                    titleWidth: title.width,
                    titleHeight: title.height,
                    displayWidth: display.width,
                    bodyColumns: getComputedStyle(
                        document.querySelector('.home-furniture-display-body')
                    ).gridTemplateColumns,
                    artWidth: art.width,
                    artRatio: art.height / art.width,
                    sameRow: Math.abs(art.top - copy.top),
                    panelAfterDisplay: panel.top - display.bottom,
                    panelWidth: panel.width,
                    summaryFontSize: Number.parseFloat(summaryStyle.fontSize),
                    summaryLineHeight: Number.parseFloat(summaryStyle.lineHeight),
                    summaryDisplay: summaryStyle.display,
                };
            }"""
        )
        self.assertLessEqual(geometry["overflow"], 1)
        self.assertLess(geometry["headerHeight"], 230)
        self.assertGreater(geometry["brandWidth"], 320)
        self.assertGreater(geometry["titleWidth"], 300)
        self.assertLess(geometry["titleHeight"], 90)
        self.assertGreater(geometry["displayWidth"], 330)
        self.assertIn("92px", geometry["bodyColumns"])
        self.assertGreaterEqual(geometry["artWidth"], 90)
        self.assertAlmostEqual(geometry["artRatio"], 1.5, delta=0.08)
        self.assertLessEqual(geometry["sameRow"], 1)
        self.assertGreaterEqual(geometry["panelAfterDisplay"], 11)
        self.assertGreater(geometry["panelWidth"], 330)
        self.assertGreaterEqual(geometry["summaryFontSize"], 15)
        self.assertGreaterEqual(geometry["summaryLineHeight"], 21)
        self.assertIn(geometry["summaryDisplay"], ("flow-root", "-webkit-box"))
        self.assertTrue(fallback.is_visible())
        self.assertEqual(preview.locator(".home-shelf-preview-action").count(), 2)
        for action in preview.locator(".home-shelf-preview-action").all():
            action_box = action.bounding_box()
            self.assertIsNotNone(action_box)
            self.assertGreaterEqual(action_box["height"], 44)

        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(100)
        navigation_top = page.locator(".primary-nav").bounding_box()["y"]
        for action in preview.locator(".home-shelf-preview-action").all():
            action_box = action.bounding_box()
            self.assertLessEqual(action_box["y"] + action_box["height"], navigation_top - 8)

        page.set_viewport_size({"width": 320, "height": 720})
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )

    def test_header_utilities_open_collection_search_and_add(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        click_desktop_menu_action(page, "search")
        page.wait_for_selector("#collectionView:not([hidden])")
        page.wait_for_function("document.activeElement.id === 'query'")

        page.locator(".brand-home").click()
        page.wait_for_selector("#homeView:not([hidden])")

        click_desktop_menu_action(page, "add")
        page.wait_for_selector("#collectionView:not([hidden])")
        page.wait_for_function("document.activeElement.id === 'catalogTitle'")

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
        for width, height in ((1280, 720), (1440, 900), (1920, 1080)):
            page.set_viewport_size({"width": width, "height": height})
            layout_metrics = page.evaluate(
                """() => {
                    const stats = document.querySelector('#stats').getBoundingClientRect();
                    const statsStyle = getComputedStyle(document.querySelector('#stats'));
                    const rows = [...document.querySelectorAll('[data-playlist-entry]')];
                    const firstHeader = document.querySelector('.spotlight-playlist th');
                    const firstCell = document.querySelector('.spotlight-playlist td');
                    const firstSpineMeta = document.querySelector('.vhs-spine-meta');
                    const previewFacts = document.querySelector('.spotlight-preview-facts');
                    const tableWrap = document.querySelector(
                        '.spotlight-table-wrap'
                    ).getBoundingClientRect();
                    return {
                        viewportHeight: window.innerHeight,
                        pageHeight: document.documentElement.scrollHeight,
                        pageWidth: document.documentElement.scrollWidth,
                        viewportWidth: window.innerWidth,
                        headerHeight: document.querySelector(
                            '.app-header'
                        ).getBoundingClientRect().height,
                        statsFontSize: parseFloat(statsStyle.fontSize),
                        playlistHeaderFontSize: parseFloat(
                            getComputedStyle(firstHeader).fontSize
                        ),
                        playlistCellFontSize: parseFloat(
                            getComputedStyle(firstCell).fontSize
                        ),
                        spineMetaFontSize: parseFloat(
                            getComputedStyle(firstSpineMeta).fontSize
                        ),
                        previewFactsFit:
                            previewFacts.scrollWidth <= previewFacts.clientWidth + 1,
                        statsHeight: stats.height,
                        statsLineHeight: parseFloat(statsStyle.lineHeight),
                        firstRowHeight: rows[0]?.getBoundingClientRect().height || 0,
                        lastRowBottom: rows.at(-1)?.getBoundingClientRect().bottom || 0,
                        tableBottom: tableWrap.bottom
                    };
                }"""
            )
            # U2-R.C3 deliberately lets the complete lower cabinet continue
            # vertically instead of compressing or hiding its console at 720p.
            self.assertGreaterEqual(layout_metrics["pageHeight"], height, layout_metrics)
            self.assertLessEqual(layout_metrics["pageHeight"], height + 320, layout_metrics)
            if (width, height) == (1440, 900):
                self.assertLessEqual(layout_metrics["pageHeight"], height + 160, layout_metrics)
            if (width, height) == (1920, 1080):
                self.assertLessEqual(layout_metrics["pageHeight"], height + 1, layout_metrics)
            self.assertLessEqual(
                layout_metrics["pageWidth"], layout_metrics["viewportWidth"] + 1, layout_metrics
            )
            self.assertLessEqual(layout_metrics["headerHeight"], 70, layout_metrics)
            self.assertGreaterEqual(layout_metrics["statsFontSize"], 12, layout_metrics)
            self.assertGreaterEqual(layout_metrics["playlistHeaderFontSize"], 11, layout_metrics)
            self.assertGreaterEqual(layout_metrics["playlistCellFontSize"], 12, layout_metrics)
            self.assertGreaterEqual(layout_metrics["spineMetaFontSize"], 10, layout_metrics)
            self.assertTrue(layout_metrics["previewFactsFit"], layout_metrics)
            self.assertLessEqual(
                layout_metrics["statsHeight"],
                layout_metrics["statsLineHeight"] * 1.35,
                layout_metrics,
            )
            self.assertGreaterEqual(layout_metrics["firstRowHeight"], 20, layout_metrics)
            self.assertLessEqual(
                abs(layout_metrics["lastRowBottom"] - layout_metrics["tableBottom"]),
                2,
                layout_metrics,
            )

        self.assertEqual(
            page.locator("#spotlightTitle").inner_text().strip().casefold(),
            "cartelera disponible",
        )

        ambience = page.locator(".spotlight-ambience")
        self.assertEqual(ambience.count(), 1)
        self.assertEqual(ambience.get_attribute("aria-hidden"), "true")
        self.assertEqual(
            ambience.evaluate("element => getComputedStyle(element).pointerEvents"), "none"
        )
        # Decorative-only: it must not sit above the real controls it shares a
        # stacking context with, or it would silently swallow clicks/taps.
        stage_z_index = page.locator(".spotlight-stage").evaluate(
            "element => getComputedStyle(element).zIndex"
        )
        ambience_z_index = ambience.evaluate("element => getComputedStyle(element).zIndex")
        self.assertGreater(int(stage_z_index or "0"), int(ambience_z_index or "0"))

        self.assertEqual(page.locator(".spotlight-poster-caption").count(), 0)
        self.assertEqual(page.locator(".spotlight-carousel-controls").count(), 0)
        self.assertEqual(page.locator(".spotlight-selector-heading strong").count(), 0)
        self.assertEqual(page.locator(".spotlight-reason").count(), 0)
        self.assertEqual(page.locator(".spotlight-preview-signal[aria-hidden='true']").count(), 1)
        signal_points = page.locator(".spotlight-signal-wave").get_attribute("points")
        marquee_geometry = page.evaluate(
            """() => {
                const selector = document.querySelector(
                    '.spotlight-selector'
                ).getBoundingClientRect();
                const heading = document.querySelector(
                    '.spotlight-selector-heading'
                ).getBoundingClientRect();
                const indicators = document.querySelector(
                    '.spotlight-selector-options'
                ).getBoundingClientRect();
                const preview = document.querySelector(
                    '.spotlight-preview'
                ).getBoundingClientRect();
                const signal = document.querySelector(
                    '.spotlight-preview-signal'
                ).getBoundingClientRect();
                return {
                    headingCenterRatio:
                        ((heading.top + heading.height / 2) - selector.top) / selector.height,
                    indicatorCenterRatio:
                        ((indicators.top + indicators.height / 2) - selector.top) / selector.height,
                    signalWidthRatio: signal.width / preview.width
                };
            }"""
        )
        self.assertGreaterEqual(marquee_geometry["headingCenterRatio"], 0.085)
        self.assertLessEqual(marquee_geometry["headingCenterRatio"], 0.115)
        self.assertGreaterEqual(marquee_geometry["indicatorCenterRatio"], 0.87)
        self.assertLessEqual(marquee_geometry["indicatorCenterRatio"], 0.915)
        self.assertGreaterEqual(marquee_geometry["signalWidthRatio"], 0.38)
        self.assertEqual(
            page.locator("#spotlight").evaluate(
                "element => getComputedStyle(element).borderTopWidth"
            ),
            "0px",
        )
        self.assertEqual(
            page.locator(".spotlight-selector").evaluate(
                "element => getComputedStyle(element).borderRightWidth"
            ),
            "0px",
        )
        poster_fill = page.locator(".spotlight-poster-trigger").evaluate(
            """element => {
                const trigger = element.getBoundingClientRect();
                const art = element.firstElementChild.getBoundingClientRect();
                return {
                    width: Math.abs(trigger.width - art.width),
                    height: Math.abs(trigger.height - art.height)
                };
            }"""
        )
        self.assertLessEqual(poster_fill["width"], 1)
        self.assertLessEqual(poster_fill["height"], 1)
        poster_geometry = page.locator(".spotlight-poster-card").evaluate(
            """element => {
                const selector = element.closest('.spotlight-selector').getBoundingClientRect();
                const card = element.getBoundingClientRect();
                const poster = element.querySelector(
                    '.spotlight-poster, .spotlight-poster-fallback'
                );
                return {
                    topRatio: (card.top - selector.top) / selector.height,
                    bottomRatio: (card.bottom - selector.top) / selector.height,
                    objectFit: poster ? getComputedStyle(poster).objectFit : ''
                };
            }"""
        )
        self.assertGreaterEqual(poster_geometry["topRatio"], 0.18)
        self.assertLessEqual(poster_geometry["bottomRatio"], 0.87)
        self.assertEqual(poster_geometry["objectFit"], "contain")
        self.assertEqual(
            page.locator(".spotlight-selector-heading span").inner_text().strip().casefold(),
            "hoy",
        )

        catalog_box = page.locator("#catalogButton").bounding_box()
        menu_box = page.locator("#systemMenu > summary").bounding_box()
        self.assertIsNotNone(catalog_box)
        self.assertIsNotNone(menu_box)
        self.assertLessEqual(abs(menu_box["x"] - (catalog_box["x"] + catalog_box["width"])), 1)

        desktop_date_control = page.locator(
            ".spotlight-playlist-head > .spotlight-date-control-desktop"
        )
        self.assertEqual(desktop_date_control.count(), 1)
        self.assertEqual(
            desktop_date_control.evaluate("element => getComputedStyle(element).position"),
            "static",
        )
        desktop_date_control.locator('[data-click="home-date-yesterday"]').click()
        page.wait_for_function(
            "document.querySelector('.spotlight-selector-heading span')?."
            "textContent.trim() === 'Ayer'"
        )
        self.assertEqual(
            desktop_date_control.locator('[data-click="home-date-yesterday"]').get_attribute(
                "aria-pressed"
            ),
            "true",
        )
        self.assertEqual(
            page.locator(".spotlight-signal-wave").get_attribute("points"),
            signal_points,
        )

    def test_home_selector_keeps_one_tab_stop_and_changes_preview_with_arrows(self) -> None:
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
        selector = page.locator(".spotlight-selector-option")
        self.assertEqual(selector.count(), 2)
        self.assertEqual(selector.nth(0).get_attribute("tabindex"), "0")
        self.assertEqual(selector.nth(1).get_attribute("tabindex"), "-1")
        self.assertLessEqual(selector.nth(0).bounding_box()["height"], 40)
        first_signal_points = page.locator(".spotlight-signal-wave").get_attribute("points")

        selector.nth(0).focus()
        selected_before = page.evaluate("window.getHomePlaybackState().selectedEntryKey")
        page.keyboard.press("ArrowDown")

        self.assertEqual(page.evaluate("document.activeElement.dataset.index"), "1")
        self.assertEqual(selector.nth(1).get_attribute("aria-pressed"), "true")
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), selected_before
        )
        page.keyboard.press("Enter")
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), selected_before
        )

        page.keyboard.press("Tab")
        self.assertIn(
            page.evaluate("document.activeElement.dataset.click"),
            {
                "spotlight-select",
                "spotlight-air-select",
                "playlist-select",
                "home-date-today",
                "home-date-yesterday",
            },
        )
        page.locator("[data-playlist-entry]").nth(1).click()
        second_signal_points = page.locator(".spotlight-signal-wave").get_attribute("points")
        self.assertNotEqual(second_signal_points, first_signal_points)
        page.locator("[data-playlist-entry]").nth(0).click()
        self.assertEqual(
            page.locator(".spotlight-signal-wave").get_attribute("points"),
            first_signal_points,
        )
        page.set_viewport_size({"width": 390, "height": 844})
        self.assertTrue(page.locator(".spotlight-date-control-mobile").is_visible())
        self.assertFalse(page.locator(".spotlight-date-control-desktop").is_visible())
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
            '"▶"',
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
        page.locator('[data-click="spotlight-air-select"][data-index="5"]').click()
        self.assertEqual(page.evaluate("window.getHomePlaybackState().spotlightIndex"), 5)
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.click"), "spotlight-air-select"
        )
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
        viewport_metrics = page.evaluate(
            """() => ({
                viewport: window.innerHeight,
                page: document.documentElement.scrollHeight,
                header: document.querySelector('.app-header')?.getBoundingClientRect().height || 0,
                spotlight: document.querySelector(
                    '#spotlight'
                )?.getBoundingClientRect().height || 0,
                categories: document.querySelector(
                    '#homeShelfCategories'
                )?.getBoundingClientRect().height || 0,
                sections: document.querySelector(
                    '#homeSections'
                )?.getBoundingClientRect().height || 0
            })"""
        )
        self.assertGreater(viewport_metrics["page"], viewport_metrics["viewport"])
        self.assertLessEqual(
            viewport_metrics["page"], viewport_metrics["viewport"] + 320, viewport_metrics
        )

    def test_desktop_menu_duplicate_commands_close_details_and_navigate(self) -> None:
        page = self.page

        def open_menu() -> None:
            page.locator("#systemMenu > summary").click()
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
        self.assertEqual(shelf.nth(0).get_attribute("data-vhs-state"), "selected")
        self.assertEqual(shelf.nth(1).get_attribute("data-vhs-state"), "closed")
        # The row shows each work as a spine (title/meta only, no raster asset);
        # the audited PNG frame now belongs to the opened preview instead.
        preview_frame = page.locator(
            '[data-home-shelf-preview="available"] .home-shelf-preview-frame'
        )
        self.assertIn(
            "vhs-cassette-frame-v1.png",
            preview_frame.evaluate("element => getComputedStyle(element).backgroundImage"),
        )

        shelf.nth(0).focus()
        page.keyboard.press("ArrowRight")

        self.assertEqual(
            page.evaluate("document.activeElement.dataset.entryKey"), "available-akira"
        )
        self.assertEqual(shelf.nth(1).get_attribute("aria-pressed"), "true")
        self.assertEqual(shelf.nth(1).get_attribute("data-vhs-state"), "selected")
        self.assertEqual(
            page.locator('[data-home-shelf-preview="available"] h3').text_content(), "Akira"
        )
        self.assertEqual(
            page.locator('[data-home-shelf-preview="available"]').get_attribute("data-vhs-state"),
            "open",
        )
        page.keyboard.press("Tab")
        self.assertEqual(
            page.evaluate("document.activeElement.dataset.click"),
            "open-detail-with-case-transition",
        )

        shelf.nth(0).click()
        self.assertEqual(
            page.locator('[data-home-shelf-preview="available"] h3').text_content(), "Heat"
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
        self.assertIn(
            "vhs-continuous-furniture-v2.png",
            cabinet.evaluate("element => getComputedStyle(element).backgroundImage"),
        )
        self.assertTrue(
            cabinet.evaluate(
                """element => {
                    const preview = element.querySelector('#homeShelfPreview');
                    return preview && preview.parentElement === element;
                }"""
            )
        )
        self.assertTrue(
            all(
                "vhs-shelf-bay-v1.png"
                not in bays.nth(index).evaluate(
                    "element => getComputedStyle(element).backgroundImage"
                )
                for index in range(4)
            )
        )
        self.assertTrue(furniture.evaluate("element => element.scrollWidth > element.clientWidth"))
        navigation = page.locator("#homeShelfCategories")
        controls = navigation.locator(".home-shelf-scroll-control")
        self.assertTrue(navigation.is_visible())
        self.assertEqual(
            navigation.locator(".home-shelf-navigation-label").text_content(),
            "4 categorías · recorrido lateral",
        )
        self.assertTrue(controls.nth(0).is_disabled())
        self.assertFalse(controls.nth(1).is_disabled())
        self.assertEqual(page.locator(".home-program-heading").count(), 0)
        self.assertEqual(page.locator(".home-shelf-bay > h2.sr-only").count(), 4)
        self.assertEqual(
            furniture.evaluate("element => getComputedStyle(element).scrollbarWidth"), "none"
        )
        geometry = cabinet.evaluate(
            """element => {
                const cabinet = element.getBoundingClientRect();
                const shelf = element.querySelector('#homeSections').getBoundingClientRect();
                const panels = [
                    element.querySelector('.home-furniture-action-panel'),
                    element.querySelector('.home-furniture-display'),
                    element.querySelector('.home-furniture-format-panel'),
                ].map(node => node.getBoundingClientRect());
                return {
                    shelfTop: (shelf.top - cabinet.top) / cabinet.height,
                    shelfBottom: (shelf.bottom - cabinet.top) / cabinet.height,
                    panelsContained: panels.every(panel =>
                        panel.left >= cabinet.left && panel.right <= cabinet.right
                        && panel.top >= cabinet.top && panel.bottom <= cabinet.bottom
                    ),
                    panelsSeparated: panels[0].right <= panels[1].left
                        && panels[1].right <= panels[2].left,
                };
            }"""
        )
        self.assertAlmostEqual(geometry["shelfTop"], 0.1844, delta=0.012)
        self.assertAlmostEqual(geometry["shelfBottom"], 0.639, delta=0.012)
        self.assertTrue(geometry["panelsContained"])
        self.assertTrue(geometry["panelsSeparated"])
        first_spine = page.locator('[data-home-section="bay-0"] .home-shelf-tape').nth(0)
        spine_readability = first_spine.evaluate(
            """element => {
                const spine = element.getBoundingClientRect();
                const title = element.querySelector('.vhs-spine-title').getBoundingClientRect();
                const meta = element.querySelector('.vhs-spine-meta');
                const metaRect = meta.getBoundingClientRect();
                return {
                    titleHeightRatio: title.height / spine.height,
                    metaHeight: metaRect.height,
                    metaWritingMode: getComputedStyle(meta).writingMode,
                };
            }"""
        )
        self.assertGreaterEqual(spine_readability["titleHeightRatio"], 0.5)
        self.assertLessEqual(spine_readability["metaHeight"], 20)
        self.assertEqual(spine_readability["metaWritingMode"], "horizontal-tb")
        self.assertEqual(
            first_spine.locator(".vhs-spine-meta > span").all_text_contents(),
            ["1995", "PEL"],
        )
        self.assertIn(
            "La insoportable levedad del ser. 1995. Formato: pelicula.",
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

        page.emulate_media(reduced_motion="reduce")
        self.assertEqual(
            furniture.evaluate("element => getComputedStyle(element).scrollBehavior"), "auto"
        )

    def test_home_furniture_console_keeps_primary_copy_legible_at_desktop_sizes(
        self,
    ) -> None:
        page = self.page
        synopsis = (
            "Un detective y un ladrón profesional se enfrentan en Los Ángeles "
            "mientras sus vidas privadas empiezan a reflejarse."
        )

        def add_console_copy(route) -> None:
            response = route.fetch()
            payload = response.json()
            items = payload.get("items") or []
            home = payload.get("home") or {}
            if items:
                item = {
                    **items[0],
                    "title": "Heat: fuego contra fuego",
                    "description": synopsis,
                    "wikipedia_extract": "Este extracto no debe desplazar la descripción.",
                    "directors": ["Michael Mann"],
                    "genres": ["Policial"],
                }
                home["sections"] = [
                    {
                        "id": "console",
                        "title": "Disponible esta noche",
                        "items": [
                            {
                                "key": "console-heat",
                                "origin": {"kind": "catalog"},
                                "item": item,
                                "reason": {
                                    "label": "Lista para ver",
                                    "detail": "El motivo editorial queda detrás de la sinopsis.",
                                },
                            }
                        ],
                    }
                ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", add_console_copy)
        self._open_and_wait_for_catalog(page)
        preview = page.locator('[data-home-shelf-preview="console"]')
        self.assertEqual(preview.locator(".home-shelf-preview-summary").text_content(), synopsis)
        self.assertIn(
            "Dirección: Michael Mann",
            preview.locator(".home-shelf-preview-meta").text_content(),
        )

        for width, height in ((1280, 720), (1440, 900), (1920, 1080)):
            with self.subTest(viewport=(width, height)):
                page.set_viewport_size({"width": width, "height": height})
                metrics = preview.evaluate(
                    """element => {
                        const cabinet = element.closest('.home-furniture');
                        const display = element.querySelector('.home-furniture-display');
                        const copy = element.querySelector('.home-shelf-preview-copy');
                        const title = copy.querySelector('h3');
                        const meta = copy.querySelector('.home-shelf-preview-meta');
                        const summary = copy.querySelector('.home-shelf-preview-summary');
                        const panel = element.querySelector('.home-furniture-action-panel');
                        const panelRect = panel.getBoundingClientRect();
                        const actions = [...panel.querySelectorAll('button')];
                        return {
                            cabinetHeight: cabinet.getBoundingClientRect().height,
                            displayHeight: display.getBoundingClientRect().height,
                            titleHeight: title.getBoundingClientRect().height,
                            metaFontSize: parseFloat(getComputedStyle(meta).fontSize),
                            summaryFontSize: parseFloat(getComputedStyle(summary).fontSize),
                            summaryHeight: summary.getBoundingClientRect().height,
                            copyFits: copy.scrollHeight <= copy.clientHeight + 1,
                            actionHeights: actions.map(
                                action => action.getBoundingClientRect().height
                            ),
                            actionsContained: actions.every(action => {
                                const rect = action.getBoundingClientRect();
                                return rect.top >= panelRect.top - 1
                                    && rect.bottom <= panelRect.bottom + 1
                                    && rect.left >= panelRect.left - 1
                                    && rect.right <= panelRect.right + 1;
                            }),
                        };
                    }"""
                )
                self.assertGreaterEqual(metrics["cabinetHeight"], 639)
                self.assertGreaterEqual(metrics["displayHeight"], 112)
                self.assertGreaterEqual(metrics["titleHeight"], 16)
                self.assertGreaterEqual(metrics["metaFontSize"], 12)
                self.assertGreaterEqual(metrics["summaryFontSize"], 12)
                self.assertGreaterEqual(metrics["summaryHeight"], 16)
                self.assertTrue(metrics["copyFits"])
                self.assertTrue(metrics["actionsContained"])
                self.assertTrue(
                    all(action_height >= 36 for action_height in metrics["actionHeights"])
                )

        page.set_viewport_size({"width": 1280, "height": 720})
        self.assertGreater(
            page.evaluate("document.documentElement.scrollHeight"),
            page.evaluate("window.innerHeight"),
        )

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
        self.assertEqual(page.locator("#homeSections").get_attribute("data-bay-count"), "0")
        self.assertEqual(page.locator("#homeSections").get_attribute("tabindex"), "-1")

    def test_direct_spine_choice_activates_its_bay_but_keeps_playlist_independent(
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
        self.assertEqual(page.locator(".home-shelf-preview").count(), 1)

        initial_state = page.evaluate("window.getHomePlaybackState()")
        initial_playlist_selection = page.locator("[data-playlist-entry].is-selected").evaluate_all(
            "elements => elements.map(element => element.dataset.entryKey)"
        )

        # Clicking a spine in another visible bay activates that bay and its
        # preview directly. The upper playlist remains independent.
        memory_spines = page.locator('[data-home-section="memory"] .home-shelf-tape')
        memory_spines.nth(1).click()
        state = page.evaluate("window.getHomePlaybackState()")
        self.assertEqual(state["activeShelfId"], "memory")
        self.assertEqual(state["playlistSource"], initial_state["playlistSource"])
        self.assertEqual(state["selectedEntryKey"], initial_state["selectedEntryKey"])
        self.assertEqual(state["selectedItemId"], initial_state["selectedItemId"])
        self.assertEqual(
            page.locator('[data-home-section="memory"]').get_attribute("data-active"),
            "true",
        )
        self.assertEqual(
            page.locator('[data-home-section="available"]').get_attribute("data-active"),
            "false",
        )
        self.assertEqual(
            page.locator(".home-shelf-preview").get_attribute("data-home-shelf-preview"), "memory"
        )
        self.assertEqual(
            page.locator(".home-shelf-preview").get_attribute("data-selected-entry-key"),
            "memory-heat",
        )
        self.assertEqual(
            page.locator(".home-furniture-display-heading strong").text_content(),
            "Tu archivo pide memoria",
        )
        self.assertEqual(
            page.locator(
                '[data-home-section="memory"] .home-shelf-tape[aria-pressed="true"]'
            ).get_attribute("data-entry-key"),
            "memory-heat",
        )
        self.assertEqual(
            page.locator("[data-playlist-entry].is-selected").evaluate_all(
                "elements => elements.map(element => element.dataset.entryKey)"
            ),
            initial_playlist_selection,
        )
        self.assertEqual(page.evaluate("document.activeElement.dataset.entryKey"), "memory-heat")

        # Enter on a spine in a different bay follows the same state transition.
        available_spines = page.locator('[data-home-section="available"] .home-shelf-tape')
        available_spines.nth(1).focus()
        page.keyboard.press("Enter")
        state = page.evaluate("window.getHomePlaybackState()")
        self.assertEqual(state["activeShelfId"], "available")
        self.assertEqual(state["playlistSource"], initial_state["playlistSource"])
        self.assertEqual(state["selectedEntryKey"], initial_state["selectedEntryKey"])
        self.assertEqual(
            page.locator(".home-shelf-preview").get_attribute("data-selected-entry-key"),
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

        # Bay activation still owns the explicit playlist synchronization and
        # restores that bay's remembered spine.
        memory_bay = page.locator('[data-home-section="memory"].home-shelf-bay')
        memory_bay.dispatch_event("click")
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().playlistSource"), "shelf:memory"
        )
        self.assertEqual(
            page.evaluate("window.getHomePlaybackState().selectedEntryKey"), "memory-heat"
        )
        self.assertEqual(
            page.locator(".home-shelf-preview").get_attribute("data-selected-entry-key"),
            "memory-heat",
        )

        page_scroll_before = page.evaluate("window.scrollY")
        selected_row = page.locator("[data-playlist-entry].is-selected")
        selected_row.focus()
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
                    const rail = element.closest('.home-shelf-rail').getBoundingClientRect();
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
            page.locator(".home-shelf-preview").get_attribute("data-selected-entry-key"),
            "memory-extra-11",
        )

        self.assertEqual(page.locator(".home-shelf-preview").count(), 1)
        self.assertEqual(page.locator(".home-shelf-preview-actions button").count(), 2)

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
        self.assertNotEqual(
            plaques.nth(0).evaluate("element => getComputedStyle(element).borderColor"),
            plaques.nth(1).evaluate("element => getComputedStyle(element).borderColor"),
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
        self.assertTrue(all(width <= 221 for width in geometry["widths"]))
        self.assertLessEqual(geometry["gap"], 37)
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
                    "element => element.getBoundingClientRect().width <= 1 "
                    "&& element.getBoundingClientRect().height <= 1"
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

        preview = page.locator('[data-home-shelf-preview="available"]')
        self.assertEqual(preview.get_by_text("Ver más").count(), 1)
        self.assertEqual(preview.locator(".home-furniture-frame-strip > span").count(), 2)
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

        preview = page.locator('[data-home-shelf-preview="followed"]')
        self.assertEqual(preview.get_by_text("Ver ficha del Club").count(), 1)
        # The whole point: a not-yet-personal recommendation never offers to
        # "edit my record" for a record that doesn't exist yet.
        self.assertEqual(preview.get_by_text("Editar mi ficha").count(), 0)
        collection_action_box = preview.get_by_text("Ver ficha del Club").bounding_box()
        self.assertIsNotNone(collection_action_box)
        self.assertGreater(collection_action_box["width"], 300)
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
            page.locator('[data-home-shelf-preview="available"]').get_by_text("Ver más").click()
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
        view_more = page.locator('[data-home-shelf-preview="available"]').get_by_text("Ver más")
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
        page.locator("#externalSource").check()
        page.locator("#query").fill("Heat")
        page.locator("#searchButton").click()
        page.wait_for_selector('[data-click="prepare-merge"][data-index="0"]')

        page.locator('[data-click="prepare-merge"][data-index="0"]').click()
        page.wait_for_function(
            "(document.querySelector('#catalogMergeResults').textContent || '').includes('Heat')"
        )
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
        page.locator("#systemMenu > summary").click()
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
