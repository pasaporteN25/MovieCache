"""Installed command dispatcher for Movie Inbox."""

from __future__ import annotations

import sys
from collections.abc import Callable

from movie_inbox.cli import (
    account,
    backup,
    cache,
    database,
    enrich_catalog,
    imdb_dataset,
    import_catalog,
    match_external_links,
    migrate,
    scan_library,
    search_lab,
)
from movie_inbox.web import server

Command = Callable[[list[str] | None], int]
COMMANDS: dict[str, tuple[Command, str]] = {
    "account": (account.main, "Bootstrap the local owner account."),
    "import": (import_catalog.main, "Import or merge TXT, JSON and CSV catalogs."),
    "scan": (scan_library.main, "Scan a local video library incrementally."),
    "serve": (server.main, "Open the local catalog viewer."),
    "migrate": (migrate.main, "Upgrade a legacy JSON catalog."),
    "enrich": (enrich_catalog.main, "Clean titles and fetch missing metadata."),
    "match": (match_external_links.main, "Attach trusted external links."),
    "db": (database.main, "Import, export and inspect SQLite catalogs."),
    "cache": (cache.main, "Inspect, prune or clear the image cache."),
    "backup": (backup.main, "Create and verify persistent instance backups."),
    "search-lab": (search_lab.main, "Measure search quality without changing a catalog."),
    "imdb-dataset": (
        imdb_dataset.main,
        "Prototype: download and index IMDb's non-commercial datasets.",
    ),
}


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] in {"-h", "--help", "help"}:
        print_help()
        return 0

    name = arguments.pop(0)
    command = COMMANDS.get(name)
    if command is None:
        available = ", ".join(COMMANDS)
        print(f"Unknown command: {name}\nAvailable commands: {available}", file=sys.stderr)
        return 2
    return command[0](arguments)


def print_help() -> None:
    print("usage: movie-inbox <command> [options]\n")
    print("commands:")
    for name, (_, description) in COMMANDS.items():
        print(f"  {name:<10} {description}")
    print("\nRun movie-inbox <command> --help for command-specific options.")


if __name__ == "__main__":
    raise SystemExit(main())
