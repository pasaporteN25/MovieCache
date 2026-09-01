"""Owner-only operational endpoints for optional external integrations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.curation_history import CurationHistoryError
from movie_inbox.application.curation_workflow import CurationConflict
from movie_inbox.application.external_retirement import ExternalRetirementConflict
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.web.dependencies import authorized_json, require_owner, require_token
from movie_inbox.web.responses import error_response

router = APIRouter()


@router.get(
    "/api/integrations/tmdb/retirement/preview",
    dependencies=[Depends(require_token)],
)
def tmdb_retirement_preview(request: Request) -> JSONResponse:
    require_owner(request)
    try:
        return JSONResponse(request.app.state.tmdb_retirement_service.preview())
    except (CatalogRepositoryError, CurationHistoryError, OSError):
        return error_response("tmdb_retirement_unavailable", 503)


@router.get(
    "/api/integrations/tmdb/retirement/history",
    dependencies=[Depends(require_token)],
)
def tmdb_retirement_history(request: Request) -> JSONResponse:
    require_owner(request)
    try:
        return JSONResponse(request.app.state.tmdb_retirement_service.history())
    except (CurationHistoryError, OSError):
        return error_response("tmdb_retirement_history_unavailable", 503)


@router.post("/api/integrations/tmdb/retirement/purge")
def purge_tmdb_metadata(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    try:
        result = request.app.state.tmdb_retirement_service.purge(
            str(body.get("preview_id") or ""),
            confirmed=body.get("confirmed") is True,
        )
        return JSONResponse({"ok": True, "reason": "tmdb_metadata_purged", **result})
    except ValueError:
        return error_response("tmdb_retirement_confirmation_required", 400)
    except ExternalRetirementConflict as error:
        reason = str(error)
        status = 404 if reason.endswith("not_found") else 409
        return error_response(reason, status)
    except (CatalogRepositoryError, CurationHistoryError, CurationConflict, OSError):
        return error_response("tmdb_retirement_failed", 503)


@router.post("/api/integrations/tmdb/retirement/undo")
def undo_tmdb_retirement(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    try:
        operation = request.app.state.tmdb_retirement_service.undo(
            str(body.get("operation_id") or "")
        )
        return JSONResponse(
            {"ok": True, "reason": "tmdb_metadata_restored", "operation": operation}
        )
    except ExternalRetirementConflict as error:
        reason = str(error)
        status = 404 if reason.endswith("not_found") else 409
        return error_response(reason, status)
    except CurationConflict:
        return error_response("tmdb_retirement_catalog_changed", 409)
    except (CatalogRepositoryError, CurationHistoryError, OSError):
        return error_response("tmdb_retirement_undo_failed", 503)


__all__ = ["router"]
