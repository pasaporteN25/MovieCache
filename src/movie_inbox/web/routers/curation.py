"""Curation queue: comparison, merge, undo and link/duplicate decisions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.curation_history import CurationHistoryError
from movie_inbox.application.curation_workflow import CurationWorkflowError
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.domain.merge_review import MergeReviewError
from movie_inbox.web.catalog_api import build_curation_payload, load_items
from movie_inbox.web.dependencies import (
    authorized_json,
    catalog_pointer,
    comparison_inputs,
    history_session_id,
    request_workflow,
    require_ready_identity,
    require_token,
    session_catalog,
    session_catalog_rows,
)
from movie_inbox.web.responses import curation_application_error_response, repository_error_response

router = APIRouter()


@router.get("/api/curation", dependencies=[Depends(require_token)])
def curation(request: Request) -> JSONResponse:
    try:
        identity = require_ready_identity(request)
        _, _, rows = session_catalog_rows(request, identity)
        return JSONResponse(build_curation_payload(rows))
    except CatalogRepositoryError as error:
        return repository_error_response(error)


@router.get("/api/curation/history", dependencies=[Depends(require_token)])
def curation_history(request: Request, mode: str = "persistent") -> JSONResponse:
    try:
        return JSONResponse(request_workflow(request).history(mode, history_session_id(request)))
    except (ValueError, CurationHistoryError) as error:
        return curation_application_error_response(error)


@router.post("/api/curation/compare")
def compare_curation(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        group = _group_inputs(catalog, body)
        if group is not None:
            members, survivor, _ = group
            review = request_workflow(request).compare_group(members, survivor=survivor)
            return JSONResponse(catalog.public_payload(review))
        left, right, incoming = comparison_inputs(catalog, body)
        review = request_workflow(request).compare(
            left,
            right=right,
            incoming=incoming,
            survivor_side=str(body.get("survivor_side") or "left"),
        )
        if incoming is not None:
            review["incoming"] = incoming
        return JSONResponse(catalog.public_payload(review))
    except (
        ValueError,
        MergeReviewError,
        CurationWorkflowError,
        CatalogRepositoryError,
    ) as error:
        return curation_application_error_response(error)


@router.post("/api/curation/merge")
def merge_curation(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        group = _group_inputs(catalog, body)
        if group is not None:
            members, survivor, member_references = group
            result = request_workflow(request).merge_group(
                members,
                survivor=survivor,
                choices=body.get("choices") if isinstance(body.get("choices"), dict) else {},
                expected_review_id=str(body.get("review_id") or ""),
                reference_aliases=member_references,
                history_mode=str(body.get("history_mode") or "persistent"),
                session_id=history_session_id(request),
            )
            return JSONResponse({"ok": True, "reason": "merged", **result})
        left, right, incoming = comparison_inputs(catalog, body)
        result = request_workflow(request).merge(
            left,
            right=right,
            incoming=incoming,
            survivor_side=str(body.get("survivor_side") or "left"),
            choices=body.get("choices") if isinstance(body.get("choices"), dict) else {},
            expected_review_id=str(body.get("review_id") or ""),
            history_mode=str(body.get("history_mode") or "persistent"),
            session_id=history_session_id(request),
        )
        return JSONResponse({"ok": True, "reason": "merged", **result})
    except (
        ValueError,
        MergeReviewError,
        CurationWorkflowError,
        CurationHistoryError,
        CatalogRepositoryError,
    ) as error:
        return curation_application_error_response(error)


@router.post("/api/curation/auto-resolve")
def auto_resolve_curation_duplicates(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        items = load_items(catalog.config.patterns)
        result = request_workflow(request).auto_resolve_duplicates(
            items,
            history_mode=str(body.get("history_mode") or "persistent"),
            session_id=history_session_id(request),
        )
        return JSONResponse({"ok": True, "reason": "auto_resolved", **result})
    except (
        ValueError,
        MergeReviewError,
        CurationWorkflowError,
        CurationHistoryError,
        CatalogRepositoryError,
    ) as error:
        return curation_application_error_response(error)


@router.post("/api/curation/undo")
def undo_curation(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        operation = request_workflow(request).undo(
            str(body.get("operation_id") or ""),
            history_mode=str(body.get("history_mode") or "persistent"),
            session_id=history_session_id(request),
        )
        return JSONResponse({"ok": True, "reason": "undone", "operation": operation})
    except (
        ValueError,
        CurationWorkflowError,
        CurationHistoryError,
        CatalogRepositoryError,
    ) as error:
        return curation_application_error_response(error)


@router.post("/api/curation/history/clear")
def clear_curation_history(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        count = request_workflow(request).clear_history(
            str(body.get("history_mode") or "persistent"),
            history_session_id(request),
            confirmed=body.get("confirmed") is True,
        )
        return JSONResponse({"ok": True, "reason": "cleared", "cleared": count})
    except (ValueError, CurationHistoryError) as error:
        return curation_application_error_response(error)


@router.post("/api/curation/link")
def curate_link(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        result = request_workflow(request).update_link_decision(
            catalog_pointer(catalog, body),
            str(body.get("status") or ""),
            history_mode=str(body.get("history_mode") or "persistent"),
            session_id=history_session_id(request),
        )
        return JSONResponse({"ok": True, "reason": "updated", **result})
    except (
        ValueError,
        CurationWorkflowError,
        CurationHistoryError,
        CatalogRepositoryError,
    ) as error:
        return curation_application_error_response(error)


@router.post("/api/curation/duplicate")
def curate_duplicate(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    try:
        catalog = session_catalog(request)
        group = _group_inputs(catalog, body)
        if group is not None:
            members, _, member_references = group
            result = request_workflow(request).update_duplicate_group_decision(
                members,
                str(body.get("status") or ""),
                member_references=member_references,
                history_mode=str(body.get("history_mode") or "persistent"),
                session_id=history_session_id(request),
            )
        else:
            result = request_workflow(request).update_duplicate_decision(
                catalog_pointer(catalog, body),
                str(body.get("other_reference") or ""),
                str(body.get("status") or ""),
                history_mode=str(body.get("history_mode") or "persistent"),
                session_id=history_session_id(request),
            )
        return JSONResponse({"ok": True, "reason": "updated", **result})
    except (
        ValueError,
        CurationWorkflowError,
        CurationHistoryError,
        CatalogRepositoryError,
    ) as error:
        return curation_application_error_response(error)


def _group_inputs(catalog: Any, body: dict[str, Any]) -> tuple[list[Any], Any, list[str]] | None:
    raw_members = body.get("members")
    if not isinstance(raw_members, list):
        return None
    if not 2 <= len(raw_members) <= 50:
        raise ValueError("A duplicate group needs between 2 and 50 members")
    members = [catalog_pointer(catalog, member) for member in raw_members]
    member_references = [
        str(member.get("ref") or "") if isinstance(member, dict) else "" for member in raw_members
    ]
    if not all(member_references):
        member_references = []
    raw_survivor = body.get("survivor")
    survivor = (
        catalog_pointer(catalog, raw_survivor) if isinstance(raw_survivor, dict) else members[0]
    )
    return members, survivor, member_references
