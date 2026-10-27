"""[X12 B] `movie-inbox identity resolve`: fill missing Wikidata ids now.

The server already does this slowly in the background. This is the same work
done at once -- for a catalogue just imported, or before a curation session.
It asks Wikipedia for the Wikidata id of each article an entry links to, fifty
articles per request, and writes back only empty, unlocked fields. It prints
counts only, so its output can be shared without sharing the catalogue.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from movie_inbox.application.identity_resolution_service import (
    IdentityAttemptStore,
    IdentityResolutionService,
    ResolutionReport,
)
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.external.wikidata import fetch_wikidata_release_years
from movie_inbox.external.wikipedia import fetch_wikidata_ids_for_articles
from movie_inbox.infrastructure.identity_attempt_repository import (
    SqliteIdentityAttemptRepository,
)
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="movie-inbox identity",
        description="Complete the external identity of catalogue entries.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    resolve = commands.add_parser(
        "resolve",
        help="Look up the Wikidata id of entries that only have a Wikipedia link.",
    )
    resolve.add_argument("catalogs", nargs="+", type=Path, help="JSON or SQLite catalogs.")
    resolve.add_argument(
        "--instance-db",
        type=Path,
        help=(
            "Instance database, to skip articles that recently answered without an "
            "id and to remember new ones. Optional."
        ),
    )
    resolve.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after this many articles (rounded up to a batch of 50). 0 means all.",
    )
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be 0 or positive")
    missing = [path for path in args.catalogs if not path.exists()]
    if missing:
        parser.error(f"Catalog not found: {missing[0]}")

    attempts: IdentityAttemptStore | None = None
    if args.instance_db:
        SqliteIdentityRepository(args.instance_db).initialize()
        attempts = SqliteIdentityAttemptRepository(args.instance_db)
    repositories = [open_catalog_repository(path, normalize_item) for path in args.catalogs]
    service = IdentityResolutionService(
        lambda: repositories,
        fetch_wikidata_ids_for_articles,
        fetch_wikidata_release_years,
        attempts,
    )
    batches = max(1, -(-args.limit // 50)) if args.limit else 10_000
    report = service.resolve_all(max_batches=batches)
    print_report(report)
    return 1 if report.failed and not report.resolved else 0


def print_report(report: ResolutionReport) -> None:
    print("Identity resolution")
    print(f"- Wikidata ids filled: {report.resolved}")
    print(f"- Years filled: {report.years}")
    print(f"- Articles without a Wikidata id: {report.missing}")
    print(f"- Not answered (network or catalog errors): {report.failed}")
    print(f"- Still pending: {report.pending}")
    for error in report.errors:
        print(f"  ! {error}")


if __name__ == "__main__":
    raise SystemExit(main())
