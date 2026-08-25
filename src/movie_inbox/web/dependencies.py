"""Session, auth and per-request catalog helpers shared by every router."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from fastapi import Depends, Request, Response

from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.application.curation_workflow import CatalogPointer
from movie_inbox.application.home_service import EditorialHomeService, home_image_items
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.domain.privacy import ItemPrivacyOverride
from movie_inbox.infrastructure.home_snapshot_repository import HomeSnapshotRepositoryError
from movie_inbox.web.catalog_api import (
    curation_workflow,
    enrich_selected_result,
    item_from_search_result,
    load_items,
    write_path_for,
)
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.responses import MAX_IMPORT_BODY_BYTES, ApiRequestError, read_json_object
from movie_inbox.web.security import viewer_allowed_origins

AUTH_SESSION_COOKIE = "movie_inbox_auth"
HISTORY_SESSION_COOKIE = "movie_inbox_history_session"


@dataclass(frozen=True)
class SessionCatalog:
    config: ViewerConfig
    references: dict[str, str]
    references_by_path: dict[str, str]
    source_names: tuple[str, ...]
    write_name: str

    @classmethod
    def from_identity(cls, base: ViewerConfig, identity: AuthenticatedIdentity) -> SessionCatalog:
        source_paths = [source.path for source in identity.catalog.sources]
        if not source_paths or not identity.catalog.write_path:
            raise ApiRequestError("catalog_unavailable", 503)
        references = {
            f"source-{position}": path for position, path in enumerate(source_paths, start=1)
        }
        references_by_path = {
            _resolved_path(path): reference for reference, path in references.items()
        }
        runtime = replace(
            base,
            patterns=source_paths,
            write_json=identity.catalog.write_path,
        )
        return cls(
            runtime,
            references,
            references_by_path,
            tuple(Path(path).name for path in source_paths),
            Path(identity.catalog.write_path).name,
        )

    def source_path(self, reference: str) -> str:
        return self.references.get(str(reference or ""), "")

    def public_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        public: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["_source_file"] = self.references_by_path.get(
                _resolved_path(str(row.get("_source_file") or "")),
                "",
            )
            public.append(item)
        return public

    def public_payload(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self.public_payload(item) for item in value]
        if isinstance(value, dict):
            public: dict[str, Any] = {}
            for key, item in value.items():
                if key in {"source_file", "_source_file"} and isinstance(item, str):
                    public[key] = self.references_by_path.get(_resolved_path(item), "")
                else:
                    public[key] = self.public_payload(item)
            return public
        return value


def _resolved_path(value: str) -> str:
    path = Path(str(value or ""))
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


def require_token(request: Request) -> None:
    config = request.app.state.viewer_config
    supplied = str(request.headers.get("X-Movie-Inbox-Token") or "")
    if not supplied or not secrets.compare_digest(supplied, config.api_token):
        raise ApiRequestError("invalid_token", 403)


def require_origin(request: Request) -> None:
    config = request.app.state.viewer_config
    origin = str(request.headers.get("Origin") or "").strip().casefold()
    if origin not in viewer_allowed_origins(config.port, config.public_origin):
        raise ApiRequestError("invalid_origin", 403)


def require_identity(request: Request) -> AuthenticatedIdentity:
    identity = getattr(request.state, "identity", None)
    if not isinstance(identity, AuthenticatedIdentity):
        raise ApiRequestError("authentication_required", 401)
    return identity


def require_ready_identity(request: Request) -> AuthenticatedIdentity:
    identity = require_identity(request)
    if identity.user.must_change_password:
        raise ApiRequestError("password_change_required", 403)
    return identity


def require_owner(request: Request) -> AuthenticatedIdentity:
    identity = require_ready_identity(request)
    if not identity.user.is_owner:
        raise ApiRequestError("owner_required", 403)
    return identity


async def authorized_json(
    request: Request,
    _: AuthenticatedIdentity = Depends(require_ready_identity),
) -> dict[str, Any]:
    require_token(request)
    require_origin(request)
    return await read_json_object(request)


async def authorized_import_json(
    request: Request,
    _: AuthenticatedIdentity = Depends(require_ready_identity),
) -> dict[str, Any]:
    require_token(request)
    require_origin(request)
    return await read_json_object(request, max_bytes=MAX_IMPORT_BODY_BYTES)


async def authenticated_json(
    request: Request,
    _: AuthenticatedIdentity = Depends(require_identity),
) -> dict[str, Any]:
    require_token(request)
    require_origin(request)
    return await read_json_object(request)


async def login_json(request: Request) -> dict[str, Any]:
    require_token(request)
    require_origin(request)
    return await read_json_object(request)


def history_session_id(request: Request) -> str:
    return str(
        request.cookies.get(HISTORY_SESSION_COOKIE)
        or request.headers.get("X-Movie-Inbox-Token")
        or "anonymous"
    )


def set_auth_cookie(response: Response, token: str, config: ViewerConfig) -> None:
    response.set_cookie(
        AUTH_SESSION_COOKIE,
        token,
        max_age=config.session_ttl_seconds,
        httponly=True,
        secure=config.public_origin.casefold().startswith("https://"),
        samesite="strict",
        path="/",
    )


def session_catalog(request: Request) -> SessionCatalog:
    config = request.app.state.viewer_config
    return SessionCatalog.from_identity(config, require_ready_identity(request))


def session_catalog_rows(
    request: Request,
    identity: AuthenticatedIdentity,
) -> tuple[SessionCatalog, list[dict[str, Any]], list[dict[str, Any]]]:
    config = request.app.state.viewer_config
    availability_service = request.app.state.availability_service
    privacy_service = request.app.state.privacy_service
    catalog = SessionCatalog.from_identity(config, identity)
    catalog_rows = load_items(catalog.config.patterns)
    rows = availability_service.decorate_items(
        catalog.public_rows(catalog_rows),
        include_sources=identity.user.is_owner,
    )
    overrides = privacy_service.item_overrides(identity)
    for row in rows:
        row["_privacy"] = overrides.get(
            str(row.get("id") or ""),
            ItemPrivacyOverride(),
        ).to_dict()
    return catalog, catalog_rows, rows


def editorial_home_payload(
    request: Request,
    identity: AuthenticatedIdentity,
    rows: list[dict[str, Any]],
    local_date: str,
    *,
    saved_featured: bool = False,
) -> dict[str, Any]:
    home_service = cast(EditorialHomeService, request.app.state.home_service)
    home_snapshot_repository = request.app.state.home_snapshot_repository
    image_warmer = request.app.state.image_warmer
    collection_service = request.app.state.collection_service
    warnings: list[str] = []
    try:
        followed = collection_service.followed_collections(identity.user.id)
    except CollectionRepositoryError:
        followed = []
        warnings.append("collections_unavailable")
    payload = home_service.build(
        identity.user.id,
        local_date,
        rows,
        followed,
        warnings=warnings,
    )
    featured_source = "live"
    try:
        snapshot = (
            home_snapshot_repository.get(identity.user.id, local_date) if saved_featured else None
        )
        if snapshot is not None:
            featured = home_service.restore_featured_snapshot(snapshot, rows)
            payload["featured"] = featured
            payload["hero"] = featured[0] if featured else None
            featured_source = "saved"
        else:
            home_snapshot_repository.save(
                identity.user.id,
                local_date,
                home_service.featured_snapshot(payload),
            )
            featured_source = "reconstructed" if saved_featured else "live"
    except HomeSnapshotRepositoryError:
        payload["warnings"] = list(
            dict.fromkeys([*payload.get("warnings", []), "home_history_unavailable"])
        )
        featured_source = "unavailable"
    payload["featured_source"] = featured_source
    image_warmer.register_items(
        f"home:{identity.catalog.id}",
        home_image_items(payload),
    )
    return payload


def requested_home_date(request: Request, value: str) -> str:
    home_service = cast(EditorialHomeService, request.app.state.home_service)
    requested = str(value or "").strip() or datetime.now(UTC).date().isoformat()
    return home_service.validate_date(requested)


def request_workflow(request: Request):  # type: ignore[no-untyped-def]
    return curation_workflow(
        session_catalog(request).config, request.app.state.availability_service
    )


def catalog_pointer(catalog: SessionCatalog, payload: Any) -> CatalogPointer:
    if not isinstance(payload, dict):
        raise ValueError("Missing catalog reference")
    return CatalogPointer(
        write_path_for(
            catalog.config,
            catalog.source_path(str(payload.get("source_file") or "")),
        ),
        str(payload.get("id") or ""),
    )


def comparison_inputs(
    catalog: SessionCatalog,
    body: dict[str, Any],
) -> tuple[CatalogPointer, CatalogPointer | None, dict[str, Any] | None]:
    left = catalog_pointer(catalog, body.get("left"))
    right_payload = body.get("right")
    incoming_payload = body.get("incoming") or body.get("result")
    right = catalog_pointer(catalog, right_payload) if isinstance(right_payload, dict) else None
    incoming = None
    if isinstance(incoming_payload, dict):
        candidate = (
            incoming_payload
            if body.get("incoming_reviewed")
            else enrich_selected_result(incoming_payload)
        )
        incoming = item_from_search_result(candidate)
    return left, right, incoming


def requires_authentication(path: str) -> bool:
    return (
        path == "/"
        or path == "/password-change"
        or path == "/image-cache"
        or path == "/auth/change-password"
        or path == "/auth/logout"
        or path.startswith("/api/")
    )


def blocked_until_password_change(path: str) -> bool:
    if path.startswith("/static/") or path == "/healthz":
        return False
    return path not in {
        "/login",
        "/password-change",
        "/auth/change-password",
        "/auth/logout",
        "/api/session",
    }
