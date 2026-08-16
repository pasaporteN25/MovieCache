"""Private import drafts: preview, classify and apply TXT/CSV/JSON uploads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.application.import_service import (
    ImportDraftBusy,
    ImportDraftExpired,
    ImportDraftLimit,
    ImportDraftNotFound,
    ImportPermissionError,
)
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.infrastructure.import_parsers import ImportParseError
from movie_inbox.infrastructure.import_repository import ImportRepositoryError
from movie_inbox.web.catalog_api import catalog_service, load_items
from movie_inbox.web.dependencies import (
    SessionCatalog,
    authorized_import_json,
    authorized_json,
    require_ready_identity,
    require_token,
)
from movie_inbox.web.responses import error_response, repository_error_response

router = APIRouter()


@router.get("/api/imports", dependencies=[Depends(require_token)])
def import_drafts(request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    import_service = request.app.state.import_service
    try:
        return JSONResponse({"drafts": import_service.list_drafts(identity.user.id)})
    except ImportRepositoryError:
        return error_response("import_store_unavailable", 503)


@router.post("/api/imports")
def create_import_draft(
    request: Request,
    body: dict[str, Any] = Depends(authorized_import_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    import_service = request.app.state.import_service
    column_map = body.get("column_map")
    if column_map is not None and (
        not isinstance(column_map, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in column_map.items()
        )
    ):
        return error_response("column_map_must_be_an_object_of_strings", 400)
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        draft = import_service.create_draft(
            identity.user.id,
            str(body.get("source_name") or "importacion"),
            str(body.get("source_format") or "auto"),
            body.get("content") if isinstance(body.get("content"), str) else "",
            column_map,
            load_items(catalog.config.patterns),
        )
        return JSONResponse(draft, status_code=201)
    except ImportParseError as error:
        return error_response(str(error), 422)
    except ImportDraftLimit:
        return error_response("import_draft_limit_reached", 409)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except ImportRepositoryError:
        return error_response("import_store_unavailable", 503)


@router.get("/api/imports/{draft_id}", dependencies=[Depends(require_token)])
def import_draft_detail(draft_id: str, request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    import_service = request.app.state.import_service
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        return JSONResponse(
            import_service.draft_detail(
                identity.user.id,
                draft_id,
                load_items(catalog.config.patterns),
            )
        )
    except ImportDraftNotFound:
        return error_response("import_draft_not_found", 404)
    except ImportDraftExpired:
        return error_response("import_draft_expired", 410)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except ImportRepositoryError:
        return error_response("import_store_unavailable", 503)


@router.post("/api/imports/{draft_id}/delete")
def delete_import_draft(
    draft_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    import_service = request.app.state.import_service
    try:
        deleted = import_service.delete_draft(
            identity.user.id,
            draft_id,
            body.get("confirmed") is True,
        )
        return JSONResponse({"ok": deleted, "reason": "deleted" if deleted else "not_found"})
    except ImportDraftNotFound:
        return error_response("import_draft_not_found", 404)
    except ImportDraftBusy:
        return error_response("import_draft_busy", 409)
    except ValueError as error:
        return error_response(str(error), 400)
    except ImportRepositoryError:
        return error_response("import_store_unavailable", 503)


@router.post("/api/imports/{draft_id}/apply")
def apply_import_draft(
    draft_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    import_service = request.app.state.import_service
    item_ids = body.get("item_ids")
    personal_options = body.get("personal_options")
    if not isinstance(item_ids, list) or any(not isinstance(value, str) for value in item_ids):
        return error_response("item_ids_must_be_an_array_of_strings", 400)
    if personal_options is not None and not isinstance(personal_options, dict):
        return error_response("personal_options_must_be_an_object", 400)
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        result = import_service.apply_draft(
            identity.user.id,
            draft_id,
            str(body.get("destination") or "catalog"),
            item_ids,
            catalog_service(Path(catalog.config.write_json)),
            load_items(catalog.config.patterns),
            personal_options=personal_options,
            collection_title=str(body.get("collection_title") or ""),
            collection_description=str(body.get("collection_description") or ""),
            can_create_collection=identity.user.is_owner,
        )
        return JSONResponse(result)
    except ImportDraftNotFound:
        return error_response("import_draft_not_found", 404)
    except ImportDraftExpired:
        return error_response("import_draft_expired", 410)
    except ImportDraftBusy:
        return error_response("import_draft_busy", 409)
    except ImportPermissionError:
        return error_response("owner_required_for_collection_import", 403)
    except (ValueError, CollectionRepositoryError) as error:
        if isinstance(error, CollectionRepositoryError):
            return error_response("collection_store_unavailable", 503)
        return error_response(str(error), 400)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except ImportRepositoryError:
        return error_response("import_store_unavailable", 503)
