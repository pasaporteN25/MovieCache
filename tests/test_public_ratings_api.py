"""[F6.2]: `GET /api/ratings` over the real application, not a stub of it.

The service is covered in `tests/test_public_ratings.py`. What this file exists
to check is the half that lives outside it: that the route is wired, that an
instance without any source still answers instead of failing, and that each
attribution notice travels with the source that could have produced a score.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.public_ratings_service import PublicRatingsService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE
from movie_inbox.domain.public_ratings import IMDB_SOURCE, TMDB_SOURCE, public_rating
from movie_inbox.external.tmdb import TMDB_ATTRIBUTION_NOTICE
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.public_ratings_repository import SqlitePublicRatingsRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig


class PublicRatingsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "tmdb_url": "https://www.themoviedb.org/movie/949",
                        "imdb_url": "https://www.imdb.com/title/tt0113277/",
                        "rating": 9,
                    }
                ),
                normalize_item({"id": "sin-fuentes", "title": "Sin fuentes", "kind": "pelicula"}),
            ]
        )
        self.instance_path = root / "instance.db"
        self.password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(self.instance_path)).bootstrap_owner(
            "lucas",
            self.password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        media = root / "media"
        media.mkdir()
        self.config = ViewerConfig(
            patterns=[str(self.catalog_path)],
            title="Movie Inbox Test",
            write_json=str(self.catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(self.instance_path),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media),),
            library_scheduler_poll_seconds=3600,
        )
        self.app = create_app(self.config)
        self.context = TestClient(self.app, base_url="http://127.0.0.1:8765")
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        login = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": self.password}),
            headers=self._headers(),
        )
        self.assertEqual(login.status_code, 200, login.content)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Movie-Inbox-Token": self.config.api_token,
            "Origin": "http://127.0.0.1:8765",
            "Content-Type": "application/json",
        }

    def _get(self, path: str = "/api/ratings"):
        return self.client.get(path, headers=self._headers())

    def _install(self, **kwargs: object) -> None:
        self.app.state.public_ratings_service = PublicRatingsService(
            SqlitePublicRatingsRepository(self.instance_path),
            **kwargs,  # type: ignore[arg-type]
        )

    def test_an_instance_without_sources_answers_empty_instead_of_failing(self) -> None:
        # This is what `create_app` builds with neither a TMDb credential nor an
        # IMDb index, which is the default install.
        response = self._get()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"ratings": {}, "attribution": {}})

    def test_both_sources_reach_the_response_with_their_notices(self) -> None:
        self._install(
            imdb_lookup=lambda imdb_id: public_rating(IMDB_SOURCE, 8.3, 700_000),
            imdb_id_reader=lambda row: "tt0113277" if row.get("id") == "heat" else "",
            tmdb_loader=lambda media_type, tmdb_id: {"average": 7.8, "votes": 4321},
        )
        payload = self._get().json()

        self.assertEqual(
            [row["source"] for row in payload["ratings"]["heat"]], [IMDB_SOURCE, TMDB_SOURCE]
        )
        # A work with no external identity carries no score, and says so by
        # being absent rather than by an empty list.
        self.assertNotIn("sin-fuentes", payload["ratings"])
        self.assertEqual(payload["attribution"]["imdb"], IMDB_ATTRIBUTION_NOTICE)
        self.assertEqual(payload["attribution"]["tmdb"], TMDB_ATTRIBUTION_NOTICE)

    def test_only_the_configured_source_is_attributed(self) -> None:
        self._install(tmdb_loader=lambda media_type, tmdb_id: {"average": 7.8, "votes": 4321})
        payload = self._get().json()
        self.assertEqual(list(payload["attribution"]), ["tmdb"])

    def test_a_public_score_never_reaches_the_personal_rating(self) -> None:
        # [F3.2]'s rule, checked where it would actually break: the endpoint
        # only reads, so the viewer's own 9 survives a read that served an 8,3.
        self._install(tmdb_loader=lambda media_type, tmdb_id: {"average": 7.8, "votes": 4321})
        self._get()
        stored = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        heat = next(row for row in stored["items"] if row["id"] == "heat")
        self.assertEqual(heat["rating"], 9)
        for field in ("vote_average", "vote_count", "public_ratings", "tmdb_rating"):
            self.assertNotIn(field, heat)

    def test_the_endpoint_is_behind_the_api_token_like_every_other_read(self) -> None:
        # Public scores are not public access: the route carries the same
        # `require_token` guard as the rest of `/api/`.
        self.assertEqual(self.client.get("/api/ratings").status_code, 403)

    def test_dossier_queries_only_its_own_work_beyond_the_refresh_batch(self) -> None:
        rows = [
            normalize_item(
                {
                    "id": f"work-{index}",
                    "title": f"Work {index}",
                    "kind": "pelicula",
                    "tmdb_url": f"https://www.themoviedb.org/movie/{index + 1}",
                }
            )
            for index in range(20)
        ]
        JsonCatalogRepository(self.catalog_path, normalize_item).write(rows)
        calls = []

        def loader(media_type, tmdb_id):
            calls.append((media_type, tmdb_id))
            return {"average": 8, "votes": 100}

        self._install(tmdb_loader=loader)
        headers = {"X-Movie-Inbox-Token": "test-token"}
        response = self.client.get("/api/ratings?item_id=work-19", headers=headers)
        self.assertEqual(list(response.json()["ratings"]), ["work-19"])
        self.assertEqual(len(calls), 1)
        service = self.app.state.streaming_service
        with patch.object(service, "availability_for", return_value={}) as resolve:
            self.client.get("/api/streaming/availability?item_id=work-19", headers=headers)
            self.assertEqual([row["id"] for row in resolve.call_args.args[1]], ["work-19"])
            self.client.get("/api/streaming/availability?item_id=other-account", headers=headers)
            self.assertEqual(resolve.call_args.args[1], [])
        response = self.client.get("/api/ratings?item_id=other-account", headers=headers)
        self.assertEqual(response.json()["ratings"], {})
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
