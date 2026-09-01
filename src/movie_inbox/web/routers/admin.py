"""Member accounts and per-account privacy preferences."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.auth_service import PasswordPolicyError
from movie_inbox.application.identity_repository import (
    IdentityConflict,
    IdentityMemberActive,
    IdentityNotFound,
    IdentityOwnerProtected,
    IdentityRepositoryError,
)
from movie_inbox.application.member_service import MemberAuthorizationError
from movie_inbox.application.public_presentation_repository import PublicPresentationRepositoryError
from movie_inbox.application.public_presentation_service import (
    PublicPresentationNotFound,
    PublicPresentationValidationError,
)
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.web.catalog_api import load_items
from movie_inbox.web.dependencies import (
    SessionCatalog,
    authorized_json,
    require_owner,
    require_ready_identity,
    require_token,
)
from movie_inbox.web.responses import (
    archived_member_payload,
    error_response,
    managed_member_payload,
    repository_error_response,
)

router = APIRouter()


@router.get("/api/public-presentations", dependencies=[Depends(require_token)])
def public_presentations(request: Request) -> JSONResponse:
    identity = require_owner(request)
    service = request.app.state.public_presentation_service
    try:
        return JSONResponse({"presentations": service.list_for_owner(identity.user.id)})
    except PublicPresentationRepositoryError:
        return error_response("public_presentations_unavailable", 503)


@router.post("/api/public-presentations/preview")
def preview_public_presentation(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    service = request.app.state.public_presentation_service
    try:
        return JSONResponse({"presentation": service.preview(identity.user.id, body)})
    except PublicPresentationValidationError as error:
        return error_response(str(error), 400)
    except PublicPresentationRepositoryError:
        return error_response("public_presentations_unavailable", 503)


@router.post("/api/public-presentations")
def create_public_presentation(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    service = request.app.state.public_presentation_service
    try:
        presentation, capability = service.create(identity.user.id, body)
        return JSONResponse(
            {
                "ok": True,
                "reason": "public_presentation_created",
                "presentation": presentation,
                "url": f"/p/{capability}",
            },
            status_code=201,
        )
    except PublicPresentationValidationError as error:
        return error_response(str(error), 400)
    except PublicPresentationRepositoryError:
        return error_response("public_presentations_unavailable", 503)


@router.post("/api/public-presentations/{presentation_id}/refresh")
def refresh_public_presentation(
    presentation_id: str,
    request: Request,
    _: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    service = request.app.state.public_presentation_service
    try:
        presentation = service.refresh(identity.user.id, presentation_id)
        return JSONResponse(
            {"ok": True, "reason": "public_presentation_refreshed", "presentation": presentation}
        )
    except PublicPresentationNotFound:
        return error_response("public_presentation_not_found", 404)
    except PublicPresentationValidationError as error:
        return error_response(str(error), 400)
    except PublicPresentationRepositoryError:
        return error_response("public_presentations_unavailable", 503)


@router.post("/api/public-presentations/{presentation_id}/revoke")
def revoke_public_presentation(
    presentation_id: str,
    request: Request,
    _: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    service = request.app.state.public_presentation_service
    try:
        presentation = service.revoke(identity.user.id, presentation_id)
        return JSONResponse(
            {"ok": True, "reason": "public_presentation_revoked", "presentation": presentation}
        )
    except PublicPresentationNotFound:
        return error_response("public_presentation_not_found", 404)
    except PublicPresentationRepositoryError:
        return error_response("public_presentations_unavailable", 503)


@router.get("/api/members", dependencies=[Depends(require_token)])
def members(request: Request) -> JSONResponse:
    identity = require_owner(request)
    member_service = request.app.state.member_service
    try:
        directory = member_service.member_directory(identity.user)
        return JSONResponse(
            {
                "members": [managed_member_payload(record) for record in directory.members],
                "archived": [archived_member_payload(record) for record in directory.archived],
            }
        )
    except MemberAuthorizationError:
        return error_response("owner_required", 403)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.post("/api/members")
def create_member(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    member_service = request.app.state.member_service
    try:
        result = member_service.create_member(
            identity.user,
            str(body.get("username") or ""),
            temporary_password=str(body.get("temporary_password") or ""),
            catalog_name=str(body.get("catalog_name") or ""),
        )
        return JSONResponse(
            {
                "ok": True,
                "reason": "member_created",
                "member": managed_member_payload(result.member),
                "temporary_password": result.temporary_password,
            },
            status_code=201,
        )
    except IdentityConflict:
        return error_response("username_unavailable", 409)
    except (ValueError, PasswordPolicyError) as error:
        return error_response(str(error), 400)
    except MemberAuthorizationError:
        return error_response("owner_required", 403)
    except (CatalogRepositoryError, IdentityRepositoryError, OSError):
        return error_response("member_provisioning_failed", 503)


@router.post("/api/members/{user_id}/status")
def member_status(
    user_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    member_service = request.app.state.member_service
    if not isinstance(body.get("active"), bool):
        return error_response("active_must_be_boolean", 400)
    try:
        member = member_service.set_active(identity.user, user_id, bool(body["active"]))
        return JSONResponse(
            {
                "ok": True,
                "reason": "member_activated" if member.user.active else "member_deactivated",
                "member": managed_member_payload(member),
            }
        )
    except (IdentityNotFound, ValueError):
        return error_response("member_not_found", 404)
    except IdentityOwnerProtected:
        return error_response("owner_account_protected", 409)
    except MemberAuthorizationError:
        return error_response("owner_required", 403)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.post("/api/members/{user_id}/password-reset")
def reset_member_password(
    user_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    member_service = request.app.state.member_service
    try:
        result = member_service.reset_password(
            identity.user,
            user_id,
            temporary_password=str(body.get("temporary_password") or ""),
        )
        return JSONResponse(
            {
                "ok": True,
                "reason": "password_reset",
                "member": managed_member_payload(result.member),
                "temporary_password": result.temporary_password,
            }
        )
    except PasswordPolicyError as error:
        return error_response(str(error), 400)
    except (IdentityNotFound, ValueError):
        return error_response("member_not_found", 404)
    except MemberAuthorizationError:
        return error_response("owner_required", 403)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.post("/api/members/{user_id}/profile")
def update_member_profile(
    user_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    member_service = request.app.state.member_service
    try:
        member = member_service.update_member(
            identity.user,
            user_id,
            username=str(body.get("username") or ""),
            catalog_name=str(body.get("catalog_name") or ""),
        )
        return JSONResponse(
            {"ok": True, "reason": "member_updated", "member": managed_member_payload(member)}
        )
    except IdentityConflict:
        return error_response("username_unavailable", 409)
    except IdentityNotFound:
        return error_response("member_not_found", 404)
    except ValueError as error:
        return error_response(str(error), 400)
    except IdentityOwnerProtected:
        return error_response("owner_account_protected", 409)
    except MemberAuthorizationError:
        return error_response("owner_required", 403)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.post("/api/members/{user_id}/archive")
def archive_member(
    user_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    member_service = request.app.state.member_service
    try:
        archived = member_service.archive_member(
            identity.user,
            user_id,
            confirmed_username=str(body.get("confirmed_username") or ""),
        )
        return JSONResponse(
            {
                "ok": True,
                "reason": "member_archived",
                "archived": archived_member_payload(archived),
            }
        )
    except IdentityMemberActive:
        return error_response("member_must_be_inactive", 409)
    except IdentityOwnerProtected:
        return error_response("owner_account_protected", 409)
    except IdentityNotFound:
        return error_response("member_not_found", 404)
    except ValueError:
        return error_response("archive_confirmation_mismatch", 400)
    except MemberAuthorizationError:
        return error_response("owner_required", 403)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.post("/api/member-archives/{archive_id}/restore")
def restore_member(
    archive_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_owner(request)
    member_service = request.app.state.member_service
    try:
        result = member_service.restore_member(
            identity.user,
            archive_id,
            username=str(body.get("username") or ""),
            temporary_password=str(body.get("temporary_password") or ""),
        )
        return JSONResponse(
            {
                "ok": True,
                "reason": "member_restored",
                "member": managed_member_payload(result.member),
                "temporary_password": result.temporary_password,
            }
        )
    except IdentityConflict:
        return error_response("username_unavailable", 409)
    except PasswordPolicyError as error:
        return error_response(str(error), 400)
    except IdentityNotFound:
        return error_response("archive_not_found", 404)
    except ValueError as error:
        if "unavailable" in str(error).casefold():
            return error_response("archived_catalog_unavailable", 409)
        return error_response(str(error), 400)
    except MemberAuthorizationError:
        return error_response("owner_required", 403)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.get("/api/privacy", dependencies=[Depends(require_token)])
def privacy(request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    privacy_service = request.app.state.privacy_service
    try:
        preferences = privacy_service.preferences(identity)
        overrides = privacy_service.item_overrides(identity)
        return JSONResponse(
            {
                "preferences": preferences.to_dict(),
                "overrides": {item_id: row.to_dict() for item_id, row in overrides.items()},
            }
        )
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.post("/api/privacy")
def update_privacy(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    privacy_service = request.app.state.privacy_service
    fields = {
        "catalog_shared",
        "share_status",
        "share_watched_at",
        "share_history",
        "share_rating",
        "share_review",
    }
    if any(not isinstance(body.get(field), bool) for field in fields):
        return error_response("privacy_fields_must_be_boolean", 400)
    try:
        preferences = privacy_service.update_preferences(identity, body)
        return JSONResponse(
            {"ok": True, "reason": "privacy_updated", "preferences": preferences.to_dict()}
        )
    except IdentityNotFound:
        return error_response("account_not_found", 404)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)


@router.post("/api/privacy/items/{item_id}")
def update_item_privacy(
    item_id: str,
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    privacy_service = request.app.state.privacy_service
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        rows = load_items(catalog.config.patterns)
        if not any(str(row.get("id") or "") == item_id for row in rows):
            return error_response("not_found", 404)
        override = privacy_service.update_item_override(identity, item_id, body)
        return JSONResponse(
            {"ok": True, "reason": "item_privacy_updated", "privacy": override.to_dict()}
        )
    except ValueError as error:
        return error_response(str(error), 400)
    except CatalogRepositoryError as error:
        return repository_error_response(error)
    except IdentityRepositoryError:
        return error_response("identity_store_unavailable", 503)
