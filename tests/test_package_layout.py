from __future__ import annotations

import unittest
import tempfile
import tomllib
from pathlib import Path

from movie_inbox import __version__
from movie_inbox.application.auth_service import AuthService
from movie_inbox.cli.main import COMMANDS
from movie_inbox.external.registry import ExternalSourceService
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.assets import (
    render_html,
    render_login_html,
    render_password_change_html,
    static_asset,
)
from movie_inbox.web.config import ViewerConfig


class PackageLayoutTests(unittest.TestCase):
    def test_runtime_version_matches_package_metadata(self) -> None:
        project = tomllib.loads(
            (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(__version__, project["project"]["version"])

    def test_installed_command_surface_is_complete(self) -> None:
        self.assertEqual(
            set(COMMANDS),
            {
                "account",
                "backup",
                "cache",
                "db",
                "enrich",
                "import",
                "match",
                "migrate",
                "scan",
                "serve",
            },
        )

    def test_external_clients_are_registered_independently(self) -> None:
        service = ExternalSourceService()
        self.assertEqual(set(service.adapters), {"wikipedia", "imdb", "filmaffinity"})

    def test_packaged_frontend_assets_are_loadable(self) -> None:
        html = render_html("Catalog <Test>", "session-token")
        self.assertIn("Catalog &lt;Test&gt;", html)
        self.assertIn('content="session-token"', html)
        self.assertIn('id="importInboxPanel"', html)
        self.assertIn('id="importSourceForm"', html)
        self.assertIn('id="scannerInboxPanel"', html)
        self.assertIn('id="adminLibraries"', html)
        self.assertIn('id="libraryDialog"', html)
        login_html = render_login_html("Catalog <Test>", "session-token")
        self.assertIn("Catalog &lt;Test&gt;", login_html)
        self.assertIn('src="/static/login.js"', login_html)
        password_html = render_password_change_html("Catalog <Test>", "session-token")
        self.assertIn("Catalog &lt;Test&gt;", password_html)
        self.assertIn('src="/static/password-change.js"', password_html)
        self.assertIsNotNone(static_asset("style.css"))
        app_js = static_asset("app.js")
        self.assertIsNotNone(app_js)
        self.assertIn(b'apiFetch("/api/imports")', app_js[0])
        self.assertIn(b'apiFetch("/api/libraries")', app_js[0])
        self.assertIn(b'apiFetch("/api/scanner/queue")', app_js[0])
        self.assertIn(b'/api/catalog/export?format=', app_js[0])
        self.assertIn(b'apiFetch("/api/image-cache/status")', app_js[0])
        self.assertIn(b'apiFetch(`/api/home?date=', app_js[0])
        self.assertIn(b'data-poster-image', app_js[0])
        self.assertIn(b'fetchpriority="${fetchPriority}"', app_js[0])
        self.assertIn(b'classList.add("is-loaded")', app_js[0])
        self.assertIn(b'"Probar recorrido"', app_js[0])
        self.assertIn(b'"Aplicar inventario"', app_js[0])
        self.assertIn(b"Crear obra y vincular ${actionObject}", app_js[0])
        self.assertIn(b'data-scanner-review="confirm-candidate"', app_js[0])
        self.assertIn(b"Omitir ${actionObject}", app_js[0])
        self.assertIn(b'apiFetch("/api/library-paths/check"', app_js[0])
        self.assertIn(b'class="search-source-group"', app_js[0])
        self.assertIsNotNone(static_asset("login.js"))
        self.assertIsNotNone(static_asset("password-change.js"))
        self.assertIsNone(static_asset("../pyproject.toml"))

    def test_fastapi_application_disables_public_api_documentation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog.json"
            catalog.write_text('{"schema_version": 5, "items": []}\n', encoding="utf-8")
            instance = root / "instance.db"
            repository = SqliteIdentityRepository(instance)
            AuthService(repository).bootstrap_owner(
                "owner",
                "a-long-local-password",
                catalog_name="Mi catalogo",
                source_paths=[str(catalog)],
                write_path=str(catalog),
            )
            app = create_app(
                ViewerConfig(
                    patterns=[str(catalog)],
                    title="Movie Inbox",
                    write_json=str(catalog),
                    image_cache=False,
                    image_cache_dir=str(root / "images"),
                    image_cache_max_bytes=1024,
                    port=8765,
                    api_token="test-token",
                    instance_db=str(instance),
                )
            )
            paths = {route.path for route in app.routes}
            self.assertNotIn("/docs", paths)
            self.assertNotIn("/openapi.json", paths)
            self.assertIn("/healthz", paths)
            self.assertIn("/login", paths)
            self.assertIn("/auth/login", paths)
            self.assertIn("/password-change", paths)
            self.assertIn("/auth/change-password", paths)
            self.assertIn("/api/members", paths)
            self.assertIn("/api/imports", paths)
            self.assertIn("/api/imports/{draft_id}/apply", paths)
            self.assertIn("/api/libraries", paths)
            self.assertIn("/api/libraries/{library_id}/runs", paths)
            self.assertIn("/api/library-runs/{run_id}", paths)
            self.assertIn("/api/scanner/queue", paths)
            self.assertIn("/api/scanner/queue/{file_id}", paths)
            self.assertIn("/api/image-cache/status", paths)
            self.assertIn("/api/home", paths)


if __name__ == "__main__":
    unittest.main()
