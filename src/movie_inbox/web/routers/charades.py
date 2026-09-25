"""Charades: deck, review pass and difficulty decisions, for the caller only.

Read-only over the catalogue. The only thing this surface writes is a person's
own difficulty decision, which lives in its own table and never touches a work.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.charades_repository import CharadesRepositoryError
from movie_inbox.application.charades_service import CharadesNotReady
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.web.dependencies import authorized_json, require_ready_identity, require_token
from movie_inbox.web.responses import error_response

router = APIRouter()


@router.get("/api/charades/status", dependencies=[Depends(require_token)])
def charades_status(request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    try:
        return JSONResponse(request.app.state.charades_service.status(identity))
    except CatalogRepositoryError:
        return error_response("catalog_unavailable", 503)
    except CharadesRepositoryError:
        return error_response("charades_unavailable", 503)


@router.get("/api/charades/deck", dependencies=[Depends(require_token)])
def charades_deck(request: Request, difficulty: str = "", size: int = 0) -> JSONResponse:
    identity = require_ready_identity(request)
    try:
        payload = request.app.state.charades_service.deck(identity, difficulty, max(0, size))
    except ValueError:
        return error_response("invalid_difficulty", 400)
    except CharadesNotReady:
        # Not an error in the data: that category simply has too few works to
        # play with, and saying so is more useful than dealing a thin deck.
        return error_response("not_enough_works", 409)
    except CatalogRepositoryError:
        return error_response("catalog_unavailable", 503)
    except CharadesRepositoryError:
        return error_response("charades_unavailable", 503)
    return JSONResponse(payload)


@router.get("/api/charades/review", dependencies=[Depends(require_token)])
def charades_review(request: Request, limit: int = 50) -> JSONResponse:
    identity = require_ready_identity(request)
    try:
        return JSONResponse(
            request.app.state.charades_service.pending_review(identity, max(1, min(500, limit)))
        )
    except CatalogRepositoryError:
        return error_response("catalog_unavailable", 503)
    except CharadesRepositoryError:
        return error_response("charades_unavailable", 503)


@router.post("/api/charades/difficulty")
def set_charades_difficulty(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    try:
        request.app.state.charades_service.classify(
            identity, str(body.get("key") or ""), str(body.get("difficulty") or "")
        )
    except ValueError:
        return error_response("invalid_difficulty", 400)
    except CharadesRepositoryError:
        return error_response("charades_unavailable", 503)
    return JSONResponse({"ok": True, "reason": "difficulty_saved"})
