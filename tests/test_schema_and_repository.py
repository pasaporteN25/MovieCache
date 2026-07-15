from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.models import CatalogItem, LocalFile, MetadataSource
from movie_inbox.infrastructure.json_repository import CatalogFormatError, JsonCatalogRepository
from movie_inbox.infrastructure.schema import CatalogSchemaError, UnsupportedCatalogVersion, catalog_document, extract_catalog_items


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


if __name__ == "__main__":
    unittest.main()
