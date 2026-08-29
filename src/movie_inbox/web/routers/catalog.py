"""Colección: the personal catalog grid, item mutations, export and image cache."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from movie_inbox.application.curation_workflow import CatalogPointer, CurationConflict
from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.application.library_repository import LibraryRepositoryError
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.infrastructure.export import catalog_csv_text
from movie_inbox.infrastructure.external_catalog import external_sources_snapshot
from movie_inbox.infrastructure.schema import SCHEMA_VERSION, catalog_document
from movie_inbox.web.catalog_api import (
    append_item,
    background_enrich_catalog_item,
    catalog_service,
    curation_counts,
    delete_item_anywhere,
    enrich_selected_result,
    has_external_link,
    item_from_search_result,
    needs_background_title_enrichment,
    resolved_files,
    update_item_catalog_status,
    update_item_kind,
    update_item_metadata,
    update_item_personal,
    update_item_status,
    write_path_for,
)
from movie_inbox.web.dependencies import (
    SessionCatalog,
    authorized_json,
    editorial_home_payload,
    history_session_id,
    request_workflow,
    requested_home_date,
    require_ready_identity,
    require_token,
    session_catalog,
    session_catalog_rows,
)
from movie_inbox.web.image_proxy import cached_image
from movie_inbox.web.responses import (
    application_error_response,
    error_response,
    operation_response,
    operation_status,
    repository_error_response,
)
from movie_inbox.web.security import UnsafeRemoteUrl, validate_public_http_url

router = APIRouter()


@router.get("/api/items", dependencies=[Depends(require_token)])
def items(
    request: Request,
    home_date: str = Query(default=""),
) -> JSONResponse:
    try:
        day = requested_home_date(request, home_date)
    except ValueError:
        return error_response("invalid_home_date", 400)
    privacy_service = request.app.state.privacy_service
    library_service = request.app.state.library_service
    image_warmer = request.app.state.image_warmer
    try:
        identity = require_ready_identity(request)
        catalog, catalog_rows, rows = session_catalog_rows(request, identity)
        preferences = privacy_service.preferences(identity)
        home = editorial_home_payload(request, identity, rows, day)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)
    with_link = sum(1 for item in rows if has_external_link(item))
    duplicate_items = sum(1 for item in rows if int(item.get("_duplicate_count") or 0) > 0)
    scanner_pending = 0
    if identity.user.is_owner:
        try:
            scanner_pending = len(library_service.review_queue())
        except LibraryRepositoryError:
            scanner_pending = 0
    image_warmer.register_items(f"catalog:{identity.catalog.id}", catalog_rows)
    print(
        f"[catalog-viewer] items loaded total={len(rows)} with_link={with_link} "
        f"without_link={len(rows) - with_link} duplicate_items={duplicate_items}",
        flush=True,
    )
    return JSONResponse(
        {
            "items": rows,
            "sources": list(catalog.source_names),
            "write_json": catalog.write_name,
            "schema_version": SCHEMA_VERSION,
            "duplicate_items": duplicate_items,
            "links": {"with_link": with_link, "without_link": len(rows) - with_link},
            "curation": {"counts": {**curation_counts(rows), "scanner": scanner_pending}},
            "external": external_sources_snapshot(),
            "privacy": preferences.to_dict(),
            "home": home,
        }
    )


@router.get("/api/image-cache/status", dependencies=[Depends(require_token)])
def image_cache_status(request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    image_warmer = request.app.state.image_warmer
    return JSONResponse(
        image_warmer.status(
            f"catalog:{identity.catalog.id}",
            include_global=identity.user.is_owner,
        )
    )


@router.get("/api/catalog/export", dependencies=[Depends(require_token)])
def export_catalog(
    request: Request,
    export_format: str = Query(default="json", alias="format"),
) -> Response:
    export_format = export_format.strip().casefold()
    if export_format not in {"json", "csv"}:
        return error_response("unsupported_export_format", 400)
    try:
        identity = require_ready_identity(request)
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        rows = [
            item
            for source_path in resolved_files(catalog.config.patterns)
            for item in catalog_service(Path(source_path)).list_items()
        ]
    except CatalogRepositoryError as error:
        return repository_error_response(error)

    stamp = datetime.now(UTC).date().isoformat()
    filename = f"movie-inbox-{identity.user.username.casefold()}-{stamp}.{export_format}"
    headers = {
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    if export_format == "csv":
        # The BOM keeps accented titles readable in spreadsheet apps on Windows.
        return Response(
            content=chr(0xFEFF) + catalog_csv_text(rows),
            media_type="text/csv",
            headers=headers,
        )
    document = catalog_document([item.to_dict() for item in rows])
    return Response(
        content=json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        media_type="application/json",
        headers=headers,
    )


@router.get("/image-cache")
def image_cache(request: Request, url: str = "") -> Response:
    config = request.app.state.viewer_config
    image_warmer = request.app.state.image_warmer
    if not url:
        return error_response("missing_image_url", 400)
    if not config.image_cache:
        try:
            validated_url = validate_public_http_url(url, allowed_hosts=config.image_allowed_hosts)
        except UnsafeRemoteUrl:
            return error_response("invalid_image_url", 400)
        return RedirectResponse(validated_url, status_code=302)
    try:
        with image_warmer.foreground(url):
            body, content_type = cached_image(config, url)
    except UnsafeRemoteUrl:
        return error_response("invalid_image_url", 400)
    except (ValueError, HTTPError, URLError, TimeoutError, OSError):
        return error_response("image_fetch_failed", 502)
    return Response(
        body,
        headers={
            "Content-Type": content_type,
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@router.post("/api/add")
def add(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        selected_result = body.get("result")
        result = selected_result if isinstance(selected_result, dict) else body
        result = enrich_selected_result(result)
        item = item_from_search_result(result)
        write_path = write_path_for(
            catalog.config,
            catalog.source_path(str(body.get("target_source_file") or "")),
        )
        target_id = str(body.get("target_id") or "")
        added, reason, extra = append_item(
            write_path,
            item,
            action=str(body.get("action") or "check"),
            target_id=target_id,
            expected_source=str(body.get("expected_source") or ""),
        )
        if reason == "strong_match":
            existing_id = str(extra.get("existing_id") or "")
            try:
                merge_result = request_workflow(request).auto_merge_on_add(
                    CatalogPointer(write_path, existing_id),
                    item,
                    history_mode="persistent",
                    session_id=history_session_id(request),
                )
                added, reason, target_id = True, "merged_into_existing", existing_id
                extra = {"operation": merge_result["operation"]}
                item = merge_result["item"]
            except CurationConflict:
                added, reason, extra = append_item(
                    write_path,
                    item,
                    action="force",
                    expected_source=str(body.get("expected_source") or ""),
                )
        background_enrichment = "not_needed"
        if (
            added
            and reason in {"added", "merged", "merged_into_existing"}
            and needs_background_title_enrichment(item)
        ):
            effective_item_id = (
                target_id
                if reason in {"merged", "merged_into_existing"}
                else str(item.get("id") or "")
            )
            background_tasks.add_task(
                background_enrich_catalog_item,
                write_path,
                effective_item_id,
                item,
            )
            background_enrichment = "scheduled"
        return JSONResponse(
            {
                "ok": added,
                "reason": reason,
                "item": item,
                "background_enrichment": background_enrichment,
                **extra,
            },
            status_code=operation_status(added, reason),
        )
    except (ValueError, CatalogRepositoryError) as error:
        return application_error_response(error)


@router.post("/api/delete")
def delete(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        deleted, reason = delete_item_anywhere(
            catalog.config,
            source_file=catalog.source_path(str(body.get("source_file") or "")),
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


@router.post("/api/status")
def status(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        updated, reason = update_item_status(
            write_path_for(
                catalog.config,
                catalog.source_path(str(body.get("source_file") or "")),
            ),
            item_id=str(body.get("id") or ""),
            status=str(body.get("status") or ""),
            watched_at=str(body.get("watched_at") or ""),
        )
        return operation_response(updated, reason)
    except (ValueError, CatalogRepositoryError) as error:
        return application_error_response(error)


@router.post("/api/kind")
def kind(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        updated, reason = update_item_kind(
            write_path_for(
                catalog.config,
                catalog.source_path(str(body.get("source_file") or "")),
            ),
            item_id=str(body.get("id") or ""),
            kind=str(body.get("kind") or ""),
        )
        return operation_response(updated, reason)
    except (ValueError, CatalogRepositoryError) as error:
        return application_error_response(error)


@router.post("/api/catalog")
def catalog(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    try:
        session = session_catalog(request)
        updated, reason = update_item_catalog_status(
            write_path_for(
                session.config,
                session.source_path(str(body.get("source_file") or "")),
            ),
            item_id=str(body.get("id") or ""),
            en_catalogo=body.get("en_catalogo"),
        )
        return operation_response(updated, reason)
    except (ValueError, CatalogRepositoryError) as error:
        return application_error_response(error)


@router.post("/api/personal")
def personal(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        updated, reason = update_item_personal(
            write_path_for(
                catalog.config,
                catalog.source_path(str(body.get("source_file") or "")),
            ),
            item_id=str(body.get("id") or ""),
            watched_at=str(body.get("watched_at") or ""),
            rating=body.get("rating"),
            review=str(body.get("review") or ""),
        )
        return operation_response(updated, reason)
    except (ValueError, CatalogRepositoryError) as error:
        return application_error_response(error)


@router.post("/api/metadata")
def metadata(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        raw_values = body.get("values")
        values = raw_values if isinstance(raw_values, dict) else {}
        updated, reason = update_item_metadata(
            write_path_for(
                catalog.config,
                catalog.source_path(str(body.get("source_file") or "")),
            ),
            item_id=str(body.get("id") or ""),
            values=values,
            locked_fields=body.get("locked_fields"),
        )
        return operation_response(updated, reason)
    except (ValueError, CatalogRepositoryError) as error:
        return application_error_response(error)
