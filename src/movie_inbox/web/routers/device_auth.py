"""Authentication endpoints for native devices; never reuse browser cookie auth."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from movie_inbox.application.auth_service import (
    AuthenticationError,
    DeviceSession,
    PasswordChangeRequiredError,
)
from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.web.dependencies import device_json, require_device_identity
from movie_inbox.web.responses import DeviceApiRequestError, identity_payload

router = APIRouter()


@router.post("/api/v1/auth/login")
def login_device(request: Request, body: dict[str, Any] = Depends(device_json)) -> JSONResponse:
    username = str(body.get("username") or "")
    client_host = request.client.host if request.client else "unknown"
    limiter = request.app.state.device_login_limiter
    limiter_key = f"device:{client_host}:{username.strip().casefold()[:64]}"
    retry_after = limiter.retry_after(limiter_key)
    if retry_after:
        raise DeviceApiRequestError(
            "too_many_attempts",
            429,
            headers={"Retry-After": str(retry_after)},
        )
    try:
        session = request.app.state.auth_service.login_device(
            username,
            str(body.get("password") or ""),
            str(body.get("device_name") or ""),
        )
    except PasswordChangeRequiredError as error:
        raise DeviceApiRequestError("password_change_required", 403) from error
    except AuthenticationError as error:
        limiter.record_failure(limiter_key)
        raise DeviceApiRequestError("invalid_credentials", 401) from error
    except ValueError as error:
        raise DeviceApiRequestError("invalid_request", 400) from error
    except IdentityRepositoryError as error:
        raise DeviceApiRequestError("identity_store_unavailable", 503) from error
    limiter.clear(limiter_key)
    return JSONResponse(_session_payload(session), status_code=201)


@router.post("/api/v1/auth/refresh")
def refresh_device_session(
    request: Request,
    body: dict[str, Any] = Depends(device_json),
) -> JSONResponse:
    try:
        session = request.app.state.auth_service.refresh_device_session(
            str(body.get("refresh_token") or "")
        )
    except IdentityRepositoryError as error:
        raise DeviceApiRequestError("identity_store_unavailable", 503) from error
    if session is None:
        raise DeviceApiRequestError(
            "device_session_invalid",
            401,
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    return JSONResponse(_session_payload(session))


@router.delete("/api/v1/auth/session", status_code=204)
def revoke_device_session(
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> Response:
    del identity
    authorization = str(request.headers.get("Authorization") or "")
    _, _, access_token = authorization.partition(" ")
    try:
        request.app.state.auth_service.logout_device(access_token)
    except IdentityRepositoryError as error:
        raise DeviceApiRequestError("identity_store_unavailable", 503) from error
    return Response(status_code=204)


def _session_payload(session: DeviceSession) -> dict[str, Any]:
    identity = identity_payload(session.identity)
    identity.pop("session", None)
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": "Bearer",
        "access_expires_at": _timestamp(session.access_expires_at),
        "refresh_expires_at": _timestamp(session.refresh_expires_at),
        "identity": identity,
    }


def _timestamp(value: int) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(value, UTC).isoformat().replace("+00:00", "Z")
