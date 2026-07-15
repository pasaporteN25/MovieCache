"""FastAPI application exposing the Movie Inbox viewer and catalog API."""

from __future__ import annotations

import json
import secrets
from typing import Any
from urllib.error import HTTPError, URLError

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from movie_inbox.application.repository import (
    CatalogBusyError,
    CatalogFormatError,
    CatalogRepositoryError,
)
from movie_inbox.infrastructure.external_catalog import external_sources_snapshot
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
from movie_inbox.web.security import (
    UnsafeRemoteUrl,
    validate_public_http_url,
    viewer_allowed_hosts,
    viewer_allowed_origins,
)


MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
SESSION_COOKIE = "movie_inbox_session"
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class ApiRequestError(ValueError):
    def __init__(self, reason: str, status_code: int = 400) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


def create_app(config: ViewerConfig) -> FastAPI:
    app = FastAPI(
        title="Movie Inbox",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.viewer_config = config
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=viewer_allowed_hosts(config.public_origin))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(ApiRequestError)
    async def api_request_error(_: Request, error: ApiRequestError) -> JSONResponse:
        return error_response(error.reason, error.status_code)

    def require_token(request: Request) -> None:
        supplied = str(request.headers.get("X-Movie-Inbox-Token") or "")
        if not supplied or not secrets.compare_digest(supplied, config.api_token):
            raise ApiRequestError("invalid_token", 403)

    def require_origin(request: Request) -> None:
        origin = str(request.headers.get("Origin") or "").strip().casefold()
        if origin not in viewer_allowed_origins(config.port, config.public_origin):
            raise ApiRequestError("invalid_origin", 403)

    async def authorized_json(request: Request) -> dict[str, Any]:
        require_token(request)
        require_origin(request)
        return await read_json_object(request)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        response = HTMLResponse(render_html(config.title, config.api_token))
        response.set_cookie(
            SESSION_COOKIE,
            config.api_token,
            httponly=True,
            secure=config.public_origin.casefold().startswith("https://"),
            samesite="strict",
            path="/",
        )
        return response

    @app.get("/static/{name:path}")
    def static(name: str) -> Response:
        asset = static_asset(name)
        if not asset:
            return error_response("static_asset_not_found", 404)
        body, content_type = asset
        return Response(body, headers={"Content-Type": content_type})

    @app.get("/api/items", dependencies=[Depends(require_token)])
    def items() -> JSONResponse:
        try:
            rows = load_items(config.patterns)
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        with_link = sum(1 for item in rows if has_external_link(item))
        duplicate_items = sum(1 for item in rows if int(item.get("_duplicate_count") or 0) > 0)
        print(
            f"[catalog-viewer] items loaded total={len(rows)} with_link={with_link} "
            f"without_link={len(rows) - with_link} duplicate_items={duplicate_items}",
            flush=True,
        )
        return JSONResponse(
            {
                "items": rows,
                "sources": resolved_files(config.patterns),
                "write_json": config.write_json,
                "schema_version": SCHEMA_VERSION,
                "duplicate_items": duplicate_items,
                "external": external_sources_snapshot(),
            }
        )

    @app.get("/api/search", dependencies=[Depends(require_token)])
    def search(q: str = "", source: str = "all") -> JSONResponse:
        results = search_sources(q, source)
        print(
            f"[catalog-viewer] search query={q!r} source={source} "
            f"count={len(results)} result_sources={sorted(set(str(result.get('source') or '') for result in results))}",
            flush=True,
        )
        return JSONResponse({"results": results, "external": external_sources_snapshot()})

    @app.get("/api/source-health", dependencies=[Depends(require_token)])
    def source_health() -> JSONResponse:
        return JSONResponse({"external": external_sources_snapshot()})

    @app.get("/image-cache")
    def image_cache(request: Request, url: str = "") -> Response:
        supplied = str(request.cookies.get(SESSION_COOKIE) or request.headers.get("X-Movie-Inbox-Token") or "")
        if not supplied or not secrets.compare_digest(supplied, config.api_token):
            return error_response("invalid_token", 403)
        if not url:
            return error_response("missing_image_url", 400)
        try:
            validated_url = validate_public_http_url(url)
        except UnsafeRemoteUrl:
            return error_response("invalid_image_url", 400)
        if not config.image_cache:
            return RedirectResponse(validated_url, status_code=302)
        try:
            body, content_type = cached_image(config, validated_url)
        except (ValueError, UnsafeRemoteUrl, HTTPError, URLError, TimeoutError, OSError):
            return error_response("image_fetch_failed", 502)
        return Response(
            body,
            headers={
                "Content-Type": content_type,
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    @app.post("/api/add")
    def add(body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
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
            return JSONResponse(
                {"ok": added, "reason": reason, "item": item, **extra},
                status_code=operation_status(added, reason),
            )
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/delete")
    def delete(body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
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
            return operation_response(deleted, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/status")
    def status(body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            updated, reason = update_item_status(
                write_path_for(config, str(body.get("source_file") or "")),
                item_id=str(body.get("id") or ""),
                status=str(body.get("status") or ""),
                watched_at=str(body.get("watched_at") or ""),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/kind")
    def kind(body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            updated, reason = update_item_kind(
                write_path_for(config, str(body.get("source_file") or "")),
                item_id=str(body.get("id") or ""),
                kind=str(body.get("kind") or ""),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/catalog")
    def catalog(body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            updated, reason = update_item_catalog_status(
                write_path_for(config, str(body.get("source_file") or "")),
                item_id=str(body.get("id") or ""),
                en_catalogo=body.get("en_catalogo"),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/personal")
    def personal(body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            updated, reason = update_item_personal(
                write_path_for(config, str(body.get("source_file") or "")),
                item_id=str(body.get("id") or ""),
                watched_at=str(body.get("watched_at") or ""),
                rating=body.get("rating"),
                review=str(body.get("review") or ""),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/metadata")
    def metadata(body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            updated, reason = update_item_metadata(
                write_path_for(config, str(body.get("source_file") or "")),
                item_id=str(body.get("id") or ""),
                values=body.get("values") if isinstance(body.get("values"), dict) else {},
                locked_fields=body.get("locked_fields"),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    return app


async def read_json_object(request: Request) -> dict[str, Any]:
    content_type = str(request.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        raise ApiRequestError("Content-Type must be application/json")
    content_length = str(request.headers.get("Content-Length") or "").strip()
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as error:
            raise ApiRequestError("Invalid Content-Length") from error
        if declared_length <= 0 or declared_length > MAX_JSON_BODY_BYTES:
            raise ApiRequestError("JSON body is empty or too large")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_JSON_BODY_BYTES:
            raise ApiRequestError("JSON body is empty or too large")
        chunks.append(chunk)
    if total <= 0:
        raise ApiRequestError("JSON body is empty or too large")
    try:
        data = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApiRequestError("Invalid JSON body") from error
    if not isinstance(data, dict):
        raise ApiRequestError("Invalid JSON body")
    return data


def operation_response(ok: bool, reason: str) -> JSONResponse:
    return JSONResponse({"ok": ok, "reason": reason}, status_code=operation_status(ok, reason))


def operation_status(ok: bool, reason: str) -> int:
    if ok:
        return 200
    if reason in {"duplicate", "possible_duplicate", "merge_target_not_found"}:
        return 409
    if reason == "not_found":
        return 404
    return 400


def application_error_response(error: Exception) -> JSONResponse:
    if isinstance(error, CatalogRepositoryError):
        return repository_error_response(error)
    return error_response(str(error), 400)


def repository_error_response(error: CatalogRepositoryError) -> JSONResponse:
    if isinstance(error, CatalogBusyError):
        status = 503
    elif isinstance(error, CatalogFormatError):
        status = 422
    else:
        status = 500
    return error_response(str(error), status)


def error_response(reason: str, status_code: int) -> JSONResponse:
    return JSONResponse({"ok": False, "reason": reason}, status_code=status_code)
