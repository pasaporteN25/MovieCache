"""Build and inspect the opt-in anime-offline-database index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from movie_inbox.infrastructure.anime_offline_index import (
    ANIME_OFFLINE_ATTRIBUTION,
    AnimeLookupResult,
    anime_index_stats,
    build_anime_index,
    lookup_anime_by_external_id,
    lookup_anime_by_mal_id,
    lookup_anime_by_title,
)
from movie_inbox.infrastructure.schema import atomic_write_json

ANIME_INDEX_FILENAME = "anime-offline.db"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description=(
            "Build a local index from a user-supplied anime-offline-database snapshot. "
            "This command never downloads or modifies a catalog."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sync_parser = commands.add_parser("sync", help="Rebuild the index from a local snapshot.")
    sync_parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Local .jsonl or .json snapshot downloaded by the owner.",
    )
    sync_parser.add_argument("--output-dir", type=Path, required=True)
    sync_parser.add_argument("--report", type=Path, help="Optional JSON build report.")

    stats_parser = commands.add_parser("stats", help="Show index size, version and row counts.")
    stats_parser.add_argument("--output-dir", type=Path, required=True)

    lookup_parser = commands.add_parser("lookup", help="Query the local index read-only.")
    lookup_parser.add_argument("--output-dir", type=Path, required=True)
    lookup_group = lookup_parser.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument("--mal-id", help="MyAnimeList anime id.")
    lookup_group.add_argument(
        "--external-id",
        help="Cross-reference as provider:id, for example anilist:1535.",
    )
    lookup_group.add_argument("--title", help="Title or multilingual alias.")
    lookup_parser.add_argument("--year", type=int, help="Prefer this release year with --title.")

    args = parser.parse_args(argv)
    if args.command == "lookup" and args.year is not None and not args.title:
        parser.error("--year can only be used together with --title")
    if args.command == "sync":
        return run_sync(args.snapshot, args.output_dir, args.report)
    if args.command == "stats":
        return run_stats(args.output_dir)
    return run_lookup(args.output_dir, args.mal_id, args.external_id, args.title, args.year)


def run_sync(snapshot_path: Path, output_dir: Path, report_path: Path | None) -> int:
    index_path = Path(output_dir) / ANIME_INDEX_FILENAME
    report = build_anime_index(snapshot_path, index_path)
    payload: dict[str, Any] = {
        "anime_rows": report.anime_rows,
        "alias_rows": report.alias_rows,
        "external_id_rows": report.external_id_rows,
        "skipped_rows": report.skipped_rows,
        "index_build_seconds": round(report.elapsed_seconds, 3),
        "index_size_bytes": report.index_size_bytes,
        "index_path": str(index_path),
        "snapshot_date": report.snapshot_date,
        "snapshot_sha256": report.snapshot_sha256,
        "license_name": report.license_name,
        "license_url": report.license_url,
        "attribution": ANIME_OFFLINE_ATTRIBUTION,
    }
    if report_path:
        atomic_write_json(report_path.resolve(), payload, backup_limit=3)
    print("anime-offline-database sync summary")
    print(f"- Snapshot date: {report.snapshot_date}")
    print(f"- Indexed anime: {report.anime_rows} ({report.skipped_rows} rows skipped)")
    print(f"- Indexed titles and aliases: {report.alias_rows}")
    print(f"- Indexed cross-references: {report.external_id_rows}")
    print(f"- Build time: {report.elapsed_seconds:.1f}s")
    print(f"- Index size: {report.index_size_bytes / 1_048_576:.1f} MB")
    print(f"- Index path: {index_path}")
    print(f"- {ANIME_OFFLINE_ATTRIBUTION}")
    return 0


def run_stats(output_dir: Path) -> int:
    stats = anime_index_stats(Path(output_dir) / ANIME_INDEX_FILENAME)
    print("anime-offline-database index stats")
    print(f"- Snapshot date: {stats.snapshot_date}")
    print(f"- Anime: {stats.anime_rows}")
    print(f"- Titles and aliases: {stats.alias_rows}")
    print(f"- Cross-references: {stats.external_id_rows}")
    print(f"- Size on disk: {stats.index_size_bytes / 1_048_576:.1f} MB")
    print(f"- SHA-256: {stats.snapshot_sha256}")
    print(f"- {ANIME_OFFLINE_ATTRIBUTION}")
    return 0


def run_lookup(
    output_dir: Path,
    mal_id: str | None,
    external_id: str | None,
    title: str | None,
    year: int | None,
) -> int:
    index_path = Path(output_dir) / ANIME_INDEX_FILENAME
    if mal_id:
        found = lookup_anime_by_mal_id(index_path, mal_id)
        results = [found] if found is not None else []
    elif external_id:
        provider, separator, value = external_id.partition(":")
        if not separator or not provider.strip() or not value.strip():
            print("--external-id must use provider:id, for example anilist:1535.", file=sys.stderr)
            return 2
        found = lookup_anime_by_external_id(index_path, provider, value)
        results = [found] if found is not None else []
    else:
        assert title is not None
        results = lookup_anime_by_title(index_path, title, year)
    if not results:
        print("No matching anime found in the local index.")
        return 1
    for result in results:
        print_lookup_result(result)
    print(f"\n{ANIME_OFFLINE_ATTRIBUTION}")
    return 0


def print_lookup_result(result: AnimeLookupResult) -> None:
    year = result.release_year if result.release_year is not None else "?"
    mal = f" MAL {result.mal_id}" if result.mal_id else ""
    print(f"- {result.title} ({year}) [{result.anime_type}]{mal}")
    for alias in result.aliases:
        print(f"  alias {alias}")
    for external_id in result.external_ids:
        print(f"  id {external_id.provider}:{external_id.external_id}")


if __name__ == "__main__":
    raise SystemExit(main())
