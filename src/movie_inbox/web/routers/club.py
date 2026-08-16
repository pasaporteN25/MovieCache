"""Club: shared member catalogs and the curated collections owners publish."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.application.collection_service import CollectionItemNotFound, CollectionNotFound
from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.application.library_repository import LibraryRepositoryError
from movie_inbox.application.privacy_service import SharedCatalogUnavailable
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.web.catalog_api import catalog_service, load_items
from movie_inbox.web.dependencies import (
    SessionCatalog,
    authorized_json,
    require_ready_identity,
    require_token,
)
from movie_inbox.web.responses import error_response, repository_error_response

router = APIRouter()


@router.get("/api/community", dependencies=[Depends(require_token)])
def community(request: Request) -> JSONResponse:
    privacy_service = request.app.state.privacy_service
    try:
        identity = require_ready_identity(request)
        return JSONResponse({"catalogs": privacy_service.shared_catalogs(identity)})
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.get("/api/community/{user_id}", dependencies=[Depends(require_token)])
def shared_catalog(user_id: str, request: Request) -> JSONResponse:
    privacy_service = request.app.state.privacy_service
    image_warmer = request.app.state.image_warmer
    try:
        identity = require_ready_identity(request)
        payload = privacy_service.shared_catalog(identity, user_id)
        image_warmer.register_items(
            f"shared:{payload.get('catalog', {}).get('id', user_id)}",
            payload.get("items", []),
        )
        return JSONResponse(payload)
    except SharedCatalogUnavailable:
        return error_response("shared_catalog_not_found", 404)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except LibraryRepositoryError:
        return error_response("library_store_unavailable", 503)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.get("/api/collections", dependencies=[Depends(require_token)])
def collections(request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    collection_service = request.app.state.collection_service
    try:
        return JSONResponse({"collections": collection_service.list_collections(identity.user.id)})
    except CollectionRepositoryError:
        return error_response("collection_store_unavailable", 503)


@router.get("/api/collections/{collection_id}", dependencies=[Depends(require_token)])
def collection_detail(collection_id: str, request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    collection_service = request.app.state.collection_service
    image_warmer = request.app.state.image_warmer
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        rows = load_items(catalog.config.patterns)
        payload = collection_service.collection_detail(identity.user.id, collection_id, rows)
        image_warmer.register_items(f"collection:{collection_id}", payload.get("items", []))
        return JSONResponse(payload)
    except CollectionNotFound:
        return error_response("collection_not_found", 404)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except CollectionRepositoryError:
        return error_response("collection_store_unavailable", 503)


@router.post("/api/collections/{collection_id}/follow")
def follow_collection(
    collection_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    collection_service = request.app.state.collection_service
    if not isinstance(body.get("following"), bool):
        return error_response("following_must_be_boolean", 400)
    try:
        return JSONResponse(
            collection_service.set_following(
                identity.user.id,
                collection_id,
                bool(body["following"]),
            )
        )
    except CollectionNotFound:
        return error_response("collection_not_found", 404)
    except CollectionRepositoryError:
        return error_response("collection_store_unavailable", 503)


@router.post("/api/collections/{collection_id}/add")
def add_collection_items(
    collection_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    collection_service = request.app.state.collection_service
    item_ids = body.get("item_ids")
    if not isinstance(item_ids, list) or any(not isinstance(value, str) for value in item_ids):
        return error_response("item_ids_must_be_an_array_of_strings", 400)
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        result = collection_service.add_to_catalog(
            identity.user.id,
            collection_id,
            item_ids,
            catalog_service(Path(catalog.config.write_json)),
            load_items(catalog.config.patterns),
        )
        return JSONResponse(result)
    except CollectionNotFound:
        return error_response("collection_not_found", 404)
    except CollectionItemNotFound:
        return error_response("collection_item_not_found", 404)
    except ValueError as error:
        return error_response(str(error), 400)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except CollectionRepositoryError:
        return error_response("collection_store_unavailable", 503)
