from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.application.external_retirement import (
    ExternalRetirementConflict,
    RetirementCatalog,
    TmdbRetirementService,
)
from movie_inbox.cli.import_catalog import read_items_or_urls
from movie_inbox.domain.catalog import metadata_source_record, normalize_item
from movie_inbox.domain.external_retirement import retire_tmdb_metadata
from movie_inbox.infrastructure.curation_history import MemoryCurationHistoryRepository
from movie_inbox.infrastructure.export import catalog_csv_text
from movie_inbox.infrastructure.repositories import open_catalog_repository


def tmdb_item(item_id: str = "addio"):
    url = "https://www.themoviedb.org/movie/48691"
    return normalize_item(
        {
            "id": item_id,
            "source": "tmdb",
            "url": url,
            "tmdb_url": url,
            "tmdb_id": "48691",
            "title": "Adiós, tío Tom",
            "original_title": "Addio zio Tom",
            "kind": "pelicula",
            "year": "1971",
            "description": "Edición manual",
            "genres": ["Documental", "Drama"],
            "directors": ["Gualtiero Jacopetti"],
            "release_dates": [
                {
                    "date": "1971-09-23",
                    "source": "tmdb",
                    "source_url": url,
                    "is_primary": True,
                },
                {
                    "date": "1972-01-01",
                    "source": "imdb",
                    "source_url": "https://www.imdb.com/title/tt0180396/",
                    "is_primary": False,
                },
            ],
            "status": "watched",
            "watched_at": "2026-08-01",
            "rating": 8,
            "review": "Personal",
            "locked_fields": ["year"],
            "metadata_sources": {
                "title": metadata_source_record("tmdb", url, False),
                "original_title": metadata_source_record("tmdb", url, False),
                "kind": metadata_source_record("tmdb", url, False),
                "year": metadata_source_record("tmdb", url, False),
                "description": metadata_source_record("manual", "", False),
                "genres": metadata_source_record("imdb+tmdb", url, False),
                "directors": metadata_source_record("tmdb", url, False),
                "release_dates": metadata_source_record("imdb+tmdb", url, False),
                "tmdb_id": metadata_source_record("tmdb", url, False),
                "tmdb_url": metadata_source_record("tmdb", url, False),
            },
        }
    )


class TmdbRetirementDomainTests(unittest.TestCase):
    def test_purge_preserves_personal_locked_manual_and_shared_values(self) -> None:
        retired, report = retire_tmdb_metadata(tmdb_item())

        self.assertTrue(report["changed"])
        self.assertEqual(retired["title"], "Obra sin metadata")
        self.assertEqual(retired["original_title"], "")
        self.assertEqual(retired["tmdb_id"], "")
        self.assertEqual(retired["tmdb_url"], "")
        self.assertEqual(retired["url"], "")
        self.assertEqual(retired["source"], "retired")
        self.assertEqual(retired["directors"], [])
        self.assertEqual(retired["genres"], ["Documental", "Drama"])
        self.assertEqual(retired["metadata_sources"]["genres"]["source"], "imdb")
        self.assertEqual([row["source"] for row in retired["release_dates"]], ["imdb"])
        self.assertEqual(retired["year"], "1971")
        self.assertEqual(retired["description"], "Edición manual")
        self.assertEqual(retired["status"], "watched")
        self.assertEqual(retired["watched_at"], "2026-08-01")
        self.assertEqual(retired["rating"], 8)
        self.assertEqual(retired["review"], "Personal")
        self.assertIn("year", report["preserved_locked_fields"])
        self.assertIn("genres", report["preserved_shared_fields"])
        self.assertEqual(report["removed_release_dates"], 1)

    def test_manual_tmdb_identifier_is_not_removed(self) -> None:
        item = tmdb_item()
        item["metadata_sources"]["tmdb_id"] = metadata_source_record("manual", "", False)

        retired, report = retire_tmdb_metadata(item)

        self.assertEqual(retired["tmdb_id"], "48691")
        self.assertNotIn("tmdb_id", report["removed_fields"])


class TmdbRetirementServiceTests(unittest.TestCase):
    def test_preview_purge_history_and_undo_cover_json_and_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            json_path = root / "owner.json"
            sqlite_path = root / "member.db"
            # TmdbRetirementService round-trips catalog paths through
            # Path.resolve() (its "before"/"after" states carry a resolved
            # source_file), so the lookup here has to key on the resolved
            # path too -- an unresolved key can silently diverge from what
            # the service passes back on platforms where resolve() changes
            # the path (e.g. a Windows temp-dir junction).
            repositories = {
                path.resolve(): open_catalog_repository(path, normalize_item)
                for path in (json_path, sqlite_path)
            }
            repositories[json_path.resolve()].write([tmdb_item("owner-item")])
            repositories[sqlite_path.resolve()].write([tmdb_item("member-item")])
            history = MemoryCurationHistoryRepository()
            service = TmdbRetirementService(
                lambda path: repositories[path.resolve()],
                history,
                lambda: [
                    RetirementCatalog("owner", json_path, True),
                    RetirementCatalog("member", sqlite_path, True),
                ],
            )

            preview = service.preview()
            result = service.purge(preview["preview_id"], confirmed=True)

            self.assertTrue(preview["can_purge"])
            self.assertEqual(preview["affected_items"], 2)
            self.assertEqual(repositories[json_path.resolve()].read()[0].tmdb_id, "")
            self.assertEqual(repositories[sqlite_path.resolve()].read()[0].tmdb_id, "")
            self.assertEqual(service.history()["count"], 1)

            operation = service.undo(result["operation"]["id"])

            self.assertEqual(operation["status"], "undone")
            self.assertEqual(repositories[json_path.resolve()].read()[0].tmdb_id, "48691")
            self.assertEqual(repositories[sqlite_path.resolve()].read()[0].tmdb_id, "48691")

    def test_stale_preview_and_read_only_catalog_block_purge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.json"
            repository = open_catalog_repository(path, normalize_item)
            repository.write([tmdb_item()])
            targets = [RetirementCatalog("catalog", path, True)]
            service = TmdbRetirementService(
                lambda _path: repository,
                MemoryCurationHistoryRepository(),
                lambda: targets,
            )
            preview = service.preview()
            item = repository.read()[0]
            item.review = "Cambio posterior"
            repository.write([item])

            with self.assertRaisesRegex(
                ExternalRetirementConflict, "tmdb_retirement_preview_stale"
            ):
                service.purge(preview["preview_id"], confirmed=True)

            targets[0] = RetirementCatalog("catalog", path, False)
            blocked = service.preview()
            self.assertFalse(blocked["can_purge"])
            with self.assertRaisesRegex(
                ExternalRetirementConflict, "tmdb_retirement_read_only_catalog"
            ):
                service.purge(blocked["preview_id"], confirmed=True)

    def test_history_failure_rolls_the_catalog_back(self) -> None:
        class FailingHistory(MemoryCurationHistoryRepository):
            def append(self, operation, namespace=""):
                raise OSError("disk full")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.json"
            repository = open_catalog_repository(path, normalize_item)
            repository.write([tmdb_item()])
            service = TmdbRetirementService(
                lambda _path: repository,
                FailingHistory(),
                lambda: [RetirementCatalog("catalog", path, True)],
            )
            preview = service.preview()

            with self.assertRaises(OSError):
                service.purge(preview["preview_id"], confirmed=True)

            self.assertEqual(repository.read()[0].tmdb_id, "48691")


class TmdbImportExportTests(unittest.TestCase):
    def test_csv_round_trip_preserves_tmdb_identity_provenance_and_release_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tmdb.csv"
            path.write_text(catalog_csv_text([tmdb_item()]), encoding="utf-8")

            loaded = read_items_or_urls(path, "to_watch").items[0]

            self.assertEqual(loaded.tmdb_id, "48691")
            self.assertEqual(loaded.tmdb_url, "https://www.themoviedb.org/movie/48691")
            self.assertEqual(loaded.metadata_sources["tmdb_id"].source, "tmdb")
            self.assertEqual([row["source"] for row in loaded.release_dates], ["tmdb", "imdb"])


if __name__ == "__main__":
    unittest.main()
