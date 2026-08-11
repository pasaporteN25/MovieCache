from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from movie_inbox.infrastructure.library_scanner import FilesystemScanError, parse_release_name, scan_media_files


class LibraryScannerTests(unittest.TestCase):
    def test_missing_root_is_rejected_before_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "offline"

            with self.assertRaisesRegex(FilesystemScanError, "offline or missing"):
                scan_media_files(missing, scanned_at=1_800_000_000)

    def test_walk_permission_error_is_reported_without_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def denied_walk(*_args, **kwargs):  # type: ignore[no-untyped-def]
                kwargs["onerror"](PermissionError(13, "Permission denied", str(root)))
                return iter(())

            with patch(
                "movie_inbox.infrastructure.library_scanner.os.walk",
                side_effect=denied_walk,
            ):
                rows, errors = scan_media_files(root, scanned_at=1_800_000_000)

            self.assertEqual(rows, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("Permission denied", errors[0])

    def test_unreadable_file_is_skipped_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Heat.1995.mkv").write_bytes(b"heat")

            with patch(
                "movie_inbox.infrastructure.library_scanner.sampled_fingerprint",
                side_effect=PermissionError(13, "Permission denied"),
            ):
                rows, errors = scan_media_files(root, scanned_at=1_800_000_000)

            self.assertEqual(rows, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("Heat.1995.mkv", errors[0])
            self.assertIn("Permission denied", errors[0])

    def test_extras_and_sample_directories_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Feature.1999.mkv").write_bytes(b"feature")
            for directory in ("extras", "Sample", "samples"):
                ignored = root / directory
                ignored.mkdir()
                (ignored / f"{directory}.mp4").write_bytes(b"ignored")

            rows, errors = scan_media_files(root, scanned_at=1_800_000_000)

            self.assertEqual(errors, [])
            self.assertEqual([row["relative_path"] for row in rows], ["Feature.1999.mkv"])

    def test_default_exclusions_survive_custom_exclusion_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extras = root / "extras"
            extras.mkdir()
            (extras / "Behind.the.scenes.mp4").write_bytes(b"ignored")
            private = root / "private"
            private.mkdir()
            (private / "Hidden.2001.mkv").write_bytes(b"ignored")
            (root / "Feature.1999.mkv").write_bytes(b"feature")

            rows, errors = scan_media_files(
                root,
                excluded_dirs={"private"},
                scanned_at=1_800_000_000,
            )

            self.assertEqual(errors, [])
            self.assertEqual([row["relative_path"] for row in rows], ["Feature.1999.mkv"])

    def test_disc_markers_do_not_change_the_detected_work_title(self) -> None:
        first = parse_release_name("Once.Upon.a.Time.in.America.1984.CD1.mkv")
        second = parse_release_name("Once.Upon.a.Time.in.America.1984.disc-2.mkv")

        self.assertEqual(first, ("Once Upon a Time in America", "1984", "pelicula"))
        self.assertEqual(second, first)


if __name__ == "__main__":
    unittest.main()
