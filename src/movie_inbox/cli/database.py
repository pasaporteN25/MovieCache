"""Safe JSON/SQLite import, export and inspection commands."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from movie_inbox.domain.catalog import external_link_coverage, linked_sources, normalize_item
from movie_inbox.domain.models import CatalogItem
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.infrastructure.schema import catalog_document
from movie_inbox.infrastructure.sqlite_repository import (
    DATABASE_SCHEMA_VERSION,
    SqliteCatalogRepository,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage Movie Inbox SQLite catalogs and JSON backups."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    import_parser = commands.add_parser("import", help="Import a JSON catalog into SQLite.")
    import_parser.add_argument("catalog", type=Path, help="Input JSON catalog.")
    import_parser.add_argument(
        "--db", type=Path, required=True, help="Destination .db/.sqlite catalog."
    )
    import_parser.add_argument(
        "--replace", action="store_true", help="Replace a non-empty database after backing it up."
    )

    export_parser = commands.add_parser("export", help="Export SQLite to a versioned JSON backup.")
    export_parser.add_argument("database", type=Path, help="Input .db/.sqlite catalog.")
    export_parser.add_argument("--json", type=Path, required=True, help="Destination JSON path.")

    info_parser = commands.add_parser("info", help="Show database schema and catalog counts.")
    info_parser.add_argument("database", type=Path, help="Input .db/.sqlite catalog.")

    args = parser.parse_args(argv)
    if args.command == "import":
        return import_json(args.catalog, args.db, args.replace)
    if args.command == "export":
        return export_json(args.database, args.json)
    return show_info(args.database)


def import_json(source_path: Path, database_path: Path, replace: bool = False) -> int:
    if source_path.suffix.casefold() != ".json":
        raise ValueError("Database import requires a JSON source")
    if database_path.suffix.casefold() not in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError("Database destination must use .db, .sqlite or .sqlite3")
    if source_path.resolve() == database_path.resolve():
        raise ValueError("Source and destination must be different files")
    if not source_path.is_file():
        raise FileNotFoundError(f"Catalog does not exist: {source_path}")

    source = JsonCatalogRepository(source_path, normalize_item, read_only=True)
    destination = SqliteCatalogRepository(database_path, normalize_item)
    items = source.read()
    existing = destination.read() if database_path.exists() else []
    backup_path: Path | None = None
    if existing and not replace:
        print(f"Database already contains {len(existing)} items. Use --replace to overwrite it.")
        return 2
    if existing:
        backup_path = database_path.with_name(
            f"{database_path.stem}.pre-import-{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak.json"
        )
        JsonCatalogRepository(backup_path, normalize_item).write(existing)

    destination.write(items)
    persisted = destination.read()
    verify_catalog_round_trip(items, persisted, "SQLite import")

    print("Database import summary")
    print(f"- Input: {source_path}")
    print(f"- Database: {database_path}")
    print(f"- Database schema: {destination.database_version()}")
    print(f"- Items: {len(persisted)}")
    print("- Verification: complete canonical document")
    if backup_path:
        print(f"- Previous database backup: {backup_path}")
    return 0


def export_json(database_path: Path, json_path: Path) -> int:
    if database_path.suffix.casefold() not in {".db", ".sqlite", ".sqlite3"}:
        raise ValueError("Database source must use .db, .sqlite or .sqlite3")
    if json_path.suffix.casefold() != ".json":
        raise ValueError("Database export requires a .json destination")
    if database_path.resolve() == json_path.resolve():
        raise ValueError("Source and destination must be different files")
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    database = SqliteCatalogRepository(database_path, normalize_item)
    destination = JsonCatalogRepository(json_path, normalize_item)
    items = database.read()
    destination.write(items)
    exported = destination.read()
    verify_catalog_round_trip(items, exported, "JSON export")

    print("Database export summary")
    print(f"- Database: {database_path}")
    print(f"- JSON: {json_path}")
    print(f"- Items: {len(exported)}")
    print("- Verification: complete canonical document")
    return 0


def verify_catalog_round_trip(
    expected: list[CatalogItem],
    persisted: list[CatalogItem],
    operation: str,
) -> None:
    expected_document = catalog_document(expected)
    persisted_document = catalog_document(persisted)
    if persisted_document != expected_document:
        difference = first_document_difference(expected_document, persisted_document)
        raise RuntimeError(
            f"{operation} verification failed: canonical catalog documents differ at {difference}"
        )


def first_document_difference(expected: Any, persisted: Any, path: str = "$") -> str:
    if isinstance(expected, Mapping) and isinstance(persisted, Mapping):
        expected_keys = set(expected)
        persisted_keys = set(persisted)
        if expected_keys != persisted_keys:
            missing = sorted(expected_keys - persisted_keys)
            unexpected = sorted(persisted_keys - expected_keys)
            return f"{path} (missing={missing!r}, unexpected={unexpected!r})"
        for key in expected:
            if expected[key] != persisted[key]:
                return first_document_difference(expected[key], persisted[key], f"{path}.{key}")
        return path
    if isinstance(expected, list) and isinstance(persisted, list):
        if len(expected) != len(persisted):
            return f"{path}.length (expected={len(expected)!r}, persisted={len(persisted)!r})"
        for index, (expected_row, persisted_row) in enumerate(
            zip(expected, persisted, strict=True)
        ):
            if expected_row != persisted_row:
                return first_document_difference(expected_row, persisted_row, f"{path}[{index}]")
        return path
    return f"{path} (expected={expected!r}, persisted={persisted!r})"


def show_info(database_path: Path) -> int:
    if not database_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {database_path}")
    repository = open_catalog_repository(database_path, normalize_item)
    if not isinstance(repository, SqliteCatalogRepository):
        raise ValueError("Database info requires a SQLite catalog")
    items = repository.read()
    print("Database summary")
    print(f"- Path: {database_path}")
    print(f"- Database schema: {repository.database_version()} / {DATABASE_SCHEMA_VERSION}")
    print(f"- Items: {len(items)}")
    print(f"- Series: {sum(1 for item in items if item.kind == 'serie')}")
    print(f"- Local files: {sum(len(item.local_files) for item in items)}")
    rows = [item.to_dict() for item in items]
    print(f"- With Wikipedia: {sum(1 for row in rows if 'wikipedia' in linked_sources(row))}")
    print(f"- With IMDb: {sum(1 for row in rows if 'imdb' in linked_sources(row))}")
    print(f"- With FilmAffinity: {sum(1 for row in rows if 'filmaffinity' in linked_sources(row))}")
    print(f"- With all 3 sources: {sum(1 for row in rows if external_link_coverage(row) == 3)}")
    print(f"- With no external link: {sum(1 for row in rows if external_link_coverage(row) == 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
