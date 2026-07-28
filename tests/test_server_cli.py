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


class ServerCliTests(unittest.TestCase):
    def test_serve_starts_uvicorn_with_one_loopback_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog.json"
            password_file = Path(temporary) / "owner-password.txt"
            password_file.write_text("a-long-local-password\n", encoding="utf-8")
            JsonCatalogRepository(catalog, normalize_item).write([])

            with patch("movie_inbox.web.server.uvicorn.run") as run, redirect_stdout(StringIO()):
                result = server.main([
                    str(catalog),
                    "--owner-username",
                    "lucas",
                    "--owner-password-file",
                    str(password_file),
                    "--no-open",
                ])

            self.assertEqual(result, 0)
            app = run.call_args.args[0]
            self.assertIn("/healthz", {route.path for route in app.routes})
            self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
            self.assertEqual(run.call_args.kwargs["workers"], 1)
            self.assertEqual(run.call_args.kwargs["forwarded_allow_ips"], "127.0.0.1")
            self.assertFalse(run.call_args.kwargs["access_log"])
            self.assertTrue((Path(temporary) / ".movie-inbox" / "instance.db").is_file())

    def test_non_loopback_bind_requires_public_origin(self) -> None:
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            server.main(["catalog.json", "--host", "0.0.0.0", "--no-open"])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
