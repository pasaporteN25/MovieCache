"""[U7 B] A work's image candidates and on-demand fill, for the viewer's own catalogue.

Both routes look the work up only inside the session's catalogue, so a Club work
or another member's work answers 404 like any unknown id. Candidates are asked
live and never stored; fill completes empty, unlocked image fields only.
Contract: `docs/analisis/u7b-contrato-imagenes-2026-09-26.md`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.external.tmdb import TMDB_ATTRIBUTION_NOTICE
from movie_inbox.web.catalog_api import catalog_service, load_items, write_path_for
from movie_inbox.web.dependencies import authorized_json, require_token, session_catalog
from movie_inbox.web.responses import application_error_response, error_response

router = APIRouter()


@router.get("/api/items/{item_id}/image-candidates", dependencies=[Depends(require_token)])
def image_candidates(request: Request, item_id: str) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        item = next(
            (row for row in load_items(catalog.config.patterns) if row.get("id") == item_id),
            None,
        )
    except CatalogRepositoryError:
        return error_response("catalog_unavailable", 503)
    if item is None:
        return error_response("not_found", 404)
    answer = request.app.state.image_service.candidates(item)
    answer["attribution"] = TMDB_ATTRIBUTION_NOTICE if answer["identity"] else ""
    return JSONResponse(answer)


@router.post("/api/items/{item_id}/images/fill")
def fill_images(
    request: Request, item_id: str, body: dict[str, Any] = Depends(authorized_json)
) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        path = write_path_for(
            catalog.config, catalog.source_path(str(body.get("source_file") or ""))
        )
        result = request.app.state.image_service.fill(catalog_service(path), item_id)
    except (ValueError, CatalogRepositoryError) as error:
        return application_error_response(error)
    if result["status"] == "not_found":
        return error_response("not_found", 404)
    return JSONResponse(result)
