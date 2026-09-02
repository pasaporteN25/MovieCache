"""JSON response and error-mapping helpers shared by every router."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from movie_inbox.application.curation_history import CurationHistoryError
from movie_inbox.application.curation_workflow import CurationConflict, CurationItemNotFound
from movie_inbox.application.library_repository import LibraryConflict, LibraryRepositoryError
from movie_inbox.application.member_service import ManagedMember
from movie_inbox.application.repository import (
    CatalogBusyError,
    CatalogFormatError,
    CatalogRepositoryError,
)
from movie_inbox.application.scanner_history import ScannerHistoryError
from movie_inbox.application.scanner_workflow import (
    ScannerOperationNotApplied,
    ScannerOperationNotFound,
)
from movie_inbox.domain.identity import ArchivedMember, AuthenticatedIdentity
from movie_inbox.infrastructure.import_parsers import MAX_IMPORT_CONTENT_BYTES

MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
# JSON escaping can nearly double a valid text source without increasing its
# decoded size. The parser still enforces the actual 8 MiB source limit.
MAX_IMPORT_BODY_BYTES = (MAX_IMPORT_CONTENT_BYTES * 2) + (256 * 1024)


class ApiRequestError(ValueError):
    def __init__(self, reason: str, status_code: int = 400) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


class DeviceApiRequestError(ApiRequestError):
    """A v1 device API error with its own stable response envelope."""

    def __init__(
        self,
        code: str,
        status_code: int,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code, status_code)
        self.code = code
        self.headers = headers or {}


async def read_json_object(
    request: Request,
    max_bytes: int = MAX_JSON_BODY_BYTES,
) -> dict[str, Any]:
    content_type = (
        str(request.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
    )
    if content_type != "application/json":
        raise ApiRequestError("Content-Type must be application/json")
    content_length = str(request.headers.get("Content-Length") or "").strip()
    if content_length:
        try:
            declared_length = int(content_length)
        except ValueError as error:
            raise ApiRequestError("Invalid Content-Length") from error
        if declared_length <= 0 or declared_length > max_bytes:
            raise ApiRequestError("JSON body is empty or too large")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise ApiRequestError("JSON body is empty or too large")
        chunks.append(chunk)
    if total <= 0:
        raise ApiRequestError("JSON body is empty or too large")
    try:
        data = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ApiRequestError("Invalid JSON body") from error
    if not isinstance(data, dict):
        raise ApiRequestError("Invalid JSON body")
    return data


def operation_response(ok: bool, reason: str) -> JSONResponse:
    return JSONResponse({"ok": ok, "reason": reason}, status_code=operation_status(ok, reason))


def operation_status(ok: bool, reason: str) -> int:
    if ok:
        return 200
    if reason in {"duplicate", "possible_duplicate", "merge_target_not_found"}:
        return 409
    if reason == "not_found":
        return 404
    return 400


def application_error_response(error: Exception) -> JSONResponse:
    if isinstance(error, CatalogRepositoryError):
        return repository_error_response(error)
    return error_response(str(error), 400)


def curation_application_error_response(error: Exception) -> JSONResponse:
    if isinstance(error, CatalogRepositoryError):
        return repository_error_response(error)
    if isinstance(error, CurationConflict):
        return error_response(str(error), 409)
    if isinstance(error, CurationItemNotFound):
        return error_response(str(error), 404)
    if isinstance(error, CurationHistoryError):
        return error_response(str(error), 500)
    return error_response(str(error), 400)


def scanner_application_error_response(error: Exception) -> JSONResponse:
    if isinstance(error, (LibraryConflict, CurationConflict)):
        return error_response(str(error), 409)
    if isinstance(error, ScannerOperationNotFound):
        return error_response(str(error), 404)
    if isinstance(error, ScannerOperationNotApplied):
        return error_response(str(error), 409)
    if isinstance(error, LibraryRepositoryError):
        return error_response(str(error), 503)
    if isinstance(error, (ScannerHistoryError, CurationHistoryError)):
        # Session-mode scanner history reuses `MemoryCurationHistoryRepository`
        # (a generic, per-session in-memory store with no scanner-specific
        # logic), so its errors surface under Curacion's history exception type.
        return error_response(str(error), 500)
    return error_response(str(error), 400)


def repository_error_response(error: CatalogRepositoryError) -> JSONResponse:
    if isinstance(error, CatalogBusyError):
        status = 503
    elif isinstance(error, CatalogFormatError):
        status = 422
    else:
        status = 500
    return error_response(str(error), status)


def error_response(reason: str, status_code: int) -> JSONResponse:
    return JSONResponse({"ok": False, "reason": reason}, status_code=status_code)


def device_error_response(error: DeviceApiRequestError) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": error.code}},
        status_code=error.status_code,
        headers=error.headers,
    )


def identity_payload(identity: AuthenticatedIdentity) -> dict[str, Any]:
    return {
        "user": {
            "id": identity.user.id,
            "username": identity.user.username,
            "role": identity.user.role,
            "must_change_password": identity.user.must_change_password,
        },
        "catalog": {
            "id": identity.catalog.id,
            "name": identity.catalog.name,
        },
        "session": {
            "expires_at": identity.expires_at,
        },
    }


def managed_member_payload(member: ManagedMember) -> dict[str, Any]:
    return {
        "id": member.user.id,
        "username": member.user.username,
        "role": member.user.role,
        "active": member.user.active,
        "must_change_password": member.user.must_change_password,
        "created_at": member.user.created_at,
        "catalog": {
            "id": member.catalog.id,
            "name": member.catalog.name,
        },
    }


def archived_member_payload(member: ArchivedMember) -> dict[str, Any]:
    return {
        "id": member.id,
        "username": member.username,
        "catalog": {"name": member.catalog_name},
        "archived_at": member.archived_at,
        "catalog_available": bool(member.sources)
        and all(Path(source.path).exists() for source in member.sources),
    }
