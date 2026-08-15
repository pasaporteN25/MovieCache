from __future__ import annotations

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


class BrowserInterfaceTests(unittest.TestCase):
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
                        "kind": "anime",
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
        config = ViewerConfig(
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
            uvicorn.Config(create_app(config), host="127.0.0.1", port=cls.port, log_level="error")
        )
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with urlopen(f"{cls.base_url}/healthz", timeout=0.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("Browser test server did not become healthy")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.should_exit = True
        cls.server_thread.join(timeout=10)
        cls.temporary.cleanup()

    def test_authenticated_shell_is_accessible_and_responsive(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(self.base_url)
            page.get_by_label("Usuario").fill("lucas")
            page.get_by_label("Contraseña").fill(self.owner_password)
            page.get_by_role("button", name="Entrar").click()
            page.wait_for_selector("#homeView:not([hidden])")
            page.wait_for_function(
                "document.querySelector('#stats').textContent.includes('2 obras')"
            )

            self.assertEqual(page.locator(".primary-nav > .nav-action").count(), 4)
            self.assertEqual(page.locator(".primary-nav #randomButton").count(), 0)
            self.assertEqual(page.locator(".header-utilities #randomButton").count(), 1)
            self.assertFalse(
                page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            )

            page.locator("#homeButton").focus()
            page.keyboard.press("Tab")
            self.assertEqual(page.evaluate("document.activeElement.id"), "catalogButton")

            page.locator("#randomButton").focus()
            page.evaluate("openSearchDescription('', 'heat')")
            self.assertTrue(page.get_by_role("dialog", name="Heat").is_visible())
            page.get_by_role("button", name="Cerrar").click()
            self.assertEqual(page.evaluate("document.activeElement.id"), "randomButton")

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

            structural_live_regions = page.locator(
                "#collectionList[aria-live], #scannerQueue[aria-live], #memberList[aria-live]"
            )
            self.assertEqual(structural_live_regions.count(), 0)
            browser.close()


if __name__ == "__main__":
    unittest.main()
