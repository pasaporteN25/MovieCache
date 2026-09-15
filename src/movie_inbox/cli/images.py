"""Diagnose how well a catalogue can fill the console's image windows ([U7.1]).

It looks only at what is on this machine: the catalogue, optionally the instance
database for the Club collections an account can open, and the listing of the
image cache directory. It never downloads an image or asks a provider anything,
and it prints counts only -- no titles, no addresses, no paths -- so its output
can be shared without sharing the catalogue.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.charades import work_key
from movie_inbox.domain.image_coverage import (
    CATALOG_ORIGIN,
    CLUB_ORIGIN,
    IDENTITIES,
    SLOT_STATES,
    AddressCheck,
    WorkImageCoverage,
    classify_work,
    summarize,
)
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.web.config import DEFAULT_IMAGE_ALLOWED_HOSTS
from movie_inbox.web.image_proxy import cached_image_keys, image_cache_url_keys
from movie_inbox.web.security import validate_http_url

SLOT_LABELS = {
    "empty": "vacía",
    "rejected": "rechazada",
    "uncached": "sin caché",
    "cached": "en caché",
}
IDENTITY_LABELS = {"tmdb": "TMDb", "other": "otra", "none": "ninguna"}
ORIGIN_LABELS = {CATALOG_ORIGIN: "Catálogo", CLUB_ORIGIN: "Club"}
KIND_LABELS = {
    "pelicula": "película",
    "serie": "serie",
    "anime": "anime",
    "documental": "documental",
}


class CoverageInputError(ValueError):
    """An input the diagnosis cannot read, reported instead of an empty report."""


def main(argv: list[str] | None = None) -> int:
    # The report is labelled in Spanish. A stdout still on a legacy Windows code
    # page would mangle the accents or, on a label it cannot encode, stop halfway.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        prog="movie-inbox images",
        description="Diagnose image coverage without downloading anything.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    coverage = commands.add_parser(
        "coverage",
        help="Count, by cause, why works cannot fill the console's two image windows.",
    )
    coverage.add_argument("catalog", type=Path, help="Catalog to diagnose (.json or SQLite).")
    coverage.add_argument(
        "--instance-db",
        type=Path,
        help="Instance database. Adds the Club collections the account can open.",
    )
    coverage.add_argument(
        "--user",
        default="",
        help="Account whose Club collections are counted. Defaults to the owner.",
    )
    coverage.add_argument(
        "--image-cache-dir",
        type=Path,
        help="Image cache directory. Defaults to .catalog-cache/images next to the catalog, "
        "as serve does.",
    )
    coverage.add_argument(
        "--image-host",
        action="append",
        default=[],
        help="Extra allowed image host, exactly as passed to serve. Repeatable.",
    )
    coverage.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = parser.parse_args(argv)

    cache_dir = args.image_cache_dir or (
        args.catalog.resolve().parent / ".catalog-cache" / "images"
    )
    hosts = tuple(dict.fromkeys([*DEFAULT_IMAGE_ALLOWED_HOSTS, *args.image_host]))
    try:
        report = coverage_report(
            args.catalog,
            instance_db=args.instance_db,
            username=args.user,
            cache_dir=cache_dir,
            allowed_hosts=hosts,
        )
    except CoverageInputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0


def coverage_report(
    catalog: Path,
    *,
    instance_db: Path | None,
    username: str,
    cache_dir: Path,
    allowed_hosts: Sequence[str],
) -> dict[str, Any]:
    allowed, cached = address_checks(allowed_hosts, cache_dir)
    works: list[WorkImageCoverage] = [
        classify_work(row, CATALOG_ORIGIN, allowed=allowed, cached=cached)
        for row in _catalog_rows(catalog)
    ]
    if instance_db is not None:
        works.extend(
            classify_work(row, CLUB_ORIGIN, allowed=allowed, cached=cached)
            for row in _club_rows(instance_db, username)
        )
    return summarize(works)


def address_checks(
    allowed_hosts: Sequence[str], cache_dir: Path
) -> tuple[AddressCheck, AddressCheck]:
    """The proxy's own rules, so "rejected" means exactly what serve would refuse."""

    cache_keys = cached_image_keys(cache_dir)

    def validated(url: str) -> str:
        try:
            return validate_http_url(url, allowed_hosts)
        except ValueError:
            return ""

    def allowed(url: str) -> bool:
        return bool(validated(url))

    def cached(url: str) -> bool:
        address = validated(url)
        return bool(address) and any(key in cache_keys for key in image_cache_url_keys(address))

    return allowed, cached


def format_report(report: Mapping[str, Any]) -> str:
    totals = report["totals"]
    lines = [f"Cobertura de imágenes: {totals['works']} obras, sin descargar nada.", ""]
    lines.extend(_block("Total", totals))
    for segment in report["segments"]:
        title = f"{ORIGIN_LABELS[segment['origin']]}, {KIND_LABELS[segment['kind']]}"
        lines.append("")
        lines.extend(_block(title, segment))
    lines.extend(
        [
            "",
            "Sin red no se distingue una dirección rota, un proveedor caído ni una obra",
            "sin imagen en el proveedor: eso se mide aparte, sobre una muestra.",
        ]
    )
    return "\n".join(lines)


def _block(title: str, counts: Mapping[str, Any]) -> list[str]:
    return [
        f"{title} ({counts['works']} obras)",
        f"  Póster:      {_states(counts['poster'])}",
        f"  Panorámica:  {_states(counts['backdrop'])}",
        "  Imágenes distintas: "
        + " · ".join(f"{name}: {counts['distinct_images'][name]}" for name in ("0", "1", "2")),
        f"  Identidad:   {_identities(counts['identity'])}",
        f"  Con menos de dos imágenes, por identidad: {_identities(counts['short_by_identity'])}",
    ]


def _states(counts: Mapping[str, int]) -> str:
    return " · ".join(f"{SLOT_LABELS[name]} {counts[name]}" for name in SLOT_STATES)


def _identities(counts: Mapping[str, int]) -> str:
    return " · ".join(f"{IDENTITY_LABELS[name]} {counts[name]}" for name in IDENTITIES)


def _catalog_rows(catalog: Path) -> list[dict[str, Any]]:
    if not catalog.is_file():
        raise CoverageInputError(f"catalog not found: {catalog}")
    try:
        return [dict(row) for row in open_catalog_repository(catalog, normalize_item).read()]
    except (CatalogRepositoryError, ValueError) as error:
        raise CoverageInputError(f"cannot read catalog: {error}") from error


def _club_rows(instance_db: Path, username: str) -> list[dict[str, Any]]:
    if not instance_db.is_file():
        raise CoverageInputError(f"instance database not found: {instance_db}")
    identity = SqliteIdentityRepository(instance_db)
    if username:
        account = next(
            (
                account
                for account, _catalog in identity.list_accounts()
                if account.username == username
            ),
            None,
        )
    else:
        account = identity.owner()
    if account is None:
        raise CoverageInputError(f"account not found: {username or 'owner'}")
    try:
        collections = SqliteCollectionRepository(instance_db).list_accessible(account.id)
    except CollectionRepositoryError as error:
        raise CoverageInputError(f"cannot read collections: {error}") from error
    return _unique_works(
        dict(entry.item) for collection in collections for entry in collection.items
    )


def _unique_works(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each Club work once, even when several collections carry it.

    Collection items have per-collection ids, so identity comes from the same
    cross-store key the charades deck uses to merge the two stores.
    """

    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = work_key(row) or f"row:{len(found)}"
        found.setdefault(key, row)
    return list(found.values())
