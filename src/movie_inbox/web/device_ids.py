"""The opaque ids a paired device knows works by.

[A1.4] fixed the derivation: a keyed hash of the account's catalogue, the
position of the source a work lives in, and the work's own id, under a durable
instance secret. It lives here rather than in the device catalogue router
because [X5] needs it from routes that have nothing to do with that router --
deleting or merging a work has to leave a record under the id a phone holds.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from pathlib import Path

from fastapi import Request

from movie_inbox.application.pairing_service import DEVICE_SYNC_SECRET
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.web.dependencies import SessionCatalog


def opaque_item_id(secret: bytes, catalog_id: str, source_slot: str, item_id: str) -> str:
    message = "\x1f".join((catalog_id, source_slot, item_id)).encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).digest()[:24]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def sync_secret(request: Request) -> bytes:
    secret: str = request.app.state.identity_repository.instance_secret(DEVICE_SYNC_SECRET)
    return secret.encode("utf-8")


def device_id_for(
    secret: bytes,
    identity: AuthenticatedIdentity,
    catalog: SessionCatalog,
    source_path: str | Path,
    item_id: str,
) -> str | None:
    """The id a phone knows this catalogue work by, or None if it has none.

    None means the file is not one of this account's sources, so no phone of
    this account could be holding the work.
    """

    if not item_id:
        return None
    try:
        resolved = str(Path(source_path).resolve())
    except OSError:
        resolved = str(Path(source_path).absolute())
    reference = catalog.references_by_path.get(resolved)
    if not reference:
        return None
    return opaque_item_id(secret, identity.catalog.id, reference, item_id)
