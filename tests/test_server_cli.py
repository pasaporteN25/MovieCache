from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web import server
from movie_inbox.web.config import ExternalSourceCredentials


class ServerCliTests(unittest.TestCase):
    def test_anime_offline_index_can_be_configured_explicitly(self) -> None:
        parsed = server.build_parser().parse_args(
            ["catalog.json", "--anime-offline-index", "indexes/anime-offline.db"]
        )

        self.assertEqual(parsed.anime_offline_index, Path("indexes/anime-offline.db"))

    def test_serve_starts_uvicorn_with_one_loopback_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog.json"
            media = Path(temporary) / "media"
            media.mkdir()
            password_file = Path(temporary) / "owner-password.txt"
            password_file.write_text("a-long-local-password\n", encoding="utf-8")
            JsonCatalogRepository(catalog, normalize_item).write([])

            with patch("movie_inbox.web.server.uvicorn.run") as run, redirect_stdout(StringIO()):
                result = server.main(
                    [
                        str(catalog),
                        "--owner-username",
                        "lucas",
                        "--owner-password-file",
                        str(password_file),
                        "--library-root",
                        str(media),
                        "--image-cache-warm-interval-seconds",
                        "4",
                        "--no-open",
                    ]
                )

            self.assertEqual(result, 0)
            app = run.call_args.args[0]
            self.assertIn("/healthz", {route.path for route in app.routes})
            self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
            self.assertEqual(run.call_args.kwargs["workers"], 1)
            self.assertEqual(run.call_args.kwargs["forwarded_allow_ips"], "127.0.0.1")
            self.assertFalse(run.call_args.kwargs["access_log"])
            self.assertTrue((Path(temporary) / ".movie-inbox" / "instance.db").is_file())
            self.assertEqual(app.state.viewer_config.library_allowed_roots, (str(media.resolve()),))
            self.assertTrue(app.state.viewer_config.image_cache_warm)
            self.assertEqual(app.state.viewer_config.image_cache_warm_interval_seconds, 4)

    def test_non_loopback_bind_requires_public_origin(self) -> None:
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            server.main(["catalog.json", "--host", "0.0.0.0", "--no-open"])
        self.assertEqual(raised.exception.code, 2)

    def test_managed_scanner_root_must_be_absolute(self) -> None:
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            server.main(["catalog.json", "--library-root", "relative-media", "--no-open"])
        self.assertEqual(raised.exception.code, 2)

    def test_image_cache_warm_interval_is_bounded(self) -> None:
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            server.main(
                [
                    "catalog.json",
                    "--image-cache-warm-interval-seconds",
                    "0.1",
                    "--no-open",
                ]
            )
        self.assertEqual(raised.exception.code, 2)

    def test_tmdb_token_file_opts_instance_in_without_printing_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog.json"
            token_file = Path(temporary) / "tmdb-token.txt"
            token = "eyJ-secret-read-access-token"
            token_file.write_text(f"{token}\n", encoding="utf-8")
            JsonCatalogRepository(catalog, normalize_item).write([])
            stdout = StringIO()

            with (
                patch("movie_inbox.web.server.uvicorn.run") as run,
                patch("movie_inbox.web.server.owner_password", return_value="a-long-password"),
                redirect_stdout(stdout),
            ):
                result = server.main(
                    [
                        str(catalog),
                        "--tmdb-read-access-token-file",
                        str(token_file),
                        "--no-open",
                    ]
                )

            self.assertEqual(result, 0)
            config = run.call_args.args[0].state.viewer_config
            self.assertTrue(config.external_credentials.tmdb_configured)
            self.assertEqual(config.external_credentials.tmdb_read_access_token, token)
            self.assertIn("TMDb credentials: configured (adapter pending F5)", stdout.getvalue())
            self.assertNotIn(token, stdout.getvalue())
            self.assertNotIn(token, repr(config))
            self.assertNotIn(token, repr(config.external_credentials))

    def test_tmdb_stays_disabled_without_token_file(self) -> None:
        credentials = ExternalSourceCredentials()

        self.assertFalse(credentials.tmdb_configured)
        self.assertEqual(credentials.tmdb_read_access_token, "")

    def test_external_api_token_rejects_empty_multiline_and_oversized_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            token_file = Path(temporary) / "tmdb-token.txt"
            invalid_contents = ("\n", "first\nsecond", "x" * (16 * 1024 + 1))

            for content in invalid_contents:
                with self.subTest(size=len(content)):
                    token_file.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        server.external_api_token(token_file, source_label="TMDb")


if __name__ == "__main__":
    unittest.main()
