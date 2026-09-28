"""Diagnose ([U7.1]) and fill ([U7 B]) a catalogue's two images per work.

`coverage` looks only at what is on this machine. `fill` is the explicit batch of
the U7 B contract: it asks TMDb, only by ids the works already carry, for up to
`--limit` works and completes empty, unlocked image fields.

It looks only at what is on this machine: the catalogue, optionally the instance
database for the Club collections an account can open, and the listing of the
image cache directory. It never downloads an image or asks a provider anything,
and it prints counts only -- no titles, no addresses, no paths -- so its output
can be shared without sharing the catalogue.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.application.image_service import ImageService
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
from movie_inbox.external.image_sources import TmdbImageSource
from movie_inbox.external.tmdb import TmdbAdapter
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.web.config import DEFAULT_IMAGE_ALLOWED_HOSTS
from movie_inbox.web.image_proxy import cached_image_keys, image_cache_url_keys
from movie_inbox.web.security import validate_http_url
from movie_inbox.web.server import external_api_token

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
    fill = commands.add_parser(
        "fill",
        help="Complete empty, unlocked images from TMDb, only through ids the works carry.",
    )
    fill.add_argument("catalog", type=Path, help="Catalog to fill (.json or SQLite).")
    fill.add_argument(
        "--limit",
        type=int,
        required=True,
        help="Maximum number of works to ask TMDb about in this run.",
    )
    fill.add_argument(
        "--dry-run", action="store_true", help="Ask TMDb and report, but write nothing."
    )
    fill.add_argument(
        "--tmdb-read-access-token-file",
        type=Path,
        default=(
            Path(os.environ["MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE"])
            if os.environ.get("MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE")
            else None
        ),
        help="TMDb API Read Access Token file, the same one serve reads.",
    )
    fill.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    args = parser.parse_args(argv)
    if args.command == "fill":
        return run_fill(args)

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


FILL_STATUS_LABELS = {
    "ok": "con imágenes nuevas",
    "no_images": "TMDb no tiene más imágenes",
    "needs_review": "cruce dudoso, sin escribir",
    "no_identity": "sin id para cruzar",
    "complete": "ya completas",
    "unavailable": "TMDb no respondió",
    "rate_limited": "TMDb pidió esperar (se cortó la corrida)",
}
CROSSWALK_LABELS = {
    "accepted": "aceptado",
    "no_result": "sin resultado",
    "ambiguous": "varios resultados",
    "kind_mismatch": "tipo distinto",
    "year_mismatch": "año distinto",
    "no_year": "la obra no tiene año",
}


def run_fill(args: argparse.Namespace) -> int:
    if args.limit <= 0:
        print("error: --limit tiene que ser mayor que cero", file=sys.stderr)
        return 2
    try:
        token = external_api_token(args.tmdb_read_access_token_file, source_label="TMDb")
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if not token:
        print(
            "error: falta el token de TMDb (--tmdb-read-access-token-file o "
            "MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE)",
            file=sys.stderr,
        )
        return 2
    try:
        catalog = CatalogService(open_catalog_repository(args.catalog, normalize_item))
        service = ImageService(TmdbImageSource(TmdbAdapter(token)))

        def progress(done: int, total: int) -> None:
            if not args.json:
                print(f"\r{done}/{total}", end="", file=sys.stderr, flush=True)

        summary = service.fill_batch(
            catalog, limit=args.limit, dry_run=args.dry_run, progress=progress
        )
    except CatalogRepositoryError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if not args.json:
        print("", file=sys.stderr)
        print(format_fill_summary(summary))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def format_fill_summary(summary: Mapping[str, Any]) -> str:
    """Counts only, like `coverage`: no titles, no addresses."""

    lines = [
        f"Imágenes desde TMDb: {summary['considered']} obras consultadas"
        + (" (simulación, no se escribió nada)." if summary.get("dry_run") else "."),
    ]
    for status, count in sorted(summary["by_status"].items(), key=lambda row: -row[1]):
        lines.append(f"  {FILL_STATUS_LABELS.get(status, status)}: {count}")
    if summary["crosswalk"]:
        crosswalk = " · ".join(
            f"{CROSSWALK_LABELS.get(name, name)} {count}"
            for name, count in sorted(summary["crosswalk"].items(), key=lambda row: -row[1])
        )
        lines.append(f"  Cruce de ids: {crosswalk}")
    if summary.get("dry_run"):
        lines.append(
            f"  Se escribirían {summary['would_fill']} imágenes y "
            f"{summary['would_add_identity']} ids de TMDb."
        )
    else:
        lines.append(
            f"  Escritas: {summary.get('filled_fields', 0)} campos, "
            f"{summary.get('identities_added', 0)} ids de TMDb nuevos."
        )
    return "\n".join(lines)


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
