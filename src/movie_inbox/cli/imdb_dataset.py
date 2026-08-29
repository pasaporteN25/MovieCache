"""Prototype CLI for IMDb's official non-commercial bulk datasets.

Scope: [F1] in tareas.md. This command measures whether indexing IMDb's
bulk TSV dumps locally is viable (disk usage, first-load and re-sync
time) and offers a read-only lookup. It never touches the real catalog,
`domain/catalog.py`'s merge machinery, or `metadata_sources` — deciding
whether/how this data feeds the catalog is [Q5]'s job, not this one.

No `application/` layer: this is a self-contained, throwaway measurement
tool with nothing else to inject into yet, so this module wires
`external/` and `infrastructure/` directly, the same shape already used
by `cli/database.py`/`cli/backup.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE
from movie_inbox.external.imdb_datasets import AVAILABLE_DATASETS, download_dataset_file
from movie_inbox.infrastructure.imdb_dataset_index import (
    TitleLookupResult,
    build_index,
    index_stats,
    lookup_by_tconst,
    lookup_by_title,
)
from movie_inbox.infrastructure.schema import atomic_write_json

_INDEX_FILENAME = "imdb-dataset.db"


def main(argv: list[str] | None = None) -> int:
    # title.akas holds titles in every script IMDb tracks (Cyrillic, CJK,
    # Arabic, ...). A console still on a legacy codepage (cp1252 is the
    # Windows default) raises UnicodeEncodeError on the first one it can't
    # represent instead of just rendering it — reconfigure to UTF-8 so
    # `lookup` can't crash partway through printing real results.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Prototype: download and index IMDb's non-commercial bulk datasets locally."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sync_parser = commands.add_parser(
        "sync", help="Download title.basics/title.akas and (re)build the local index."
    )
    sync_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to hold the downloaded files and index.",
    )
    sync_parser.add_argument("--report", type=Path, help="Optional JSON report path.")

    stats_parser = commands.add_parser(
        "stats", help="Show row counts and disk usage for an existing index."
    )
    stats_parser.add_argument("--output-dir", type=Path, required=True)

    lookup_parser = commands.add_parser("lookup", help="Query the local index (read-only).")
    lookup_parser.add_argument("--output-dir", type=Path, required=True)
    lookup_group = lookup_parser.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument("--tconst", help="Look up by IMDb id, e.g. tt0113277.")
    lookup_group.add_argument("--title", help="Look up by title text.")
    lookup_parser.add_argument("--year", type=int, help="Narrow --title to a start year.")

    args = parser.parse_args(argv)
    if args.command == "lookup" and args.tconst and args.year is not None:
        parser.error("--year can only be used together with --title")

    if args.command == "sync":
        return run_sync(args.output_dir, args.report)
    if args.command == "stats":
        return run_stats(args.output_dir)
    return run_lookup(args.output_dir, args.tconst, args.title, args.year)


def run_sync(output_dir: Path, report_path: Path | None) -> int:
    output_dir = Path(output_dir)
    downloads: dict[str, dict[str, Any]] = {}
    for name in AVAILABLE_DATASETS:
        destination = output_dir / f"{name}.tsv.gz"
        result = download_dataset_file(name, destination)
        downloads[name] = {
            "bytes_downloaded": result.bytes_downloaded,
            "elapsed_seconds": round(result.elapsed_seconds, 3),
        }
    index_path = output_dir / _INDEX_FILENAME
    build_report = build_index(
        output_dir / "title.basics.tsv.gz",
        output_dir / "title.akas.tsv.gz",
        index_path,
    )
    report: dict[str, Any] = {
        "downloads": downloads,
        "basics_rows": build_report.basics_rows,
        "basics_skipped_lines": build_report.basics_skipped_lines,
        "akas_rows": build_report.akas_rows,
        "akas_skipped_lines": build_report.akas_skipped_lines,
        "index_build_seconds": round(build_report.elapsed_seconds, 3),
        "index_size_bytes": build_report.index_size_bytes,
        "index_path": str(index_path),
        "attribution": IMDB_ATTRIBUTION_NOTICE,
    }
    if report_path:
        atomic_write_json(report_path.resolve(), report, backup_limit=3)
    print_sync_report(report)
    return 0


def print_sync_report(report: dict[str, Any]) -> None:
    print("IMDb dataset sync summary")
    for name, info in report["downloads"].items():
        megabytes = info["bytes_downloaded"] / 1_048_576
        print(f"- Downloaded {name}.tsv.gz: {megabytes:.1f} MB in {info['elapsed_seconds']:.1f}s")
    print(
        f"- Indexed {report['basics_rows']} titles ({report['basics_skipped_lines']} lines skipped)"
    )
    print(
        f"- Indexed {report['akas_rows']} alternate titles "
        f"({report['akas_skipped_lines']} lines skipped)"
    )
    print(f"- Index build time: {report['index_build_seconds']:.1f}s")
    print(f"- Index size on disk: {report['index_size_bytes'] / 1_048_576:.1f} MB")
    print(f"- Index path: {report['index_path']}")
    print(f"- {report['attribution']}")


def run_stats(output_dir: Path) -> int:
    stats = index_stats(Path(output_dir) / _INDEX_FILENAME)
    print("IMDb dataset index stats")
    print(f"- Titles: {stats.basics_rows}")
    print(f"- Alternate titles: {stats.akas_rows}")
    print(f"- Size on disk: {stats.index_size_bytes / 1_048_576:.1f} MB")
    return 0


def run_lookup(output_dir: Path, tconst: str | None, title: str | None, year: int | None) -> int:
    index_path = Path(output_dir) / _INDEX_FILENAME
    if tconst:
        found = lookup_by_tconst(index_path, tconst)
        results = [found] if found is not None else []
    else:
        assert title is not None
        results = lookup_by_title(index_path, title, year)
    if not results:
        print("No matching title found in the local index.")
        return 1
    for result in results:
        print_lookup_result(result)
    print(f"\n{IMDB_ATTRIBUTION_NOTICE}")
    return 0


def print_lookup_result(result: TitleLookupResult) -> None:
    year = result.start_year if result.start_year is not None else "?"
    print(f"- {result.tconst}: {result.primary_title} ({year}) [{result.title_type}]")
    if result.original_title != result.primary_title:
        print(f"  Original title: {result.original_title}")
    if result.runtime_minutes:
        print(f"  Runtime: {result.runtime_minutes} min")
    if result.genres:
        print(f"  Genres: {result.genres}")
    for aka in result.akas:
        marker = " (original)" if aka.is_original_title else ""
        region = f" [{aka.region}]" if aka.region else ""
        print(f"  aka {aka.title}{region}{marker}")


if __name__ == "__main__":
    raise SystemExit(main())
