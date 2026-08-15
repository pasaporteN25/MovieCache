"""Create and verify portable backups of a Movie Inbox instance directory."""

from __future__ import annotations

import argparse
import hashlib
import os
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

BACKUP_PREFIX = "movie-inbox-instance"
REQUIRED_FILES = ("instance.db", "movie-inbox.db")


@dataclass(frozen=True)
class BackupResult:
    archive: Path
    checksum: Path
    files: int
    bytes: int
    removed: int


@dataclass(frozen=True)
class BackupVerification:
    archive: Path
    files: int
    bytes: int
    checksum_verified: bool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and verify backups of the persistent Movie Inbox instance directory."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create_parser = commands.add_parser("create", help="Create an atomic, verified .tar.gz backup.")
    create_parser.add_argument("source", type=Path, help="Persistent instance directory.")
    create_parser.add_argument(
        "--output-dir", type=Path, required=True, help="Directory for backup archives."
    )
    create_parser.add_argument(
        "--retention-days",
        type=int,
        default=14,
        help="Delete completed backups older than this many days. Defaults to 14.",
    )
    create_parser.add_argument(
        "--include-image-cache",
        action="store_true",
        help="Include the reproducible image cache in the archive.",
    )

    verify_parser = commands.add_parser(
        "verify", help="Read an archive and validate its checksum and contents."
    )
    verify_parser.add_argument("archive", type=Path, help="Backup .tar.gz archive.")

    args = parser.parse_args(argv)
    if args.command == "verify":
        verification = verify_backup(args.archive, require_checksum=True)
        print_verification(verification)
        return 0
    if args.retention_days < 1:
        parser.error("--retention-days must be at least 1")
    result = create_backup(
        args.source,
        args.output_dir,
        retention_days=args.retention_days,
        include_image_cache=args.include_image_cache,
    )
    print_result(result)
    return 0


def create_backup(
    source: Path,
    output_dir: Path,
    *,
    retention_days: int = 14,
    include_image_cache: bool = False,
    now: datetime | None = None,
) -> BackupResult:
    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Instance directory does not exist: {source}")
    if retention_days < 1:
        raise ValueError("Backup retention must be at least one day")
    if output_dir == source or source in output_dir.parents:
        raise ValueError("Backup output directory must be outside the instance directory")
    missing = [name for name in REQUIRED_FILES if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Instance backup is missing required files: {', '.join(missing)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    filename = f"{BACKUP_PREFIX}-{timestamp.strftime('%Y%m%d-%H%M%SZ')}.tar.gz"
    archive = output_dir / filename
    checksum = archive.with_name(f"{archive.name}.sha256")
    temporary_archive = archive.with_name(f".{archive.name}.tmp")
    temporary_checksum = checksum.with_name(f".{checksum.name}.tmp")
    if archive.exists() or checksum.exists():
        raise FileExistsError(f"Backup already exists: {archive}")

    try:
        with tarfile.open(temporary_archive, "w:gz") as bundle:
            for path in backup_paths(source, include_image_cache=include_image_cache):
                relative = path.relative_to(source)
                archive_name = PurePosixPath("movie-inbox", *relative.parts).as_posix()
                bundle.add(path, arcname=archive_name, recursive=False)
        verification = verify_backup(temporary_archive, require_checksum=False)
        digest = sha256_file(temporary_archive)
        temporary_checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
        os.replace(temporary_checksum, checksum)
        os.replace(temporary_archive, archive)
    except Exception:
        temporary_archive.unlink(missing_ok=True)
        temporary_checksum.unlink(missing_ok=True)
        if checksum.exists() and not archive.exists():
            checksum.unlink()
        raise

    removed = prune_backups(output_dir, timestamp - timedelta(days=retention_days), keep=archive)
    return BackupResult(
        archive=archive,
        checksum=checksum,
        files=verification.files,
        bytes=verification.bytes,
        removed=removed,
    )


def backup_paths(source: Path, *, include_image_cache: bool) -> list[Path]:
    paths: list[Path] = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if not include_image_cache and relative.parts and relative.parts[0] == "image-cache":
            continue
        if path.is_symlink():
            raise ValueError(f"Instance backup refuses symbolic links: {path}")
        if path.is_dir() or path.is_file():
            paths.append(path)
    return sorted(paths, key=lambda value: value.relative_to(source).as_posix())


def verify_backup(archive: Path, *, require_checksum: bool = True) -> BackupVerification:
    archive = archive.resolve()
    if not archive.is_file():
        raise FileNotFoundError(f"Backup archive does not exist: {archive}")
    checksum_verified = False
    if require_checksum:
        checksum_path = archive.with_name(f"{archive.name}.sha256")
        if not checksum_path.is_file():
            raise FileNotFoundError(f"Backup checksum does not exist: {checksum_path}")
        checksum_parts = checksum_path.read_text(encoding="ascii").strip().split(maxsplit=1)
        if not checksum_parts:
            raise RuntimeError(f"Backup checksum is empty: {checksum_path}")
        expected = checksum_parts[0]
        actual = sha256_file(archive)
        if not expected or expected.casefold() != actual.casefold():
            raise RuntimeError(f"Backup checksum mismatch: {archive}")
        checksum_verified = True

    files = 0
    total_bytes = 0
    names: set[str] = set()
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            for member in bundle:
                member_path = PurePosixPath(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise RuntimeError(f"Unsafe path in backup archive: {member.name}")
                names.add(member_path.as_posix())
                if not member.isfile():
                    continue
                stream = bundle.extractfile(member)
                if stream is None:
                    raise RuntimeError(f"Cannot read backup member: {member.name}")
                while chunk := stream.read(1024 * 1024):
                    total_bytes += len(chunk)
                files += 1
    except (tarfile.TarError, OSError) as error:
        raise RuntimeError(f"Invalid backup archive: {archive}") from error

    required = {f"movie-inbox/{name}" for name in REQUIRED_FILES}
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"Backup archive is missing required files: {', '.join(missing)}")
    return BackupVerification(archive, files, total_bytes, checksum_verified)


def prune_backups(output_dir: Path, cutoff: datetime, *, keep: Path) -> int:
    removed = 0
    cutoff_epoch = cutoff.timestamp()
    for archive in output_dir.glob(f"{BACKUP_PREFIX}-*.tar.gz"):
        if archive == keep or archive.stat().st_mtime >= cutoff_epoch:
            continue
        archive.unlink()
        archive.with_name(f"{archive.name}.sha256").unlink(missing_ok=True)
        removed += 1
    return removed


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def print_result(result: BackupResult) -> None:
    print("Instance backup")
    print(f"- Archive: {result.archive}")
    print(f"- Checksum: {result.checksum}")
    print(f"- Files: {result.files}")
    print(f"- Uncompressed data: {format_bytes(result.bytes)}")
    print(f"- Expired backups removed: {result.removed}")
    print("- Verification: checksum and required databases")


def print_verification(result: BackupVerification) -> None:
    print("Backup verification")
    print(f"- Archive: {result.archive}")
    print(f"- Files: {result.files}")
    print(f"- Uncompressed data: {format_bytes(result.bytes)}")
    print(f"- Checksum: {'verified' if result.checksum_verified else 'not requested'}")
    print("- Required databases: verified")


def format_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


if __name__ == "__main__":
    raise SystemExit(main())
