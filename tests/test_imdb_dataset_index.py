from __future__ import annotations

import gzip
import tempfile
import unittest
from pathlib import Path

from movie_inbox.infrastructure.imdb_dataset_index import (
    IMDB_DATASET_INDEX_SCHEMA_VERSION,
    ImdbDatasetIndexStale,
    build_index,
    index_stats,
    lookup_by_tconst,
    lookup_by_title,
)

_BASICS_HEADER = (
    "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\t"
    "startYear\tendYear\truntimeMinutes\tgenres\n"
)
_AKAS_HEADER = "titleId\tordering\ttitle\tregion\tlanguage\ttypes\tattributes\tisOriginalTitle\n"


def _write_gzip_tsv(path: Path, lines: list[str]) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.writelines(lines)


class BuildIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.basics_path = self.root / "title.basics.tsv.gz"
        self.akas_path = self.root / "title.akas.tsv.gz"
        self.destination = self.root / "imdb-dataset.db"

    def _write_two_title_dataset(self) -> None:
        _write_gzip_tsv(
            self.basics_path,
            [
                _BASICS_HEADER,
                "tt0113277\tmovie\tHeat\tHeat\t0\t1995\t\\N\t170\tAction,Crime,Drama\n",
                "tt0068646\tmovie\tThe Godfather\tThe Godfather\t0\t1972\t\\N\t175\tCrime,Drama\n",
            ],
        )
        _write_gzip_tsv(
            self.akas_path,
            [
                _AKAS_HEADER,
                "tt0113277\t1\tHeat\t\\N\t\\N\t\\N\timdbDisplay\t1\n",
                "tt0113277\t2\tCalor\tES\t\\N\t\\N\t\\N\t0\n",
                "tt0068646\t1\tThe Godfather\t\\N\t\\N\t\\N\timdbDisplay\t1\n",
            ],
        )

    def test_a_fresh_build_reports_accurate_counts_and_a_real_file_on_disk(self) -> None:
        self._write_two_title_dataset()
        report = build_index(self.basics_path, self.akas_path, self.destination)
        self.assertEqual(report.basics_rows, 2)
        self.assertEqual(report.basics_skipped_lines, 1)  # the header
        self.assertEqual(report.akas_rows, 3)
        self.assertEqual(report.akas_skipped_lines, 1)  # the header
        self.assertTrue(self.destination.exists())
        self.assertEqual(report.index_size_bytes, self.destination.stat().st_size)
        self.assertGreater(report.index_size_bytes, 0)

    def test_no_leftover_temp_file_survives_a_successful_build(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        leftovers = list(self.root.glob(".*.tmp"))
        self.assertEqual(leftovers, [])

    def test_lookup_by_tconst_returns_the_title_with_its_akas_in_order(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        result = lookup_by_tconst(self.destination, "tt0113277")
        assert result is not None
        self.assertEqual(result.primary_title, "Heat")
        self.assertEqual(result.start_year, 1995)
        self.assertEqual([aka.title for aka in result.akas], ["Heat", "Calor"])
        self.assertEqual(result.akas[1].region, "ES")
        self.assertTrue(result.akas[0].is_original_title)
        self.assertFalse(result.akas[1].is_original_title)

    def test_lookup_by_tconst_returns_none_for_an_unknown_id(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        self.assertIsNone(lookup_by_tconst(self.destination, "tt9999999"))

    def test_lookup_by_title_matches_either_primary_or_original_title(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        results = lookup_by_title(self.destination, "The Godfather")
        self.assertEqual([result.tconst for result in results], ["tt0068646"])

    def test_lookup_by_title_narrows_by_year_when_given(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        self.assertEqual(len(lookup_by_title(self.destination, "Heat", year=1995)), 1)
        self.assertEqual(lookup_by_title(self.destination, "Heat", year=1974), [])

    def test_index_stats_reports_row_counts_and_disk_size(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        stats = index_stats(self.destination)
        self.assertEqual(stats.basics_rows, 2)
        self.assertEqual(stats.akas_rows, 3)
        self.assertEqual(stats.index_size_bytes, self.destination.stat().st_size)

    def test_a_second_build_fully_replaces_the_first_instead_of_appending(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        _write_gzip_tsv(
            self.basics_path,
            [
                _BASICS_HEADER,
                "tt0071562\tmovie\tThe Godfather Part II\tThe Godfather Part II\t0\t1974"
                "\t\\N\t202\tCrime,Drama\n",
            ],
        )
        _write_gzip_tsv(self.akas_path, [_AKAS_HEADER])
        report = build_index(self.basics_path, self.akas_path, self.destination)
        self.assertEqual(report.basics_rows, 1)
        stats = index_stats(self.destination)
        self.assertEqual(stats.basics_rows, 1)
        self.assertIsNone(lookup_by_tconst(self.destination, "tt0113277"))
        self.assertIsNotNone(lookup_by_tconst(self.destination, "tt0071562"))

    def test_looking_up_against_a_missing_index_raises_a_clear_error(self) -> None:
        with self.assertRaises(FileNotFoundError):
            lookup_by_tconst(self.destination, "tt0113277")

    def test_a_stale_schema_version_is_reported_instead_of_silently_used(self) -> None:
        self._write_two_title_dataset()
        build_index(self.basics_path, self.akas_path, self.destination)
        import sqlite3

        connection = sqlite3.connect(self.destination)
        connection.execute(f"PRAGMA user_version = {IMDB_DATASET_INDEX_SCHEMA_VERSION + 1}")
        connection.commit()
        connection.close()
        with self.assertRaises(ImdbDatasetIndexStale):
            index_stats(self.destination)


if __name__ == "__main__":
    unittest.main()
