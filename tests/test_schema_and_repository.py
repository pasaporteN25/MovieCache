from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.models import CatalogItem, LocalFile, MetadataSource
from movie_inbox.infrastructure.json_repository import CatalogFormatError, JsonCatalogRepository
from movie_inbox.infrastructure.schema import (
    CatalogSchemaError,
    UnsupportedCatalogVersion,
    atomic_write_json,
    catalog_document,
    extract_catalog_items,
)


class SchemaAndRepositoryTests(unittest.TestCase):
    def test_legacy_list_is_migrated_to_v4_shape(self) -> None:
        rows = extract_catalog_items([{"title": "Heat", "year": "1995", "en_catalogo": "si"}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "pelicula")
        self.assertEqual(rows[0]["status"], "to_watch")
        self.assertTrue(rows[0]["en_catalogo"])
        self.assertIn("local_files", rows[0])
        self.assertIn("metadata_sources", rows[0])

    def test_future_and_malformed_catalogs_are_rejected(self) -> None:
        with self.assertRaises(UnsupportedCatalogVersion):
            extract_catalog_items({"schema_version": 5, "items": []})
        with self.assertRaises(CatalogSchemaError):
            extract_catalog_items({"schema_version": 4, "items": "not-an-array"})
        with self.assertRaises(CatalogSchemaError):
            extract_catalog_items({"schema_version": 4, "items": [], "unexpected": True})
        with self.assertRaises(CatalogSchemaError):
            extract_catalog_items({"schema_version": 4, "items": [None]})

    def test_invalid_v4_item_cannot_be_written(self) -> None:
        with self.assertRaises(CatalogSchemaError):
            catalog_document([{"id": "one", "title": "Heat"}])

    def test_models_and_repository_round_trip(self) -> None:
        item = normalize_item(
            {
                "id": "heat-1995",
                "title": "Heat",
                "year": "1995",
                "kind": "pelicula",
                "local_files": [{"path": "Heat.mkv", "name": "Heat.mkv", "available": "false"}],
                "metadata_sources": {
                    "title": {"source": "manual", "url": "", "updated_at": "", "inferred": "false"}
                },
            }
        )
        self.assertIsInstance(item, CatalogItem)
        self.assertIsInstance(item.local_files[0], LocalFile)
        self.assertFalse(item.local_files[0].available)
        self.assertIsInstance(item.metadata_sources["title"], MetadataSource)
        self.assertFalse(item.metadata_sources["title"].inferred)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.json"
            repository = JsonCatalogRepository(path, normalize_item)
            repository.write([item])
            loaded = repository.read()
            self.assertEqual(loaded[0].title, "Heat")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 4)

            path.write_text('{"schema_version": 5, "items": []}', encoding="utf-8")
            with self.assertRaises(CatalogFormatError):
                repository.read()

    def test_normalization_repairs_identifier_titles_and_detects_series(self) -> None:
        item = normalize_item(
            {
                "id": "the-fly",
                "title": "tt0091064",
                "english_title": "tt0091064",
                "alternative_titles": ["The Fly"],
                "kind": "pelicula",
                "description": "1986 science fiction film",
            }
        )
        series = normalize_item(
            {
                "id": "tantei",
                "title": "Tantei Monogatari",
                "kind": "pelicula",
                "description": "1979-1980 Japanese TV series",
            }
        )

        self.assertEqual(item.title, "The Fly")
        self.assertEqual(item.english_title, "")
        self.assertEqual(item.kind, "pelicula")
        self.assertEqual(series.kind, "serie")

    def test_atomic_json_writes_keep_one_replaceable_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.json"
            path.write_text('{"revision": 1}', encoding="utf-8")
            stale = path.with_name("catalog.20260723-120000-000000.bak.json")
            stale.write_text('{"revision": 0}', encoding="utf-8")

            atomic_write_json(path, {"revision": 2})

            backup = path.with_name("catalog.bak.json")
            self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), {"revision": 1})
            self.assertFalse(stale.exists())

            atomic_write_json(path, {"revision": 3})

            self.assertEqual(json.loads(backup.read_text(encoding="utf-8")), {"revision": 2})
            self.assertEqual(list(path.parent.glob("catalog*.bak.json")), [backup])


if __name__ == "__main__":
    unittest.main()
