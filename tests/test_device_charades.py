"""[A2.4]: what a phone needs to deal the same charades deck as the server, offline.

[G2] made the generator portable precisely so a phone could deal without a
connection, and ADR-0005 has the phone playing offline. That promise has two
halves: a Kotlin port of the generator, and the deck's input reaching the phone.
These tests hold the second half -- the snapshot a device receives is enough, on
its own, to deal the deck the server would deal -- and hold that nothing beyond
the game crosses with it.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.charades import (
    EASY,
    HARD,
    MIN_PER_DIFFICULTY,
    CharadeWork,
    build_deck,
    deck_fingerprint,
    deck_seed,
)
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.infrastructure.charades_repository import SqliteCharadesRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

NUMBERED = MIN_PER_DIFFICULTY + 5
PRIVATE_REVIEW = "una opinion que es solo mia"
PRIVATE_NOTE = "una nota privada"


class DeviceCharadesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        works: list[dict[str, Any]] = [
            {
                "id": f"obra-{index}",
                "title": f"Obra {index}",
                "year": str(1950 + index),
                "kind": "pelicula",
                "tmdb_id": str(1000 + index),
                "status": "watched",
                "rating": 8,
                "review": PRIVATE_REVIEW,
                "notes": PRIVATE_NOTE,
            }
            for index in range(NUMBERED)
        ]
        # Nobody classified this one and it has no votes: it cannot be played,
        # but it still belongs to the fingerprint two players compare.
        works.append({"id": "sin-id", "title": "Sin identificador", "year": "1999"})
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item(work) for work in works]
        )
        self.instance_path = root / "instance.db"
        self.password = "a-long-local-password"
        identity = SqliteIdentityRepository(self.instance_path)
        identity.initialize()
        AuthService(identity).bootstrap_owner(
            "lucas",
            self.password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        owner = identity.owner()
        catalog = identity.default_catalog_for(owner.id) if owner else None
        assert owner is not None and catalog is not None
        self.identity = AuthenticatedIdentity(user=owner, catalog=catalog, expires_at=0)
        decisions = SqliteCharadesRepository(self.instance_path)
        for index in range(NUMBERED):
            difficulty = HARD if index == 0 else EASY
            decisions.set_difficulty(owner.id, f"tmdb:{1000 + index}", difficulty)

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

    def _snapshot(self) -> dict[str, Any]:
        response = self.client.get("/api/v1/charades", headers=self.bearer)
        self.assertEqual(response.status_code, 200, response.content)
        payload: dict[str, Any] = response.json()
        return payload

    def test_the_snapshot_alone_deals_the_deck_the_server_deals(self) -> None:
        snapshot = self._snapshot()
        works = [CharadeWork(**row) for row in snapshot["works"]]

        # What a phone does with nothing but the snapshot and the generator.
        fingerprint = deck_fingerprint(work.key for work in works)
        easy = [work for work in works if work.difficulty == EASY]
        dealt_on_the_phone = [
            work.key for work in build_deck(easy, deck_seed([EASY, 10], fingerprint), 10)
        ]

        server = self.app.state.charades_service.deck(self.identity, EASY, 10)
        self.assertEqual(fingerprint, snapshot["fingerprint"])
        self.assertEqual(fingerprint, server["fingerprint"])
        self.assertEqual(dealt_on_the_phone, [row["key"] for row in server["works"]])

    def test_unclassified_works_travel_because_the_fingerprint_covers_them(self) -> None:
        snapshot = self._snapshot()
        unclassified = [row for row in snapshot["works"] if not row["difficulty"]]

        self.assertEqual(len(snapshot["works"]), NUMBERED + 1)
        self.assertEqual([row["title"] for row in unclassified], ["Sin identificador"])
        self.assertEqual(snapshot["unclassified"], 1)

    def test_a_decision_a_person_made_is_what_the_phone_plays(self) -> None:
        snapshot = self._snapshot()
        by_key = {row["key"]: row for row in snapshot["works"]}

        self.assertEqual(by_key["tmdb:1000"]["difficulty"], HARD)
        self.assertEqual(by_key["tmdb:1001"]["difficulty"], EASY)
        self.assertEqual(snapshot["counts"][EASY], NUMBERED - 1)
        # Only easy has enough works to be offered; hard has one.
        self.assertEqual(snapshot["playable_difficulties"], [EASY])
        self.assertEqual(snapshot["timer_options"][EASY], [60, 120, 180])

    def test_nothing_but_the_game_crosses(self) -> None:
        response = self.client.get("/api/v1/charades", headers=self.bearer)
        raw = response.text

        for private in (PRIVATE_REVIEW, PRIVATE_NOTE, "watched", str(self.catalog_path)):
            self.assertNotIn(private, raw)
        for row in response.json()["works"]:
            self.assertEqual(set(row), {"key", "title", "year", "difficulty", "source"})

    def test_it_needs_a_device_session(self) -> None:
        response = self.client.get("/api/v1/charades")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
