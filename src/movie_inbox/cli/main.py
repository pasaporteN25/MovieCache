"""Installed command dispatcher for Movie Inbox."""

from __future__ import annotations

import sys
from collections.abc import Callable

from movie_inbox.cli import database, enrich_catalog, import_catalog, match_external_links, migrate, scan_library
from movie_inbox.web import server


Command = Callable[[list[str] | None], int]
COMMANDS: dict[str, tuple[Command, str]] = {
    "import": (import_catalog.main, "Import or merge TXT, JSON and CSV catalogs."),
    "scan": (scan_library.main, "Scan a local video library incrementally."),
    "serve": (server.main, "Open the local catalog viewer."),
    "migrate": (migrate.main, "Upgrade a legacy JSON catalog."),
    "enrich": (enrich_catalog.main, "Clean titles and fetch missing metadata."),
    "match": (match_external_links.main, "Attach trusted external links."),
    "db": (database.main, "Import, export and inspect SQLite catalogs."),
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
        print(f"  {name:<8} {description}")
    print("\nRun movie-inbox <command> --help for command-specific options.")


if __name__ == "__main__":
    raise SystemExit(main())
