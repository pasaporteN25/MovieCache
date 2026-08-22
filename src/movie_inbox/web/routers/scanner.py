"""Managed libraries (file inventory) and the Scanner review queue."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.curation_history import CurationHistoryError
from movie_inbox.application.library_repository import (
    LibraryConflict,
    LibraryNotFound,
    LibraryRepositoryError,
    LibraryRunBusy,
)
from movie_inbox.application.library_service import LibraryPathError
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.application.scanner_workflow import ScannerWorkflowError
from movie_inbox.domain.libraries import LibraryValidationError, work_identity
from movie_inbox.web.catalog_api import (
    background_enrich_catalog_item,
    catalog_service,
    load_items,
    needs_background_title_enrichment,
    write_path_for,
)
from movie_inbox.web.dependencies import (
    authorized_json,
    history_session_id,
    require_owner,
    require_token,
    session_catalog,
)
from movie_inbox.web.responses import (
    error_response,
    repository_error_response,
    scanner_application_error_response,
)

router = APIRouter()


def _scanner_workflow(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.scanner_workflow


@router.get("/api/scanner/history", dependencies=[Depends(require_token)])
def scanner_history(request: Request, mode: str = "persistent") -> JSONResponse:
    require_owner(request)
    try:
        return JSONResponse(
            _scanner_workflow(request).history(mode, history_session_id(request))
        )
    except (ValueError, CurationHistoryError) as error:
        return scanner_application_error_response(error)


@router.post("/api/scanner/undo")
def undo_scanner_operation(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    try:
        operation = _scanner_workflow(request).undo(
            str(body.get("operation_id") or ""),
            history_mode=str(body.get("history_mode") or "persistent"),
            session_id=history_session_id(request),
        )
        return JSONResponse({"ok": True, "reason": "undone", "operation": operation})
    except (
        ValueError,
        ScannerWorkflowError,
        LibraryConflict,
        LibraryRepositoryError,
        CurationHistoryError,
    ) as error:
        return scanner_application_error_response(error)


@router.post("/api/scanner/history/clear")
def clear_scanner_history(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    try:
        count = _scanner_workflow(request).clear_history(
            str(body.get("history_mode") or "persistent"),
            history_session_id(request),
            confirmed=body.get("confirmed") is True,
        )
        return JSONResponse({"ok": True, "reason": "cleared", "cleared": count})
    except (ValueError, CurationHistoryError) as error:
        return scanner_application_error_response(error)


@router.get("/api/libraries", dependencies=[Depends(require_token)])
def managed_libraries(request: Request) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        return JSONResponse(
            {
                "configured": library_service.configured,
                "allowed_roots": [str(path) for path in library_service.allowed_roots],
                "libraries": library_service.list_libraries(),
                "queue_count": len(library_service.review_queue()),
            }
        )
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.get("/api/library-paths", dependencies=[Depends(require_token)])
def browse_library_paths(request: Request, path: str = "") -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        return JSONResponse(library_service.browse_paths(path))
    except LibraryPathError as error:
        return error_response(str(error), 400)


@router.post("/api/library-paths/check")
def check_library_path(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        return JSONResponse({"ok": True, **library_service.check_path(str(body.get("path") or ""))})
    except LibraryPathError as error:
        return error_response(str(error), 400)


@router.post("/api/libraries")
def create_managed_library(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    library_service = request.app.state.library_service
    try:
        library = library_service.create_library(identity.user.id, body)
        return JSONResponse(
            {
                "ok": True,
                "reason": "library_created",
                "library": library_service.library_payload(library),
            },
            status_code=201,
        )
    except (ValueError, LibraryValidationError, LibraryPathError) as error:
        return error_response(str(error), 400)
    except LibraryRepositoryError as error:
        return error_response(str(error), 409 if "already" in str(error).casefold() else 503)


@router.get("/api/libraries/{library_id}", dependencies=[Depends(require_token)])
def managed_library_detail(library_id: str, request: Request) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        return JSONResponse({"library": library_service.library_detail(library_id)})
    except LibraryNotFound:
        return error_response("library_not_found", 404)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.post("/api/libraries/{library_id}/update")
def update_managed_library(
    library_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        library = library_service.update_library(library_id, body)
        return JSONResponse(
            {
                "ok": True,
                "reason": "library_updated",
                "library": library_service.library_payload(library),
            }
        )
    except LibraryNotFound:
        return error_response("library_not_found", 404)
    except LibraryRunBusy:
        return error_response("library_scan_busy", 409)
    except (ValueError, LibraryValidationError) as error:
        return error_response(str(error), 400)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.post("/api/libraries/{library_id}/status")
def update_managed_library_status(
    library_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    if not isinstance(body.get("active"), bool):
        return error_response("active_must_be_boolean", 400)
    try:
        library = library_service.set_active(library_id, body["active"])
        return JSONResponse(
            {
                "ok": True,
                "reason": "library_status_updated",
                "library": library_service.library_payload(library),
            }
        )
    except LibraryNotFound:
        return error_response("library_not_found", 404)
    except LibraryRunBusy:
        return error_response("library_scan_busy", 409)
    except LibraryValidationError as error:
        return error_response(str(error), 409)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.post("/api/libraries/{library_id}/delete")
def delete_managed_library(
    library_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    if body.get("confirmed") is not True:
        return error_response("confirmation_required", 409)
    try:
        if not library_service.delete_library(library_id):
            return error_response("library_not_found", 404)
        return JSONResponse({"ok": True, "reason": "library_deleted"})
    except LibraryRunBusy:
        return error_response("library_scan_busy", 409)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.post("/api/libraries/{library_id}/runs")
def run_managed_library(
    library_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        run = library_service.queue_scan(library_id, str(body.get("mode") or "dry_run"))
        background_tasks.add_task(library_service.execute_run, run.id)
        return JSONResponse(
            {
                "ok": True,
                "reason": "library_scan_queued",
                "run": library_service.run_payload(run),
            },
            status_code=202,
        )
    except LibraryNotFound:
        return error_response("library_not_found", 404)
    except LibraryRunBusy:
        return error_response("library_scan_busy", 409)
    except (ValueError, LibraryValidationError, LibraryPathError) as error:
        return error_response(str(error), 409)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.get("/api/library-runs/{run_id}", dependencies=[Depends(require_token)])
def managed_library_run(run_id: str, request: Request) -> JSONResponse:
    require_owner(request)
    library_repository = request.app.state.library_repository
    library_service = request.app.state.library_service
    try:
        run = library_repository.get_run(run_id)
        if run is None:
            return error_response("library_run_not_found", 404)
        return JSONResponse({"run": library_service.run_payload(run)})
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.get("/api/scanner/queue", dependencies=[Depends(require_token)])
def scanner_review_queue(request: Request) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        queue = library_service.review_queue()
        return JSONResponse({"items": queue, "count": len(queue)})
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)


@router.post("/api/scanner/queue/{file_id}")
def review_scanner_item(
    file_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    library_service = request.app.state.library_service
    try:
        action = str(body.get("action") or "").strip().casefold()
        if action == "link_catalog":
            catalog_item_id = str(body.get("catalog_item_id") or "").strip()
            catalog = session_catalog(request)
            catalog_item = next(
                (
                    item
                    for item in load_items(catalog.config.patterns)
                    if str(item.get("id") or "") == catalog_item_id
                ),
                None,
            )
            if catalog_item is None:
                return error_response("catalog_item_not_found", 404)
            result = _scanner_workflow(request).review(
                file_id,
                {"action": "confirm", "identity": work_identity(catalog_item)},
                history_mode=str(body.get("history_mode") or "persistent"),
                session_id=history_session_id(request),
            )
            return JSONResponse(
                {
                    "ok": True,
                    "reason": "scanner_item_linked_to_catalog",
                    "item": result["item"],
                    "operation": result["operation"],
                    "catalog_action": "existing",
                    "catalog_item": catalog.public_payload(catalog_item),
                }
            )
        if action == "create":
            scanner_item = next(
                (
                    item
                    for item in library_service.review_queue()
                    if str(item.get("id") or "") == file_id
                ),
                None,
            )
            if scanner_item is None:
                raise LibraryNotFound("Scanner queue item was not found")
            catalog = session_catalog(request)
            write_path = write_path_for(catalog.config, "")
            created, catalog_reason, catalog_result = catalog_service(
                write_path
            ).ensure_scanner_item(
                {**body, "scanner_reference": file_id},
                comparison_items=load_items(catalog.config.patterns),
            )
            if catalog_reason == "possible_duplicate":
                return JSONResponse(
                    {
                        "ok": False,
                        "reason": catalog_reason,
                        "candidates": catalog.public_payload(catalog_result.get("candidates", [])),
                        "distinct_review_token": str(
                            catalog_result.get("distinct_review_token") or ""
                        ),
                    },
                    status_code=409,
                )
            catalog_item = catalog_result.get("item")
            if not isinstance(catalog_item, dict):
                return error_response("catalog_item_unavailable", 500)
            item = library_service.review_file(
                file_id,
                {
                    "action": "confirm",
                    "identity": work_identity(catalog_item),
                },
            )
            background_enrichment = "not_needed"
            if catalog_result.get("writable") and needs_background_title_enrichment(catalog_item):
                background_tasks.add_task(
                    background_enrich_catalog_item,
                    write_path,
                    str(catalog_item.get("id") or ""),
                    catalog_item,
                )
                background_enrichment = "scheduled"
            return JSONResponse(
                {
                    "ok": True,
                    "reason": "scanner_item_created_and_linked"
                    if created
                    else "scanner_item_reused_and_linked",
                    "item": item,
                    "catalog_action": catalog_reason,
                    "catalog_item": catalog.public_payload(catalog_item),
                    "background_enrichment": background_enrichment,
                },
                status_code=201 if created else 200,
            )
        result = _scanner_workflow(request).review(
            file_id,
            body,
            history_mode=str(body.get("history_mode") or "persistent"),
            session_id=history_session_id(request),
        )
        return JSONResponse(
            {
                "ok": True,
                "reason": "scanner_item_reviewed",
                "item": result["item"],
                "operation": result["operation"],
            }
        )
    except LibraryNotFound:
        return error_response("scanner_item_not_found", 404)
    except ValueError as error:
        return error_response(str(error), 400)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except (LibraryConflict, ScannerWorkflowError, CurationHistoryError) as error:
        return scanner_application_error_response(error)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)
