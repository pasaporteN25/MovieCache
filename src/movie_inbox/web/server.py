"""CLI and lifecycle for the local catalog web server."""

from __future__ import annotations

import argparse
import secrets
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from movie_inbox.web.catalog_api import first_catalog_file
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.handlers import make_handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="View JSON or SQLite movie catalogs in a local browser UI.")
    parser.add_argument("inputs", nargs="+", help="JSON/SQLite catalogs or glob patterns, for example catalog.json or movie-inbox.db.")
    parser.add_argument("--port", type=int, default=8765, help="Local server port.")
    parser.add_argument("--title", default="Movie Inbox", help="Viewer title.")
    parser.add_argument(
        "--write-json",
        dest="write_catalog",
        help="Catalog file to update when adding items. Defaults to the first viewed catalog.",
    )
    parser.add_argument("--no-image-cache", action="store_true", help="Use remote image URLs directly instead of local image cache.")
    parser.add_argument("--image-cache-dir", type=Path, help="Directory for cached images. Defaults to .catalog-cache/images next to the writable catalog.")
    parser.add_argument("--image-cache-max-mb", type=float, default=5.0, help="Maximum size per cached image.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    write_catalog = args.write_catalog or first_catalog_file(args.inputs)
    image_cache_dir = args.image_cache_dir or (Path(write_catalog).resolve().parent / ".catalog-cache" / "images")
    config = ViewerConfig(
        patterns=args.inputs,
        title=args.title,
        write_json=write_catalog,
        image_cache=not args.no_image_cache,
        image_cache_dir=str(image_cache_dir),
        image_cache_max_bytes=max(1, int(args.image_cache_max_mb * 1024 * 1024)),
        port=args.port,
        api_token=secrets.token_urlsafe(32),
    )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(config))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Viewing {', '.join(args.inputs)}")
    print(f"Writing changes to {write_catalog}")
    print(f"Image cache: {config.image_cache_dir}" if config.image_cache else "Image cache: disabled")
    print(f"Open {url}")
    print("Press Ctrl+C to stop.")

    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
