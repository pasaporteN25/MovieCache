from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.repository import CatalogFormatError, CatalogRepositoryError
from movie_inbox.cli.database import export_json, import_json, verify_catalog_round_trip
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.infrastructure.sqlite_repository import SCHEMA_V1, SqliteCatalogRepository


def sample_item(item_id: str = "heat-1995"):
    return normalize_item(
        {
            "id": item_id,
            "url": "https://www.imdb.com/title/tt0113277/",
            "source": "imdb",
            "title": "Heat",
            "original_title": "Heat",
            "spanish_title": "Fuego contra fuego",
            "alternative_titles": ["Heat 1995"],
            "kind": "pelicula",
            "status": "to_watch",
            "rating": 0,
            "year": "1995",
            "release_dates": [
                {
                    "date": "1995-12-15",
                    "precision": "day",
                    "country": "US",
                    "release_type": "theatrical",
                    "source": "wikidata",
                    "source_url": "https://www.wikidata.org/wiki/Q42198",
                    "is_primary": True,
                }
            ],
            "imdb_url": "https://www.imdb.com/title/tt0113277/",
            "wikidata_id": "Q42198",
            "genres": ["Crime", "Drama"],
            "directors": ["Michael Mann"],
            "writers": ["Michael Mann"],
            "cast": ["Al Pacino", "Robert De Niro"],
            "page_image": "https://images.example/poster.jpg",
            "backdrop_image": "https://images.example/backdrop.jpg",
            "tmdb_id": "949",
            "en_catalogo": True,
            "local_files": [
                {
                    "path": "D:/Movies/Heat.mkv",
                    "name": "Heat.mkv",
                    "size_bytes": 1234,
                    "modified_at": "2026-07-15T00:00:00Z",
                    "part": "",
                    "library_id": "movies-a",
                    "relative_path": "Heat.mkv",
                    "fingerprint": "abc123",
                    "last_seen_at": "2026-07-15T00:00:00Z",
                    "available": True,
                }
            ],
            "tags": ["favorite"],
            "metadata_sources": {
                "title": {
                    "source": "imdb",
                    "url": "https://www.imdb.com/title/tt0113277/",
                    "updated_at": "2026-07-15T00:00:00Z",
                    "inferred": False,
                }
            },
            "locked_fields": ["title"],
            "link_curation_status": "resolved",
            "duplicate_decisions": {
                "other::catalog.json": {
                    "status": "not_duplicate",
                    "updated_at": "2026-07-25T00:00:00Z",
                }
            },
            "curation_updated_at": "2026-07-25T00:00:00Z",
            "added_at": "2026-07-15T00:00:00Z",
            "custom_field": "preserved",
        }
    )


class SqliteRepositoryTests(unittest.TestCase):
    def test_version_one_database_is_migrated_for_landscape_artwork(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.sqlite"
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(SCHEMA_V1)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES (1, 'initial', '2026-07-01')"
                )
                connection.commit()

            repository = SqliteCatalogRepository(path, normalize_item)
            self.assertEqual(repository.database_version(), 4)
            with closing(sqlite3.connect(path)) as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(catalog_items)")}
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            self.assertTrue({"backdrop_image", "tmdb_id", "link_curation_status", "curation_updated_at"} <= columns)
            self.assertIn("duplicate_decisions", tables)
            self.assertIn("release_dates", tables)

    def test_relational_round_trip_preserves_catalog_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "movie-inbox.db"
            repository = SqliteCatalogRepository(path, normalize_item)
            repository.write([sample_item()])

            loaded = repository.read()[0]
            self.assertEqual(loaded.title, "Heat")
            self.assertEqual(loaded.spanish_title, "Fuego contra fuego")
            self.assertEqual(loaded.genres, ["Crime", "Drama"])
            self.assertEqual(loaded.imdb_url, "https://www.imdb.com/title/tt0113277/")
            self.assertEqual(loaded.wikidata_id, "Q42198")
            self.assertEqual(loaded.backdrop_image, "https://images.example/backdrop.jpg")
            self.assertEqual(loaded.tmdb_id, "949")
            self.assertEqual(loaded.release_dates[0]["date"], "1995-12-15")
            self.assertEqual(loaded.link_curation_status, "resolved")
            self.assertEqual(loaded.duplicate_decisions["other::catalog.json"]["status"], "not_duplicate")
            self.assertEqual(loaded.local_files[0].library_id, "movies-a")
            self.assertEqual(loaded.metadata_sources["title"].source, "imdb")
            self.assertEqual(loaded.extra["custom_field"], "preserved")

            with closing(sqlite3.connect(path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                }
            self.assertTrue(
                {"catalog_items", "external_ids", "local_files", "seasons", "episodes", "duplicate_decisions", "release_dates"}
                <= tables
            )
            self.assertEqual(repository.database_version(), 4)

    def test_catalog_service_mutates_sqlite_transactionally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.sqlite", normalize_item)
            repository.write([sample_item()])
            updated, reason = CatalogService(repository).update_status("heat-1995", "watched", "2026-07-15")
            self.assertTrue(updated)
            self.assertEqual(reason, "updated")
            loaded = repository.read()[0]
            self.assertEqual(loaded.status, "watched")
            self.assertEqual(loaded.watched_at, "2026-07-15")

    def test_status_update_does_not_rewrite_secondary_relations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.sqlite"
            repository = SqliteCatalogRepository(path, normalize_item)
            repository.write([sample_item()])
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE relation_audit(event TEXT NOT NULL);
                    CREATE TRIGGER audit_tag_delete AFTER DELETE ON tags
                    BEGIN INSERT INTO relation_audit(event) VALUES ('tag_deleted'); END;
                    CREATE TRIGGER audit_file_delete AFTER DELETE ON local_files
                    BEGIN INSERT INTO relation_audit(event) VALUES ('file_deleted'); END;
                    """
                )
                connection.commit()

            updated, _ = CatalogService(repository).update_status("heat-1995", "watched", "2026-07-15")
            self.assertTrue(updated)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM relation_audit").fetchone()[0], 0)

    def test_metadata_update_only_rewrites_changed_relations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.sqlite"
            repository = SqliteCatalogRepository(path, normalize_item)
            repository.write([sample_item()])
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE relation_audit(event TEXT NOT NULL);
                    CREATE TRIGGER audit_file_delete AFTER DELETE ON local_files
                    BEGIN INSERT INTO relation_audit(event) VALUES ('file_deleted'); END;
                    CREATE TRIGGER audit_tag_delete AFTER DELETE ON tags
                    BEGIN INSERT INTO relation_audit(event) VALUES ('tag_deleted'); END;
                    """
                )
                connection.commit()

            updated, _ = CatalogService(repository).update_metadata(
                "heat-1995",
                {"genres": ["Crime", "Thriller"]},
                None,
            )
            self.assertTrue(updated)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM relation_audit").fetchone()[0], 0)
            self.assertEqual(repository.get("heat-1995").genres, ["Crime", "Thriller"])

    def test_batch_mutation_does_not_rewrite_unchanged_items(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.sqlite"
            repository = SqliteCatalogRepository(path, normalize_item)
            repository.write([sample_item()])
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE relation_audit(event TEXT NOT NULL);
                    CREATE TRIGGER audit_file_delete AFTER DELETE ON local_files
                    BEGIN INSERT INTO relation_audit(event) VALUES ('file_deleted'); END;
                    CREATE TRIGGER audit_tag_delete AFTER DELETE ON tags
                    BEGIN INSERT INTO relation_audit(event) VALUES ('tag_deleted'); END;
                    """
                )
                connection.commit()

            added, reason, _ = CatalogService(repository).append_item(
                {"id": "arrival-2016", "title": "Arrival", "year": "2016", "kind": "pelicula"}
            )
            self.assertTrue(added)
            self.assertEqual(reason, "added")
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM relation_audit").fetchone()[0], 0)
            self.assertEqual([item.id for item in repository.read()], ["arrival-2016", "heat-1995"])

    def test_scanner_item_is_created_once_and_reused_by_strong_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.sqlite", normalize_item)
            repository.write([sample_item()])
            service = CatalogService(repository)

            created, reason, result = service.ensure_scanner_item(
                {"title": "1917", "year": "2019", "kind": "pelicula"}
            )
            reused, reused_reason, reused_result = service.ensure_scanner_item(
                {"title": "1917", "year": "2019", "kind": "pelicula"}
            )

            self.assertTrue(created)
            self.assertEqual(reason, "created")
            self.assertFalse(result["item"]["en_catalogo"])
            self.assertFalse(reused)
            self.assertEqual(reused_reason, "existing")
            self.assertEqual(reused_result["item"]["id"], result["item"]["id"])
            self.assertEqual(len(repository.read()), 2)
            with self.assertRaisesRegex(ValueError, "four-digit year"):
                service.ensure_scanner_item({"title": "Arrival", "year": "unknown", "kind": "pelicula"})

    def test_scanner_requires_the_current_review_token_to_keep_both_works(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.sqlite", normalize_item)
            repository.write([
                normalize_item({"id": "once-upon", "title": "Once Upon a Time", "year": "2020"})
            ])
            service = CatalogService(repository)
            payload = {
                "title": "Once Upon Time",
                "year": "2020",
                "kind": "pelicula",
                "scanner_reference": "file-once-upon",
            }

            blocked, blocked_reason, review = service.ensure_scanner_item(payload)
            blocked_without_intent, no_intent_reason, _ = service.ensure_scanner_item({
                **payload,
                "distinct_review_token": review["distinct_review_token"],
            })
            blocked_again, repeated_reason, repeated_review = service.ensure_scanner_item({
                **payload,
                "distinct_intent": True,
                "distinct_review_token": "stale-token",
            })
            created, created_reason, created_result = service.ensure_scanner_item({
                **payload,
                "distinct_intent": True,
                "distinct_review_token": repeated_review["distinct_review_token"],
            })
            retried, retry_reason, retry_result = service.ensure_scanner_item({
                **payload,
                "distinct_intent": True,
                "distinct_review_token": repeated_review["distinct_review_token"],
            })

            self.assertFalse(blocked)
            self.assertEqual(blocked_reason, "possible_duplicate")
            self.assertTrue(review["distinct_review_token"])
            self.assertFalse(blocked_without_intent)
            self.assertEqual(no_intent_reason, "possible_duplicate")
            self.assertFalse(blocked_again)
            self.assertEqual(repeated_reason, "possible_duplicate")
            self.assertEqual(review["distinct_review_token"], repeated_review["distinct_review_token"])
            self.assertTrue(created)
            self.assertEqual(created_reason, "created_distinct")
            self.assertEqual(created_result["reviewed_candidate_ids"], ["once-upon"])
            self.assertFalse(retried)
            self.assertEqual(retry_reason, "existing")
            self.assertEqual(retry_result["item"]["id"], created_result["item"]["id"])
            rows = repository.read()
            self.assertEqual(len(rows), 2)
            distinct = next(item for item in rows if item.id != "once-upon")
            self.assertEqual(distinct.duplicate_decisions["once-upon"]["status"], "not_duplicate")

    def test_scanner_only_overrides_an_exact_match_after_distinct_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.sqlite", normalize_item)
            repository.write([
                normalize_item({"id": "heat-imdb", "title": "Heat", "year": "1995", "kind": "pelicula"})
            ])
            service = CatalogService(repository)
            payload = {
                "title": "Heat",
                "year": "1995",
                "kind": "pelicula",
                "scanner_reference": "file-heat-copy",
            }

            reused, reused_reason, reused_result = service.ensure_scanner_item(payload)
            blocked, blocked_reason, review = service.ensure_scanner_item({
                **payload,
                "distinct_intent": True,
            })
            created, created_reason, created_result = service.ensure_scanner_item({
                **payload,
                "distinct_intent": True,
                "distinct_review_token": review["distinct_review_token"],
            })

            self.assertFalse(reused)
            self.assertEqual(reused_reason, "existing")
            self.assertEqual(reused_result["item"]["id"], "heat-imdb")
            self.assertFalse(blocked)
            self.assertEqual(blocked_reason, "possible_duplicate")
            self.assertTrue(created)
            self.assertEqual(created_reason, "created_distinct")
            self.assertEqual(created_result["reviewed_candidate_ids"], ["heat-imdb"])
            self.assertEqual(len(repository.read()), 2)

    def test_scanner_blocks_numeric_title_with_a_bad_legacy_year(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.sqlite", normalize_item)
            repository.write([
                normalize_item({
                    "id": "legacy-1917",
                    "title": "1917",
                    "year": "1917",
                    "kind": "pelicula",
                    "imdb_url": "https://www.imdb.com/title/tt8579674/",
                })
            ])

            created, reason, result = CatalogService(repository).ensure_scanner_item(
                {"title": "1917", "year": "2019", "kind": "pelicula"}
            )

            self.assertFalse(created)
            self.assertEqual(reason, "possible_duplicate")
            self.assertEqual(result["candidates"][0]["id"], "legacy-1917")
            self.assertEqual(result["candidates"][0]["reason"], "exact_title_year_mismatch")
            self.assertEqual(len(repository.read()), 1)

    def test_scanner_checks_read_only_catalog_sources_before_creating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.sqlite", normalize_item)
            repository.write([sample_item()])

            created, reason, result = CatalogService(repository).ensure_scanner_item(
                {"title": "Arrival", "year": "2016", "kind": "pelicula"},
                comparison_items=[
                    normalize_item({"id": "arrival-read-only", "title": "Arrival", "year": "2016"})
                ],
            )

            self.assertFalse(created)
            self.assertEqual(reason, "existing")
            self.assertEqual(result["item"]["id"], "arrival-read-only")
            self.assertFalse(result["writable"])
            self.assertEqual(len(repository.read()), 1)

    def test_attach_local_file_is_granular_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.sqlite"
            repository = SqliteCatalogRepository(path, normalize_item)
            item = sample_item()
            item.local_files = []
            item.local_name = ""
            item.local_path = ""
            repository.write([item])
            local_file = {
                "path": "D:/Movies/Heat.mkv",
                "name": "Heat.mkv",
                "library_id": "movies-a",
                "relative_path": "Heat.mkv",
            }
            self.assertTrue(repository.attach_local_file("heat-1995", local_file))
            self.assertTrue(repository.attach_local_file("heat-1995", local_file))
            loaded = repository.get("heat-1995")
            self.assertIsNotNone(loaded)
            self.assertEqual(len(loaded.local_files), 1)
            self.assertTrue(loaded.en_catalogo)

    def test_catalog_rewrite_preserves_series_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.db"
            repository = SqliteCatalogRepository(path, normalize_item)
            series = sample_item("series-1")
            series.kind = "serie"
            repository.write([series])
            with closing(sqlite3.connect(path)) as connection:
                connection.execute(
                    "INSERT INTO seasons(id, item_id, season_number, title) VALUES (?, ?, ?, ?)",
                    ("series-1-s1", "series-1", 1, "Season 1"),
                )
                connection.execute(
                    "INSERT INTO episodes(id, season_id, episode_number, title) VALUES (?, ?, ?, ?)",
                    ("series-1-s1-e1", "series-1-s1", 1, "Pilot"),
                )
                connection.commit()
            CatalogService(repository).update_catalog_status("series-1", False)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM seasons").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0], 1)

    def test_duplicate_item_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = SqliteCatalogRepository(Path(temporary) / "catalog.db", normalize_item)
            with self.assertRaises(CatalogFormatError):
                repository.write([sample_item(), sample_item()])

    def test_json_import_and_export_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "catalog.json"
            database = root / "catalog.db"
            exported = root / "backup.json"
            JsonCatalogRepository(source, normalize_item).write([sample_item()])

            with redirect_stdout(StringIO()):
                self.assertEqual(import_json(source, database), 0)
                self.assertEqual(export_json(database, exported), 0)
            payload = json.loads(exported.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 6)
            self.assertEqual(payload["items"][0]["id"], "heat-1995")

    def test_json_import_reads_source_without_creating_a_sidecar_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "catalog.json"
            database = root / "catalog.db"
            JsonCatalogRepository(source, normalize_item).write([sample_item()])
            lock_path = root / ".catalog.json.lock"

            original_open = os.open

            def reject_source_lock(path, flags, mode=0o777):  # type: ignore[no-untyped-def]
                if Path(path) == lock_path:
                    raise OSError(30, "Read-only file system", str(path))
                return original_open(path, flags, mode)

            with patch("movie_inbox.infrastructure.json_repository.os.open", side_effect=reject_source_lock):
                with redirect_stdout(StringIO()):
                    self.assertEqual(import_json(source, database), 0)

            self.assertFalse(lock_path.exists())
            self.assertEqual(SqliteCatalogRepository(database, normalize_item).read()[0].id, "heat-1995")

    def test_read_only_json_repository_rejects_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "catalog.json"
            JsonCatalogRepository(source, normalize_item).write([sample_item()])
            repository = JsonCatalogRepository(source, normalize_item, read_only=True)

            self.assertEqual(repository.read()[0].id, "heat-1995")
            with self.assertRaisesRegex(CatalogRepositoryError, "read-only"):
                repository.write([])

    def test_round_trip_verification_compares_complete_documents(self) -> None:
        expected = sample_item()
        changed = sample_item()
        changed.review = "A changed review must fail verification"
        with self.assertRaisesRegex(RuntimeError, r"canonical catalog documents differ at \$\.items\[0\]\.review"):
            verify_catalog_round_trip([expected], [changed], "test")

    def test_normalizing_an_item_does_not_duplicate_its_legacy_local_file(self) -> None:
        item = sample_item()
        normalized_again = normalize_item(item.to_dict())
        self.assertEqual(len(normalized_again.local_files), 1)
        self.assertEqual(normalized_again.local_files[0].library_id, "movies-a")

    def test_import_refuses_to_replace_existing_database_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "catalog.json"
            database = root / "catalog.db"
            JsonCatalogRepository(source, normalize_item).write([sample_item("new-item")])
            SqliteCatalogRepository(database, normalize_item).write([sample_item("existing-item")])

            with redirect_stdout(StringIO()):
                self.assertEqual(import_json(source, database), 2)

            self.assertEqual(SqliteCatalogRepository(database, normalize_item).read()[0].id, "existing-item")

    def test_export_rejects_missing_database_and_non_json_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                export_json(root / "missing.db", root / "backup.json")
            database = root / "catalog.db"
            SqliteCatalogRepository(database, normalize_item).write([sample_item()])
            with self.assertRaises(ValueError):
                export_json(database, root / "backup.txt")

    def test_read_does_not_create_a_missing_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "missing.db"
            repository = SqliteCatalogRepository(path, normalize_item)
            with self.assertRaisesRegex(CatalogRepositoryError, "does not exist"):
                repository.read()
            self.assertFalse(path.exists())

    def test_repository_factory_uses_file_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertIsInstance(open_catalog_repository(root / "catalog.json", normalize_item), JsonCatalogRepository)
            self.assertIsInstance(open_catalog_repository(root / "catalog.db", normalize_item), SqliteCatalogRepository)
            with self.assertRaises(ValueError):
                open_catalog_repository(root / "catalog.txt", normalize_item)


if __name__ == "__main__":
    unittest.main()
