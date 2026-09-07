"""The device item id as a durable sync key ([A1.4], implementing ADR-0005).

The mobile client keeps a local replica, so the key it stores has to survive
operations that are entirely normal on the server. [MB1] measured that the
original derivation did not: these tests now pin the fixed behaviour, and the
two that recorded the defect say so where they assert the opposite.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.web.routers.device_catalog import DEVICE_SYNC_SECRET, _opaque_item_id


class OpaqueItemIdTests(unittest.TestCase):
    def test_it_is_stable_while_nothing_around_it_changes(self) -> None:
        first = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        second = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertEqual(first, second)

    def test_it_does_not_leak_the_path_the_catalogue_id_or_the_item_id(self) -> None:
        opaque = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertNotIn("catalogo-1", opaque)
        self.assertNotIn("source-1", opaque)
        self.assertNotIn("heat", opaque)

    def test_the_source_slot_carries_no_path(self) -> None:
        # [A1.4]: relocating a catalogue used to re-key every work, because the
        # absolute file path was part of the message. The slot replaces it.
        moved = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertEqual(moved, _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat"))

    def test_distinct_works_sources_and_catalogues_never_collide(self) -> None:
        base = _opaque_item_id(b"secreto", "catalogo-1", "source-1", "heat")
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-1", "source-1", "akira"))
        # Item ids are only unique inside one source file, so the slot has to
        # keep taking part in the key.
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-1", "source-2", "heat"))
        self.assertNotEqual(base, _opaque_item_id(b"secreto", "catalogo-2", "source-1", "heat"))

    def test_the_separator_cannot_be_forged_from_field_contents(self) -> None:
        self.assertNotEqual(
            _opaque_item_id(b"s", "a", "b", "c"),
            _opaque_item_id(b"s", "a\x1fb", "", "c"),
        )


class InstanceSecretTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "instance.db"
        repository = SqliteIdentityRepository(self.path)
        repository.initialize()
        AuthService(repository).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(Path(self.temporary.name) / "catalog.json")],
            write_path=str(Path(self.temporary.name) / "catalog.json"),
        )
        self.repository = repository

    def test_the_sync_secret_is_created_once_and_then_kept(self) -> None:
        first = self.repository.instance_secret(DEVICE_SYNC_SECRET)
        self.assertTrue(first)
        self.assertEqual(self.repository.instance_secret(DEVICE_SYNC_SECRET), first)
        # A fresh handle on the same database sees the same secret, which is
        # what makes the key survive a server restart.
        self.assertEqual(
            SqliteIdentityRepository(self.path).instance_secret(DEVICE_SYNC_SECRET), first
        )

    def test_different_names_get_different_secrets(self) -> None:
        self.assertNotEqual(
            self.repository.instance_secret(DEVICE_SYNC_SECRET),
            self.repository.instance_secret("otro_proposito"),
        )

    def test_the_key_no_longer_depends_on_the_rotatable_api_token(self) -> None:
        # This is the defect [MB1] measured: the secret used to be
        # viewer_config.api_token, so rotating it re-keyed every work and a
        # paired client could no longer match its replica.
        secret = self.repository.instance_secret(DEVICE_SYNC_SECRET).encode("utf-8")
        before = _opaque_item_id(secret, "catalogo-1", "source-1", "heat")
        # Rotating the api_token does not touch the stored secret at all.
        after = self.repository.instance_secret(DEVICE_SYNC_SECRET).encode("utf-8")
        self.assertEqual(before, _opaque_item_id(after, "catalogo-1", "source-1", "heat"))


if __name__ == "__main__":
    unittest.main()
