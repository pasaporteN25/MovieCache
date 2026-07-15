"""HTTP request handlers for the local catalog viewer."""

from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from movie_inbox.infrastructure.external_catalog import external_sources_snapshot
from movie_inbox.application.repository import (
    CatalogBusyError,
    CatalogFormatError,
    CatalogRepositoryError,
)
from movie_inbox.infrastructure.schema import SCHEMA_VERSION
from movie_inbox.web.assets import render_html, static_asset
from movie_inbox.web.catalog_api import (
    append_item,
    delete_item_anywhere,
    enrich_selected_result,
    has_external_link,
    item_from_search_result,
    load_items,
    resolved_files,
    search_sources,
    update_item_catalog_status,
    update_item_kind,
    update_item_metadata,
    update_item_personal,
    update_item_status,
    write_path_for,
)
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.image_proxy import cached_image
from movie_inbox.web.security import UnsafeRemoteUrl, validate_public_http_url


MAX_JSON_BODY_BYTES = 2 * 1024 * 1024


def make_handler(config: ViewerConfig) -> type[BaseHTTPRequestHandler]:
    class CatalogHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if not self.authorize_host():
                return
            path = urlparse(self.path).path
            if path == "/":
                self.respond_html(render_html(config.title, config.api_token))
                return
            if path.startswith("/static/"):
                asset = static_asset(path.removeprefix("/static/"))
                if not asset:
                    self.send_error(404, "Static asset not found")
                    return
                body, content_type = asset
                self.respond(body, content_type)
                return
            if path.startswith("/api/") and not self.authorize_token():
                return
            if path == "/api/items":
                try:
                    items = load_items(config.patterns)
                except CatalogRepositoryError as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
                    return
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
                    "external": external_sources_snapshot(),
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
                payload = {"results": results, "external": external_sources_snapshot()}
                self.respond_json(payload)
                return
            if path == "/api/source-health":
                payload = {"external": external_sources_snapshot()}
                self.respond_json(payload)
                return
            if path == "/image-cache":
                params = parse_qs(urlparse(self.path).query)
                if not self.authorize_token(params.get("token", [""])[0]):
                    return
                self.respond_cached_image(params.get("url", [""])[0])
                return
            self.send_error(404, "Not found")

        def do_POST(self) -> None:
            if not self.authorize_host() or not self.authorize_post():
                return
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
                    self.respond_json({"ok": added, "reason": reason, "item": item, **extra}, operation_status(added, reason))
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
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
                    self.respond_json({"ok": deleted, "reason": reason}, operation_status(deleted, reason))
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
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
                    self.respond_json({"ok": updated, "reason": reason}, operation_status(updated, reason))
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
                return
            if path == "/api/kind":
                try:
                    body = self.read_json_body()
                    updated, reason = update_item_kind(
                        write_path_for(config, str(body.get("source_file") or "")),
                        item_id=str(body.get("id") or ""),
                        kind=str(body.get("kind") or ""),
                    )
                    self.respond_json({"ok": updated, "reason": reason}, operation_status(updated, reason))
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
                return
            if path == "/api/catalog":
                try:
                    body = self.read_json_body()
                    updated, reason = update_item_catalog_status(
                        write_path_for(config, str(body.get("source_file") or "")),
                        item_id=str(body.get("id") or ""),
                        en_catalogo=body.get("en_catalogo"),
                    )
                    self.respond_json({"ok": updated, "reason": reason}, operation_status(updated, reason))
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
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
                    self.respond_json({"ok": updated, "reason": reason}, operation_status(updated, reason))
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
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
                    self.respond_json({"ok": updated, "reason": reason}, operation_status(updated, reason))
                except (ValueError, CatalogRepositoryError) as error:
                    self.respond_json({"ok": False, "reason": str(error)}, exception_status(error))
                return
            self.send_error(404, "Not found")

        def do_OPTIONS(self) -> None:
            self.send_error(405, "CORS is not enabled")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def read_json_body(self) -> dict[str, Any]:
            content_type = self.headers.get_content_type()
            if content_type != "application/json":
                raise ValueError("Content-Type must be application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise ValueError("Invalid Content-Length") from error
            if length <= 0 or length > MAX_JSON_BODY_BYTES:
                raise ValueError("JSON body is empty or too large")
            raw = self.rfile.read(length).decode("utf-8")
            data = json.loads(raw or "{}")
            if not isinstance(data, dict):
                raise ValueError("Invalid JSON body")
            return data

        def respond_html(self, body: str) -> None:
            self.respond(body.encode("utf-8"), "text/html; charset=utf-8")

        def respond_json(self, payload: dict[str, Any], status: int = 200) -> None:
            self.respond(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

        def respond(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data: https:; style-src 'self'; "
                "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
                "base-uri 'none'; form-action 'self'",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def authorize_host(self) -> bool:
            host = str(self.headers.get("Host") or "").strip().casefold()
            port = int(self.server.server_address[1])
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if host not in allowed:
                self.respond_json({"ok": False, "reason": "invalid_host"}, 403)
                return False
            return True

        def authorize_token(self, query_token: str = "") -> bool:
            supplied = query_token or str(self.headers.get("X-Movie-Inbox-Token") or "")
            if not supplied or not secrets.compare_digest(supplied, config.api_token):
                self.respond_json({"ok": False, "reason": "invalid_token"}, 403)
                return False
            return True

        def authorize_post(self) -> bool:
            if not self.authorize_token():
                return False
            origin = str(self.headers.get("Origin") or "").strip().casefold()
            port = int(self.server.server_address[1])
            allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
            if origin not in allowed:
                self.respond_json({"ok": False, "reason": "invalid_origin"}, 403)
                return False
            return True

        def respond_cached_image(self, image_url: str) -> None:
            if not image_url:
                self.send_error(400, "Missing image URL")
                return
            try:
                validated_url = validate_public_http_url(image_url)
            except UnsafeRemoteUrl:
                self.send_error(400, "Invalid image URL")
                return
            if not config.image_cache:
                self.redirect(validated_url)
                return
            try:
                body, content_type = cached_image(config, validated_url)
            except (ValueError, UnsafeRemoteUrl, HTTPError, URLError, TimeoutError, OSError):
                self.send_error(502, "Image could not be fetched safely")
                return

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def redirect(self, location: str) -> None:
            self.send_response(302)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

    return CatalogHandler


def operation_status(ok: bool, reason: str) -> int:
    if ok:
        return 200
    if reason in {"duplicate", "possible_duplicate", "merge_target_not_found"}:
        return 409
    if reason == "not_found":
        return 404
    return 400


def exception_status(error: Exception) -> int:
    if isinstance(error, CatalogBusyError):
        return 503
    if isinstance(error, CatalogFormatError):
        return 422
    if isinstance(error, CatalogRepositoryError):
        return 500
    return 400
