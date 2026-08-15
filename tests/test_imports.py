from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.import_service import (
    IMPORT_DRAFT_TTL_SECONDS,
    ImportDraftExpired,
    ImportDraftLimit,
    ImportPermissionError,
    ImportService,
)
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.import_parsers import ImportParseError, parse_import_content
from movie_inbox.infrastructure.import_repository import SqliteImportDraftRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository


class ImportParserTests(unittest.TestCase):
    def test_txt_preserves_balanced_wikipedia_parentheses_and_sanitizes_source_name(self) -> None:
        parsed = parse_import_content(
            "C:\\Users\\Lucas\\movies.txt",
            "auto",
            "Heat 1995\nhttps://en.wikipedia.org/wiki/Ran_(film)\n",
        )

        self.assertEqual(parsed.source_name, "movies.txt")
        self.assertEqual(parsed.source_format, "txt")
        self.assertEqual([row.item["title"] for row in parsed.items], ["Heat", "Ran (film)"])
        self.assertEqual(parsed.items[1].item["url"], "https://en.wikipedia.org/wiki/Ran_(film)")

    def test_csv_mapping_and_json_import_remove_local_paths(self) -> None:
        csv_import = parse_import_content(
            "movies.csv",
            "csv",
            "obra,estreno,vista\nIkiru,1952,watched\n",
            {"title": "obra", "year": "estreno", "status": "vista"},
        )
        json_import = parse_import_content(
            "catalog.json",
            "json",
            '[{"title":"Heat","local_name":"Heat.mkv","local_path":"D:/Movies/Heat.mkv",'
            '"path":"D:/Movies","_source_file":"D:/catalog.json","en_catalogo":true}]',
        )

        self.assertEqual(csv_import.items[0].item["title"], "Ikiru")
        self.assertEqual(csv_import.items[0].item["status"], "watched")
        item = json_import.items[0].item
        self.assertTrue(item["en_catalogo"])
        self.assertEqual(item["local_files"], [])
        self.assertEqual(item["local_name"], "")
        self.assertEqual(item["local_path"], "")
        self.assertNotIn("path", item)
        self.assertNotIn("_source_file", item)

    def test_binary_and_duplicate_json_keys_are_rejected(self) -> None:
        with self.assertRaises(ImportParseError):
            parse_import_content("bad.txt", "txt", "Heat\x00Ikiru")
        with self.assertRaises(ImportParseError):
            parse_import_content("bad.json", "json", '[{"title":"Heat","title":"Crash"}]')

    def test_json_depth_is_rejected_before_decoding_nested_content(self) -> None:
        nested = "[" * 17 + '{"title":"Heat"}' + "]" * 17
        with self.assertRaisesRegex(ImportParseError, "depth limit"):
            parse_import_content("deep.json", "json", nested)

        valid = parse_import_content(
            "contenido-pegado",
            "auto",
            '[{"title":"A title with [[brackets]] and {braces}"}]',
        )
        self.assertEqual(valid.source_format, "json")
        self.assertEqual(valid.items[0].item["title"], "A title with [[brackets]] and {braces}")


class ImportServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog_path = self.root / "owner.json"
        self.catalog_repository = JsonCatalogRepository(self.catalog_path, normalize_item)
        self.catalog_repository.write(
            [normalize_item({"id": "heat-existing", "title": "Heat", "year": "1995"})]
        )
        self.identity_repository = SqliteIdentityRepository(self.root / "instance.db")
        self.owner, _ = AuthService(self.identity_repository).bootstrap_owner(
            "owner",
            "a-long-owner-password",
            catalog_name="Owner catalog",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        self.clock_value = 1_800_000_000
        self.import_repository = SqliteImportDraftRepository(self.root / "instance.db")
        self.collection_repository = SqliteCollectionRepository(self.root / "instance.db")
        self.service = ImportService(
            self.import_repository,
            self.collection_repository,
            parser=parse_import_content,
            clock=lambda: self.clock_value,
            id_factory=lambda: "draft-001",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def catalog_items(self):
        return [item.to_dict() for item in self.catalog_repository.read()]

    def test_preview_classifies_catalog_matches_and_source_duplicates(self) -> None:
        draft = self.service.create_draft(
            self.owner.id,
            "movies.txt",
            "txt",
            "Heat 1995\nIkiru 1952\nIkiru 1952\n",
            None,
            self.catalog_items(),
        )

        self.assertEqual(draft["counts"]["review"], 1)
        self.assertEqual(draft["counts"]["new"], 1)
        self.assertEqual(draft["counts"]["present"], 1)
        duplicate = next(row for row in draft["items"] if row["reason"] == "duplicate_in_source")
        self.assertFalse(duplicate["collection_eligible"])
        summaries = self.service.list_drafts(self.owner.id)
        self.assertEqual(summaries[0]["counts"], draft["counts"])
        self.assertNotIn("items", summaries[0])
        self.assertEqual(self.service.list_drafts("another-user"), [])

    def test_preview_candidates_do_not_persist_existing_local_file_names(self) -> None:
        self.catalog_repository.write(
            [
                normalize_item(
                    {
                        "id": "heat-existing",
                        "title": "Heat",
                        "year": "1995",
                        "local_name": "Heat.private.mkv",
                        "local_path": "D:/Private/Heat.private.mkv",
                    }
                )
            ]
        )
        draft = self.service.create_draft(
            self.owner.id,
            "movies.txt",
            "txt",
            "Heat 1995",
            None,
            self.catalog_items(),
        )

        self.assertEqual(draft["items"][0]["state"], "review")
        self.assertNotIn("local_name", draft["items"][0]["candidates"][0])
        self.assertNotIn("D:/Private", str(draft))

    def test_draft_expires_after_48_hours_and_is_removed(self) -> None:
        draft = self.service.create_draft(
            self.owner.id,
            "movies.txt",
            "txt",
            "Ikiru 1952",
            None,
            self.catalog_items(),
        )
        self.clock_value += IMPORT_DRAFT_TTL_SECONDS

        with self.assertRaises(ImportDraftExpired):
            self.service.draft_detail(self.owner.id, draft["id"], self.catalog_items())
        self.assertIsNone(self.import_repository.get_for_user(self.owner.id, draft["id"]))

    def test_user_must_remove_a_draft_after_reaching_the_active_limit(self) -> None:
        limited = ImportService(
            self.import_repository,
            self.collection_repository,
            parser=parse_import_content,
            clock=lambda: self.clock_value,
            id_factory=lambda: "limited-draft",
            max_drafts=1,
        )
        limited.create_draft(
            self.owner.id,
            "first.txt",
            "txt",
            "Ikiru 1952",
            None,
            self.catalog_items(),
        )

        with self.assertRaises(ImportDraftLimit):
            limited.create_draft(
                self.owner.id,
                "second.txt",
                "txt",
                "Ran 1985",
                None,
                self.catalog_items(),
            )

    def test_expired_stale_apply_claim_is_eventually_purged(self) -> None:
        draft = self.service.create_draft(
            self.owner.id,
            "movies.txt",
            "txt",
            "Ikiru 1952",
            None,
            self.catalog_items(),
        )
        claimed = self.import_repository.claim_for_apply(
            self.owner.id,
            draft["id"],
            self.clock_value,
            self.clock_value - 300,
        )
        self.assertEqual(claimed.status, "applying")
        self.clock_value += IMPORT_DRAFT_TTL_SECONDS + (15 * 60) + 1

        self.assertEqual(self.service.list_drafts(self.owner.id), [])
        self.assertIsNone(self.import_repository.get_for_user(self.owner.id, draft["id"]))

    def test_personal_import_is_idempotent_and_respects_field_options(self) -> None:
        draft = self.service.create_draft(
            self.owner.id,
            "watched.csv",
            "csv",
            "title,year,status,watched_at,rating,review,en_catalogo\nIkiru,1952,watched,2026-07-01,9,Excelente,true\n",
            None,
            self.catalog_items(),
        )
        item_id = draft["items"][0]["id"]
        options = {
            "include_status": False,
            "include_watched_at": False,
            "include_rating": False,
            "include_review": True,
        }

        first = self.service.apply_draft(
            self.owner.id,
            draft["id"],
            "catalog",
            [item_id],
            CatalogService(self.catalog_repository),
            self.catalog_items(),
            personal_options=options,
        )
        second = self.service.apply_draft(
            self.owner.id,
            draft["id"],
            "catalog",
            [item_id],
            CatalogService(self.catalog_repository),
            self.catalog_items(),
            personal_options=options,
        )

        self.assertEqual(first, second)
        self.assertEqual(first["summary"]["added"], 1)
        imported = next(item for item in self.catalog_repository.read() if item.title == "Ikiru")
        self.assertEqual(imported.status, "to_watch")
        self.assertEqual(imported.watched_at, "")
        self.assertEqual(imported.rating, 0)
        self.assertEqual(imported.review, "Excelente")
        self.assertTrue(imported.en_catalogo)
        self.assertEqual(imported.local_files, [])
        self.assertEqual(imported.extra["import_sources"][0]["draft_id"], draft["id"])

    def test_applying_a_draft_does_not_extend_its_48_hour_expiry(self) -> None:
        draft = self.service.create_draft(
            self.owner.id,
            "movies.txt",
            "txt",
            "Ikiru 1952",
            None,
            self.catalog_items(),
        )
        original_expiry = draft["expires_at"]
        self.clock_value += IMPORT_DRAFT_TTL_SECONDS - 60
        applied = self.service.apply_draft(
            self.owner.id,
            draft["id"],
            "catalog",
            [draft["items"][0]["id"]],
            CatalogService(self.catalog_repository),
            self.catalog_items(),
        )
        detail = self.service.draft_detail(self.owner.id, draft["id"], self.catalog_items())

        self.assertTrue(applied["ok"])
        self.assertEqual(detail["expires_at"], original_expiry)
        self.clock_value += 60
        with self.assertRaises(ImportDraftExpired):
            self.service.draft_detail(self.owner.id, draft["id"], self.catalog_items())

    def test_owner_can_create_private_collection_without_touching_catalog(self) -> None:
        draft = self.service.create_draft(
            self.owner.id,
            "selection.csv",
            "csv",
            "title,year,status,rating,review\nHeat,1995,watched,8,Great\nIkiru,1952,watched,10,Perfect\n",
            None,
            self.catalog_items(),
        )
        selected = [row["id"] for row in draft["items"] if row["collection_eligible"]]

        result = self.service.apply_draft(
            self.owner.id,
            draft["id"],
            "collection",
            selected,
            CatalogService(self.catalog_repository),
            self.catalog_items(),
            collection_title="Japanese classics",
            collection_description="Imported selection",
            can_create_collection=True,
        )

        self.assertEqual(result["summary"]["created"], 2)
        collection = self.collection_repository.get_accessible(
            self.owner.id,
            result["collection"]["id"],
        )
        self.assertIsNotNone(collection)
        self.assertEqual(collection.visibility, "private")
        self.assertEqual(collection.source_kind, "import")
        self.assertNotIn("status", collection.items[0].item)
        self.assertNotIn("review", collection.items[0].item)
        self.assertEqual(len(self.catalog_repository.read()), 1)

    def test_member_cannot_create_imported_collection(self) -> None:
        draft = self.service.create_draft(
            self.owner.id,
            "movies.txt",
            "txt",
            "Ikiru 1952",
            None,
            self.catalog_items(),
        )
        with self.assertRaises(ImportPermissionError):
            self.service.apply_draft(
                self.owner.id,
                draft["id"],
                "collection",
                [draft["items"][0]["id"]],
                CatalogService(self.catalog_repository),
                self.catalog_items(),
                collection_title="Private list",
                can_create_collection=False,
            )


if __name__ == "__main__":
    unittest.main()
