"""[A2.6] second step: where the account's works can be watched, on a device.

Three properties these tests exist to hold, all of them from ADR-0004:

* "we did not check" and "not on any platform" are different answers, and the
  wire must not blur them;
* a copy kept on a phone expires when TMDb's terms say it does, so the deadline
  travels with the row;
* JustWatch is named wherever the data goes, with access to the whole API at
  stake if it is not.
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
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.streaming import (
    JUSTWATCH_ATTRIBUTION_NOTICE,
    MAX_RETENTION_DAYS,
    AvailabilitySnapshot,
    PlatformOffer,
    RegionPolicy,
    StreamingRegion,
    retention_expires_at,
)
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.streaming_repository import SqliteStreamingRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

HEAT = {
    "id": "heat",
    "title": "Heat",
    "year": "1995",
    "kind": "pelicula",
    "tmdb_id": "949",
    "tmdb_url": "https://www.themoviedb.org/movie/949",
}
UNKNOWN = {"id": "sin-tmdb", "title": "Obra sin identidad", "kind": "pelicula"}


def _stamp(days_ago: float) -> str:
    moment = datetime.now(UTC) - timedelta(days=days_ago)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class RetentionDeadlineTests(unittest.TestCase):
    def test_the_deadline_is_the_check_plus_the_contractual_ceiling(self) -> None:
        checked = "2026-09-09T10:00:00Z"
        expected = datetime.fromisoformat(checked.replace("Z", "+00:00")) + timedelta(
            days=MAX_RETENTION_DAYS
        )
        self.assertEqual(
            retention_expires_at(checked),
            expected.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )

    def test_nothing_to_expire_reports_nothing(self) -> None:
        self.assertEqual(retention_expires_at(""), "")

    def test_an_unreadable_stamp_is_already_over(self) -> None:
        # It cannot be shown to be inside the window, so a client must not keep
        # showing it. Same direction the server takes for the same reason.
        self.assertEqual(retention_expires_at("ayer"), "ayer")


class DeviceAvailabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item(HEAT), normalize_item(UNKNOWN)]
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
        self.streaming = SqliteStreamingRepository(self.instance_path)
        self.streaming.upsert_region(StreamingRegion("AR", "Argentina", True))
        self.streaming.set_region_policy(RegionPolicy(default_region="AR"))

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
        self.context = TestClient(create_app(self.config), base_url="http://127.0.0.1:8765")
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

    def _snapshot(self, checked_at: str, *, kind: str = "flatrate") -> None:
        self.streaming.save_availability(
            AvailabilitySnapshot(
                work_key="movie:949",
                region_code="AR",
                checked_at=checked_at,
                offers=(PlatformOffer("8", "Netflix", kind),),
                link="https://www.themoviedb.org/movie/949/watch?locale=AR",
            )
        )

    def _get(self) -> Any:
        return self.client.get("/api/v1/availability", headers=self.bearer)

    def _device_ids(self) -> dict[str, str]:
        page = self.client.get("/api/v1/catalog/items", headers=self.bearer).json()
        return {row["title"]: row["id"] for row in page["items"]}

    def test_an_answer_comes_back_keyed_by_the_same_opaque_id_the_catalogue_uses(
        self,
    ) -> None:
        self._snapshot(_stamp(1))
        response = self._get()
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        heat_id = self._device_ids()["Heat"]
        self.assertIn(heat_id, body["availability"])
        row = body["availability"][heat_id]
        self.assertTrue(row["en_plataforma"])
        self.assertEqual([offer["provider_name"] for offer in row["available_on"]], ["Netflix"])
        self.assertEqual(row["region_code"], "AR")

    def test_a_work_nobody_asked_about_is_absent_rather_than_reported_unavailable(
        self,
    ) -> None:
        # The whole point of ADR-0004's `known` flag: an absent key means "we did
        # not check", and a client cannot mistake that for "it is nowhere".
        self._snapshot(_stamp(1))
        body = self._get().json()
        self.assertNotIn(self._device_ids()["Obra sin identidad"], body["availability"])

    def test_the_row_carries_the_deadline_a_replica_must_honour(self) -> None:
        checked = _stamp(10)
        self._snapshot(checked)
        row = self._get().json()["availability"][self._device_ids()["Heat"]]
        self.assertEqual(row["checked_at"], checked)
        self.assertEqual(row["expires_at"], retention_expires_at(checked))
        self.assertGreater(row["expires_at"], row["checked_at"])

    def test_a_snapshot_past_the_ceiling_is_not_handed_over_at_all(self) -> None:
        # The server refuses to serve it, so a phone never gets the chance to
        # keep showing it.
        self._snapshot(_stamp(MAX_RETENTION_DAYS + 1))
        body = self._get().json()
        self.assertEqual(body["availability"], {})

    def test_renting_is_not_reported_as_being_available(self) -> None:
        # Saying "available on Google Play" about something you must pay per
        # title for would tell the viewer something false.
        self._snapshot(_stamp(1), kind="rent")
        row = self._get().json()["availability"][self._device_ids()["Heat"]]
        self.assertFalse(row["en_plataforma"])
        self.assertEqual(row["available_on"], [])
        self.assertEqual([offer["provider_name"] for offer in row["acquire_on"]], ["Netflix"])

    def test_justwatch_is_named_even_when_there_is_nothing_to_report(self) -> None:
        # The obligation is on the integration, not on a populated response.
        self.assertEqual(
            self._get().json()["attribution"]["justwatch"], JUSTWATCH_ATTRIBUTION_NOTICE
        )

    def test_the_web_endpoint_names_justwatch_too(self) -> None:
        # It did not before this change, which was a live compliance gap: the
        # terms put access to the whole API at risk, not just this feature.
        headers = {
            "X-Movie-Inbox-Token": self.config.api_token,
            "Origin": "http://127.0.0.1:8765",
            "Content-Type": "application/json",
        }
        login = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": self.password}),
            headers=headers,
        )
        self.assertEqual(login.status_code, 200, login.content)
        body = self.client.get("/api/streaming/availability", headers=headers).json()
        self.assertEqual(body["attribution"]["justwatch"], JUSTWATCH_ATTRIBUTION_NOTICE)

    def test_it_needs_a_device_session(self) -> None:
        self.assertEqual(self.client.get("/api/v1/availability").status_code, 401)


if __name__ == "__main__":
    unittest.main()
