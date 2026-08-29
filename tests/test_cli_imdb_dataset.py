from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from movie_inbox.cli import main as cli_main
from movie_inbox.cli.imdb_dataset import main, run_lookup, run_stats, run_sync
from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE
from movie_inbox.external.imdb_datasets import DownloadResult
from movie_inbox.infrastructure.imdb_dataset_index import (
    AkaEntry,
    IndexBuildReport,
    IndexStats,
    TitleLookupResult,
)


def _sample_title() -> TitleLookupResult:
    return TitleLookupResult(
        tconst="tt0113277",
        title_type="movie",
        primary_title="Heat",
        original_title="Heat",
        start_year=1995,
        end_year=None,
        runtime_minutes=170,
        genres="Action,Crime,Drama",
        akas=(AkaEntry(title="Calor", region="ES", language=None, is_original_title=False),),
    )


class RunSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output_dir = Path(self.temporary.name)

    def test_sync_downloads_both_initial_datasets_and_builds_the_index(self) -> None:
        download_calls: list[str] = []

        def fake_download(name: str, destination: Path, **kwargs: object) -> DownloadResult:
            download_calls.append(name)
            return DownloadResult(
                name=name, url="https://x", bytes_downloaded=1234, elapsed_seconds=0.5
            )

        build_calls: list[tuple[Path, Path, Path]] = []

        def fake_build(basics_path: Path, akas_path: Path, destination: Path) -> IndexBuildReport:
            build_calls.append((basics_path, akas_path, destination))
            return IndexBuildReport(
                basics_rows=2,
                basics_skipped_lines=1,
                akas_rows=3,
                akas_skipped_lines=1,
                elapsed_seconds=1.5,
                index_size_bytes=4096,
            )

        with (
            patch("movie_inbox.cli.imdb_dataset.download_dataset_file", side_effect=fake_download),
            patch("movie_inbox.cli.imdb_dataset.build_index", side_effect=fake_build),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = run_sync(self.output_dir, None)

        self.assertEqual(exit_code, 0)
        self.assertEqual(sorted(download_calls), ["title.akas", "title.basics"])
        self.assertEqual(len(build_calls), 1)
        basics_path, akas_path, destination = build_calls[0]
        self.assertEqual(basics_path, self.output_dir / "title.basics.tsv.gz")
        self.assertEqual(akas_path, self.output_dir / "title.akas.tsv.gz")
        self.assertEqual(destination, self.output_dir / "imdb-dataset.db")
        output = buffer.getvalue()
        self.assertIn("2 titles", output)
        self.assertIn("3 alternate titles", output)
        self.assertIn(IMDB_ATTRIBUTION_NOTICE, output)

    def test_sync_writes_a_json_report_when_a_path_is_given(self) -> None:
        report_path = self.output_dir / "report.json"

        def fake_download(name: str, destination: Path, **kwargs: object) -> DownloadResult:
            return DownloadResult(
                name=name, url="https://x", bytes_downloaded=10, elapsed_seconds=0.1
            )

        def fake_build(basics_path: Path, akas_path: Path, destination: Path) -> IndexBuildReport:
            return IndexBuildReport(
                basics_rows=1,
                basics_skipped_lines=1,
                akas_rows=1,
                akas_skipped_lines=1,
                elapsed_seconds=0.2,
                index_size_bytes=100,
            )

        with (
            patch("movie_inbox.cli.imdb_dataset.download_dataset_file", side_effect=fake_download),
            patch("movie_inbox.cli.imdb_dataset.build_index", side_effect=fake_build),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run_sync(self.output_dir, report_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["basics_rows"], 1)
        self.assertEqual(report["attribution"], IMDB_ATTRIBUTION_NOTICE)


class RunStatsTests(unittest.TestCase):
    def test_stats_prints_row_counts_and_disk_size(self) -> None:
        with patch(
            "movie_inbox.cli.imdb_dataset.index_stats",
            return_value=IndexStats(basics_rows=10, akas_rows=25, index_size_bytes=2_097_152),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = run_stats(Path("/some/dir"))
        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("10", output)
        self.assertIn("25", output)
        self.assertIn("2.0 MB", output)


class RunLookupTests(unittest.TestCase):
    def test_lookup_by_tconst_prints_the_title_its_akas_and_the_attribution(self) -> None:
        with patch(
            "movie_inbox.cli.imdb_dataset.lookup_by_tconst", return_value=_sample_title()
        ) as mock_lookup:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = run_lookup(Path("/some/dir"), "tt0113277", None, None)
        mock_lookup.assert_called_once_with(Path("/some/dir") / "imdb-dataset.db", "tt0113277")
        self.assertEqual(exit_code, 0)
        output = buffer.getvalue()
        self.assertIn("Heat", output)
        self.assertIn("Calor", output)
        self.assertIn(IMDB_ATTRIBUTION_NOTICE, output)

    def test_lookup_by_title_narrows_by_year(self) -> None:
        with patch(
            "movie_inbox.cli.imdb_dataset.lookup_by_title", return_value=[_sample_title()]
        ) as mock_lookup:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                run_lookup(Path("/some/dir"), None, "Heat", 1995)
        mock_lookup.assert_called_once_with(Path("/some/dir") / "imdb-dataset.db", "Heat", 1995)

    def test_no_match_reports_failure_without_a_traceback(self) -> None:
        with patch("movie_inbox.cli.imdb_dataset.lookup_by_tconst", return_value=None):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = run_lookup(Path("/some/dir"), "tt9999999", None, None)
        self.assertEqual(exit_code, 1)
        self.assertIn("No matching title", buffer.getvalue())


class MainDispatchTests(unittest.TestCase):
    def test_year_without_title_is_rejected_by_argument_parsing(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(buffer):
            with self.assertRaises(SystemExit) as raised:
                main(["lookup", "--output-dir", ".", "--tconst", "tt1", "--year", "1995"])
        self.assertEqual(raised.exception.code, 2)

    def test_main_dispatches_sync_to_run_sync(self) -> None:
        with patch("movie_inbox.cli.imdb_dataset.run_sync", return_value=0) as mock_run:
            exit_code = main(["sync", "--output-dir", "/tmp/imdb"])
        self.assertEqual(exit_code, 0)
        mock_run.assert_called_once_with(Path("/tmp/imdb"), None)

    def test_the_command_is_registered_in_the_installed_command_surface(self) -> None:
        self.assertIn("imdb-dataset", cli_main.COMMANDS)
        self.assertIs(cli_main.COMMANDS["imdb-dataset"][0], main)


if __name__ == "__main__":
    unittest.main()
