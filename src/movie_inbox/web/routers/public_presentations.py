"""Anonymous, read-only public presentation routes.

No private router, serializer, cookie, or CSRF dependency belongs here.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from movie_inbox.application.public_presentation_repository import PublicPresentationRepositoryError
from movie_inbox.application.public_presentation_service import (
    PublicPresentationNotFound,
    is_public_capability,
)
from movie_inbox.web.assets import render_public_presentation_html

router = APIRouter()

PUBLIC_RESPONSE_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
}


@router.api_route(
    "/p/{capability}", methods=["GET", "HEAD"], response_class=HTMLResponse, response_model=None
)
def public_landing(capability: str, request: Request) -> HTMLResponse | JSONResponse:
    if not is_public_capability(capability):
        return _not_found()
    limiter = request.app.state.public_presentation_limiter
    client_host = request.client.host if request.client else "unknown"
    retry_after = limiter.consume(f"{client_host}:{capability}")
    if retry_after:
        response = _not_found()
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response
    try:
        request.app.state.public_presentation_service.public_payload(capability)
    except PublicPresentationNotFound:
        return _not_found()
    except PublicPresentationRepositoryError:
        return _unavailable()
    return HTMLResponse(
        render_public_presentation_html(capability), headers=PUBLIC_RESPONSE_HEADERS
    )


@router.get("/public/v1/presentations/{capability}")
def public_presentation(capability: str, request: Request) -> JSONResponse:
    if not is_public_capability(capability):
        return _not_found()
    limiter = request.app.state.public_presentation_limiter
    client_host = request.client.host if request.client else "unknown"
    retry_after = limiter.consume(f"{client_host}:{capability}")
    if retry_after:
        response = _not_found()
        response.status_code = 429
        response.headers["Retry-After"] = str(retry_after)
        return response
    try:
        payload = request.app.state.public_presentation_service.public_payload(capability)
    except PublicPresentationNotFound:
        return _not_found()
    except PublicPresentationRepositoryError:
        return _unavailable()
    return JSONResponse(payload, headers=PUBLIC_RESPONSE_HEADERS)


def _not_found() -> JSONResponse:
    return JSONResponse(
        {"detail": "public_presentation_not_found"},
        status_code=404,
        headers=PUBLIC_RESPONSE_HEADERS,
    )


def _unavailable() -> JSONResponse:
    return JSONResponse(
        {"detail": "public_presentation_unavailable"},
        status_code=503,
        headers=PUBLIC_RESPONSE_HEADERS,
    )
