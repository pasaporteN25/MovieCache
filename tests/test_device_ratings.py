"""[A2.6] last step: public scores on a device, beside the viewer's own.

The owner's decision was to show several sources rather than pick one, so the
reader compares instead of being handed a yardstick. What these tests hold is
that the comparison survives the trip: both sources arrive, ordered by how much
opinion is behind them, and neither ever reaches the personal rating.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.public_ratings_service import PublicRatingsService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE
from movie_inbox.domain.public_ratings import (
    IMDB_SOURCE,
    RATING_MAX_RETENTION_DAYS,
    TMDB_SOURCE,
    public_rating,
    rating_expires_at,
)
from movie_inbox.domain.streaming import retention_expires_at
from movie_inbox.external.tmdb import TMDB_ATTRIBUTION_NOTICE
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.public_ratings_repository import SqlitePublicRatingsRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

HEAT: dict[str, Any] = {
    "id": "heat",
    "title": "Heat",
    "year": "1995",
    "kind": "pelicula",
    "tmdb_id": "949",
    "tmdb_url": "https://www.themoviedb.org/movie/949",
    "imdb_url": "https://www.imdb.com/title/tt0113277/",
    "rating": 9,
}


class RatingExpiryTests(unittest.TestCase):
    def test_it_agrees_with_the_streaming_ceiling_it_shares_a_clause_with(self) -> None:
        # Two modules, one upstream's terms. They are implemented separately so
        # neither concern depends on the other, so this is what stops them
        # drifting apart in silence.
        for stamp in ("2026-09-09T10:00:00Z", "2026-01-01T00:00:00Z", "", "ayer"):
            with self.subTest(stamp=stamp):
                self.assertEqual(rating_expires_at(stamp), retention_expires_at(stamp))

    def test_only_a_score_that_ages_carries_a_date(self) -> None:
        checked = "2026-09-09T10:00:00Z"
        tmdb = public_rating(TMDB_SOURCE, 7.8, 4321, checked)
        imdb = public_rating(IMDB_SOURCE, 8.3, 700_000)
        assert tmdb is not None and imdb is not None

        expected = datetime.fromisoformat(checked.replace("Z", "+00:00")) + timedelta(
            days=RATING_MAX_RETENTION_DAYS
        )
        self.assertEqual(
            tmdb.to_dict()["expires_at"],
            expected.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )
        # IMDb comes from a local index the owner re-syncs on their own
        # schedule: nothing upstream caps how long it may be kept, so an expiry
        # would be an invention.
        self.assertNotIn("expires_at", imdb.to_dict())
        self.assertNotIn("checked_at", imdb.to_dict())


class DeviceRatingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(HEAT),
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
        session = self.client.post(
            "/api/v1/auth/login",
            content=json.dumps(
                {"username": "lucas", "password": self.password, "device_name": "Pixel"}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(session.status_code, 201, session.content)
        self.bearer = {"Authorization": f"Bearer {session.json()['access_token']}"}

    def _install(self, **kwargs: object) -> None:
        self.app.state.public_ratings_service = PublicRatingsService(
            SqlitePublicRatingsRepository(self.instance_path),
            **kwargs,  # type: ignore[arg-type]
        )

    def _both_sources(self) -> None:
        checked = (
            (datetime.now(UTC) - timedelta(days=2))
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        self._install(
            imdb_lookup=lambda _id: public_rating(IMDB_SOURCE, 8.3, 700_000),
            imdb_id_reader=lambda row: "tt0113277" if row.get("id") == "heat" else "",
            tmdb_loader=lambda media_type, tmdb_id: {"average": 7.8, "votes": 900},
        )
        self.checked = checked

    def _get(self) -> Any:
        return self.client.get("/api/v1/ratings", headers=self.bearer)

    def _device_ids(self) -> dict[str, str]:
        page = self.client.get("/api/v1/catalog/items", headers=self.bearer).json()
        return {row["title"]: row["id"] for row in page["items"]}

    def test_both_sources_arrive_with_the_sturdiest_opinion_first(self) -> None:
        self._both_sources()
        body = self._get().json()
        rows = body["ratings"][self._device_ids()["Heat"]]
        self.assertEqual([row["source"] for row in rows], [IMDB_SOURCE, TMDB_SOURCE])
        self.assertEqual(rows[0]["votes"], 700_000)

    def test_the_tmdb_row_tells_a_replica_when_to_stop_showing_it(self) -> None:
        self._both_sources()
        rows = self._get().json()["ratings"][self._device_ids()["Heat"]]
        tmdb = next(row for row in rows if row["source"] == TMDB_SOURCE)
        imdb = next(row for row in rows if row["source"] == IMDB_SOURCE)
        self.assertEqual(tmdb["expires_at"], rating_expires_at(tmdb["checked_at"]))
        self.assertGreater(tmdb["expires_at"], tmdb["checked_at"])
        self.assertNotIn("expires_at", imdb)

    def test_a_work_with_no_score_is_absent_rather_than_empty(self) -> None:
        self._both_sources()
        body = self._get().json()
        self.assertNotIn(self._device_ids()["Sin fuentes"], body["ratings"])

    def test_both_notices_travel_with_the_scores(self) -> None:
        self._both_sources()
        attribution = self._get().json()["attribution"]
        self.assertEqual(attribution["imdb"], IMDB_ATTRIBUTION_NOTICE)
        self.assertEqual(attribution["tmdb"], TMDB_ATTRIBUTION_NOTICE)

    def test_only_a_configured_source_is_attributed(self) -> None:
        self._install(tmdb_loader=lambda media_type, tmdb_id: {"average": 7.8, "votes": 900})
        self.assertEqual(list(self._get().json()["attribution"]), ["tmdb"])

    def test_an_instance_with_no_sources_answers_empty_instead_of_failing(self) -> None:
        # The default install: public scores are supplementary, and a phone
        # simply shows the viewer's own.
        body = self._get().json()
        self.assertEqual(body, {"ratings": {}, "attribution": {}})

    def test_a_public_score_never_reaches_the_personal_rating(self) -> None:
        # [F3.2]'s rule, checked where it would break: the endpoint only reads,
        # so the viewer's own 9 survives a read that served an 8,3.
        self._both_sources()
        self._get()
        stored = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        heat = next(row for row in stored["items"] if row["id"] == "heat")
        self.assertEqual(heat["rating"], 9)
        for field in ("vote_average", "vote_count", "public_ratings", "tmdb_rating"):
            self.assertNotIn(field, heat)

    def test_it_needs_a_device_session(self) -> None:
        self.assertEqual(self.client.get("/api/v1/ratings").status_code, 401)


if __name__ == "__main__":
    unittest.main()
