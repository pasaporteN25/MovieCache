from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

import uvicorn
from playwright.sync_api import sync_playwright

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
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
        self.assertFalse(
            page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        )

        page.locator("#homeButton").focus()
        page.keyboard.press("Tab")
        self.assertEqual(page.evaluate("document.activeElement.id"), "catalogButton")

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
            "#randomButton",
        ):
            box = page.locator(selector).bounding_box()
            self.assertIsNotNone(box, selector)
            self.assertGreaterEqual(box["height"], 44, selector)

    def test_ficha_description_dialog_focus_and_naming(self) -> None:
        page = self.page
        self._open_and_wait_for_catalog(page)

        page.locator("#randomButton").focus()
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

        page.get_by_role("button", name="Cerrar").click()
        self.assertEqual(page.evaluate("document.activeElement.id"), "randomButton")

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
        page.locator("#inboxBadge").wait_for(state="visible")
        self.assertEqual(page.locator("#inboxBadge").inner_text(), "2")
        self.assertFalse(page.locator("#inboxScannerBadge").is_visible())

        page.locator("#inboxButton").click()
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
        cls.queue_item_id = queue["items"][0]["id"]
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

        page.locator("#inboxButton").click()
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
        page.locator("#inboxScannerBadge").wait_for(state="visible")
        self.assertFalse(page.locator("#inboxBadge").is_visible())
        self.assertEqual(page.locator("#inboxScannerBadge").inner_text(), "1")

        page.locator("#inboxButton").click()
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

        page.locator("#inboxButton").click()
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

        page.locator("#inboxButton").click()
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

        def add_items(items: list) -> tuple[bool, None]:
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

        page.locator("#inboxButton").click()
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


if __name__ == "__main__":
    unittest.main()
