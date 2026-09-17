"""Allowlisted personal-catalog resources for the versioned device API.

Covers the account's own works and, since [A2.6], the collections it follows.
Both are served through allowlists rather than by handing over stored rows.
"""

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
from movie_inbox.application.streaming_repository import StreamingRepositoryError
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE
from movie_inbox.domain.streaming import (
    JUSTWATCH_ATTRIBUTION_NOTICE,
    retention_expires_at,
)
from movie_inbox.external.tmdb import TMDB_ATTRIBUTION_NOTICE
from movie_inbox.web.catalog_api import load_items, patch_item_personal
from movie_inbox.web.dependencies import (
    SessionCatalog,
    device_json,
    require_device_identity,
    session_catalog_rows,
)
from movie_inbox.web.responses import ApiRequestError, DeviceApiRequestError, identity_payload

# Name of the persistent secret the device sync key is derived from.
DEVICE_SYNC_SECRET = "device_sync_key"

# Namespaces for collection ids, so an id minted for a collection can never be
# mistaken for one minted for an item inside it.
#
# The catalogue keeps the derivation [A1.4] fixed, deliberately outside this
# scheme. Its stability across restarts and token rotations is a decided
# property of a paired replica, and folding a namespace into it would re-key
# every work a device holds -- a real cost, to make two helpers look alike.
COLLECTION_NAMESPACE = "collection"
COLLECTION_ITEM_NAMESPACE = "collection-item"

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
    if reason == "conflict":
        # [X2]: a declared `base` value no longer matches what is stored.
        # Nothing was written; the caller re-reads and merges before retrying.
        raise DeviceApiRequestError("personal_conflict", 409)
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


@router.get("/api/v1/collections")
def list_followed_collections(
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    """Collections this account follows ([A2.6], first step).

    Only followed ones. A device replica is meant to hold what its owner reads,
    not to become a directory of everything the instance can see.

    Items are left out here on purpose: a collection can be long, and a summary
    that grows without bound is the kind of endpoint that works until someone
    follows a list of five hundred films.
    """

    try:
        collections = request.app.state.collection_service.followed_collections(identity.user.id)
    except (LibraryRepositoryError, IdentityRepositoryError) as error:
        raise _catalog_error(error) from error
    secret = _sync_secret(request)
    return JSONResponse(
        {
            "collections": [
                {
                    "id": _opaque_id(secret, COLLECTION_NAMESPACE, collection.id),
                    "title": collection.title,
                    "description": collection.description,
                    "updated_at": collection.updated_at,
                    "count": len(collection.items),
                }
                for collection in collections
            ]
        }
    )


@router.get("/api/v1/collections/{collection_id}/items")
def collection_items(
    collection_id: str,
    request: Request,
    cursor: str = "",
    limit: str = "50",
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    """One followed collection's works, paged like the catalogue is.

    A collection item carries no personal state, and that is not an omission:
    following a collection does not copy its works into your catalogue, so there
    is no status, rating or review to report. A phone that wants those looks the
    work up in its own replica.
    """

    try:
        collections = request.app.state.collection_service.followed_collections(identity.user.id)
    except (LibraryRepositoryError, IdentityRepositoryError) as error:
        raise _catalog_error(error) from error
    secret = _sync_secret(request)
    found = next(
        (
            collection
            for collection in collections
            if hmac.compare_digest(
                _opaque_id(secret, COLLECTION_NAMESPACE, collection.id), collection_id
            )
        ),
        None,
    )
    if found is None:
        # Also the answer when the account stopped following it, which is the
        # honest one: it is no longer a collection this device may read.
        raise DeviceApiRequestError("collection_not_found", 404)
    entries = [
        {
            "id": _opaque_id(secret, COLLECTION_ITEM_NAMESPACE, f"{found.id}\x1f{entry.id}"),
            "position": entry.position,
            **_collection_item_payload(entry.item),
        }
        for entry in found.items
    ]
    size = _page_size(limit)
    context = f"collection:{_digest(found.id)}"
    offset = _page_offset(request, cursor, context)
    page = entries[offset : offset + size]
    next_offset = offset + len(page)
    return JSONResponse(
        {
            "items": page,
            "next_cursor": _cursor(request, context, next_offset)
            if next_offset < len(entries)
            else None,
        }
    )


@router.get("/api/v1/availability")
def device_availability(
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    """Where the account's works can be watched ([A2.6], second step).

    Keyed by the same opaque id the catalogue endpoints use, so a phone can join
    this onto the replica it already holds without ever seeing an internal id.

    Three things this response is careful about.

    `known: false` is not "not available". It means nobody asked, or the answer
    aged out. A client that renders it as "not on any platform" states something
    that was never checked, and ADR-0004 is explicit that the two are different
    answers.

    `expires_at` is when the client must stop showing the row. TMDb's terms cap
    how long anything obtained from them may be kept, and a replica that ignored
    that would be the instance breaking the terms by proxy. Sending the deadline
    rather than the rule also means the rule can change without every installed
    client being wrong.

    The JustWatch notice travels with the data because ADR-0004 accepted this
    source on that condition, with access to the whole API at stake.
    """

    entries = _device_catalog_entries(request, identity)
    service = request.app.state.streaming_service
    try:
        resolved = service.availability_for(identity, [entry.row for entry in entries])
    except StreamingRepositoryError as error:
        raise DeviceApiRequestError("availability_unavailable", 503) from error
    availability: dict[str, Any] = {}
    for entry in entries:
        found = resolved.get(entry.catalog_item_id)
        if found is None or not found.known:
            # Left out rather than sent as a false negative. An absent key is
            # "we did not check"; a present one is an answer.
            continue
        availability[entry.device_id] = {
            "en_plataforma": found.en_plataforma,
            "available_on": [offer.to_dict() for offer in found.available_on],
            "acquire_on": [offer.to_dict() for offer in found.acquire_on],
            "region_code": found.region_code,
            "checked_at": found.checked_at,
            "expires_at": retention_expires_at(found.checked_at),
            "link": found.link,
        }
    return JSONResponse(
        {
            "availability": availability,
            "attribution": {"justwatch": JUSTWATCH_ATTRIBUTION_NOTICE},
        }
    )


@router.get("/api/v1/ratings")
def device_ratings(
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    """Public scores beside the viewer's own ([A2.6], last step).

    Several sources at once rather than one chosen for the reader, which was the
    owner's decision: the point is to compare, with your own rating next to
    them. Ordered most-supported first, so the sturdiest opinion leads -- never
    by source, because ranking the sources would be picking for the reader after
    all.

    These are other people's opinions and they never touch the personal
    `rating`. This endpoint only reads ([F3.2]).

    A TMDb row carries `checked_at` and `expires_at`; an IMDb row carries
    neither, and that is right rather than missing. IMDb scores come out of the
    local index the owner re-syncs on their own schedule, with nothing upstream
    capping how long they may be kept.
    """

    service = request.app.state.public_ratings_service
    if not service.sources_configured:
        # Nothing configured is not an error: public scores are supplementary,
        # and a phone simply shows the viewer's own.
        return JSONResponse({"ratings": {}, "attribution": {}})
    entries = _device_catalog_entries(request, identity)
    found = service.ratings_for([entry.row for entry in entries])
    ratings: dict[str, Any] = {}
    for entry in entries:
        rows = found.get(entry.catalog_item_id)
        if rows:
            ratings[entry.device_id] = [row.to_dict() for row in rows]
    attribution: dict[str, str] = {}
    if service.imdb_lookup is not None:
        attribution["imdb"] = IMDB_ATTRIBUTION_NOTICE
    if service.tmdb_loader is not None:
        attribution["tmdb"] = TMDB_ATTRIBUTION_NOTICE
    return JSONResponse({"ratings": ratings, "attribution": attribution})


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
    secret = _sync_secret(request)
    for row in rows:
        # Item ids are only unique within one source file, so the source still
        # takes part in the key -- by position, which carries no path. The rows
        # already hold that position as a public reference (`source-1`,
        # `source-2`): resolving it as a path again never matched, and every
        # work fell back to a single slot.
        source_reference = str(row.get("_source_file") or "")
        catalog_item_id = str(row.get("id") or "")
        if source_reference not in catalog.references or not catalog_item_id:
            continue
        entries.append(
            DeviceCatalogItem(
                _opaque_item_id(secret, identity.catalog.id, source_reference, catalog_item_id),
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
    """[X9]: signed with the durable instance secret, not api_token, so a
    restart mid-download does not invalidate the next page's cursor."""

    secret = _sync_secret(request)
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


def _sync_secret(request: Request) -> bytes:
    secret: str = request.app.state.identity_repository.instance_secret(DEVICE_SYNC_SECRET)
    return secret.encode("utf-8")


def _opaque_id(secret: bytes, namespace: str, value: str) -> str:
    """Stable, opaque, and impossible to confuse across namespaces.

    Stable because it comes from the durable instance secret [A1.4] created, so
    a restart or a rotated api_token does not re-key a paired device's replica.
    """

    message = "\x1f".join((namespace, value)).encode("utf-8")
    digest = hmac.new(secret, message, hashlib.sha256).digest()[:24]
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _collection_item_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    """The identity of a work in a collection, and nothing else.

    Collection rows are already restricted to shareable fields when they are
    written (`COLLECTION_ITEM_FIELDS`), so this is a second allowlist over an
    already narrow one. That is deliberate: invariant 4 does not get to depend
    on a guarantee made somewhere else in the codebase.
    """

    return {
        "title": str(item.get("title") or ""),
        "original_title": _optional_text(item.get("original_title")),
        "year": _optional_text(item.get("year")),
        "kind": str(item.get("kind") or "pelicula"),
        "description": _optional_text(item.get("description") or item.get("wikipedia_extract")),
        "image_url": _optional_text(item.get("page_image") or item.get("backdrop_image")),
        "genres": [str(value) for value in item.get("genres") or [] if str(value)],
        "runtime_minutes": _optional_positive_int(item.get("duration_minutes")),
    }


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
