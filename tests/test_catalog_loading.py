from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.web.catalog_api import load_items


class CatalogLoadingTests(unittest.TestCase):
    def test_unchanged_catalog_reads_are_cached_and_return_isolated_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text("{}", encoding="utf-8")
            rows = [
                normalize_item(
                    {
                        "id": "akira",
                        "title": "Akira",
                        "alternative_titles": ["アキラ"],
                        "year": "1988",
                    }
                )
            ]
            with patch("movie_inbox.web.catalog_api.read_json_items", return_value=rows) as reader:
                first = load_items([str(path)])
                first[0]["alternative_titles"].append("mutated by caller")
                second = load_items([str(path)])

                self.assertEqual(reader.call_count, 1)
                self.assertEqual(second[0]["alternative_titles"], ["アキラ"])

                path.write_text('{"changed": true}', encoding="utf-8")
                load_items([str(path)])
                self.assertEqual(reader.call_count, 2)


if __name__ == "__main__":
    unittest.main()
