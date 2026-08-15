"""Inspect and maintain the bounded image cache."""

from __future__ import annotations

import argparse
from pathlib import Path

from movie_inbox.web.config import DEFAULT_IMAGE_CACHE_TOTAL_BYTES
from movie_inbox.web.image_proxy import clear_image_cache, image_cache_info, prune_image_cache

DEFAULT_CACHE_DIR = Path(".catalog-cache/images")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect, prune or clear the Movie Inbox image cache."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    info_parser = commands.add_parser("info", help="Show cache path, file count and total size.")
    add_cache_dir(info_parser)

    prune_parser = commands.add_parser(
        "prune", help="Remove least-recently-used images above the size limit."
    )
    add_cache_dir(prune_parser)
    prune_parser.add_argument(
        "--max-total-mb",
        type=float,
        default=DEFAULT_IMAGE_CACHE_TOTAL_BYTES / (1024 * 1024),
        help="Maximum total cache size after pruning.",
    )

    clear_parser = commands.add_parser("clear", help="Remove all files from the image cache.")
    add_cache_dir(clear_parser)

    args = parser.parse_args(argv)
    if args.command == "info":
        info = image_cache_info(args.cache_dir)
        print_cache_info(info.path, info.files, info.total_bytes)
        return 0
    if args.command == "clear":
        info = clear_image_cache(args.cache_dir)
        print(
            f"Cleared {info.removed_files} files "
            f"({format_bytes(info.removed_bytes)}) from {info.path}"
        )
        return 0
    if args.max_total_mb <= 0:
        parser.error("--max-total-mb must be greater than zero")
    maximum = int(args.max_total_mb * 1024 * 1024)
    info = prune_image_cache(args.cache_dir, maximum)
    print_cache_info(info.path, info.files, info.total_bytes, maximum)
    print(f"Removed: {info.removed_files} files ({format_bytes(info.removed_bytes)})")
    return 0


def add_cache_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dir",
        dest="cache_dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Image cache directory. Defaults to .catalog-cache/images.",
    )


def print_cache_info(
    path: Path, files: int, total_bytes: int, max_bytes: int | None = None
) -> None:
    print("Image cache")
    print(f"- Path: {path.resolve()}")
    print(f"- Files: {files}")
    print(f"- Size: {format_bytes(total_bytes)}")
    if max_bytes is not None:
        print(f"- Limit: {format_bytes(max_bytes)}")


def format_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


if __name__ == "__main__":
    raise SystemExit(main())
