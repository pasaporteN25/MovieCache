from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from movie_inbox.cli.main import COMMANDS
from movie_inbox.external.registry import ExternalSourceService
from movie_inbox.web.app import create_app
from movie_inbox.web.assets import render_html, static_asset
from movie_inbox.web.config import ViewerConfig


class PackageLayoutTests(unittest.TestCase):
    def test_installed_command_surface_is_complete(self) -> None:
        self.assertEqual(set(COMMANDS), {"import", "scan", "serve", "migrate", "enrich", "match", "db"})

    def test_external_clients_are_registered_independently(self) -> None:
        service = ExternalSourceService()
        self.assertEqual(set(service.adapters), {"wikipedia", "imdb", "filmaffinity"})

    def test_packaged_frontend_assets_are_loadable(self) -> None:
        html = render_html("Catalog <Test>", "session-token")
        self.assertIn("Catalog &lt;Test&gt;", html)
        self.assertIn('content="session-token"', html)
        self.assertIsNotNone(static_asset("style.css"))
        self.assertIsNotNone(static_asset("app.js"))
        self.assertIsNone(static_asset("../pyproject.toml"))

    def test_fastapi_application_disables_public_api_documentation(self) -> None:
        app = create_app(
            ViewerConfig(
                patterns=["catalog.json"],
                title="Movie Inbox",
                write_json="catalog.json",
                image_cache=False,
                image_cache_dir=".catalog-cache/images",
                image_cache_max_bytes=1024,
                port=8765,
                api_token="test-token",
            )
        )
        paths = {route.path for route in app.routes}
        self.assertNotIn("/docs", paths)
        self.assertNotIn("/openapi.json", paths)
        self.assertIn("/healthz", paths)


if __name__ == "__main__":
    unittest.main()
