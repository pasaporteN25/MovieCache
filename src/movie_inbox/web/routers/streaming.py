"""Streaming back office: markets, platforms and each member's own choice.

Owner-only endpoints configure what the instance consults. The member endpoints
only ever read and write the caller's own preferences, never another account's.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.streaming_repository import (
    StreamingRegionNotFound,
    StreamingRepositoryError,
)
from movie_inbox.application.streaming_service import (
    StreamingAuthorizationError,
    StreamingSourceUnavailable,
)
from movie_inbox.domain.streaming import StreamingConfigurationError
from movie_inbox.web.dependencies import (
    authorized_json,
    require_owner,
    require_ready_identity,
    require_token,
)
from movie_inbox.web.responses import error_response

router = APIRouter()


@router.get("/api/streaming/configuration", dependencies=[Depends(require_token)])
def streaming_configuration(request: Request) -> JSONResponse:
    require_owner(request)
    service = request.app.state.streaming_service
    try:
        payload = service.configuration()
    except StreamingRepositoryError:
        return error_response("streaming_unavailable", 503)
    payload["upstream_configured"] = service.upstream_configured
    return JSONResponse(payload)


@router.get("/api/streaming/upstream-regions", dependencies=[Depends(require_token)])
def upstream_regions(request: Request) -> JSONResponse:
    require_owner(request)
    service = request.app.state.streaming_service
    try:
        return JSONResponse({"regions": service.available_upstream_regions()})
    except StreamingSourceUnavailable:
        return error_response("streaming_source_not_configured", 409)
    except (OSError, ValueError):
        # The upstream is a network call: a failure here is an availability
        # problem, not a bad request from the owner.
        return error_response("streaming_source_unavailable", 502)


@router.post("/api/streaming/regions")
def add_region(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    require_owner(request)
    service = request.app.state.streaming_service
    try:
        return JSONResponse({"region": service.add_region(body).to_dict()})
    except StreamingConfigurationError:
        return error_response("invalid_region", 400)
    except StreamingRepositoryError:
        return error_response("streaming_unavailable", 503)


@router.post("/api/streaming/regions/{code}/status")
def set_region_status(
    code: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    require_owner(request)
    service = request.app.state.streaming_service
    try:
        region = service.set_region_enabled(code, bool(body.get("enabled")))
    except StreamingRegionNotFound:
        return error_response("region_not_found", 404)
    except StreamingConfigurationError:
        return error_response("invalid_region", 400)
    except StreamingRepositoryError:
        return error_response("streaming_unavailable", 503)
    return JSONResponse({"region": region.to_dict()})


@router.post("/api/streaming/policy")
def set_policy(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
    require_owner(request)
    service = request.app.state.streaming_service
    try:
        return JSONResponse({"policy": service.set_policy(body).to_dict()})
    except StreamingConfigurationError:
        return error_response("invalid_policy", 400)
    except StreamingRepositoryError:
        return error_response("streaming_unavailable", 503)


@router.post("/api/streaming/regions/{code}/providers/refresh")
def refresh_providers(code: str, request: Request) -> JSONResponse:
    require_owner(request)
    service = request.app.state.streaming_service
    try:
        providers = service.refresh_providers(code)
    except StreamingSourceUnavailable:
        return error_response("streaming_source_not_configured", 409)
    except StreamingRegionNotFound:
        return error_response("region_not_found", 404)
    except StreamingConfigurationError:
        return error_response("invalid_provider", 400)
    except StreamingRepositoryError:
        return error_response("streaming_unavailable", 503)
    except (OSError, ValueError):
        return error_response("streaming_source_unavailable", 502)
    return JSONResponse({"providers": [provider.to_dict() for provider in providers]})


@router.get("/api/streaming/preferences", dependencies=[Depends(require_token)])
def streaming_preferences(request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    service = request.app.state.streaming_service
    try:
        return JSONResponse(service.preferences_for(identity))
    except StreamingRepositoryError:
        return error_response("streaming_unavailable", 503)


@router.post("/api/streaming/preferences")
def update_streaming_preferences(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    service = request.app.state.streaming_service
    try:
        preferences = service.update_preferences(identity, body)
    except StreamingAuthorizationError:
        return error_response("region_choice_not_allowed", 403)
    except StreamingConfigurationError:
        return error_response("invalid_preferences", 400)
    except StreamingRepositoryError:
        return error_response("streaming_unavailable", 503)
    return JSONResponse({"preferences": preferences.to_dict()})
