"""Allowlisted personal-catalog resources for the versioned device API."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.application.import_service import (
    DeviceDraftFull,
    ImportDraftBusy,
    ImportDraftLimit,
)
from movie_inbox.application.library_repository import LibraryRepositoryError
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.application.search_service import search_catalog_items
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.web.catalog_api import load_items, patch_item_personal
from movie_inbox.web.dependencies import (
    SessionCatalog,
    _resolved_path,
    device_json,
    require_device_identity,
    session_catalog_rows,
)
from movie_inbox.web.responses import ApiRequestError, DeviceApiRequestError, identity_payload

# Name of the persistent secret the device sync key is derived from.
DEVICE_SYNC_SECRET = "device_sync_key"

router = APIRouter()
_DEVICE_PAGE_SIZE = 50
_MAX_DEVICE_PAGE_SIZE = 100


@dataclass(frozen=True)
class DeviceCatalogItem:
    device_id: str
    source_reference: str
    catalog_item_id: str
    row: dict[str, Any]


@router.get("/api/v1/me")
def device_identity(
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    payload = identity_payload(identity)
    payload.pop("session", None)
    return JSONResponse(payload)


@router.get("/api/v1/catalog/items")
def list_catalog_items(
    request: Request,
    cursor: str = "",
    limit: str = "50",
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    entries = _device_catalog_entries(request, identity)
    return JSONResponse(
        _page(
            request,
            entries,
            cursor=cursor,
            limit=limit,
            context="catalog",
        )
    )


@router.get("/api/v1/catalog/items/{item_id}")
def catalog_item(
    item_id: str,
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    entry = _entry_by_id(_device_catalog_entries(request, identity), item_id)
    if entry is None:
        raise DeviceApiRequestError("item_not_found", 404)
    return JSONResponse(_device_item_payload(entry))


@router.patch("/api/v1/catalog/items/{item_id}/personal")
def patch_personal_item(
    item_id: str,
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
    body: dict[str, Any] = Depends(device_json),
) -> JSONResponse:
    entries = _device_catalog_entries(request, identity)
    entry = _entry_by_id(entries, item_id)
    if entry is None:
        raise DeviceApiRequestError("item_not_found", 404)
    try:
        catalog = _session_catalog(request, identity)
        updated, reason = patch_item_personal(
            Path(catalog.source_path(entry.source_reference)),
            entry.catalog_item_id,
            body,
        )
    except (ValueError, CatalogRepositoryError) as error:
        raise _catalog_error(error) from error
    if not updated or reason == "not_found":
        raise DeviceApiRequestError("item_not_found", 404)
    refreshed = _entry_by_id(_device_catalog_entries(request, identity), item_id)
    if refreshed is None:
        raise DeviceApiRequestError("item_not_found", 404)
    return JSONResponse(_device_item_payload(refreshed))


# 200 rather than 201: this appends to a pile that usually already exists,
# and a retry creates nothing at all. What happened is in the body.
@router.post("/api/v1/catalog/drafts")
def add_offline_drafts(
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
    body: dict[str, Any] = Depends(device_json),
) -> JSONResponse:
    """Receive works a phone recorded with no connection ([A2.3]).

    The use case this exists for, in the owner's words: saving a film to the
    collection without being at the computer or at home.

    Nothing reaches the catalogue here. Each work is classified against it and
    parked in the account's pending pile, because an addition made offline has
    no shared base to merge against -- it is an import, and imports go through
    review. `state` says what the server found: `present` if the account already
    has it, `review` if it might, `new` if it clearly does not.

    Safe to retry. Works are keyed by the id the phone generated, so a sync that
    succeeds here and fails on the way back does not duplicate anything: the
    second attempt reports them under `duplicates`.
    """

    entries = body.get("items")
    if not isinstance(entries, list) or not entries:
        raise DeviceApiRequestError("invalid_request", 400)
    rows: list[dict[str, Any]] = [row for row in entries if isinstance(row, dict)]
    if len(rows) != len(entries):
        raise DeviceApiRequestError("invalid_request", 400)
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        catalog_items = load_items(catalog.config.patterns)
        result = request.app.state.import_service.append_device_items(
            identity.user.id, rows, catalog_items
        )
    except DeviceDraftFull as error:
        raise DeviceApiRequestError("device_draft_full", 409) from error
    except ImportDraftBusy as error:
        # Being applied in the browser right now. The phone keeps the works.
        raise DeviceApiRequestError("draft_busy", 409) from error
    except ImportDraftLimit as error:
        raise DeviceApiRequestError("draft_limit_reached", 409) from error
    except ValueError as error:
        raise DeviceApiRequestError("invalid_request", 400) from error
    except (CatalogRepositoryError, LibraryRepositoryError, IdentityRepositoryError) as error:
        raise _catalog_error(error) from error
    return JSONResponse(result)


@router.get("/api/v1/search")
def search_catalog(
    request: Request,
    q: str = "",
    cursor: str = "",
    limit: str = "50",
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    query = q.strip()
    if not query or len(query) > 200:
        raise DeviceApiRequestError("invalid_request", 400)
    entries = _device_catalog_entries(request, identity)
    matching_rows = search_catalog_items(
        [entry.row for entry in entries], query, limit=len(entries)
    )
    entries_by_key = {(entry.source_reference, entry.catalog_item_id): entry for entry in entries}
    results = [
        entries_by_key[(str(row.get("_source_file") or ""), str(row.get("id") or ""))]
        for row in matching_rows
        if (str(row.get("_source_file") or ""), str(row.get("id") or "")) in entries_by_key
    ]
    return JSONResponse(
        _page(
            request,
            results,
            cursor=cursor,
            limit=limit,
            context=f"search:{_digest(query)}",
        )
    )


def _device_catalog_entries(
    request: Request,
    identity: AuthenticatedIdentity,
) -> list[DeviceCatalogItem]:
    try:
        catalog, _, rows = session_catalog_rows(request, identity)
    except (CatalogRepositoryError, LibraryRepositoryError, IdentityRepositoryError) as error:
        raise _catalog_error(error) from error
    entries: list[DeviceCatalogItem] = []
    # [A1.4]: the key is derived from a persistent instance secret rather than
    # from api_token, and from the source's position rather than its path.
    # Rotating the token or relocating a catalogue are both normal operations
    # and must not re-key every work in a paired client's local replica.
    secret = request.app.state.identity_repository.instance_secret(DEVICE_SYNC_SECRET).encode(
        "utf-8"
    )
    for row in rows:
        source_reference = str(row.get("_source_file") or "")
        catalog_item_id = str(row.get("id") or "")
        if not source_reference or not catalog_item_id:
            continue
        # Item ids are only unique within one source file, so the source still
        # takes part in the key -- by position, which carries no path.
        source_slot = catalog.references_by_path.get(_resolved_path(source_reference), "source-0")
        entries.append(
            DeviceCatalogItem(
                _opaque_item_id(secret, identity.catalog.id, source_slot, catalog_item_id),
                source_reference,
                catalog_item_id,
                dict(row),
            )
        )
    return sorted(entries, key=lambda entry: (_title_key(entry.row), entry.device_id))


def _session_catalog(request: Request, identity: AuthenticatedIdentity) -> SessionCatalog:
    try:
        return SessionCatalog.from_identity(request.app.state.viewer_config, identity)
    except ApiRequestError as error:
        raise DeviceApiRequestError("catalog_unavailable", 503) from error


def _entry_by_id(entries: Sequence[DeviceCatalogItem], item_id: str) -> DeviceCatalogItem | None:
    return next((entry for entry in entries if hmac.compare_digest(entry.device_id, item_id)), None)


def _device_item_payload(entry: DeviceCatalogItem) -> dict[str, Any]:
    row = entry.row
    raw_availability = row.get("_availability")
    availability = (
        cast(Mapping[str, Any], raw_availability) if isinstance(raw_availability, Mapping) else {}
    )
    effective = bool(availability.get("effective") or row.get("en_catalogo"))
    return {
        "id": entry.device_id,
        "title": str(row.get("title") or ""),
        "original_title": _optional_text(row.get("original_title")),
        "year": _optional_text(row.get("year")),
        "kind": str(row.get("kind") or "pelicula"),
        "description": _optional_text(row.get("description") or row.get("wikipedia_extract")),
        "image_url": _optional_text(row.get("page_image") or row.get("backdrop_image")),
        "genres": [str(value) for value in row.get("genres") or [] if str(value)],
        "runtime_minutes": _optional_positive_int(row.get("duration_minutes")),
        "personal": {
            "status": str(row.get("status") or "to_watch"),
            "watched_at": _optional_text(row.get("watched_at")),
            "rating": _optional_rating(row.get("rating")),
            "review": _optional_text(row.get("review")),
        },
        "availability": {
            "state": "available" if effective else "unavailable",
            "count": max(0, int(availability.get("file_count") or 0)),
        },
    }


def _page(
    request: Request,
    entries: Sequence[DeviceCatalogItem],
    *,
    cursor: str,
    limit: str,
    context: str,
) -> dict[str, Any]:
    size = _page_size(limit)
    offset = _page_offset(request, cursor, context)
    page = list(entries[offset : offset + size])
    next_offset = offset + len(page)
    next_cursor = _cursor(request, context, next_offset) if next_offset < len(entries) else None
    return {"items": [_device_item_payload(entry) for entry in page], "next_cursor": next_cursor}


def _page_size(raw_limit: str) -> int:
    try:
        value = int(raw_limit)
    except ValueError as error:
        raise DeviceApiRequestError("invalid_request", 400) from error
    if not 1 <= value <= _MAX_DEVICE_PAGE_SIZE:
        raise DeviceApiRequestError("invalid_request", 400)
    return value


def _page_offset(request: Request, cursor: str, context: str) -> int:
    if not cursor:
        return 0
    if len(cursor) > 512:
        raise DeviceApiRequestError("invalid_request", 400)
    try:
        encoded_payload, signature = cursor.split(".", 1)
        payload = _decode(encoded_payload)
        expected = _cursor_signature(request, encoded_payload)
        offset = int(payload["offset"])
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise DeviceApiRequestError("invalid_request", 400) from error
    if (
        not hmac.compare_digest(signature, expected)
        or payload.get("context") != context
        or offset < 0
    ):
        raise DeviceApiRequestError("invalid_request", 400)
    return offset


def _cursor(request: Request, context: str, offset: int) -> str:
    encoded_payload = _encode({"context": context, "offset": offset})
    return f"{encoded_payload}.{_cursor_signature(request, encoded_payload)}"


def _cursor_signature(request: Request, encoded_payload: str) -> str:
    secret = request.app.state.viewer_config.api_token.encode("utf-8")
    return hmac.new(secret, encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()[:32]


def _encode(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(value: str) -> dict[str, Any]:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(value + padding)
    payload = json.loads(decoded.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid cursor")
    return payload


def _opaque_item_id(secret: bytes, catalog_id: str, source_slot: str, item_id: str) -> str:
    message = "\x1f".join((catalog_id, source_slot, item_id)).encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).digest()[:24]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _title_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("title") or "").casefold(), str(row.get("year") or ""))


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _optional_rating(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 1 <= parsed <= 10 else None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _catalog_error(error: Exception) -> DeviceApiRequestError:
    if isinstance(error, CatalogRepositoryError):
        return DeviceApiRequestError("catalog_unavailable", 503)
    if isinstance(error, (LibraryRepositoryError, IdentityRepositoryError)):
        return DeviceApiRequestError("identity_store_unavailable", 503)
    if isinstance(error, ValueError):
        return DeviceApiRequestError("invalid_request", 400)
    return DeviceApiRequestError("catalog_unavailable", 503)
