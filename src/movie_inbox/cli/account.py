"""Bootstrap the first self-hosted Movie Inbox owner account."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.repositories import CATALOG_SUFFIXES, open_catalog_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the local Movie Inbox owner account.")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser(
        "bootstrap", help="Create the first owner and adopt a personal catalog."
    )
    bootstrap.add_argument(
        "--instance-db", type=Path, required=True, help="Private SQLite instance database."
    )
    bootstrap.add_argument(
        "--catalog",
        type=Path,
        action="append",
        required=True,
        help="Catalog source owned by this account. Can be repeated.",
    )
    bootstrap.add_argument(
        "--write-catalog", type=Path, help="Writable catalog source. Defaults to the first catalog."
    )
    bootstrap.add_argument("--username", default="owner", help="Initial owner username.")
    bootstrap.add_argument(
        "--catalog-name", default="Mi catalogo", help="Personal catalog display name."
    )
    bootstrap.add_argument(
        "--password-file", type=Path, help="Read the initial password from this file."
    )
    args = parser.parse_args(argv)
    try:
        return bootstrap_owner(
            args.instance_db,
            args.catalog,
            args.write_catalog or args.catalog[0],
            args.username,
            args.catalog_name,
            args.password_file,
        )
    except ValueError as error:
        parser.error(str(error))
        return 2


def bootstrap_owner(
    instance_db: Path,
    catalogs: list[Path],
    write_catalog: Path,
    username: str,
    catalog_name: str,
    password_file: Path | None,
) -> int:
    _validate_catalog_paths(catalogs, write_catalog)
    ensure_catalog_exists(write_catalog)
    repository = SqliteIdentityRepository(instance_db)
    repository.initialize()
    if repository.has_users():
        print(f"Instance already has an owner: {instance_db}")
        return 2
    password = password_from_file_or_prompt(password_file)
    user, catalog = AuthService(repository).bootstrap_owner(
        username,
        password,
        catalog_name=catalog_name,
        source_paths=[str(path) for path in catalogs],
        write_path=str(write_catalog),
    )
    print("Owner bootstrap complete")
    print(f"- Instance database: {instance_db.resolve()}")
    print(f"- Owner: {user.username}")
    print(f"- Personal catalog: {catalog.name}")
    print(f"- Writable source: {catalog.write_path}")
    return 0


def ensure_catalog_exists(path: Path) -> None:
    if path.exists():
        return
    repository = open_catalog_repository(path, normalize_item)
    repository.write([])


def password_from_file_or_prompt(password_file: Path | None) -> str:
    if password_file:
        try:
            if password_file.stat().st_size > 4096:
                raise ValueError("Owner password file is too large")
            return password_file.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as error:
            raise ValueError(f"Cannot read owner password file: {password_file}") from error
    first = getpass.getpass("Initial owner password: ")
    second = getpass.getpass("Repeat owner password: ")
    if first != second:
        raise ValueError("Owner passwords do not match")
    return first


def _validate_catalog_paths(catalogs: list[Path], write_catalog: Path) -> None:
    if not catalogs:
        raise ValueError("At least one catalog is required")
    for path in [*catalogs, write_catalog]:
        if path.suffix.casefold() not in CATALOG_SUFFIXES:
            supported = ", ".join(sorted(CATALOG_SUFFIXES))
            raise ValueError(f"Unsupported catalog extension for {path}. Use one of: {supported}")
    catalog_paths = {_resolved(path) for path in catalogs}
    if _resolved(write_catalog) not in catalog_paths:
        raise ValueError("--write-catalog must also be listed with --catalog")


def _resolved(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


if __name__ == "__main__":
    raise SystemExit(main())
