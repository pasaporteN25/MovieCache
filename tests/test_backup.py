from __future__ import annotations

import os
import tarfile
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from movie_inbox.cli.backup import BACKUP_PREFIX, create_backup, sha256_file, verify_backup


class BackupTests(unittest.TestCase):
    def test_backup_is_atomic_verified_and_excludes_the_image_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "data"
            output = root / "backups"
            (source / "catalogs").mkdir(parents=True)
            (source / "image-cache").mkdir()
            (source / "instance.db").write_bytes(b"instance-state")
            (source / "movie-inbox.db").write_bytes(b"catalog-state")
            (source / "catalogs" / "member.db").write_bytes(b"member-state")
            (source / "image-cache" / "poster.jpg").write_bytes(b"reproducible")

            result = create_backup(
                source,
                output,
                now=datetime(2026, 8, 11, 3, 30, tzinfo=UTC),
            )

            self.assertEqual(result.archive.name, f"{BACKUP_PREFIX}-20260811-033000Z.tar.gz")
            self.assertTrue(result.checksum.is_file())
            self.assertIn(sha256_file(result.archive), result.checksum.read_text(encoding="ascii"))
            verification = verify_backup(result.archive)
            self.assertTrue(verification.checksum_verified)
            self.assertEqual(verification.files, 3)
            with tarfile.open(result.archive, "r:gz") as bundle:
                names = set(bundle.getnames())
            self.assertIn("movie-inbox/instance.db", names)
            self.assertIn("movie-inbox/movie-inbox.db", names)
            self.assertIn("movie-inbox/catalogs/member.db", names)
            self.assertFalse(any("image-cache" in name for name in names))
            self.assertFalse(any(path.name.endswith(".tmp") for path in output.iterdir()))

    def test_retention_removes_old_archive_and_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "data"
            output = root / "backups"
            source.mkdir()
            output.mkdir()
            (source / "instance.db").write_bytes(b"instance")
            (source / "movie-inbox.db").write_bytes(b"catalog")
            old = output / f"{BACKUP_PREFIX}-20260101-000000Z.tar.gz"
            old.write_bytes(b"old")
            old_checksum = old.with_name(f"{old.name}.sha256")
            old_checksum.write_text("old", encoding="ascii")
            old_epoch = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
            os.utime(old, (old_epoch, old_epoch))

            result = create_backup(
                source,
                output,
                retention_days=14,
                now=datetime(2026, 8, 11, tzinfo=UTC),
            )

            self.assertEqual(result.removed, 1)
            self.assertFalse(old.exists())
            self.assertFalse(old_checksum.exists())

    def test_backup_requires_both_instance_databases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "data"
            source.mkdir()
            (source / "instance.db").write_bytes(b"instance")

            with self.assertRaisesRegex(FileNotFoundError, "movie-inbox.db"):
                create_backup(source, root / "backups")

    def test_verification_rejects_a_modified_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "data"
            source.mkdir()
            (source / "instance.db").write_bytes(b"instance")
            (source / "movie-inbox.db").write_bytes(b"catalog")
            result = create_backup(source, root / "backups")
            result.archive.write_bytes(result.archive.read_bytes() + b"modified")

            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                verify_backup(result.archive)


if __name__ == "__main__":
    unittest.main()
