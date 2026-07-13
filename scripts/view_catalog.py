#!/usr/bin/env python3
"""
Run a local catalog viewer for one or more Chrome extension JSON exports.

Examples:
    python scripts/view_catalog.py catalog.json
    python scripts/view_catalog.py exports/*.json --port 8765

The server rereads the JSON files on each refresh, so new exports can be viewed
without rebuilding a static page.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import html
import json
import re
import time
import unicodedata
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import catalog_domain as domain
from catalog_sources import EXTERNAL_SOURCES
from catalog_domain import (
    annotate_duplicate_items,
    canonical_url,
    external_urls,
    has_external_link,
    merge_lists,
    normalize_bool,
    normalize_date,
    normalize_item,
    normalize_kind,
    normalize_rating,
    normalize_tags,
    source_url_field,
    stable_id,
    title_match_key,
    title_match_keys_for_item,
)
from catalog_repository import CatalogRepositoryError, JsonCatalogRepository
from catalog_service import CatalogService
from catalog_schema import (
    METADATA_FIELDS,
    SCHEMA_VERSION,
    normalize_local_files,
)
from txt_to_catalog import fetch_metadata


_CATALOG_SERVICES: dict[str, CatalogService] = {}


@dataclass
class ViewerConfig:
    patterns: list[str]
    title: str
    write_json: str
    image_cache: bool
    image_cache_dir: str
    image_cache_max_bytes: int


def main() -> int:
    parser = argparse.ArgumentParser(description="View movie catalog JSON exports in a local browser UI.")
    parser.add_argument("inputs", nargs="+", help="JSON files or glob patterns, for example catalog.json or exports/*.json.")
    parser.add_argument("--port", type=int, default=8765, help="Local server port.")
    parser.add_argument("--title", default="Movie Inbox", help="Viewer title.")
    parser.add_argument("--write-json", help="JSON file to update when adding items. Defaults to the first viewed JSON.")
    parser.add_argument("--no-image-cache", action="store_true", help="Use remote image URLs directly instead of local image cache.")
    parser.add_argument("--image-cache-dir", type=Path, help="Directory for cached images. Defaults to .catalog-cache/images next to the writable JSON.")
    parser.add_argument("--image-cache-max-mb", type=float, default=5.0, help="Maximum size per cached image.")
    parser.add_argument("--no-open", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()

    write_json = args.write_json or first_json_file(args.inputs)
    image_cache_dir = args.image_cache_dir or (Path(write_json).resolve().parent / ".catalog-cache" / "images")
    config = ViewerConfig(
        patterns=args.inputs,
        title=args.title,
        write_json=write_json,
        image_cache=not args.no_image_cache,
        image_cache_dir=str(image_cache_dir),
        image_cache_max_bytes=max(1, int(args.image_cache_max_mb * 1024 * 1024)),
    )
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(config))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Viewing {', '.join(args.inputs)}")
    print(f"Writing additions to {write_json}")
    if config.image_cache:
        print(f"Image cache: {config.image_cache_dir}")
    else:
        print("Image cache: disabled")
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


def make_handler(config: ViewerConfig) -> type[BaseHTTPRequestHandler]:
    class CatalogHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self.respond_html(render_html(config.title))
                return
            if path == "/api/items":
                items = load_items(config.patterns)
                with_link = sum(1 for item in items if has_external_link(item))
                duplicate_items = sum(1 for item in items if int(item.get("_duplicate_count") or 0) > 0)
                print(
                    f"[catalog-viewer] items loaded total={len(items)} with_link={with_link} "
                    f"without_link={len(items) - with_link} duplicate_items={duplicate_items}",
                    flush=True,
                )
                payload = {
                    "items": items,
                    "sources": resolved_files(config.patterns),
                    "write_json": config.write_json,
                    "schema_version": SCHEMA_VERSION,
                    "duplicate_items": duplicate_items,
                    "external": EXTERNAL_SOURCES.snapshot(),
                }
                self.respond_json(payload)
                return
            if path == "/api/search":
                params = parse_qs(urlparse(self.path).query)
                query = params.get("q", [""])[0]
                source = params.get("source", ["all"])[0]
                results = search_sources(query, source)
                print(
                    f"[catalog-viewer] search query={query!r} source={source} "
                    f"count={len(results)} result_sources={sorted(set(str(result.get('source') or '') for result in results))}",
                    flush=True,
                )
                payload = {"results": results, "external": EXTERNAL_SOURCES.snapshot()}
                self.respond_json(payload)
                return
            if path == "/api/source-health":
                payload = {"external": EXTERNAL_SOURCES.snapshot()}
                self.respond_json(payload)
                return
            if path == "/image-cache":
                params = parse_qs(urlparse(self.path).query)
                self.respond_cached_image(params.get("url", [""])[0])
                return
            self.send_error(404, "Not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/add":
                try:
                    body = self.read_json_body()
                    result = body.get("result") if isinstance(body.get("result"), dict) else body
                    result = enrich_selected_result(result)
                    item = item_from_search_result(result)
                    added, reason, extra = append_item(
                        write_path_for(config, str(body.get("target_source_file") or "")),
                        item,
                        action=str(body.get("action") or "check"),
                        target_id=str(body.get("target_id") or ""),
                        expected_source=str(body.get("expected_source") or ""),
                    )
                    self.respond_json({"ok": added, "reason": reason, "item": item, **extra})
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)})
                return
            if path == "/api/delete":
                try:
                    body = self.read_json_body()
                    deleted, reason = delete_item_anywhere(
                        config,
                        source_file=str(body.get("source_file") or ""),
                        item_id=str(body.get("id") or ""),
                        item_url=str(body.get("url") or ""),
                        title=str(body.get("title") or ""),
                        year=str(body.get("year") or ""),
                        local_name=str(body.get("local_name") or ""),
                        confirmed=bool(body.get("confirmed")),
                    )
                    self.respond_json({"ok": deleted, "reason": reason})
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)})
                return
            if path == "/api/status":
                try:
                    body = self.read_json_body()
                    updated, reason = update_item_status(
                        write_path_for(config, str(body.get("source_file") or "")),
                        item_id=str(body.get("id") or ""),
                        status=str(body.get("status") or ""),
                        watched_at=str(body.get("watched_at") or ""),
                    )
                    self.respond_json({"ok": updated, "reason": reason})
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)})
                return
            if path == "/api/kind":
                try:
                    body = self.read_json_body()
                    updated, reason = update_item_kind(
                        write_path_for(config, str(body.get("source_file") or "")),
                        item_id=str(body.get("id") or ""),
                        kind=str(body.get("kind") or ""),
                    )
                    self.respond_json({"ok": updated, "reason": reason})
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)})
                return
            if path == "/api/catalog":
                try:
                    body = self.read_json_body()
                    updated, reason = update_item_catalog_status(
                        write_path_for(config, str(body.get("source_file") or "")),
                        item_id=str(body.get("id") or ""),
                        en_catalogo=body.get("en_catalogo"),
                    )
                    self.respond_json({"ok": updated, "reason": reason})
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)})
                return
            if path == "/api/personal":
                try:
                    body = self.read_json_body()
                    updated, reason = update_item_personal(
                        write_path_for(config, str(body.get("source_file") or "")),
                        item_id=str(body.get("id") or ""),
                        watched_at=str(body.get("watched_at") or ""),
                        rating=body.get("rating"),
                        review=str(body.get("review") or ""),
                    )
                    self.respond_json({"ok": updated, "reason": reason})
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)})
                return
            if path == "/api/metadata":
                try:
                    body = self.read_json_body()
                    updated, reason = update_item_metadata(
                        write_path_for(config, str(body.get("source_file") or "")),
                        item_id=str(body.get("id") or ""),
                        values=body.get("values") if isinstance(body.get("values"), dict) else {},
                        locked_fields=body.get("locked_fields"),
                    )
                    self.respond_json({"ok": updated, "reason": reason})
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)})
                return
            self.send_error(404, "Not found")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw or "{}")
            if not isinstance(data, dict):
                raise ValueError("Invalid JSON body")
            return data

        def respond_html(self, body: str) -> None:
            self.respond(body.encode("utf-8"), "text/html; charset=utf-8")

        def respond_json(self, payload: dict[str, Any]) -> None:
            self.respond(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def respond(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def respond_cached_image(self, image_url: str) -> None:
            if not image_url:
                self.send_error(400, "Missing image URL")
                return
            parsed = urlparse(image_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                self.send_error(400, "Invalid image URL")
                return
            if not config.image_cache:
                self.redirect(image_url)
                return
            try:
                body, content_type = cached_image(config, image_url)
            except ValueError:
                self.redirect(image_url)
                return
            except (HTTPError, URLError, TimeoutError, OSError):
                self.redirect(image_url)
                return

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.end_headers()
            self.wfile.write(body)

        def redirect(self, location: str) -> None:
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return CatalogHandler


def first_json_file(patterns: list[str]) -> str:
    files = resolved_files(patterns)
    if not files:
        raise SystemExit("No JSON file found to write additions.")
    return files[0]


def write_path_for(config: ViewerConfig, source_file: str) -> Path:
    if source_file:
        try:
            source_path = Path(source_file).resolve()
            for file in resolved_files(config.patterns):
                if Path(file).resolve() == source_path:
                    return Path(file)
        except OSError:
            pass
    return Path(config.write_json)


def resolved_files(patterns: list[str]) -> list[str]:
    files: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            files.extend(matches)
        else:
            files.append(pattern)
    return sorted(str(Path(file)) for file in files if Path(file).suffix.lower() == ".json")


def load_items(patterns: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for file in resolved_files(patterns):
        try:
            rows = read_json_items(Path(file))
        except CatalogRepositoryError as error:
            print(f"[catalog-viewer] catalog read error file={file} error={error}", flush=True)
            continue
        for item in rows:
            item["_source_file"] = str(file)
            items.append(item)
    annotate_duplicate_items(items)
    return sorted(items, key=lambda item: str(item.get("added_at") or item.get("addedAt") or ""), reverse=True)


def read_json_items(path: Path) -> list[dict[str, Any]]:
    return catalog_service(path).list_items()


def write_json_items(path: Path, items: list[dict[str, Any]]) -> None:
    catalog_service(path).repository.write(items)


def catalog_service(path: Path) -> CatalogService:
    try:
        key = str(path.resolve())
    except OSError:
        key = str(path.absolute())
    if key not in _CATALOG_SERVICES:
        _CATALOG_SERVICES[key] = CatalogService(JsonCatalogRepository(Path(key), domain.normalize_item))
    return _CATALOG_SERVICES[key]


# Keep the HTTP layer on the shared domain and service implementations while the
# remaining page/search code is moved out of this legacy module incrementally.
annotate_duplicate_items = domain.annotate_duplicate_items
canonical_url = domain.canonical_url
external_urls = domain.external_urls
has_external_link = domain.has_external_link
merge_lists = domain.merge_lists
metadata_source_record = domain.metadata_source_record
normalize_bool = domain.normalize_bool
normalize_date = domain.normalize_date
normalize_item = domain.normalize_item
normalize_kind = domain.normalize_kind
normalize_rating = domain.normalize_rating
normalize_tags = domain.normalize_tags
source_url_field = domain.source_url_field
stable_id = domain.stable_id
title_match_key = domain.title_match_key
title_match_keys_for_item = domain.title_match_keys_for_item


def append_item(
    path: Path,
    item: dict[str, Any],
    action: str = "check",
    target_id: str = "",
    expected_source: str = "",
) -> tuple[bool, str, dict[str, Any]]:
    added, reason, extra = catalog_service(path).append_item(item, action, target_id)
    if added and reason == "merged":
        print(
            f"[catalog-viewer] merge ok path={path} target_id={target_id} "
            f"incoming_source={item.get('source', '')} incoming_url={item.get('url', '')}",
            flush=True,
        )
    return added, reason, extra


def delete_item_anywhere(
    config: ViewerConfig,
    source_file: str,
    item_id: str,
    item_url: str,
    title: str,
    year: str,
    local_name: str,
    confirmed: bool,
) -> tuple[bool, str]:
    paths = [write_path_for(config, source_file)]
    for file in resolved_files(config.patterns):
        path = Path(file)
        if all(path.resolve() != existing.resolve() for existing in paths):
            paths.append(path)
    last_reason = "not_found"
    for path in paths:
        deleted, reason = delete_item(path, item_id, item_url, title, year, local_name, confirmed)
        if deleted:
            return True, reason
        last_reason = reason
    return False, last_reason


def delete_item(
    path: Path,
    item_id: str,
    item_url: str,
    title: str,
    year: str,
    local_name: str,
    confirmed: bool,
) -> tuple[bool, str]:
    return catalog_service(path).delete_item(item_id, item_url, title, year, local_name, confirmed)


def update_item_status(path: Path, item_id: str, status: str, watched_at: str = "") -> tuple[bool, str]:
    return catalog_service(path).update_status(item_id, status, watched_at)


def update_item_kind(path: Path, item_id: str, kind: str) -> tuple[bool, str]:
    return catalog_service(path).update_kind(item_id, kind)


def update_item_catalog_status(path: Path, item_id: str, en_catalogo: Any) -> tuple[bool, str]:
    return catalog_service(path).update_catalog_status(item_id, en_catalogo)


def update_item_personal(path: Path, item_id: str, watched_at: str, rating: Any, review: str) -> tuple[bool, str]:
    return catalog_service(path).update_personal(item_id, watched_at, rating, review)


def update_item_metadata(
    path: Path,
    item_id: str,
    values: dict[str, Any],
    locked_fields: Any,
) -> tuple[bool, str]:
    return catalog_service(path).update_metadata(item_id, values, locked_fields)


def search_sources(query: str, source: str = "all") -> list[dict[str, Any]]:
    started = time.monotonic()
    results, external_state = EXTERNAL_SOURCES.search(query, source)
    cache_hit = external_state.get("cache", {}).get("last_request_hit")
    print(
        f"[catalog-viewer] external search completed query={query!r} source={source} "
        f"seconds={time.monotonic() - started:.2f} count={len(results)} cache_hit={cache_hit}",
        flush=True,
    )
    return results


def enrich_selected_result(result: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(result)
    source = str(enriched.get("source") or source_from_url(str(enriched.get("url") or "")))
    if source not in {"wikipedia", "imdb", "filmaffinity"}:
        return enriched
    result_url = str(enriched.get("url") or "")
    cache_key = canonical_url(result_url) or result_url
    metadata, _ = EXTERNAL_SOURCES.selected_metadata(cache_key, lambda _: fetch_metadata(result_url))
    if not metadata:
        return enriched
    for field in (
        "title",
        "original_title",
        "spanish_title",
        "english_title",
        "year",
        "description",
        "wikipedia_title",
        "wikidata_id",
        "page_image",
        "wikipedia_extract",
    ):
        if metadata.get(field):
            enriched[field] = metadata[field]
    for field in ("alternative_titles", "genres", "directors", "writers", "cast"):
        values = normalize_tags(metadata.get(field))
        if values:
            enriched[field] = merge_lists(normalize_tags(enriched.get(field)), values)
    for field in ("wikipedia_url", "imdb_url", "filmaffinity_url"):
        if metadata.get(field):
            enriched[field] = metadata[field]
    metadata_url = str(metadata.get("url") or "")
    if source == "wikipedia" and metadata_url:
        enriched["url"] = metadata_url
        enriched["wikipedia_url"] = metadata_url
    elif source == "imdb":
        enriched["imdb_url"] = result_url
    elif source == "filmaffinity":
        enriched["filmaffinity_url"] = result_url
    return enriched


def item_from_search_result(result: dict[str, Any]) -> dict[str, Any]:
    url = str(result.get("url") or "").strip()
    title = str(result.get("title") or "").strip()
    if not url or not title:
        raise ValueError("Result must include title and url")
    source = str(result.get("source") or source_from_url(url))
    link_field = source_url_field(source, url)
    source_links = {
        "wikipedia_url": str(result.get("wikipedia_url") or ""),
        "imdb_url": str(result.get("imdb_url") or ""),
        "filmaffinity_url": str(result.get("filmaffinity_url") or ""),
    }
    if link_field:
        source_links[link_field] = source_links.get(link_field) or url
    item = {
        "id": stable_id(url),
        "url": url,
        "source": source,
        "title": title,
        "original_title": str(result.get("original_title") or ""),
        "spanish_title": str(result.get("spanish_title") or ""),
        "english_title": str(result.get("english_title") or ""),
        "alternative_titles": normalize_tags(result.get("alternative_titles")),
        "kind": normalize_kind(result.get("kind")),
        "status": str(result.get("status") or "to_watch"),
        "watched_at": normalize_date(result.get("watched_at")),
        "rating": normalize_rating(result.get("rating")),
        "year": str(result.get("year") or ""),
        "description": str(result.get("description") or ""),
        **source_links,
        "wikipedia_title": str(result.get("wikipedia_title") or (title if source == "wikipedia" else "")),
        "wikidata_id": str(result.get("wikidata_id") or ""),
        "genres": normalize_tags(result.get("genres")),
        "directors": normalize_tags(result.get("directors")),
        "writers": normalize_tags(result.get("writers")),
        "cast": normalize_tags(result.get("cast")),
        "page_image": str(result.get("page_image") or ""),
        "wikipedia_extract": str(result.get("wikipedia_extract") or ""),
        "en_catalogo": False,
        "local_files": [],
        "local_name": "",
        "local_path": "",
        "tags": [],
        "notes": "",
        "review": "",
        "metadata_sources": {},
        "locked_fields": [],
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    item["metadata_sources"] = {
        field: metadata_source_record(source, url, inferred=False)
        for field in METADATA_FIELDS
        if item.get(field) not in (None, "", [], {})
    }
    return item


IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}

IMAGE_CONTENT_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def cached_image(config: ViewerConfig, image_url: str) -> tuple[bytes, str]:
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid image URL")

    cache_dir = Path(config.image_cache_dir)
    key = hashlib.sha1(image_url.encode("utf-8")).hexdigest()
    cached = next((path for path in cache_dir.glob(f"{key}.*") if path.is_file()), None) if cache_dir.exists() else None
    if cached:
        return cached.read_bytes(), image_content_type(cached.suffix)

    body, content_type = download_image(image_url, config.image_cache_max_bytes)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{key}{image_extension(parsed.path, content_type)}"
    cache_path.write_bytes(body)
    return body, content_type


def download_image(image_url: str, max_bytes: int) -> tuple[bytes, str]:
    request = Request(
        image_url,
        headers={
            "User-Agent": "MovieInboxViewer/0.1 (+local personal catalog)",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=10) as response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise ValueError("URL did not return an image")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("Image is too large")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("Image is too large")
        return body, content_type


def image_extension(path: str, content_type: str) -> str:
    suffix = Path(urlparse(path).path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return ".jpg" if suffix == ".jpeg" else suffix
    return IMAGE_CONTENT_EXTENSIONS.get(content_type, ".img")


def image_content_type(suffix: str) -> str:
    return IMAGE_EXTENSIONS.get(suffix.lower(), "application/octet-stream")


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def source_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "wikipedia.org" in host:
        return "wikipedia"
    if "imdb.com" in host:
        return "imdb"
    if "filmaffinity.com" in host:
        return "filmaffinity"
    return host.removeprefix("www.")


def render_html(title: str) -> str:
    escaped_title = html_escape(title)
    return rf"""<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escaped_title}</title>
    <style>
      :root {{
        color-scheme: light;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #20242a;
        background: #f5f2ec;
      }}
      *, *::before, *::after {{ box-sizing: border-box; }}
      body {{ margin: 0; }}
      main {{ margin: 0 auto; max-width: 1280px; padding: 22px; }}
      header {{
        align-items: start;
        display: grid;
        gap: 16px;
        margin-bottom: 16px;
      }}
      h1 {{ font-size: 28px; line-height: 1.1; margin: 0; }}
      .stats {{ color: #626b76; font-size: 13px; margin-top: 6px; }}
      .search-console {{
        background: #fffdf8;
        border: 1px solid #d4cec3;
        border-radius: 8px;
        display: grid;
        gap: 10px;
        padding: 12px;
      }}
      .search-main {{
        display: grid;
        gap: 8px;
        grid-template-columns: minmax(220px, 1fr) 120px 120px 100px 100px;
      }}
      .source-toggle {{
        align-items: center;
        border: 1px solid #c8c1b6;
        border-radius: 6px;
        color: #30363c;
        display: flex;
        gap: 7px;
        justify-content: center;
        min-height: 38px;
        padding: 8px 10px;
      }}
      .source-toggle input {{
        min-height: auto;
        width: auto;
      }}
      .source-toggle.disabled {{
        background: #f1eee8;
        color: #59626d;
      }}
      .search-action {{
        background: #263238;
        border-color: #263238;
        color: #fffdf8;
      }}
      .filter-row {{
        display: grid;
        gap: 8px;
        grid-template-columns: 1fr;
      }}
      input, select, button {{
        background: #fffdf8;
        border: 1px solid #c8c1b6;
        border-radius: 6px;
        color: #20242a;
        font: inherit;
        min-height: 38px;
        padding: 8px 10px;
        width: 100%;
      }}
      .source-toggle input {{
        min-height: auto;
        padding: 0;
        width: auto;
      }}
      button {{ cursor: pointer; font-weight: 700; }}
      .kind-select {{
        font-size: 12px;
        min-height: 30px;
        padding: 4px 6px;
        width: auto;
      }}
      .layout {{
        display: grid;
        gap: 14px;
        grid-template-columns: 220px 1fr;
      }}
      .search-sections {{
        display: grid;
        gap: 10px;
      }}
      .search-section {{
        border-top: 1px solid #ebe5db;
        display: none;
        gap: 8px;
        padding-top: 10px;
      }}
      .search-section.active {{
        display: grid;
      }}
      .section-heading {{
        align-items: center;
        display: flex;
        gap: 8px;
        justify-content: space-between;
      }}
      .section-heading strong {{
        font-size: 13px;
      }}
      .search-results {{
        align-items: stretch;
        display: grid;
        gap: 10px;
        grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      }}
      .search-result {{
        align-self: stretch;
        background: #fffdf8;
        border: 1px solid #d4cec3;
        border-radius: 8px;
        display: grid;
        grid-template-rows: 112px minmax(0, 1fr);
        overflow: hidden;
      }}
      .search-result.compact-result {{
        height: 440px;
        max-height: 440px;
        min-height: 440px;
      }}
      .search-result.comparison-result {{
        grid-column: 1 / -1;
        grid-template-rows: 112px auto;
        height: auto;
      }}
      .search-result:hover {{
        border-color: #aaa195;
        box-shadow: 0 8px 18px rgba(32, 36, 42, 0.07);
      }}
      .search-result h3 {{
        display: -webkit-box;
        font-size: 14px;
        line-height: 1.25;
        margin: 0;
        min-height: 35px;
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
      }}
      .search-result p {{
        color: #59626d;
        font-size: 12px;
        line-height: 1.35;
        margin: 4px 0 0;
      }}
      .result-summary {{
        display: -webkit-box;
        min-height: 32px;
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
      }}
      .description-more {{
        background: transparent;
        border: 0;
        color: #315f5b;
        justify-self: start;
        min-height: auto;
        padding: 0;
        width: auto;
      }}
      .result-media {{
        background: #dfdbd2;
        height: 112px;
        object-fit: cover;
        width: 100%;
      }}
      .result-placeholder {{
        align-items: center;
        background: linear-gradient(135deg, #ece6dc, #d7d4cc);
        color: #6b6258;
        display: flex;
        font-size: 11px;
        font-weight: 700;
        height: 112px;
        justify-content: center;
        padding: 10px;
        text-align: center;
        text-transform: uppercase;
      }}
      .result-body {{
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-height: 0;
        padding: 10px;
      }}
      .result-actions {{
        border-top: 1px solid #ebe5db;
        display: grid;
        gap: 6px;
        grid-template-columns: 1fr 1fr;
        margin-top: auto;
        padding-top: 8px;
      }}
      .compact-result .result-body > .meta {{ max-height: 32px; overflow: hidden; }}
      .compact-result .card-badges {{ flex-wrap: nowrap; min-height: 23px; overflow: hidden; }}
      .result-actions a {{
        align-items: center;
        border: 1px solid #c8c1b6;
        border-radius: 6px;
        display: flex;
        justify-content: center;
        min-height: 38px;
        padding: 8px 10px;
        text-decoration: none;
      }}
      .result-actions .span-all {{
        grid-column: 1 / -1;
      }}
      .action-primary {{
        background: #263238;
        border-color: #263238;
        color: #fffdf8;
      }}
      .action-secondary {{
        background: #f7f3eb;
      }}
      .action-danger {{
        border-color: #b9564c;
        color: #8e2f28;
      }}
      .load-more {{
        grid-column: 1 / -1;
        justify-self: start;
        width: auto;
      }}
      .catalog-more {{
        margin-top: 14px;
        width: auto;
      }}
      dialog {{
        background: #fffdf8;
        border: 1px solid #bdb5a9;
        border-radius: 8px;
        color: #20242a;
        max-height: min(680px, calc(100vh - 48px));
        max-width: 680px;
        padding: 0;
        width: calc(100% - 32px);
      }}
      dialog::backdrop {{ background: rgba(24, 27, 30, 0.56); }}
      .description-dialog-body {{ display: grid; gap: 12px; padding: 18px; }}
      .description-dialog-body h2 {{ font-size: 18px; }}
      .description-dialog-body p {{ line-height: 1.55; margin: 0; white-space: pre-wrap; }}
      .description-dialog-actions {{ display: flex; justify-content: end; }}
      .description-dialog-actions button {{ width: auto; }}
      .status-line {{
        color: #626b76;
        font-size: 12px;
      }}
      .layout > aside {{
        align-self: start;
        border: 1px solid #d4cec3;
        border-radius: 8px;
        background: #fffdf8;
        display: grid;
        gap: 14px;
        padding: 12px;
        position: sticky;
        top: 12px;
      }}
      .side-section {{
        border-top: 1px solid #ebe5db;
        display: grid;
        gap: 8px;
        padding-top: 10px;
      }}
      .side-section:first-child {{
        border-top: 0;
        padding-top: 0;
      }}
      .side-section h3 {{
        color: #4d5660;
        font-size: 12px;
        letter-spacing: 0;
        margin: 0;
        text-transform: uppercase;
      }}
      .menu-tabs {{
        display: grid;
        gap: 6px;
        grid-template-columns: 1fr 1fr;
      }}
      .menu-tab.active {{
        background: #263238;
        border-color: #263238;
        color: #fffdf8;
      }}
      .db-panel {{
        display: grid;
        gap: 8px;
      }}
      .db-panel[hidden] {{
        display: none;
      }}
      .db-panel label {{
        color: #59626d;
        display: grid;
        gap: 4px;
        font-size: 12px;
        font-weight: 700;
      }}
      .db-panel input[readonly] {{
        color: #30363c;
        font-size: 12px;
      }}
      .db-list {{
        display: grid;
        gap: 6px;
      }}
      .db-item {{
        border: 1px solid #ebe5db;
        border-radius: 6px;
        display: grid;
        gap: 3px;
        padding: 7px 8px;
      }}
      .db-item strong {{
        font-size: 12px;
      }}
      .db-item span {{
        color: #626b76;
        font-size: 12px;
        overflow-wrap: anywhere;
      }}
      .metric {{ display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }}
      .metric strong {{ font-size: 16px; }}
      .danger {{
        border-color: #b9564c;
        color: #8e2f28;
      }}
      .duplicate-box {{
        background: #f6efe3;
        border: 1px solid #d6c4a8;
        border-radius: 8px;
        display: grid;
        gap: 8px;
        grid-column: 1 / -1;
        padding: 10px;
      }}
      .duplicate-actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .compare-box {{
        background: #f9f5ed;
        border: 1px solid #d8cab5;
        border-radius: 8px;
        display: grid;
        gap: 8px;
        grid-column: 1 / -1;
        padding: 10px;
      }}
      .diff-grid {{
        border: 1px solid #ded4c6;
        border-radius: 6px;
        display: grid;
        gap: 1px;
        overflow: hidden;
      }}
      .diff-row {{
        background: #fffdf8;
        display: grid;
        gap: 8px;
        grid-template-columns: 90px 1fr 1fr;
        padding: 6px 8px;
      }}
      .diff-row strong, .diff-row span {{
        font-size: 12px;
        overflow-wrap: anywhere;
      }}
      .diff-row span {{
        color: #59626d;
      }}
      .grid {{
        align-items: stretch;
        display: grid;
        gap: 12px;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      }}
      .card {{
        align-self: stretch;
        background: #fffdf8;
        border: 1px solid #d4cec3;
        border-radius: 8px;
        cursor: pointer;
        display: grid;
        grid-template-rows: 150px minmax(0, 1fr);
        height: 570px;
        max-height: 570px;
        min-height: 570px;
        overflow: hidden;
      }}
      .card:hover {{
        border-color: #aaa195;
        box-shadow: 0 8px 20px rgba(32, 36, 42, 0.08);
      }}
      .image {{
        background: #dfdbd2;
        height: 150px;
        object-fit: cover;
        width: 100%;
      }}
      .image-placeholder {{
        align-items: center;
        background: linear-gradient(135deg, #ece6dc, #d7d4cc);
        color: #6b6258;
        display: flex;
        font-size: 12px;
        font-weight: 700;
        height: 150px;
        justify-content: center;
        text-transform: uppercase;
      }}
      .body {{ display: flex; flex-direction: column; gap: 8px; min-height: 0; padding: 12px; }}
      .body, .result-body, .title {{ min-width: 0; }}
      .title {{ align-items: start; display: flex; gap: 8px; justify-content: space-between; }}
      h2 {{ font-size: 16px; line-height: 1.25; margin: 0; overflow-wrap: anywhere; }}
      .card h2 {{
        display: -webkit-box;
        min-height: 40px;
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
      }}
      .pill {{
        border: 1px solid #c8c1b6;
        border-radius: 999px;
        color: #4d5660;
        flex: 0 0 auto;
        font-size: 11px;
        padding: 3px 7px;
      }}
      .pill.good {{
        background: #eef4ef;
        border-color: #b9d2bf;
        color: #315f3b;
      }}
      .pill.muted {{
        background: #f1eee8;
      }}
      .pill.warning {{
        background: #fff1d7;
        border-color: #dfbd7b;
        color: #765116;
      }}
      .meta {{ color: #68717c; display: flex; flex-wrap: wrap; gap: 6px; font-size: 12px; }}
      .card-badges {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }}
      .card > .body > .meta {{ max-height: 32px; overflow: hidden; }}
      .card > .body > .card-badges {{ max-height: 48px; overflow: hidden; }}
      .summary {{
        color: #32383f;
        display: -webkit-box;
        font-size: 13px;
        line-height: 1.4;
        margin: 0;
        overflow: hidden;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 3;
      }}
      .card-facts {{
        border-top: 1px solid #ebe5db;
        display: grid;
        gap: 1px;
        grid-template-columns: 1fr 1fr;
        overflow: hidden;
        padding-top: 8px;
      }}
      .card .links {{ margin-top: auto; }}
      .card-fact {{
        background: #f7f3eb;
        border-radius: 6px;
        display: grid;
        gap: 2px;
        min-height: 44px;
        padding: 7px 8px;
      }}
      .card-fact strong {{
        color: #7a7168;
        font-size: 10px;
        text-transform: uppercase;
      }}
      .card-fact span {{
        color: #30363c;
        font-size: 12px;
        line-height: 1.35;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .facts {{
        display: grid;
        gap: 4px;
        grid-template-columns: 72px 1fr;
        margin: 0;
      }}
      .facts dt {{
        color: #6d7480;
        font-size: 12px;
        font-weight: 700;
      }}
      .facts dd {{
        color: #32383f;
        font-size: 12px;
        line-height: 1.35;
        margin: 0;
      }}
      .personal-panel {{
        border-top: 1px solid #ebe5db;
        padding-top: 8px;
      }}
      .personal-panel summary {{
        color: #4d5660;
        cursor: pointer;
        font-size: 12px;
        font-weight: 700;
      }}
      .personal-grid {{
        display: grid;
        gap: 8px;
        margin-top: 8px;
      }}
      .personal-grid label {{
        color: #59626d;
        display: grid;
        gap: 4px;
        font-size: 12px;
        font-weight: 700;
      }}
      .personal-grid select {{
        width: 88px;
      }}
      .personal-grid textarea {{
        min-height: 92px;
        resize: vertical;
      }}
      .personal-actions {{
        align-items: center;
        display: grid;
        gap: 8px;
        grid-template-columns: 110px 1fr;
      }}
      .metadata-editor {{ display: grid; gap: 10px; }}
      .metadata-row {{
        border: 1px solid #ebe5db;
        border-radius: 6px;
        display: grid;
        gap: 6px;
        padding: 8px;
      }}
      .metadata-row > label:first-child {{
        color: #4d5660;
        display: grid;
        font-size: 12px;
        font-weight: 700;
        gap: 4px;
      }}
      .metadata-row textarea {{ min-height: 90px; resize: vertical; }}
      .metadata-control {{ align-items: center; display: flex; gap: 8px; justify-content: space-between; }}
      .metadata-origin {{ color: #68717c; font-size: 11px; overflow-wrap: anywhere; }}
      .lock-control {{ align-items: center; display: flex; font-size: 12px; gap: 6px; }}
      .lock-control input {{ min-height: auto; width: auto; }}
      .metadata-actions {{ align-items: center; display: flex; gap: 8px; }}
      .metadata-actions button {{ width: auto; }}
      .links {{
        border-top: 1px solid #ebe5db;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding-top: 8px;
      }}
      .drawer-backdrop {{
        background: rgba(32, 36, 42, 0.36);
        display: none;
        inset: 0;
        position: fixed;
        z-index: 20;
      }}
      .drawer-backdrop.open {{ display: block; }}
      .detail-drawer {{
        background: #fffdf8;
        border-left: 1px solid #d4cec3;
        bottom: 0;
        box-shadow: -16px 0 32px rgba(32, 36, 42, 0.18);
        display: grid;
        grid-template-rows: auto 1fr;
        max-width: 620px;
        position: fixed;
        right: 0;
        top: 0;
        transform: translateX(100%);
        transition: transform 160ms ease;
        width: min(620px, 100%);
        z-index: 21;
      }}
      .detail-drawer.open {{ transform: translateX(0); }}
      .drawer-top {{
        align-items: center;
        border-bottom: 1px solid #ebe5db;
        display: flex;
        gap: 10px;
        justify-content: space-between;
        padding: 12px 14px;
      }}
      .drawer-top strong {{
        font-size: 14px;
      }}
      .drawer-close {{
        width: auto;
      }}
      .drawer-body {{
        display: grid;
        gap: 14px;
        overflow: auto;
        padding: 14px;
      }}
      .drawer-hero {{
        display: grid;
        gap: 12px;
        grid-template-columns: 136px 1fr;
      }}
      .drawer-poster {{
        background: #dfdbd2;
        border-radius: 8px;
        height: 204px;
        object-fit: cover;
        width: 136px;
      }}
      .drawer-control {{
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 8px 0;
      }}
      .drawer-control span {{
        color: #59626d;
        font-size: 12px;
        font-weight: 700;
      }}
      .drawer-control .kind-select {{
        width: 150px;
      }}
      .drawer-section {{
        border-top: 1px solid #ebe5db;
        display: grid;
        gap: 8px;
        padding-top: 12px;
      }}
      .drawer-section h3 {{
        font-size: 13px;
        margin: 0;
      }}
      a {{ color: #2e686c; font-size: 13px; font-weight: 700; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}
      .empty {{
        border: 1px dashed #bfb7aa;
        border-radius: 8px;
        color: #666d76;
        display: none;
        padding: 28px;
        text-align: center;
      }}
      @media (max-width: 860px) {{
        header, .layout {{ grid-template-columns: 1fr; }}
        .layout > aside {{ position: static; }}
      }}
      @media (max-width: 640px) {{
        main {{ padding: 16px; }}
        .search-main {{ grid-template-columns: 1fr 1fr; }}
        .search-main input {{ grid-column: 1 / -1; }}
        .filter-row {{ grid-template-columns: 1fr; }}
        .drawer-hero {{ grid-template-columns: 92px 1fr; }}
        .drawer-poster {{ height: 138px; width: 92px; }}
      }}
      @media (max-width: 440px) {{
        .search-main {{ grid-template-columns: 1fr; }}
        .search-main input {{ grid-column: auto; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header>
        <div>
          <h1>{escaped_title}</h1>
          <div class="stats" id="stats">Cargando...</div>
        </div>
        <section class="search-console">
          <div class="search-main">
            <input id="query" type="search" placeholder="Buscar catalogo, Wikipedia, IMDb o FilmAffinity...">
            <label class="source-toggle disabled"><input id="catalogSource" type="checkbox" checked disabled> Catalogo</label>
            <label class="source-toggle"><input id="externalSource" type="checkbox"> Externo</label>
            <button id="searchButton" class="search-action" type="button">Buscar</button>
            <button id="clearManualSearch" type="button">Limpiar</button>
          </div>
          <div class="search-sections">
            <section class="search-section" id="catalogMergeSection">
              <div class="section-heading">
                <strong>Catalogo local</strong>
                <div class="status-line" id="catalogMergeStatus"></div>
              </div>
              <div class="search-results" id="catalogMergeResults"></div>
            </section>
            <section class="search-section" id="externalSearchSection">
              <div class="section-heading">
                <strong>Fuentes externas</strong>
                <div class="status-line" id="manualSearchStatus"></div>
              </div>
              <div class="search-results" id="manualSearchResults"></div>
            </section>
          </div>
        </section>
      </header>
      <section class="layout">
        <aside>
          <section class="side-section">
            <h3>Resumen</h3>
            <div class="metric"><span>Total</span><strong id="total">0</strong></div>
            <div class="metric"><span>Visibles</span><strong id="visible">0</strong></div>
            <div class="metric"><span>Vistas</span><strong id="watchedCount">0</strong></div>
            <div class="metric"><span>Por ver</span><strong id="toWatchCount">0</strong></div>
            <div class="metric"><span>Puntuadas</span><strong id="ratedCount">0</strong></div>
            <div class="metric"><span>Con imagen</span><strong id="withImage">0</strong></div>
            <div class="metric"><span>Con link</span><strong id="wikiLinks">0</strong></div>
            <div class="metric"><span>Sin link</span><strong id="withoutWiki">0</strong></div>
            <div class="metric"><span>IMDb</span><strong id="imdbLinks">0</strong></div>
            <div class="metric"><span>FilmAffinity</span><strong id="faLinks">0</strong></div>
            <div class="metric"><span>Duplicadas</span><strong id="duplicateCount">0</strong></div>
            <div class="metric"><span>Fuentes JSON</span><strong id="sourceFiles">0</strong></div>
          </section>
          <section class="side-section">
            <h3>Filtros</h3>
            <div class="filter-row">
              <select id="status"></select>
              <select id="kind"></select>
              <select id="source"></select>
            </div>
          </section>
          <section class="side-section">
            <h3>Menu</h3>
            <div class="menu-tabs">
              <button id="databaseMenuCatalog" class="menu-tab active" type="button">Bases de datos</button>
              <button id="databaseMenuExternal" class="menu-tab" type="button">External DBs</button>
            </div>
            <div id="databaseCatalogPanel" class="db-panel"></div>
            <div id="databaseExternalPanel" class="db-panel" hidden></div>
          </section>
          <section class="side-section">
            <h3>Herramientas</h3>
            <button id="startWikiReview" type="button">Revisar sin link</button>
            <button id="previousWikiReview" type="button">Anterior</button>
            <button id="nextWikiReview" type="button">Siguiente</button>
            <div class="status-line" id="wikiReviewStatus"></div>
            <button id="randomizeView" type="button">Randomizar</button>
            <button id="resetOrder" type="button">Orden normal</button>
            <button id="showDuplicates" type="button">Ver duplicadas</button>
            <button id="refresh">Actualizar</button>
          </section>
        </aside>
        <div>
          <section class="grid" id="grid"></section>
          <button id="catalogLoadMore" class="catalog-more" type="button" hidden>Cargar mas</button>
          <p class="empty" id="empty">No hay resultados para esos filtros.</p>
        </div>
      </section>
    </main>
    <div id="detailBackdrop" class="drawer-backdrop"></div>
    <aside id="detailDrawer" class="detail-drawer" aria-hidden="true">
      <div class="drawer-top">
        <strong>Detalle</strong>
        <button id="closeDetail" class="drawer-close" type="button">Cerrar</button>
      </div>
      <div id="detailBody" class="drawer-body"></div>
    </aside>
    <dialog id="descriptionDialog">
      <div class="description-dialog-body">
        <h2 id="descriptionDialogTitle"></h2>
        <p id="descriptionDialogText"></p>
        <div class="description-dialog-actions">
          <button id="closeDescriptionDialog" type="button">Cerrar</button>
        </div>
      </div>
    </dialog>
    <script>
      let items = [];
      let sourceFiles = [];
      let manualResults = [];
      let selectedManualIndex = null;
      let selectedExistingIdForSearch = null;
      let manualSearchSource = "all";
      let catalogMergeResults = [];
      let wikiReviewQueue = [];
      let wikiReviewIndex = 0;
      let randomOrder = [];
      let openPersonalId = "";
      let selectedDetailId = "";
      let activeQuery = "";
      let writeJsonPath = "";
      let databasePanel = "catalog";
      let manualVisibleCount = 6;
      let catalogMergeVisibleCount = 6;
      let externalSourcesLastUsed = [];
      let externalSourcesAttempted = [];
      let externalSearchController = null;
      let duplicatesOnly = false;
      let catalogVisibleCount = 36;
      let externalHealth = {{ sources: {{}}, cache: {{}} }};
      const SEARCH_PAGE_SIZE = 6;
      const CATALOG_PAGE_SIZE = 36;
      const fields = {{
        query: document.querySelector("#query"),
        catalogSource: document.querySelector("#catalogSource"),
        externalSource: document.querySelector("#externalSource"),
        searchButton: document.querySelector("#searchButton"),
        status: document.querySelector("#status"),
        kind: document.querySelector("#kind"),
        source: document.querySelector("#source"),
        grid: document.querySelector("#grid"),
        stats: document.querySelector("#stats"),
        total: document.querySelector("#total"),
        visible: document.querySelector("#visible"),
        watchedCount: document.querySelector("#watchedCount"),
        toWatchCount: document.querySelector("#toWatchCount"),
        ratedCount: document.querySelector("#ratedCount"),
        withImage: document.querySelector("#withImage"),
        wikiLinks: document.querySelector("#wikiLinks"),
        withoutWiki: document.querySelector("#withoutWiki"),
        imdbLinks: document.querySelector("#imdbLinks"),
        faLinks: document.querySelector("#faLinks"),
        duplicateCount: document.querySelector("#duplicateCount"),
        sourceFiles: document.querySelector("#sourceFiles"),
        startWikiReview: document.querySelector("#startWikiReview"),
        previousWikiReview: document.querySelector("#previousWikiReview"),
        nextWikiReview: document.querySelector("#nextWikiReview"),
        wikiReviewStatus: document.querySelector("#wikiReviewStatus"),
        randomizeView: document.querySelector("#randomizeView"),
        resetOrder: document.querySelector("#resetOrder"),
        showDuplicates: document.querySelector("#showDuplicates"),
        clearManualSearch: document.querySelector("#clearManualSearch"),
        manualSearchStatus: document.querySelector("#manualSearchStatus"),
        manualSearchResults: document.querySelector("#manualSearchResults"),
        externalSearchSection: document.querySelector("#externalSearchSection"),
        catalogMergeSection: document.querySelector("#catalogMergeSection"),
        catalogMergeStatus: document.querySelector("#catalogMergeStatus"),
        catalogMergeResults: document.querySelector("#catalogMergeResults"),
        databaseMenuCatalog: document.querySelector("#databaseMenuCatalog"),
        databaseMenuExternal: document.querySelector("#databaseMenuExternal"),
        databaseCatalogPanel: document.querySelector("#databaseCatalogPanel"),
        databaseExternalPanel: document.querySelector("#databaseExternalPanel"),
        detailBackdrop: document.querySelector("#detailBackdrop"),
        detailDrawer: document.querySelector("#detailDrawer"),
        detailBody: document.querySelector("#detailBody"),
        closeDetail: document.querySelector("#closeDetail"),
        catalogLoadMore: document.querySelector("#catalogLoadMore"),
        descriptionDialog: document.querySelector("#descriptionDialog"),
        descriptionDialogTitle: document.querySelector("#descriptionDialogTitle"),
        descriptionDialogText: document.querySelector("#descriptionDialogText"),
        closeDescriptionDialog: document.querySelector("#closeDescriptionDialog"),
        empty: document.querySelector("#empty")
      }};

      document.querySelector("#refresh").addEventListener("click", load);
      fields.searchButton.addEventListener("click", runSearch);
      fields.externalSource.addEventListener("change", renderDatabaseMenu);
      fields.clearManualSearch.addEventListener("click", clearManualSearch);
      fields.startWikiReview.addEventListener("click", startWikiReview);
      fields.previousWikiReview.addEventListener("click", previousWikiReview);
      fields.nextWikiReview.addEventListener("click", nextWikiReview);
      fields.randomizeView.addEventListener("click", randomizeView);
      fields.resetOrder.addEventListener("click", resetViewOrder);
      fields.showDuplicates.addEventListener("click", toggleDuplicatesOnly);
      fields.databaseMenuCatalog.addEventListener("click", () => setDatabasePanel("catalog"));
      fields.databaseMenuExternal.addEventListener("click", () => setDatabasePanel("external"));
      fields.closeDetail.addEventListener("click", closeDetail);
      fields.detailBackdrop.addEventListener("click", closeDetail);
      fields.catalogLoadMore.addEventListener("click", showMoreCatalogItems);
      fields.closeDescriptionDialog.addEventListener("click", () => fields.descriptionDialog.close());
      fields.query.addEventListener("keydown", (event) => {{
        if (event.key === "Enter") runSearch();
        if (event.key === "Escape") clearManualSearch();
      }});
      document.addEventListener("keydown", (event) => {{
        if (event.key === "Escape" && selectedDetailId) closeDetail();
      }});
      [fields.status, fields.kind, fields.source].forEach((field) => field.addEventListener("input", () => {{
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }}));
      load();

      async function load() {{
        const response = await fetch("/api/items");
        const payload = await response.json();
        items = payload.items || [];
        sourceFiles = payload.sources || [];
        writeJsonPath = payload.write_json || "";
        externalHealth = payload.external || externalHealth;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        setupSelect(fields.status, "Estado", items.map((item) => item.status));
        setupSelect(fields.kind, "Tipo", items.map((item) => item.kind));
        setupSelect(fields.source, "Fuente", items.map((item) => item.source));
        render();
        renderDatabaseMenu();
      }}

      function setupSelect(select, label, values) {{
        const selected = select.value;
        const unique = [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
        select.innerHTML = `<option value="">${{label}}</option>` + unique.map((value) => `<option value="${{escapeAttr(value)}}">${{escapeHtml(value)}}</option>`).join("");
        select.value = unique.includes(selected) ? selected : "";
      }}

      function setDatabasePanel(panel) {{
        databasePanel = panel;
        fields.databaseMenuCatalog.classList.toggle("active", panel === "catalog");
        fields.databaseMenuExternal.classList.toggle("active", panel === "external");
        fields.databaseCatalogPanel.hidden = panel !== "catalog";
        fields.databaseExternalPanel.hidden = panel !== "external";
        renderDatabaseMenu();
      }}

      function renderDatabaseMenu() {{
        const sourceList = sourceFiles.length
          ? sourceFiles.map((file) => `<div class="db-item"><strong>JSON</strong><span>${{escapeHtml(file)}}</span></div>`).join("")
          : `<div class="db-item"><strong>JSON</strong><span>Sin archivo resuelto.</span></div>`;
        fields.databaseCatalogPanel.innerHTML = `
          <label>
            JSON editable
            <input type="text" readonly value="${{escapeAttr(writeJsonPath || "-")}}">
          </label>
          <div class="db-list">${{sourceList}}</div>
        `;
        fields.databaseExternalPanel.innerHTML = `
          <div class="db-list">
            ${{externalDatabaseItem("Wikipedia", "wikipedia")}}
            ${{externalDatabaseItem("IMDb", "imdb")}}
            ${{externalDatabaseItem("FilmAffinity", "filmaffinity")}}
            ${{externalCacheItem()}}
          </div>
        `;
        fields.databaseMenuCatalog.classList.toggle("active", databasePanel === "catalog");
        fields.databaseMenuExternal.classList.toggle("active", databasePanel === "external");
        fields.databaseCatalogPanel.hidden = databasePanel !== "catalog";
        fields.databaseExternalPanel.hidden = databasePanel !== "external";
      }}

      function externalDatabaseItem(label, source) {{
        const health = externalHealth?.sources?.[source] || {{}};
        const consumed = externalSourcesLastUsed.includes(source);
        const attempted = externalSourcesAttempted.includes(source);
        const stateLabels = {{ ready: "lista", ok: "disponible", empty: "sin resultados", error: "error" }};
        const state = stateLabels[health.status] || (fields.externalSource.checked ? "lista" : "apagada");
        const request = attempted ? (consumed ? `${{health.result_count || 0}} resultados` : "sin resultados") : "sin consultar";
        const latency = health.latency_ms ? `${{health.latency_ms}} ms` : "";
        const error = health.error ? ` | ${{health.error}}` : "";
        const status = [state, request, latency].filter(Boolean).join(" | ") + error;
        return `<div class="db-item"><strong>${{escapeHtml(label)}}</strong><span>${{escapeHtml(status)}}</span></div>`;
      }}

      function externalCacheItem() {{
        const cache = externalHealth?.cache || {{}};
        const entries = Number(cache.search_entries || 0) + Number(cache.metadata_entries || 0);
        return `<div class="db-item"><strong>Cache</strong><span>${{entries}} entradas | ${{Number(cache.hits || 0)}} hits | ${{Number(cache.misses || 0)}} misses</span></div>`;
      }}

      async function runSearch() {{
        const requestedQuery = fields.query.value.trim();
        activeQuery = requestedQuery.length >= 2 ? requestedQuery : "";
        selectedManualIndex = null;
        selectedExistingIdForSearch = null;
        manualResults = [];
        catalogMergeResults = [];
        manualVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        render();
        renderDatabaseMenu();
        if (requestedQuery.length < 2) {{
          if (requestedQuery) {{
            fields.catalogMergeSection.classList.add("active");
            fields.catalogMergeStatus.textContent = "Escribi al menos 2 caracteres.";
          }}
          return;
        }}
        searchCatalogForMerge(activeQuery);
        if (fields.externalSource.checked) {{
          await searchManual("all");
        }}
      }}

      function filteredItems() {{
        const query = activeQuery.trim();
        return items.filter((item) => {{
          const haystack = [
            item.title,
            item.original_title,
            item.spanish_title,
            item.english_title,
            asList(item.alternative_titles).join(" "),
            item.local_name,
            item.local_path,
            localFilesText(item),
            item.year,
            item.description,
            item.wikipedia_extract,
            item.notes,
            item.review,
            item.watched_at,
            item.rating,
            asList(item.genres).join(" "),
            asList(item.directors).join(" "),
            asList(item.writers).join(" "),
            asList(item.cast).join(" "),
            Array.isArray(item.tags) ? item.tags.join(" ") : item.tags
          ].join(" ");
          return (!query || matchesSearchText(haystack, query))
            && (!duplicatesOnly || Number(item._duplicate_count || 0) > 0)
            && (!fields.status.value || item.status === fields.status.value)
            && (!fields.kind.value || item.kind === fields.kind.value)
            && (!fields.source.value || item.source === fields.source.value);
        }});
      }}

      function applyRandomOrder(list) {{
        if (!randomOrder.length) return list;
        const byId = new Map(list.map((item) => [item.id, item]));
        const ordered = randomOrder.map((id) => byId.get(id)).filter(Boolean);
        const orderedIds = new Set(ordered.map((item) => item.id));
        return [...ordered, ...list.filter((item) => !orderedIds.has(item.id))];
      }}

      function render() {{
        const baseFiltered = filteredItems();
        const filtered = applyRandomOrder(baseFiltered);
        const shown = filtered.slice(0, catalogVisibleCount);

        fields.stats.textContent = `${{shown.length}} mostradas de ${{filtered.length}} visibles (${{items.length}} items)${{randomOrder.length ? " | orden aleatorio" : ""}}${{duplicatesOnly ? " | solo duplicadas" : ""}}`;
        fields.total.textContent = items.length;
        fields.visible.textContent = filtered.length;
        fields.watchedCount.textContent = items.filter((item) => item.status === "watched").length;
        fields.toWatchCount.textContent = items.filter((item) => item.status === "to_watch").length;
        fields.ratedCount.textContent = items.filter((item) => normalizeRating(item.rating) > 0).length;
        fields.withImage.textContent = items.filter((item) => item.page_image).length;
        fields.wikiLinks.textContent = items.filter(hasExternalLink).length;
        fields.withoutWiki.textContent = items.filter((item) => !hasExternalLink(item)).length;
        fields.imdbLinks.textContent = items.filter((item) => hasHost(item.url, "imdb.com") || hasHost(item.imdb_url, "imdb.com")).length;
        fields.faLinks.textContent = items.filter((item) => hasHost(item.url, "filmaffinity.com") || hasHost(item.filmaffinity_url, "filmaffinity.com")).length;
        fields.duplicateCount.textContent = items.filter((item) => Number(item._duplicate_count || 0) > 0).length;
        fields.showDuplicates.textContent = duplicatesOnly ? "Ver todo" : "Ver duplicadas";
        fields.sourceFiles.textContent = sourceFiles.length;
        fields.empty.style.display = filtered.length ? "none" : "block";
        fields.grid.innerHTML = shown.map(card).join("");
        fields.catalogLoadMore.hidden = shown.length >= filtered.length;
        fields.catalogLoadMore.textContent = `Cargar mas (${{filtered.length - shown.length}})`;
        renderDetail();
      }}

      function showMoreCatalogItems() {{
        catalogVisibleCount += CATALOG_PAGE_SIZE;
        render();
      }}

      function randomizeView() {{
        const visibleIds = filteredItems().map((item) => item.id);
        randomOrder = shuffle(visibleIds);
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }}

      function resetViewOrder() {{
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }}

      function toggleDuplicatesOnly() {{
        duplicatesOnly = !duplicatesOnly;
        randomOrder = [];
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        render();
      }}

      function shuffle(values) {{
        const shuffled = [...values];
        for (let index = shuffled.length - 1; index > 0; index -= 1) {{
          const swapIndex = Math.floor(Math.random() * (index + 1));
          [shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]];
        }}
        return shuffled;
      }}

      function card(item) {{
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || "";
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        const image = item.page_image
          ? `<img class="image" src="${{escapeAttr(cachedImageSrc(item.page_image))}}" alt="" loading="lazy" decoding="async">`
          : `<div class="image-placeholder">${{escapeHtml((shownTitle || "Sin imagen").slice(0, 18))}}</div>`;
        const tags = Array.isArray(item.tags) ? item.tags : [];
        const rating = normalizeRating(item.rating);
        const personal = rating ? `${{rating}}/10` : item.status === "watched" ? "vista" : "sin puntaje";
        return `<article class="card" onclick="openDetail('${{escapeAttr(item.id)}}')">
          ${{image}}
          <div class="body">
            <div class="title">
              <h2>${{escapeHtml(shownTitle || "Sin titulo")}}</h2>
            </div>
            ${{subtitle ? `<div class="meta">${{meta(subtitle)}}</div>` : ""}}
            <div class="card-badges">
              <span class="pill ${{item.status === "watched" ? "good" : ""}}">${{escapeHtml(item.status || "sin estado")}}</span>
              <span class="pill ${{hasExternalLink(item) ? "good" : "muted"}}">${{hasExternalLink(item) ? "con link" : "sin link"}}</span>
              <span class="pill ${{isInCatalog(item.en_catalogo) ? "good" : "muted"}}">${{isInCatalog(item.en_catalogo) ? "catalogo: si" : "catalogo: no"}}</span>
              ${{Number(item._duplicate_count || 0) > 0 ? `<span class="pill warning">duplicada +${{item._duplicate_count}}</span>` : ""}}
            </div>
            <div class="meta">
              ${{meta(item.year)}}${{meta(item.kind)}}${{meta(item.source)}}${{meta(rating ? `puntaje: ${{rating}}/10` : "")}}${{meta(item.watched_at ? `vista: ${{item.watched_at}}` : "")}}${{meta(tags.join(", "))}}
              ${{meta(localFileCountLabel(item))}}
            </div>
            ${{summary ? `<p class="summary">${{escapeHtml(summary)}}</p>` : ""}}
            <div class="card-facts">
              ${{cardFact("Año", item.year)}}
              ${{cardFact("Director", firstListValue(item.directors))}}
              ${{cardFact("Genero", listText(item.genres, 2))}}
              ${{cardFact("Personal", personal)}}
            </div>
            <div class="links" onclick="event.stopPropagation()">
              <a href="#" onclick="event.preventDefault(); openDetail('${{escapeAttr(item.id)}}')">Detalle</a>
              <a href="#" onclick="toggleWatched(event, '${{escapeAttr(item.id)}}', '${{escapeAttr(item.status || "to_watch")}}')">${{item.status === "watched" ? "Marcar pendiente" : "Marcar vista"}}</a>
              <a href="#" onclick="findLinkForCatalog(event, '${{escapeAttr(item.id)}}')">Buscar link</a>
            </div>
          </div>
        </article>`;
      }}

      function cardFact(label, value) {{
        return `<div class="card-fact"><strong>${{escapeHtml(label)}}</strong><span>${{escapeHtml(value || "-")}}</span></div>`;
      }}

      function personalPanel(item, forceOpen = false) {{
        const rating = normalizeRating(item.rating);
        const ratingOptions = Array.from({{ length: 11 }}, (_, value) => (
          `<option value="${{value}}" ${{value === rating ? "selected" : ""}}>${{value}}</option>`
        )).join("");
        const open = forceOpen || openPersonalId === item.id ? " open" : "";
        const watched = item.watched_at ? `Vista: ${{item.watched_at}}` : "Sin fecha de vista";
        const summary = [rating ? `${{rating}}/10` : "Sin puntaje", watched].join(" | ");
        return `<details class="personal-panel"${{open}} ontoggle="trackPersonalPanel(event, '${{escapeAttr(item.id)}}')">
          <summary>${{escapeHtml(summary)}}</summary>
          <div class="personal-grid">
            <label>
              Fecha vista
              <input data-personal-watched-at type="date" value="${{escapeAttr(item.watched_at || "")}}">
            </label>
            <label>
              Puntaje
              <select data-personal-rating>
                ${{ratingOptions}}
              </select>
            </label>
            <label class="review-field">
              Review
              <textarea data-personal-review rows="4">${{escapeHtml(item.review || "")}}</textarea>
            </label>
            <div class="personal-actions">
              <button type="button" onclick="savePersonal(event, '${{escapeAttr(item.id)}}')">Guardar</button>
              <span class="status-line" data-personal-status></span>
            </div>
          </div>
        </details>`;
      }}

      function factsPanel(item) {{
        const rows = [
          ["Genero", item.genres, 4],
          ["Original", item.original_title, 1],
          ["Español", item.spanish_title, 1],
          ["Inglés", item.english_title, 1],
          ["Alternativos", item.alternative_titles, 6],
          ["Director", item.directors, 4],
          ["Guion", item.writers, 4],
          ["Reparto", item.cast, 8]
        ].map(([label, values, limit]) => {{
          const text = listText(values, limit);
          return text ? `<dt>${{escapeHtml(label)}}</dt><dd>${{escapeHtml(text)}}</dd>` : "";
        }}).filter(Boolean);
        const localText = localFilesText(item);
        if (localText) rows.push(`<dt>Archivos</dt><dd>${{escapeHtml(localText)}}</dd>`);
        if (Number(item._duplicate_count || 0) > 0) {{
          const duplicateText = `${{item._duplicate_count}} coincidencia(s): ${{item._duplicate_reason || "misma obra"}}`;
          rows.push(`<dt>Duplicados</dt><dd>${{escapeHtml(duplicateText)}}</dd>`);
        }}
        const content = rows.join("");
        return content ? `<dl class="facts">${{content}}</dl>` : "";
      }}

      function openDetail(id) {{
        selectedDetailId = id;
        renderDetail();
        fields.detailBackdrop.classList.add("open");
        fields.detailDrawer.classList.add("open");
        fields.detailDrawer.setAttribute("aria-hidden", "false");
      }}

      function closeDetail() {{
        selectedDetailId = "";
        fields.detailBackdrop.classList.remove("open");
        fields.detailDrawer.classList.remove("open");
        fields.detailDrawer.setAttribute("aria-hidden", "true");
        fields.detailBody.innerHTML = "";
      }}

      function renderDetail() {{
        if (!selectedDetailId) return;
        const item = items.find((entry) => entry.id === selectedDetailId);
        if (!item) {{
          closeDetail();
          return;
        }}
        const rating = normalizeRating(item.rating);
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        const image = item.page_image
          ? `<img class="drawer-poster" src="${{escapeAttr(cachedImageSrc(item.page_image))}}" alt="" decoding="async">`
          : `<div class="drawer-poster"></div>`;
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || "";
        fields.detailBody.innerHTML = `
          <section class="drawer-hero">
            ${{image}}
            <div>
              <h2>${{escapeHtml(shownTitle || "Sin titulo")}}</h2>
              <div class="meta">
                ${{meta(item.year)}}${{meta(item.source)}}${{meta(item.status)}}${{meta(rating ? `puntaje: ${{rating}}/10` : "")}}${{meta(item.watched_at ? `vista: ${{item.watched_at}}` : "")}}${{meta(isInCatalog(item.en_catalogo) ? "catalogo: si" : "catalogo: no")}}${{meta(Number(item._duplicate_count || 0) > 0 ? `duplicada +${{item._duplicate_count}}` : "")}}
              </div>
              ${{subtitle ? `<div class="meta">${{meta(subtitle)}}</div>` : ""}}
              <div class="drawer-control">
                <span>Tipo</span>
                ${{kindSelect(item)}}
              </div>
              ${{summary ? `<p class="summary">${{escapeHtml(summary)}}</p>` : ""}}
            </div>
          </section>
          <section class="drawer-section">
            <h3>Ficha</h3>
            ${{factsPanel(item) || `<span class="status-line">Sin ficha enriquecida.</span>`}}
          </section>
          <section class="drawer-section">
            <h3>Metadata</h3>
            ${{metadataEditor(item)}}
          </section>
          <section class="drawer-section">
            <h3>Mi registro</h3>
            ${{personalPanel(item, true)}}
          </section>
          <section class="drawer-section">
            <h3>Links</h3>
            <div class="links">${{detailLinks(item)}}</div>
          </section>
          <section class="drawer-section">
            <h3>Acciones</h3>
            <div class="links">
              <a href="#" onclick="toggleWatched(event, '${{escapeAttr(item.id)}}', '${{escapeAttr(item.status || "to_watch")}}')">${{item.status === "watched" ? "Marcar pendiente" : "Marcar vista"}}</a>
              <a href="#" onclick="toggleCatalog(event, '${{escapeAttr(item.id)}}')">${{isInCatalog(item.en_catalogo) ? "Quitar catalogo" : "Marcar catalogo"}}</a>
              <a href="#" onclick="findLinkForCatalog(event, '${{escapeAttr(item.id)}}')">Buscar link</a>
              <a href="#" data-id="${{escapeAttr(item.id)}}" onclick="deleteCatalogItem(event, this.dataset.id)">Eliminar</a>
            </div>
          </section>
        `;
      }}

      function detailLinks(item) {{
        const links = [
          item.url ? `<a href="${{escapeAttr(item.url)}}" target="_blank" rel="noreferrer">Abrir link</a>` : "",
          item.wikipedia_url ? `<a href="${{escapeAttr(item.wikipedia_url)}}" target="_blank" rel="noreferrer">Wikipedia</a>` : "",
          item.imdb_url ? `<a href="${{escapeAttr(item.imdb_url)}}" target="_blank" rel="noreferrer">IMDb</a>` : "",
          item.filmaffinity_url ? `<a href="${{escapeAttr(item.filmaffinity_url)}}" target="_blank" rel="noreferrer">FilmAffinity</a>` : "",
          item.wikidata_id ? `<a href="https://www.wikidata.org/wiki/${{escapeAttr(item.wikidata_id)}}" target="_blank" rel="noreferrer">Wikidata</a>` : ""
        ].filter(Boolean).join("");
        return links || `<span class="status-line">Sin links asociados.</span>`;
      }}

      function metadataEditor(item) {{
        const rows = [
          ["Titulo", "title", "text"],
          ["Original", "original_title", "text"],
          ["Español", "spanish_title", "text"],
          ["Inglés", "english_title", "text"],
          ["Alternativos", "alternative_titles", "text"],
          ["Tipo", "kind", "kind"],
          ["Año", "year", "text"],
          ["Descripcion", "description", "textarea"],
          ["Generos", "genres", "text"],
          ["Directores", "directors", "text"],
          ["Guionistas", "writers", "text"],
          ["Reparto", "cast", "text"]
        ];
        return `<div class="metadata-editor">
          ${{rows.map(([label, field, control]) => metadataEditorRow(item, label, field, control)).join("")}}
          <div class="metadata-actions">
            <button type="button" onclick="saveMetadata(event, '${{escapeAttr(item.id)}}')">Guardar metadata</button>
            <span class="status-line" data-metadata-status></span>
          </div>
        </div>`;
      }}

      function metadataEditorRow(item, label, field, control) {{
        const listFields = ["alternative_titles", "genres", "directors", "writers", "cast"];
        const value = listFields.includes(field) ? asList(item[field]).join(", ") : String(item[field] || "");
        const locked = asList(item.locked_fields).includes(field);
        const origin = item.metadata_sources?.[field] || {{}};
        const source = origin.source
          ? `${{origin.source}}${{origin.inferred ? " (inferida)" : ""}}${{origin.updated_at ? ` | ${{String(origin.updated_at).slice(0, 10)}}` : ""}}`
          : "sin procedencia";
        const input = control === "textarea"
          ? `<textarea data-metadata-field="${{field}}" rows="4">${{escapeHtml(value)}}</textarea>`
          : control === "kind"
            ? `<select data-metadata-field="${{field}}">${{["pelicula", "serie", "anime", "documental"].map((option) => `<option value="${{option}}" ${{option === value ? "selected" : ""}}>${{option}}</option>`).join("")}}</select>`
            : `<input data-metadata-field="${{field}}" type="text" value="${{escapeAttr(value)}}">`;
        return `<div class="metadata-row">
          <label>${{escapeHtml(label)}}${{input}}</label>
          <div class="metadata-control">
            <span class="metadata-origin">${{escapeHtml(source)}}</span>
            <label class="lock-control"><input data-lock-field="${{field}}" type="checkbox" ${{locked ? "checked" : ""}}> Bloquear</label>
          </div>
        </div>`;
      }}

      function kindSelect(item) {{
        const value = normalizeKind(item.kind);
        const options = ["pelicula", "serie", "anime", "documental"];
        return `<select class="kind-select" onclick="event.stopPropagation()" onchange="updateKind(event, '${{escapeAttr(item.id)}}')">
          ${{options.map((option) => `<option value="${{option}}" ${{option === value ? "selected" : ""}}>${{option}}</option>`).join("")}}
        </select>`;
      }}

      function cachedImageSrc(url) {{
        return `/image-cache?url=${{encodeURIComponent(url)}}`;
      }}

      async function searchManual(source = "all", statusPrefix = "") {{
        const query = fields.query.value.trim();
        if (query.length < 2) return;
        if (externalSearchController) externalSearchController.abort();
        const controller = new AbortController();
        externalSearchController = controller;
        manualSearchSource = source;
        manualResults = [];
        selectedManualIndex = null;
        manualVisibleCount = SEARCH_PAGE_SIZE;
        fields.externalSearchSection.classList.add("active");
        fields.manualSearchStatus.textContent = statusPrefix || "Buscando...";
        fields.manualSearchResults.innerHTML = "";
        fields.searchButton.disabled = true;
        fields.searchButton.textContent = "Buscando...";
        try {{
          const response = await fetch(`/api/search?q=${{encodeURIComponent(query)}}&source=${{encodeURIComponent(source)}}`, {{
            signal: controller.signal
          }});
          if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
          const payload = await response.json();
          manualResults = payload.results || [];
          externalHealth = payload.external || externalHealth;
          externalSourcesAttempted = source === "all" ? ["wikipedia", "imdb", "filmaffinity"] : [source];
          externalSourcesLastUsed = [...new Set(manualResults.map((result) => result.source || "").filter(Boolean))];
          console.log("[catalog-viewer] search results", {{
            source,
            query,
            count: manualResults.length,
            sources: [...new Set(manualResults.map((result) => result.source || ""))]
          }});
          fields.manualSearchStatus.textContent = manualResults.length
            ? `${{manualResults.length}} resultados${{source === "wikipedia" ? " de Wikipedia" : ""}}`
            : "Sin resultados";
          renderManualResults();
          renderDatabaseMenu();
          renderDatabaseMenu();
        }} catch (error) {{
          if (error.name !== "AbortError") {{
            fields.manualSearchStatus.textContent = "No se pudo completar la búsqueda externa.";
            console.error("[catalog-viewer] external search failed", error);
          }}
        }} finally {{
          if (externalSearchController === controller) {{
            externalSearchController = null;
            fields.searchButton.disabled = false;
            fields.searchButton.textContent = "Buscar";
          }}
        }}
      }}

      function clearManualSearch() {{
        if (externalSearchController) externalSearchController.abort();
        externalSearchController = null;
        fields.searchButton.disabled = false;
        fields.searchButton.textContent = "Buscar";
        manualResults = [];
        catalogMergeResults = [];
        selectedManualIndex = null;
        selectedExistingIdForSearch = null;
        manualSearchSource = "all";
        activeQuery = "";
        manualVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        catalogVisibleCount = CATALOG_PAGE_SIZE;
        externalSourcesLastUsed = [];
        externalSourcesAttempted = [];
        fields.externalSource.checked = false;
        fields.query.value = "";
        fields.manualSearchStatus.textContent = "";
        fields.manualSearchResults.innerHTML = "";
        fields.catalogMergeStatus.textContent = "";
        fields.catalogMergeResults.innerHTML = "";
        fields.externalSearchSection.classList.remove("active");
        fields.catalogMergeSection.classList.remove("active");
        render();
        renderDatabaseMenu();
        fields.query.focus();
      }}

      function prepareManualMerge(index) {{
        selectedManualIndex = index;
        if (selectedExistingIdForSearch) {{
          const item = items.find((entry) => entry.id === selectedExistingIdForSearch);
          catalogMergeResults = item ? [item] : [];
          catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
          fields.catalogMergeSection.classList.add("active");
          fields.catalogMergeStatus.textContent = item ? "Entrada seleccionada para comparar." : "No se encontró la entrada seleccionada.";
          renderCatalogMergeResults();
          return;
        }}
        const result = manualResults[index] || {{}};
        fields.query.value = [result.title, result.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        render();
        searchCatalogForMerge();
      }}

      function searchCatalogForMerge(queryValue = "") {{
        const query = (queryValue || fields.query.value).trim().toLowerCase();
        if (!query) return;
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        catalogMergeResults = items
          .map((item) => ({{ item, score: catalogMatchScore(item, query) }}))
          .filter((entry) => entry.score > 0)
          .sort((a, b) => b.score - a.score)
          .slice(0, 60)
          .map((entry) => entry.item);
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeStatus.textContent = selectedManualIndex === null
          ? `${{catalogMergeResults.length}} coincidencias locales.`
          : `${{catalogMergeResults.length}} entradas encontradas para comparar.`;
        renderCatalogMergeResults();
      }}

      function renderManualResults() {{
        const visible = manualResults.slice(0, manualVisibleCount);
        const more = manualResults.length > manualVisibleCount
          ? `<button class="load-more" type="button" onclick="showMoreManualResults()">Cargar mas (${{manualResults.length - manualVisibleCount}})</button>`
          : "";
        fields.manualSearchResults.innerHTML = visible.map(searchResult).join("") + more;
      }}

      function renderCatalogMergeResults() {{
        const visible = catalogMergeResults.slice(0, catalogMergeVisibleCount);
        const more = catalogMergeResults.length > catalogMergeVisibleCount
          ? `<button class="load-more" type="button" onclick="showMoreCatalogResults()">Cargar mas (${{catalogMergeResults.length - catalogMergeVisibleCount}})</button>`
          : "";
        fields.catalogMergeResults.innerHTML = visible.map(catalogMergeResult).join("") + more;
      }}

      function showMoreManualResults() {{
        manualVisibleCount += SEARCH_PAGE_SIZE;
        renderManualResults();
      }}

      function showMoreCatalogResults() {{
        catalogMergeVisibleCount += SEARCH_PAGE_SIZE;
        renderCatalogMergeResults();
      }}

      async function startWikiReview() {{
        wikiReviewQueue = items.filter((item) => !hasExternalLink(item));
        wikiReviewIndex = 0;
        if (!wikiReviewQueue.length) {{
          fields.wikiReviewStatus.textContent = "No quedan entradas sin link.";
          return;
        }}
        await reviewCurrentWikiItem();
      }}

      async function previousWikiReview() {{
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.max(0, wikiReviewIndex - 1);
        await reviewCurrentWikiItem();
      }}

      async function nextWikiReview() {{
        if (!wikiReviewQueue.length) await startWikiReview();
        if (!wikiReviewQueue.length) return;
        wikiReviewIndex = Math.min(wikiReviewQueue.length - 1, wikiReviewIndex + 1);
        await reviewCurrentWikiItem();
      }}

      async function reviewCurrentWikiItem() {{
        const item = wikiReviewQueue[wikiReviewIndex];
        if (!item) return;
        fields.wikiReviewStatus.textContent = `${{wikiReviewIndex + 1}}/${{wikiReviewQueue.length}}: ${{item.title || item.local_name || "Sin titulo"}}`;
        await findLinkForItem(item);
      }}

      function catalogMergeResult(item) {{
        const incoming = selectedManualIndex === null ? null : manualResults[selectedManualIndex];
        const comparison = incoming ? diffComparison(incoming, item) : "";
        const summary = item.wikipedia_extract || item.description || item.notes || item.review || item.local_name || "";
        const shownTitle = displayTitle(item);
        const subtitle = titleSubtitle(item);
        return `<article class="search-result ${{comparison ? "comparison-result" : "compact-result"}}">
          ${{resultMedia(shownTitle || item.local_name, item.page_image)}}
          <div class="result-body">
            <h3>${{escapeHtml(shownTitle || "Sin titulo")}}</h3>
            ${{subtitle ? `<div class="meta">${{meta(subtitle)}}</div>` : ""}}
            <div class="meta">
              ${{meta(item.year)}}${{meta(item.kind)}}${{meta(item.source)}}${{meta(firstListValue(item.genres))}}${{meta(firstListValue(item.directors))}}
            </div>
            <div class="card-badges">
              <span class="pill ${{hasExternalLink(item) ? "good" : "muted"}}">${{hasExternalLink(item) ? "con link" : "sin link"}}</span>
              <span class="pill ${{isInCatalog(item.en_catalogo) ? "good" : "muted"}}">${{isInCatalog(item.en_catalogo) ? "catalogo: si" : "catalogo: no"}}</span>
            </div>
            ${{searchDescription(summary, "catalog", item.id)}}
            ${{comparison}}
            <div class="result-actions">
              <button class="action-primary ${{incoming ? "" : "span-all"}}" type="button" onclick="openDetail('${{escapeAttr(item.id)}}')">Detalle</button>
              ${{incoming ? `<button class="action-secondary" type="button" onclick="mergeSearchResult(${{selectedManualIndex}}, '${{escapeAttr(item.id)}}')">Combinar</button>` : ""}}
              ${{item.url ? `<a class="action-secondary span-all" href="${{escapeAttr(item.url)}}" target="_blank" rel="noreferrer">Abrir link</a>` : ""}}
            </div>
          </div>
        </article>`;
      }}

      function searchResult(result, index) {{
        const description = result.description || result.wikipedia_extract || "";
        const similarity = selectedExistingIdForSearch ? candidateSimilarity(result) : "";
        const primaryAction = selectedExistingIdForSearch ? "Combinar" : "Agregar";
        const shownTitle = displayTitle(result);
        const subtitle = titleSubtitle(result);
        return `<article class="search-result compact-result">
          ${{resultMedia(shownTitle, result.page_image)}}
          <div class="result-body">
            <h3>${{escapeHtml(shownTitle || "Sin titulo")}}</h3>
            ${{subtitle ? `<div class="meta">${{meta(subtitle)}}</div>` : ""}}
            <div class="meta">
              ${{meta(result.source)}}${{meta(result.year)}}${{meta(firstListValue(result.genres))}}${{meta(firstListValue(result.directors))}}${{meta(result.url ? new URL(result.url).hostname.replace(/^www\\./, "") : "")}}${{meta(similarity)}}
            </div>
            <div class="card-badges">
              <span class="pill good">${{escapeHtml(result.source || "externo")}}</span>
              <span class="pill ${{result.url ? "good" : "muted"}}">${{result.url ? "con link" : "sin link"}}</span>
            </div>
            ${{searchDescription(description, "manual", index)}}
            <div class="result-actions">
              <button class="action-primary" data-index="${{index}}" onclick="addSearchResult(${{index}})">${{primaryAction}}</button>
              <button class="action-secondary" type="button" onclick="prepareManualMerge(${{index}})">Comparar</button>
              ${{result.url ? `<a class="action-secondary span-all" href="${{escapeAttr(result.url)}}" target="_blank" rel="noreferrer">Detalle</a>` : ""}}
            </div>
          </div>
        </article>`;
      }}

      function resultMedia(title, imageUrl) {{
        return imageUrl
          ? `<img class="result-media" src="${{escapeAttr(cachedImageSrc(imageUrl))}}" alt="" loading="lazy" decoding="async">`
          : `<div class="result-placeholder">${{escapeHtml((title || "Sin imagen").slice(0, 24))}}</div>`;
      }}

      function searchDescription(description, collection, key) {{
        if (!description) return "";
        const text = String(description).trim();
        const more = text.length > 90
          ? `<button class="description-more" type="button" onclick="openSearchDescription('${{collection}}', '${{escapeAttr(key)}}')">Ver mas</button>`
          : "";
        return `<p class="result-summary">${{escapeHtml(text)}}</p>${{more}}`;
      }}

      function openSearchDescription(collection, key) {{
        const item = collection === "manual"
          ? manualResults[Number(key)]
          : items.find((entry) => entry.id === key);
        if (!item) return;
        const title = displayTitle(item) || "Descripcion";
        const description = item.wikipedia_extract || item.description || item.notes || item.review || "Sin descripcion.";
        fields.descriptionDialogTitle.textContent = title;
        fields.descriptionDialogText.textContent = description;
        fields.descriptionDialog.showModal();
      }}

      function candidateSimilarity(result) {{
        const existing = items.find((entry) => entry.id === selectedExistingIdForSearch);
        if (!existing) return "";
        let score = bestTitleSimilarity(existing, result);
        if (existing.year && String(existing.year) === String(result.year || "")) score = Math.min(100, score + 20);
        return `similitud: ${{score}}%`;
      }}

      function bestTitleSimilarity(leftItem, rightItem) {{
        const leftTitles = titleSearchValues(leftItem).map(normalizeText).filter(Boolean);
        const rightTitles = titleSearchValues(rightItem).map(normalizeText).filter(Boolean);
        let best = 0;
        for (const leftTitle of leftTitles) {{
          for (const rightTitle of rightTitles) {{
            const leftTerms = new Set(leftTitle.split(/\s+/).filter(Boolean));
            const rightTerms = new Set(rightTitle.split(/\s+/).filter(Boolean));
            const shared = [...leftTerms].filter((term) => rightTerms.has(term)).length;
            const total = Math.max(leftTerms.size, rightTerms.size, 1);
            best = Math.max(best, Math.round((shared / total) * 100));
          }}
        }}
        return best;
      }}

      async function addSearchResult(index) {{
        const cards = [...fields.manualSearchResults.querySelectorAll("[data-index]")];
        const button = cards.find((element) => Number(element.dataset.index) === index);
        button.disabled = true;
        button.textContent = selectedExistingIdForSearch ? "Combinando..." : "Agregando...";
        if (selectedExistingIdForSearch) {{
          if (!isExternalResult(manualResults[index])) {{
            button.disabled = false;
            button.textContent = "Combinar";
            alert("Este resultado no tiene un link externo reconocido. Elegí Wikipedia, IMDb o FilmAffinity.");
            console.warn("[catalog-viewer] blocked result without trusted link", {{ result: manualResults[index] }});
            return;
          }}
          await mergeSearchResult(index, selectedExistingIdForSearch);
          return;
        }}
        const response = await fetch("/api/add", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(manualResults[index])
        }});
        const payload = await response.json();
        if (payload.reason === "possible_duplicate") {{
          button.disabled = false;
          button.textContent = "Agregar";
          showDuplicateChoice(index, payload.candidates || []);
          return;
        }}
        button.textContent = payload.ok ? "Agregado" : payload.reason === "duplicate" ? "Ya existe" : "Error";
        await load();
      }}

      function showDuplicateChoice(index, candidates) {{
        const blocks = candidates.map((candidate) => `
          <div>
            <strong>${{escapeHtml(candidate.title || "Sin titulo")}}</strong>
            <div class="meta">
              ${{meta(candidate.year)}}${{meta(candidate.source)}}${{meta(firstListValue(candidate.genres))}}${{meta(firstListValue(candidate.directors))}}${{meta(isInCatalog(candidate.en_catalogo) ? "catalogo: si" : "catalogo: no")}}
            </div>
          </div>
          <div class="duplicate-actions">
            <button onclick="mergeSearchResult(${{index}}, '${{escapeAttr(candidate.id)}}')">Combinar</button>
            ${{candidate.url ? `<a href="${{escapeAttr(candidate.url)}}" target="_blank" rel="noreferrer">Ver existente</a>` : ""}}
          </div>
        `).join("");
        fields.manualSearchResults.insertAdjacentHTML("afterbegin", `
          <section class="duplicate-box">
            <strong>Posible duplicado encontrado</strong>
            <span>Ya existe una entrada con titulo y año parecidos. Podés combinarla, agregar igual o cancelar.</span>
            ${{blocks}}
            <div class="duplicate-actions">
              <button onclick="forceAddSearchResult(${{index}})">Agregar igual</button>
              <button onclick="runSearch()">Cancelar</button>
            </div>
          </section>
        `);
      }}

      async function mergeSearchResult(index, targetId) {{
        if (!isExternalResult(manualResults[index])) {{
          alert("Este resultado no tiene un link externo reconocido. Elegí un resultado de Wikipedia, IMDb o FilmAffinity.");
          console.warn("[catalog-viewer] blocked result without trusted link", {{ targetId, result: manualResults[index] }});
          return;
        }}
        const beforeCounts = linkCounts();
        const response = await postAdd(manualResults[index], "merge", targetId);
        const payload = await response.json();
        if (!payload.ok) {{
          alert(payload.reason || "No se pudo combinar");
          return;
        }}
        await load();
        const afterCounts = linkCounts();
        console.log("[catalog-viewer] link merge", {{
          targetId,
          result: manualResults[index],
          before: beforeCounts,
          after: afterCounts
        }});
        selectedExistingIdForSearch = null;
        if (wikiReviewQueue.length) {{
          wikiReviewQueue = items.filter((item) => !hasExternalLink(item));
          wikiReviewIndex = Math.min(wikiReviewIndex, Math.max(wikiReviewQueue.length - 1, 0));
          if (wikiReviewQueue.length) {{
            await reviewCurrentWikiItem();
          }} else {{
            fields.wikiReviewStatus.textContent = "No quedan entradas sin link.";
          }}
          return;
        }}
        await runSearch();
      }}

      async function forceAddSearchResult(index) {{
        await postAdd(manualResults[index], "force", "");
        await load();
        await runSearch();
      }}

      async function postAdd(result, action, targetId) {{
        const target = items.find((entry) => entry.id === targetId);
        return fetch("/api/add", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            result,
            action,
            target_id: targetId,
            target_source_file: target?._source_file || "",
            expected_source: ""
          }})
        }});
      }}

      function catalogMatchScore(item, query) {{
        const terms = query.split(/\s+/).filter(Boolean);
        const titles = titleSearchValues(item).map(normalizeText).filter(Boolean);
        const local = normalizeText(item.local_name || "");
        const year = String(item.year || "");
        const url = normalizeText(item.url || "");
        const haystack = `${{titles.join(" ")}} ${{local}} ${{year}} ${{url}}`;
        let score = 0;
        for (const term of terms) {{
          const normalizedTerm = normalizeText(term);
          if (haystack.includes(normalizedTerm)) {{
            score += 1;
          }} else if (normalizedTerm.length >= 5 && haystack.split(/\s+/).some((word) => oneEditApart(word, normalizedTerm))) {{
            score += 0.6;
          }}
        }}
        if (titles.includes(normalizeText(query))) score += 5;
        if (year && query.includes(year)) score += 2;
        return score;
      }}

      function diffComparison(incoming, existing) {{
        const fieldsToCompare = [
          ["Titulo", "title"],
          ["Original", "original_title"],
          ["Español", "spanish_title"],
          ["Inglés", "english_title"],
          ["Alternativos", "alternative_titles"],
          ["Año", "year"],
          ["Fuente", "source"],
          ["URL", "url"],
          ["Wikidata", "wikidata_id"],
          ["Genero", "genres"],
          ["Director", "directors"],
          ["Guion", "writers"],
          ["Reparto", "cast"],
          ["Catalogo", "en_catalogo"],
          ["Archivo", "local_name"],
          ["Archivos", "local_files"],
          ["Estado", "status"],
          ["Vista", "watched_at"],
          ["Puntaje", "rating"],
          ["Review", "review"]
        ];
        const rows = fieldsToCompare
          .map(([label, key]) => {{
            const left = displayField(existing[key], key);
            const right = displayField(incoming[key], key);
            if (!left && !right) return "";
            return `<div class="diff-row">
              <strong>${{escapeHtml(label)}}</strong>
              <span>${{escapeHtml(left || "-")}}</span>
              <span>${{escapeHtml(right || "-")}}</span>
            </div>`;
          }})
          .filter(Boolean)
          .join("");
        return `<section class="compare-box">
          <strong>Comparación: existente / resultado nuevo</strong>
          <div class="diff-grid">${{rows}}</div>
        </section>`;
      }}

      function displayField(value, key) {{
        if (key === "en_catalogo") return isInCatalog(value) ? "si" : "no";
        if (key === "local_files") return localFilesText({{ local_files: value }});
        if (["alternative_titles", "genres", "directors", "writers", "cast"].includes(key)) return asList(value).join(", ");
        return String(value || "");
      }}

      function normalizeText(value) {{
        return String(value || "")
          .toLowerCase()
          .normalize("NFD")
          .replace(/[\u0300-\u036f]/g, "")
          .replace(/\([^)]*\)/g, " ")
          .replace(/[^a-z0-9]+/g, " ")
          .trim();
      }}

      function matchesSearchText(value, query) {{
        const normalizedValue = normalizeText(value);
        const normalizedQuery = normalizeText(query);
        if (!normalizedQuery || normalizedValue.includes(normalizedQuery)) return true;
        const words = normalizedValue.split(/\s+/).filter(Boolean);
        return normalizedQuery.split(/\s+/).filter(Boolean).every((term) => (
          words.some((word) => word.includes(term) || (term.length >= 5 && oneEditApart(word, term)))
        ));
      }}

      function oneEditApart(left, right) {{
        if (Math.abs(left.length - right.length) > 1) return false;
        let leftIndex = 0;
        let rightIndex = 0;
        let edits = 0;
        while (leftIndex < left.length && rightIndex < right.length) {{
          if (left[leftIndex] === right[rightIndex]) {{
            leftIndex += 1;
            rightIndex += 1;
            continue;
          }}
          edits += 1;
          if (edits > 1) return false;
          if (left.length > right.length) leftIndex += 1;
          else if (right.length > left.length) rightIndex += 1;
          else {{
            leftIndex += 1;
            rightIndex += 1;
          }}
        }}
        if (leftIndex < left.length || rightIndex < right.length) edits += 1;
        return edits <= 1;
      }}

      async function deleteCatalogItem(event, id) {{
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        const title = item?.title || item?.local_name || "Sin titulo";
        const confirmed = confirm(`Eliminar "${{title}}" del JSON? Esta accion modifica el catalogo.`);
        if (!confirmed) return;
        const response = await fetch("/api/delete", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            id,
            confirmed: true,
            source_file: item?._source_file || "",
            url: item?.url || "",
            title: item?.title || title,
            year: item?.year || "",
            local_name: item?.local_name || ""
          }})
        }});
        const payload = await response.json();
        if (!payload.ok) alert(payload.reason || "No se pudo eliminar");
        await load();
      }}

      async function toggleWatched(event, id, currentStatus) {{
        event.preventDefault();
        const nextStatus = currentStatus === "watched" ? "to_watch" : "watched";
        const item = items.find((entry) => entry.id === id);
        const response = await fetch("/api/status", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            id,
            status: nextStatus,
            watched_at: nextStatus === "watched" ? todayLocalDate() : item?.watched_at || "",
            source_file: item?._source_file || ""
          }})
        }});
        const payload = await response.json();
        if (!payload.ok) alert(payload.reason || "No se pudo cambiar el estado");
        await load();
      }}

      async function updateKind(event, id) {{
        const kind = event.target.value;
        const item = items.find((entry) => entry.id === id);
        const response = await fetch("/api/kind", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ id, kind, source_file: item?._source_file || "" }})
        }});
        const payload = await response.json();
        if (!payload.ok) alert(payload.reason || "No se pudo cambiar el tipo");
        await load();
      }}

      async function toggleCatalog(event, id) {{
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        const nextValue = !isInCatalog(item.en_catalogo);
        const response = await fetch("/api/catalog", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ id, en_catalogo: nextValue, source_file: item?._source_file || "" }})
        }});
        const payload = await response.json();
        if (!payload.ok) alert(payload.reason || "No se pudo cambiar el estado de catalogo");
        await load();
      }}

      function trackPersonalPanel(event, id) {{
        if (event.target.open) {{
          openPersonalId = id;
        }} else if (openPersonalId === id) {{
          openPersonalId = "";
        }}
      }}

      async function savePersonal(event, id) {{
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        const panel = event.target.closest(".personal-panel");
        const watchedAt = panel?.querySelector("[data-personal-watched-at]")?.value || "";
        const rating = normalizeRating(panel?.querySelector("[data-personal-rating]")?.value);
        const review = panel?.querySelector("[data-personal-review]")?.value || "";
        const status = panel?.querySelector("[data-personal-status]");
        if (status) status.textContent = "Guardando...";
        openPersonalId = id;
        const response = await fetch("/api/personal", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ id, watched_at: watchedAt, rating, review, source_file: item?._source_file || "" }})
        }});
        const payload = await response.json();
        if (!payload.ok) {{
          if (status) status.textContent = "";
          alert(payload.reason || "No se pudo guardar el registro personal");
          return;
        }}
        await load();
      }}

      async function saveMetadata(event, id) {{
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        const editor = event.target.closest(".metadata-editor");
        if (!item || !editor) return;
        const values = {{}};
        editor.querySelectorAll("[data-metadata-field]").forEach((control) => {{
          values[control.dataset.metadataField] = control.value;
        }});
        const locked = new Set(asList(item.locked_fields));
        editor.querySelectorAll("[data-lock-field]").forEach((control) => {{
          if (control.checked) locked.add(control.dataset.lockField);
          else locked.delete(control.dataset.lockField);
        }});
        const status = editor.querySelector("[data-metadata-status]");
        if (status) status.textContent = "Guardando...";
        const response = await fetch("/api/metadata", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            id,
            values,
            locked_fields: [...locked],
            source_file: item._source_file || ""
          }})
        }});
        const payload = await response.json();
        if (!payload.ok) {{
          if (status) status.textContent = "";
          alert(payload.reason || "No se pudo guardar la metadata");
          return;
        }}
        await load();
      }}

      async function findLinkForCatalog(event, id) {{
        event.preventDefault();
        const item = items.find((entry) => entry.id === id);
        if (!item) return;
        await findLinkForItem(item);
      }}

      async function findLinkForItem(item) {{
        selectedExistingIdForSearch = item.id;
        selectedManualIndex = null;
        fields.query.value = [item.title || item.local_name, item.year].filter(Boolean).join(" ");
        activeQuery = fields.query.value.trim();
        fields.externalSource.checked = true;
        render();
        catalogMergeResults = [item];
        catalogMergeVisibleCount = SEARCH_PAGE_SIZE;
        fields.catalogMergeSection.classList.add("active");
        fields.catalogMergeStatus.textContent = "Elegí un resultado externo y tocá Comparar para revisar diferencias.";
        renderCatalogMergeResults();
        await searchManual("all", "Buscando coincidencias en Wikipedia, IMDb y FilmAffinity...");
        fields.query.scrollIntoView({{ behavior: "smooth", block: "center" }});
      }}

      function meta(value) {{
        return value ? `<span>${{escapeHtml(value)}}</span>` : "";
      }}

      function displayTitle(item) {{
        return item.spanish_title || item.title || item.original_title || item.english_title || item.local_name || "";
      }}

      function titleSubtitle(item) {{
        const shown = normalizeText(displayTitle(item));
        const values = [
          ["Original", item.original_title],
          ["Ingles", item.english_title],
          ["Base", item.title]
        ];
        const row = values.find(([, value]) => value && normalizeText(value) !== shown);
        return row ? `${{row[0]}}: ${{row[1]}}` : "";
      }}

      function titleSearchValues(item) {{
        return [
          item.title,
          item.original_title,
          item.spanish_title,
          item.english_title,
          ...(asList(item.alternative_titles)),
          item.wikipedia_title,
          item.local_name,
          ...localFiles(item).flatMap((file) => [file.name, file.path])
        ].filter(Boolean);
      }}

      function localFiles(item) {{
        return Array.isArray(item?.local_files)
          ? item.local_files.filter((file) => file && typeof file === "object")
          : [];
      }}

      function localFilesText(item) {{
        return localFiles(item)
          .map((file) => file.name || file.path || "")
          .filter(Boolean)
          .join(", ");
      }}

      function localFileCountLabel(item) {{
        const count = localFiles(item).length;
        return count ? `${{count}} archivo${{count === 1 ? "" : "s"}}` : "";
      }}

      function asList(value) {{
        if (Array.isArray(value)) return value.filter(Boolean);
        if (typeof value === "string") return value.split(",").map((entry) => entry.trim()).filter(Boolean);
        return [];
      }}

      function firstListValue(value) {{
        return asList(value)[0] || "";
      }}

      function listText(value, limit) {{
        const list = asList(value);
        if (!list.length) return "";
        const visible = list.slice(0, limit);
        const suffix = list.length > limit ? ` y ${{list.length - limit}} mas` : "";
        return visible.join(", ") + suffix;
      }}

      function isInCatalog(value) {{
        return value === true || value === "si" || value === "sí" || value === "true";
      }}

      function hasHost(url, host) {{
        try {{
          return new URL(url).hostname.includes(host);
        }} catch {{
          return false;
        }}
      }}

      function hasExternalLink(item) {{
        return hasHost(item?.url, "wikipedia.org")
          || hasHost(item?.url, "imdb.com")
          || hasHost(item?.url, "filmaffinity.com")
          || hasHost(item?.wikipedia_url, "wikipedia.org")
          || hasHost(item?.imdb_url, "imdb.com")
          || hasHost(item?.filmaffinity_url, "filmaffinity.com");
      }}

      function isExternalResult(result) {{
        return result?.source === "wikipedia"
          || result?.source === "imdb"
          || result?.source === "filmaffinity"
          || hasHost(result?.url, "wikipedia.org")
          || hasHost(result?.url, "imdb.com")
          || hasHost(result?.url, "filmaffinity.com")
          || hasHost(result?.wikipedia_url, "wikipedia.org")
          || hasHost(result?.imdb_url, "imdb.com")
          || hasHost(result?.filmaffinity_url, "filmaffinity.com");
      }}

      function linkCounts() {{
        const withLink = items.filter(hasExternalLink).length;
        return {{
          withLink,
          withoutLink: items.length - withLink,
          total: items.length
        }};
      }}

      function normalizeKind(value) {{
        const text = String(value || "pelicula").toLowerCase();
        if (["movie", "film", "película"].includes(text)) return "pelicula";
        if (["series", "tv series", "tvseries"].includes(text)) return "serie";
        if (["documentary"].includes(text)) return "documental";
        return ["pelicula", "serie", "anime", "documental"].includes(text) ? text : "pelicula";
      }}

      function normalizeRating(value) {{
        const rating = Number.parseInt(value || 0, 10);
        if (Number.isNaN(rating)) return 0;
        return Math.max(0, Math.min(10, rating));
      }}

      function todayLocalDate() {{
        const date = new Date();
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
        return date.toISOString().slice(0, 10);
      }}

      function escapeHtml(value) {{
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({{
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#039;"
        }}[char]));
      }}

      function escapeAttr(value) {{
        return escapeHtml(value).replace(/`/g, "&#096;");
      }}
    </script>
  </body>
</html>
"""


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


if __name__ == "__main__":
    raise SystemExit(main())
