"""Minting the one-time ticket a phone scans to adopt an account.

The redemption side lives in `device_auth.py`, with the rest of the device
session endpoints, because what it returns is a device session.

Any member mints for **their own** account. This is deliberately not owner-only:
each account has its own catalogue, so each account pairs its own phone, and an
owner-only endpoint would either be useless to members or would have to mint on
someone else's behalf -- which is exactly the authority this must not have.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.domain.pairing import PairingError
from movie_inbox.infrastructure.qr_code import QrCodeError, qr_data_uri
from movie_inbox.web.dependencies import require_origin, require_ready_identity, require_token
from movie_inbox.web.responses import error_response

router = APIRouter()


@router.post("/api/device-pairing", dependencies=[Depends(require_token)])
def create_device_pairing(request: Request) -> JSONResponse:
    require_origin(request)
    identity = require_ready_identity(request)
    service = request.app.state.pairing_service
    try:
        ticket = service.create_ticket(identity)
    except PairingError:
        # The instance has no usable public origin, or no valid certificate pin
        # was configured. Both are administration problems, not bad requests:
        # pairing simply cannot be offered until HTTPS is set up.
        return error_response("pairing_not_configured", 409)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)
    try:
        image = qr_data_uri(json.dumps(ticket["payload"], separators=(",", ":")))
    except QrCodeError:
        # The ticket is already minted and perfectly usable; only the drawing
        # failed. Returning the payload without the image lets the surface fall
        # back to something a person can still act on, instead of losing both.
        image = ""
    return JSONResponse(_public_ticket(ticket, image), status_code=201)


def _public_ticket(ticket: dict[str, Any], qr_image: str) -> dict[str, Any]:
    """The response the browser gets.

    The plaintext ticket is inside `payload`, and inside `qr_image` drawn as a
    QR, because those are what have to reach the phone. It goes nowhere else --
    not into a log, not into a header, not into the URL. It expires in minutes
    and is good for exactly one use.

    `qr_image` is a `data:` URI meant for an `<img>`; the payload travels beside
    it so a surface can offer a manual fallback, and so a test can read what the
    QR actually encodes.
    """

    return {
        "payload": ticket["payload"],
        "qr_image": qr_image,
        "expires_at": ticket["expires_at"],
        "expires_in": ticket["expires_in"],
    }
