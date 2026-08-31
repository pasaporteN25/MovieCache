from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.collection_service import CollectionService
from movie_inbox.application.member_service import MemberService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.collections import (
    collection_item_from_availability_record,
    normalize_club_collection_description,
    normalize_club_collection_title,
    normalize_collection_item,
)
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.personal_catalogs import SqlitePersonalCatalogProvisioner
from movie_inbox.infrastructure.starter_collections import (
    AKIRA_KUROSAWA_SEED_KEY,
    akira_kurosawa_collection,
)


class CollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog_path = self.root / "owner.json"
        self.catalog_repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        self.catalog_repository.write([])
        self.identity_repository = SqliteIdentityRepository(self.root / "instance.db")
        self.owner, _ = AuthService(self.identity_repository).bootstrap_owner(
            "owner",
            "a-long-owner-password",
            catalog_name="Owner catalog",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        self.repository = SqliteCollectionRepository(self.root / "instance.db")
        self.seed = akira_kurosawa_collection(self.owner.id)
        self.service = CollectionService(self.repository)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_starter_collection_is_installed_once_with_directed_filmography(self) -> None:
        self.assertTrue(self.repository.install_once(AKIRA_KUROSAWA_SEED_KEY, self.seed))
        self.assertFalse(self.repository.install_once(AKIRA_KUROSAWA_SEED_KEY, self.seed))

        collections = self.service.list_collections(self.owner.id)

        self.assertEqual(len(collections), 1)
        self.assertEqual(collections[0]["title"], "Akira Kurosawa")
        self.assertEqual(collections[0]["counts"]["total"], 31)
        self.assertTrue(collections[0]["built_in"])
        self.assertFalse(collections[0]["followed"])

        with closing(sqlite3.connect(self.root / "instance.db")) as connection:
            connection.execute("DELETE FROM curated_collections WHERE id = ?", (self.seed.id,))
            connection.commit()
        self.assertFalse(self.repository.install_once(AKIRA_KUROSAWA_SEED_KEY, self.seed))
        self.assertEqual(self.service.list_collections(self.owner.id), [])

    def test_following_is_scoped_to_the_authenticated_user(self) -> None:
        self.repository.install_once(AKIRA_KUROSAWA_SEED_KEY, self.seed)
        members = MemberService(
            self.identity_repository,
            SqlitePersonalCatalogProvisioner(self.root / "member-catalogs"),
        )
        member = members.create_member(
            self.owner,
            "maria",
            temporary_password="a-temporary-password",
        ).member.user

        result = self.service.set_following(member.id, self.seed.id, True)

        self.assertEqual(result["reason"], "followed")
        self.assertTrue(self.service.list_collections(member.id)[0]["followed"])
        self.assertFalse(self.service.list_collections(self.owner.id)[0]["followed"])

    def test_copy_is_deduplicated_and_personal_fields_start_neutral(self) -> None:
        self.repository.install_once(AKIRA_KUROSAWA_SEED_KEY, self.seed)
        detail = self.service.collection_detail(self.owner.id, self.seed.id, [])
        rashomon = next(item for item in detail["items"] if item["title"] == "Rashomon")
        catalog = CatalogService(self.catalog_repository)

        first = self.service.add_to_catalog(
            self.owner.id,
            self.seed.id,
            [rashomon["collection_item_id"]],
            catalog,
            [],
        )
        second = self.service.add_to_catalog(
            self.owner.id,
            self.seed.id,
            [rashomon["collection_item_id"]],
            catalog,
            [item.to_dict() for item in self.catalog_repository.read()],
        )

        self.assertEqual(first["summary"]["added"], 1)
        self.assertEqual(second["summary"]["present"], 1)
        item = self.catalog_repository.read()[0]
        self.assertEqual(item.title, "Rashomon")
        self.assertEqual(item.status, "to_watch")
        self.assertEqual(item.rating, 0)
        self.assertEqual(item.review, "")
        self.assertFalse(item.en_catalogo)
        self.assertEqual(item.local_files, [])
        self.assertEqual(item.extra["collection_sources"][0]["collection_id"], self.seed.id)

    def test_copy_does_not_force_an_ambiguous_match_from_another_source(self) -> None:
        self.repository.install_once(AKIRA_KUROSAWA_SEED_KEY, self.seed)
        detail = self.service.collection_detail(self.owner.id, self.seed.id, [])
        rashomon = next(item for item in detail["items"] if item["title"] == "Rashomon")

        result = self.service.add_to_catalog(
            self.owner.id,
            self.seed.id,
            [rashomon["collection_item_id"]],
            CatalogService(self.catalog_repository),
            [
                normalize_item(
                    {"id": "legacy-rashomon", "title": "Rashomon", "year": "1950"}
                ).to_dict()
            ],
        )

        self.assertEqual(result["summary"]["review"], 1)
        self.assertEqual(result["results"][0]["reason"], "possible_duplicate")
        self.assertEqual(self.catalog_repository.read(), [])


class AvailabilityCollectionItemTests(unittest.TestCase):
    """[P2]: building a collection item from a library-availability record."""

    def _record(self, **overrides):
        record = {
            "work_key": "wikidata:Q12345",
            "identity": {"title": "Heat", "year": "1995", "kind": "pelicula"},
            "library_id": "lib-abc-123",
            "library_name": "Blu-rays del living",
            "file_count": 2,
        }
        record.update(overrides)
        return record

    def test_item_never_carries_the_library_id_or_name(self) -> None:
        entry = collection_item_from_availability_record(self._record(), 0)

        self.assertEqual(entry.id, "wikidata:Q12345")
        self.assertNotIn("library_id", entry.item)
        self.assertNotIn("library_name", entry.item)
        self.assertNotIn("lib-abc-123", str(entry.item))
        self.assertNotIn("Blu-rays del living", str(entry.item))
        self.assertEqual(entry.item["title"], "Heat")
        self.assertEqual(entry.item["file_count"], 2)

    def test_a_personal_catalog_items_full_availability_no_longer_survives_normalization(
        self,
    ) -> None:
        leaky = normalize_item(
            {
                "id": "x",
                "title": "Heat",
                "year": "1995",
                "_availability": {
                    "effective": True,
                    "sources": [
                        {
                            "library_id": "lib-abc-123",
                            "library_name": "Blu-rays del living",
                            "file_count": 2,
                        }
                    ],
                },
            }
        ).to_dict()

        safe = normalize_collection_item(leaky)

        self.assertNotIn("_availability", safe)
        self.assertNotIn("lib-abc-123", str(safe))
        self.assertNotIn("Blu-rays del living", str(safe))

    def test_missing_work_key_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            collection_item_from_availability_record(self._record(work_key=""), 0)


class ClubCollectionTitleTests(unittest.TestCase):
    def test_title_must_be_between_two_and_120_characters(self) -> None:
        self.assertEqual(normalize_club_collection_title("  Blu-rays  "), "Blu-rays")
        with self.assertRaises(ValueError):
            normalize_club_collection_title("a")
        with self.assertRaises(ValueError):
            normalize_club_collection_title("a" * 121)

    def test_description_is_capped_at_2000_characters(self) -> None:
        self.assertEqual(normalize_club_collection_description("  hola  "), "hola")
        with self.assertRaises(ValueError):
            normalize_club_collection_description("a" * 2001)


if __name__ == "__main__":
    unittest.main()
