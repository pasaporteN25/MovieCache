"""Daily editorial home programming."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.application.library_repository import LibraryRepositoryError
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.web.dependencies import (
    editorial_home_payload,
    requested_home_date,
    require_ready_identity,
    require_token,
    session_catalog_rows,
)
from movie_inbox.web.responses import error_response, repository_error_response

router = APIRouter()


@router.get("/api/home", dependencies=[Depends(require_token)])
def editorial_home(
    request: Request,
    local_date: str = Query(default="", alias="date"),
    saved_featured: bool = Query(default=False),
) -> JSONResponse:
    try:
        day = requested_home_date(request, local_date)
    except ValueError:
        return error_response("invalid_home_date", 400)
    try:
        identity = require_ready_identity(request)
        _, _, rows = session_catalog_rows(request, identity)
        return JSONResponse(
            editorial_home_payload(
                request,
                identity,
                rows,
                day,
                saved_featured=saved_featured,
            )
        )
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)
