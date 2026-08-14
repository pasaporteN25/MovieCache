from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.home_snapshot_repository import (
    HomeSnapshotRepositoryError,
    SqliteHomeSnapshotRepository,
)
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository


class HomeSnapshotRepositoryTests(unittest.TestCase):
    def test_snapshots_are_user_scoped_and_bounded_to_two_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog.json"
            JsonCatalogRepository(catalog, normalize_item).write([])
            identity_repository = SqliteIdentityRepository(root / "instance.db")
            user, _ = AuthService(identity_repository).bootstrap_owner(
                "owner",
                "a-long-owner-password",
                catalog_name="Owner catalog",
                source_paths=[str(catalog)],
                write_path=str(catalog),
            )
            repository = SqliteHomeSnapshotRepository(root / "instance.db")

            repository.save(user.id, "2026-08-12", [entry("first")])
            repository.save(user.id, "2026-08-13", [entry("second")])
            repository.save(user.id, "2026-08-14", [entry("third")])

            self.assertIsNone(repository.get(user.id, "2026-08-12"))
            self.assertEqual(repository.get(user.id, "2026-08-13"), [entry("second")])
            self.assertEqual(repository.get(user.id, "2026-08-14"), [entry("third")])

    def test_first_snapshot_for_a_date_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog.json"
            JsonCatalogRepository(catalog, normalize_item).write([])
            identity_repository = SqliteIdentityRepository(root / "instance.db")
            user, _ = AuthService(identity_repository).bootstrap_owner(
                "owner",
                "a-long-owner-password",
                catalog_name="Owner catalog",
                source_paths=[str(catalog)],
                write_path=str(catalog),
            )
            repository = SqliteHomeSnapshotRepository(root / "instance.db")

            repository.save(user.id, "2026-08-14", [entry("first")])
            repository.save(user.id, "2026-08-14", [entry("replacement")])

            self.assertEqual(repository.get(user.id, "2026-08-14"), [entry("first")])

    def test_snapshot_rejects_an_unknown_user(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity_repository = SqliteIdentityRepository(root / "instance.db")
            identity_repository.initialize()
            repository = SqliteHomeSnapshotRepository(root / "instance.db")

            with self.assertRaises(HomeSnapshotRepositoryError):
                repository.save("missing", "2026-08-14", [])


def entry(item_id: str) -> dict[str, object]:
    return {
        "item_id": item_id,
        "reason": {
            "code": "available_pending",
            "label": "Disponible y pendiente",
            "detail": "Guardada para esa jornada.",
        },
    }


if __name__ == "__main__":
    unittest.main()
