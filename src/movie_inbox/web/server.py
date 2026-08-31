"""CLI and lifecycle for the local catalog web server."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import webbrowser
from pathlib import Path

import uvicorn

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.identity_repository import IdentityCatalogMismatch
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.web.app import create_app
from movie_inbox.web.catalog_api import first_catalog_file, resolved_files
from movie_inbox.web.config import (
    DEFAULT_IMAGE_ALLOWED_HOSTS,
    DEFAULT_IMAGE_CACHE_WARM_INTERVAL_SECONDS,
    DEFAULT_SESSION_TTL_SECONDS,
    ExternalSourceCredentials,
    ViewerConfig,
)
from movie_inbox.web.security import InvalidPublicOrigin, normalize_public_origin


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="View JSON or SQLite movie catalogs in a local browser UI."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="JSON/SQLite catalogs or glob patterns, for example catalog.json or movie-inbox.db.",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address. Keep 127.0.0.1 when using Nginx."
    )
    parser.add_argument("--port", type=int, default=8765, help="Application server port.")
    parser.add_argument(
        "--public-origin",
        default="",
        help="External origin, for example https://movies.example.com.",
    )
    parser.add_argument(
        "--forwarded-allow-ips",
        default="127.0.0.1",
        help="Comma-separated proxy IPs trusted by Uvicorn for forwarded headers.",
    )
    parser.add_argument("--title", default="Movie Inbox", help="Viewer title.")
    parser.add_argument(
        "--instance-db",
        type=Path,
        help=(
            "Private account/session database. Defaults to .movie-inbox/instance.db "
            "next to the writable catalog."
        ),
    )
    parser.add_argument(
        "--member-catalog-dir",
        type=Path,
        help=(
            "Directory for automatically provisioned member catalogs. "
            "Defaults next to the instance database."
        ),
    )
    parser.add_argument(
        "--owner-username", default="owner", help="Username created on the first server start."
    )
    parser.add_argument(
        "--owner-password-file",
        type=Path,
        help="Read the first owner password from a file instead of prompting.",
    )
    parser.add_argument(
        "--tmdb-read-access-token-file",
        type=Path,
        default=(
            Path(os.environ["MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE"])
            if os.environ.get("MOVIE_INBOX_TMDB_READ_ACCESS_TOKEN_FILE")
            else None
        ),
        help=(
            "Read a TMDb API Read Access Token from a server-side file. "
            "Omit it to keep TMDb disabled."
        ),
    )
    parser.add_argument(
        "--session-days",
        type=int,
        default=DEFAULT_SESSION_TTL_SECONDS // (24 * 60 * 60),
        help="Absolute login session lifetime in days.",
    )
    parser.add_argument(
        "--write-catalog",
        "--write-json",
        dest="write_catalog",
        help="Catalog file to update when adding items. Defaults to the first viewed catalog.",
    )
    parser.add_argument(
        "--no-image-cache",
        action="store_true",
        help="Use remote image URLs directly instead of local image cache.",
    )
    parser.add_argument(
        "--image-cache-dir",
        type=Path,
        help=(
            "Directory for cached images. Defaults to .catalog-cache/images "
            "next to the writable catalog."
        ),
    )
    parser.add_argument(
        "--image-cache-max-mb", type=float, default=5.0, help="Maximum size per cached image."
    )
    parser.add_argument(
        "--image-cache-total-mb",
        type=float,
        default=512.0,
        help="Maximum total image cache size. Least-recently-used files are removed first.",
    )
    parser.add_argument(
        "--image-cache-warm-mode",
        choices=("after-access", "off"),
        default="after-access",
        help=(
            "Warm images gradually after an authenticated catalog is opened, "
            "or disable background warming."
        ),
    )
    parser.add_argument(
        "--image-cache-warm-interval-seconds",
        type=float,
        default=DEFAULT_IMAGE_CACHE_WARM_INTERVAL_SECONDS,
        help="Delay between background image downloads.",
    )
    parser.add_argument(
        "--image-host",
        action="append",
        default=[],
        help="Additional exact image hostname allowed by the proxy. Can be repeated.",
    )
    parser.add_argument(
        "--library-root",
        action="append",
        default=[],
        type=Path,
        help=(
            "Absolute server directory under which the managed scanner may read. "
            "Can be repeated; no managed paths are accepted when omitted."
        ),
    )
    parser.add_argument(
        "--no-open", action="store_true", help="Do not open the browser automatically."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    relative_library_roots = [path for path in args.library_root if not path.is_absolute()]
    if relative_library_roots:
        parser.error("--library-root must be an absolute path")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.image_cache_max_mb <= 0:
        parser.error("--image-cache-max-mb must be greater than zero")
    if args.image_cache_total_mb < args.image_cache_max_mb:
        parser.error("--image-cache-total-mb must be at least --image-cache-max-mb")
    if not 0.25 <= args.image_cache_warm_interval_seconds <= 3600:
        parser.error("--image-cache-warm-interval-seconds must be between 0.25 and 3600")
    if not 1 <= args.session_days <= 365:
        parser.error("--session-days must be between 1 and 365")
    try:
        external_credentials = ExternalSourceCredentials(
            tmdb_read_access_token=external_api_token(
                args.tmdb_read_access_token_file,
                source_label="TMDb",
            )
        )
    except ValueError as error:
        parser.error(str(error))
    try:
        public_origin = normalize_public_origin(args.public_origin)
    except InvalidPublicOrigin as error:
        parser.error(str(error))
    if args.host.casefold() not in {"127.0.0.1", "localhost", "::1"} and not public_origin:
        parser.error("--public-origin is required when binding to a non-loopback host")
    write_catalog = args.write_catalog or first_catalog_file(args.inputs)
    ensure_catalog_exists(Path(write_catalog))
    instance_db = args.instance_db or (
        Path(write_catalog).resolve().parent / ".movie-inbox" / "instance.db"
    )
    member_catalog_dir = args.member_catalog_dir or (instance_db.resolve().parent / "catalogs")
    image_cache_dir = args.image_cache_dir or (
        Path(write_catalog).resolve().parent / ".catalog-cache" / "images"
    )
    config = ViewerConfig(
        patterns=args.inputs,
        title=args.title,
        write_json=write_catalog,
        image_cache=not args.no_image_cache,
        image_cache_dir=str(image_cache_dir),
        image_cache_max_bytes=max(1, int(args.image_cache_max_mb * 1024 * 1024)),
        port=args.port,
        api_token=secrets.token_urlsafe(32),
        instance_db=str(instance_db),
        member_catalog_dir=str(member_catalog_dir),
        session_ttl_seconds=args.session_days * 24 * 60 * 60,
        host=args.host,
        public_origin=public_origin,
        forwarded_allow_ips=args.forwarded_allow_ips,
        image_cache_total_bytes=max(1, int(args.image_cache_total_mb * 1024 * 1024)),
        image_cache_warm=args.image_cache_warm_mode == "after-access",
        image_cache_warm_interval_seconds=args.image_cache_warm_interval_seconds,
        image_allowed_hosts=tuple(dict.fromkeys([*DEFAULT_IMAGE_ALLOWED_HOSTS, *args.image_host])),
        library_allowed_roots=tuple(str(path.resolve()) for path in args.library_root),
        external_credentials=external_credentials,
    )
    identity_repository = SqliteIdentityRepository(instance_db)
    identity_repository.initialize()
    auth_service = AuthService(identity_repository, session_ttl_seconds=config.session_ttl_seconds)
    sources = resolved_files(args.inputs)
    if not identity_repository.has_users():
        print("Creating the initial Movie Inbox owner account.")
        try:
            password = owner_password(args.owner_password_file)
            owner, personal_catalog = auth_service.bootstrap_owner(
                args.owner_username,
                password,
                catalog_name="Mi catalogo",
                source_paths=sources,
                write_path=write_catalog,
            )
        except ValueError as error:
            parser.error(str(error))
        print(f"Owner created: {owner.username}")
        print(f"Personal catalog adopted: {personal_catalog.write_path}")
    else:
        try:
            personal_catalog = auth_service.validate_owner_catalog(sources, write_catalog)
        except IdentityCatalogMismatch as error:
            parser.error(str(error))
    url = public_origin or f"http://127.0.0.1:{args.port}"
    print(f"Viewing {', '.join(args.inputs)}")
    print(f"Writing changes to {write_catalog}")
    print(f"Identity store: {instance_db}")
    print(f"Member catalogs: {member_catalog_dir}")
    print(f"Personal catalog: {personal_catalog.name}")
    print(
        f"Image cache: {config.image_cache_dir} (max {args.image_cache_total_mb:g} MB)"
        if config.image_cache
        else "Image cache: disabled"
    )
    if config.image_cache:
        print(
            f"Image cache warming: after access, every "
            f"{config.image_cache_warm_interval_seconds:g}s"
            if config.image_cache_warm
            else "Image cache warming: disabled"
        )
    print(
        f"Managed scanner roots: {', '.join(config.library_allowed_roots)}"
        if config.library_allowed_roots
        else "Managed scanner: disabled (no --library-root)"
    )
    print(
        "TMDb credentials: configured (adapter pending F5)"
        if config.external_credentials.tmdb_configured
        else "TMDb credentials: not configured"
    )
    print(f"Open {url}")
    print("Press Ctrl+C to stop.")

    if not args.no_open:
        webbrowser.open(url)
    uvicorn.run(
        create_app(config),
        host=args.host,
        port=args.port,
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
        workers=1,
        access_log=False,
    )
    return 0


def ensure_catalog_exists(path: Path) -> None:
    if not path.exists():
        open_catalog_repository(path, normalize_item).write([])


def owner_password(password_file: Path | None) -> str:
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


def external_api_token(token_file: Path | None, *, source_label: str) -> str:
    """Read one opaque API token without ever accepting it as a CLI value."""

    if token_file is None:
        return ""
    try:
        if token_file.stat().st_size > 16 * 1024:
            raise ValueError(f"{source_label} token file is too large")
        token = token_file.read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as error:
        raise ValueError(f"Cannot read {source_label} token file: {token_file}") from error
    if not token:
        raise ValueError(f"{source_label} token file is empty")
    if any(character.isspace() for character in token):
        raise ValueError(f"{source_label} token file must contain one token without whitespace")
    return token


if __name__ == "__main__":
    raise SystemExit(main())
