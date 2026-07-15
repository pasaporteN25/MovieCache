from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.repository import CatalogFormatError, CatalogRepositoryError
from movie_inbox.cli.database import export_json, import_json
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.infrastructure.sqlite_repository import SqliteCatalogRepository


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
            "imdb_url": "https://www.imdb.com/title/tt0113277/",
            "wikidata_id": "Q42198",
            "genres": ["Crime", "Drama"],
            "directors": ["Michael Mann"],
            "writers": ["Michael Mann"],
            "cast": ["Al Pacino", "Robert De Niro"],
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
            "added_at": "2026-07-15T00:00:00Z",
            "custom_field": "preserved",
        }
    )


class SqliteRepositoryTests(unittest.TestCase):
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
            self.assertEqual(loaded.local_files[0].library_id, "movies-a")
            self.assertEqual(loaded.metadata_sources["title"].source, "imdb")
            self.assertEqual(loaded.extra["custom_field"], "preserved")

            with closing(sqlite3.connect(path)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                }
            self.assertTrue({"catalog_items", "external_ids", "local_files", "seasons", "episodes"} <= tables)

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
            self.assertEqual(payload["schema_version"], 4)
            self.assertEqual(payload["items"][0]["id"], "heat-1995")

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
