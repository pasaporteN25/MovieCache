from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from movie_inbox.infrastructure.library_scanner import FilesystemScanError, scan_media_files


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


if __name__ == "__main__":
    unittest.main()
