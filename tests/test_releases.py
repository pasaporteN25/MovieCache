from __future__ import annotations

import csv
import io
import json
import unittest

from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.releases import merge_release_dates, normalize_release_dates
from movie_inbox.external.wikidata import wikidata_claim_release_dates
from movie_inbox.infrastructure.export import catalog_csv_text


class ReleaseDateTests(unittest.TestCase):
    def test_normalization_preserves_precision_and_one_primary_date(self) -> None:
        rows = normalize_release_dates(
            [
                {"date": "2001", "source": "manual"},
                {"date": "2001-05", "source": "manual", "is_primary": True},
                {"date": "2001-05-18", "source": "manual", "is_primary": True},
            ]
        )

        self.assertEqual([row["precision"] for row in rows], ["year", "month", "day"])
        self.assertEqual([row["is_primary"] for row in rows], [False, True, False])

    def test_merge_deduplicates_the_same_release_event(self) -> None:
        rows = merge_release_dates(
            [{"date": "2001-05-18", "release_type": "theatrical", "source": "wikidata"}],
            [
                {
                    "date": "2001-05-18",
                    "release_type": "theatrical",
                    "source_url": "https://example.test",
                }
            ],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "wikidata")
        self.assertEqual(rows[0]["source_url"], "https://example.test")

    def test_wikidata_precision_is_not_invented(self) -> None:
        claims = {
            "P577": [
                {
                    "rank": "preferred",
                    "mainsnak": {
                        "datavalue": {"value": {"time": "+1988-04-16T00:00:00Z", "precision": 11}}
                    },
                },
                {
                    "rank": "normal",
                    "mainsnak": {
                        "datavalue": {"value": {"time": "+1988-00-00T00:00:00Z", "precision": 9}}
                    },
                },
            ]
        }

        rows = wikidata_claim_release_dates(claims, "Q1")

        self.assertEqual(rows[0]["date"], "1988-04-16")
        self.assertEqual(rows[0]["precision"], "day")
        self.assertEqual(rows[1]["date"], "1988")
        self.assertEqual(rows[1]["precision"], "year")

    def test_csv_export_uses_json_for_release_dates(self) -> None:
        item = normalize_item(
            {
                "id": "heat",
                "title": "Heat",
                "year": "1995",
                "release_dates": [{"date": "1995-12-15", "source": "wikidata"}],
            }
        )

        row = next(csv.DictReader(io.StringIO(catalog_csv_text([item]))))
        dates = json.loads(row["release_dates"])

        self.assertEqual(dates[0]["date"], "1995-12-15")
        self.assertEqual(dates[0]["precision"], "day")


if __name__ == "__main__":
    unittest.main()
