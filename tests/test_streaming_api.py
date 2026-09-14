"""Owner writes to the streaming back office ask for the token and the origin.

The 0.9.0 security review found the one owner POST that did not: refreshing a
market's platform list. The session cookie is SameSite=Strict, so no other site
could have sent it, but every owner write keeps the same rule.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

_ORIGIN = "http://127.0.0.1:8765"
_TOKEN = "test-token"
_REFRESH = "/api/streaming/regions/AR/providers/refresh"


def _headers(*, token: bool = True, origin: bool = True) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Movie-Inbox-Token"] = _TOKEN
    if origin:
        headers["Origin"] = _ORIGIN
    return headers


class StreamingOwnerWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        catalog = root / "catalog.json"
        JsonCatalogRepository(catalog, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        instance = root / "instance.db"
        password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
            "lucas",
            password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(catalog)],
            write_path=str(catalog),
        )
        media = root / "media"
        media.mkdir()
        config = ViewerConfig(
            patterns=[str(catalog)],
            title="Movie Inbox Test",
            write_json=str(catalog),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token=_TOKEN,
            instance_db=str(instance),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media),),
            library_scheduler_poll_seconds=3600,
        )
        context = TestClient(create_app(config), base_url=_ORIGIN)
        self.client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        login = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": password}),
            headers=_headers(),
        )
        self.assertEqual(login.status_code, 200, login.content)

    def test_refreshing_providers_without_the_token_is_refused(self) -> None:
        response = self.client.post(_REFRESH, content="{}", headers=_headers(token=False))
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["reason"], "invalid_token")

    def test_refreshing_providers_without_the_origin_is_refused(self) -> None:
        response = self.client.post(_REFRESH, content="{}", headers=_headers(origin=False))
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["reason"], "invalid_origin")

    def test_with_both_the_request_reaches_the_service(self) -> None:
        # Past the guards, this instance has no streaming source configured.
        response = self.client.post(_REFRESH, content="{}", headers=_headers())
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()["reason"], "streaming_source_not_configured")


if __name__ == "__main__":
    unittest.main()
