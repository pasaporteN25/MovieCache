"""FastAPI application exposing the Movie Inbox viewer and catalog API."""

from __future__ import annotations

import json
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from fastapi import BackgroundTasks, Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from movie_inbox.application.auth_service import (
    AuthService,
    AuthenticationError,
    PasswordPolicyError,
)
from movie_inbox.application.curation_history import CurationHistoryError
from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.application.collection_service import (
    CollectionItemNotFound,
    CollectionNotFound,
    CollectionService,
)
from movie_inbox.application.curation_workflow import (
    CatalogPointer,
    CurationConflict,
    CurationItemNotFound,
    CurationWorkflowError,
)
from movie_inbox.application.repository import (
    CatalogBusyError,
    CatalogFormatError,
    CatalogRepositoryError,
)
from movie_inbox.application.identity_repository import (
    IdentityConflict,
    IdentityMemberActive,
    IdentityNotFound,
    IdentityOwnerProtected,
    IdentityRepositoryError,
)
from movie_inbox.application.import_repository import ImportRepositoryError
from movie_inbox.application.import_service import (
    ImportDraftBusy,
    ImportDraftExpired,
    ImportDraftLimit,
    ImportDraftNotFound,
    ImportPermissionError,
    ImportService,
)
from movie_inbox.application.library_repository import (
    LibraryNotFound,
    LibraryRepositoryError,
    LibraryRunBusy,
)
from movie_inbox.application.library_service import (
    AvailabilityService,
    LibraryPathError,
    ManagedLibraryScheduler,
    ManagedLibraryService,
)
from movie_inbox.application.member_service import (
    ManagedMember,
    MemberAuthorizationError,
    MemberService,
)
from movie_inbox.application.privacy_service import PrivacyService, SharedCatalogUnavailable
from movie_inbox.domain.identity import ArchivedMember, AuthenticatedIdentity
from movie_inbox.domain.libraries import LibraryValidationError
from movie_inbox.domain.merge_review import MergeReviewError
from movie_inbox.domain.privacy import ItemPrivacyOverride
from movie_inbox.infrastructure.external_catalog import external_sources_snapshot
from movie_inbox.infrastructure.export import catalog_csv_text
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.import_parsers import (
    ImportParseError,
    MAX_IMPORT_CONTENT_BYTES,
    parse_import_content,
)
from movie_inbox.infrastructure.import_repository import SqliteImportDraftRepository
from movie_inbox.infrastructure.library_repository import SqliteLibraryRepository
from movie_inbox.infrastructure.library_scanner import scan_media_files
from movie_inbox.infrastructure.personal_catalogs import SqlitePersonalCatalogProvisioner
from movie_inbox.infrastructure.schema import SCHEMA_VERSION, catalog_document
from movie_inbox.infrastructure.starter_collections import (
    AKIRA_KUROSAWA_SEED_KEY,
    akira_kurosawa_collection,
)
from movie_inbox.web.assets import (
    render_html,
    render_login_html,
    render_password_change_html,
    static_asset,
)
from movie_inbox.web.catalog_api import (
    append_item,
    background_enrich_catalog_item,
    build_curation_payload,
    catalog_service,
    curation_workflow,
    curation_counts,
    delete_item_anywhere,
    enrich_selected_result,
    has_external_link,
    item_from_search_result,
    load_items,
    needs_background_title_enrichment,
    resolved_files,
    search_sources,
    update_item_catalog_status,
    update_item_kind,
    update_item_metadata,
    update_item_personal,
    update_item_status,
    write_path_for,
)
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.image_proxy import cached_image
from movie_inbox.web.image_warmer import ImageCacheWarmer
from movie_inbox.web.security import (
    LoginAttemptLimiter,
    UnsafeRemoteUrl,
    validate_public_http_url,
    viewer_allowed_hosts,
    viewer_allowed_origins,
)


MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
# JSON escaping can nearly double a valid text source without increasing its
# decoded size. The parser still enforces the actual 8 MiB source limit.
MAX_IMPORT_BODY_BYTES = (MAX_IMPORT_CONTENT_BYTES * 2) + (256 * 1024)
AUTH_SESSION_COOKIE = "movie_inbox_auth"
HISTORY_SESSION_COOKIE = "movie_inbox_history_session"
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class ApiRequestError(ValueError):
    def __init__(self, reason: str, status_code: int = 400) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


@dataclass(frozen=True)
class SessionCatalog:
    config: ViewerConfig
    references: dict[str, str]
    references_by_path: dict[str, str]
    source_names: tuple[str, ...]
    write_name: str

    @classmethod
    def from_identity(cls, base: ViewerConfig, identity: AuthenticatedIdentity) -> "SessionCatalog":
        source_paths = [source.path for source in identity.catalog.sources]
        if not source_paths or not identity.catalog.write_path:
            raise ApiRequestError("catalog_unavailable", 503)
        references = {
            f"source-{position}": path
            for position, path in enumerate(source_paths, start=1)
        }
        references_by_path = {
            _resolved_path(path): reference
            for reference, path in references.items()
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


def create_app(config: ViewerConfig) -> FastAPI:
    if not config.instance_db:
        raise RuntimeError("ViewerConfig.instance_db is required")
    identity_repository = SqliteIdentityRepository(config.instance_db)
    identity_repository.initialize()
    if not identity_repository.has_users():
        raise RuntimeError("Movie Inbox owner account has not been bootstrapped")
    auth_service = AuthService(
        identity_repository,
        session_ttl_seconds=config.session_ttl_seconds,
    )
    member_catalog_dir = Path(config.member_catalog_dir or Path(config.instance_db).parent / "catalogs")
    member_service = MemberService(
        identity_repository,
        SqlitePersonalCatalogProvisioner(member_catalog_dir),
    )
    library_repository = SqliteLibraryRepository(config.instance_db)
    owner = identity_repository.owner()
    if owner is None:
        raise RuntimeError("Movie Inbox owner account is unavailable")

    def catalog_universe() -> list[dict[str, Any]]:
        universe: list[dict[str, Any]] = []
        for user, personal_catalog in identity_repository.list_accounts():
            if not user.active:
                continue
            if user.id != owner.id and not identity_repository.privacy_for(user.id).catalog_shared:
                continue
            try:
                universe.extend(load_items([source.path for source in personal_catalog.sources]))
            except CatalogRepositoryError:
                if user.id == owner.id:
                    raise
                continue
        return universe

    library_service = ManagedLibraryService(
        library_repository,
        allowed_roots=config.library_allowed_roots,
        catalog_universe=catalog_universe,
        scanner=scan_media_files,
    )
    availability_service = AvailabilityService(library_repository)
    privacy_service = PrivacyService(
        identity_repository,
        lambda patterns: availability_service.decorate_items(
            load_items(patterns),
            include_sources=False,
        ),
    )
    collection_repository = SqliteCollectionRepository(config.instance_db)
    collection_repository.install_once(
        AKIRA_KUROSAWA_SEED_KEY,
        akira_kurosawa_collection(owner.id),
    )
    collection_service = CollectionService(collection_repository)
    import_repository = SqliteImportDraftRepository(config.instance_db)
    import_service = ImportService(
        import_repository,
        collection_repository,
        parser=parse_import_content,
    )
    library_scheduler = ManagedLibraryScheduler(
        library_service,
        poll_seconds=config.library_scheduler_poll_seconds,
    )
    login_limiter = LoginAttemptLimiter()
    image_warmer = ImageCacheWarmer(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        library_scheduler.start()
        try:
            yield
        finally:
            library_scheduler.stop()
            image_warmer.stop()

    app = FastAPI(
        title="Movie Inbox",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.viewer_config = config
    app.state.identity_repository = identity_repository
    app.state.auth_service = auth_service
    app.state.member_service = member_service
    app.state.privacy_service = privacy_service
    app.state.collection_repository = collection_repository
    app.state.collection_service = collection_service
    app.state.import_repository = import_repository
    app.state.import_service = import_service
    app.state.library_repository = library_repository
    app.state.library_service = library_service
    app.state.availability_service = availability_service
    app.state.library_scheduler = library_scheduler
    app.state.image_warmer = image_warmer
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=viewer_allowed_hosts(config.public_origin))

    @app.middleware("http")
    async def security_and_authentication(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        identity: AuthenticatedIdentity | None = None
        token = str(request.cookies.get(AUTH_SESSION_COOKIE) or "")
        if token and not path.startswith("/static/") and path != "/healthz":
            try:
                identity = auth_service.authenticate(token)
            except IdentityRepositoryError:
                response = error_response("identity_store_unavailable", 503)
                return apply_security_headers(response)
        request.state.identity = identity

        if path == "/login" and identity is not None:
            destination = "/password-change" if identity.user.must_change_password else "/"
            response = RedirectResponse(destination, status_code=303)
        elif path == "/password-change" and identity is None:
            response = RedirectResponse("/login", status_code=303)
        elif path == "/password-change" and identity is not None and not identity.user.must_change_password:
            response = RedirectResponse("/", status_code=303)
        elif path == "/" and identity is None:
            response = RedirectResponse("/login", status_code=303)
        elif path == "/" and identity is not None and identity.user.must_change_password:
            response = RedirectResponse("/password-change", status_code=303)
        elif (
            identity is not None
            and identity.user.must_change_password
            and _blocked_until_password_change(path)
        ):
            response = error_response("password_change_required", 403)
        elif _requires_authentication(path) and identity is None:
            response = error_response("authentication_required", 401)
        else:
            response = await call_next(request)
        return apply_security_headers(response)

    def apply_security_headers(response: Response) -> Response:
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(ApiRequestError)
    async def api_request_error(_: Request, error: ApiRequestError) -> JSONResponse:
        return error_response(error.reason, error.status_code)

    def require_token(request: Request) -> None:
        supplied = str(request.headers.get("X-Movie-Inbox-Token") or "")
        if not supplied or not secrets.compare_digest(supplied, config.api_token):
            raise ApiRequestError("invalid_token", 403)

    def require_origin(request: Request) -> None:
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

    def set_auth_cookie(response: Response, token: str) -> None:
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
        return SessionCatalog.from_identity(config, require_ready_identity(request))

    def request_workflow(request: Request):  # type: ignore[no-untyped-def]
        return curation_workflow(session_catalog(request).config)

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

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/login", response_class=HTMLResponse)
    def login_page() -> HTMLResponse:
        return HTMLResponse(render_login_html(config.title, config.api_token))

    @app.get("/password-change", response_class=HTMLResponse)
    def password_change_page() -> HTMLResponse:
        return HTMLResponse(render_password_change_html(config.title, config.api_token))

    @app.post("/auth/login")
    def login(
        request: Request,
        body: dict[str, Any] = Depends(login_json),
    ) -> JSONResponse:
        username = str(body.get("username") or "")
        client_host = request.client.host if request.client else "unknown"
        limiter_key = f"{client_host}:{username.strip().casefold()[:64]}"
        retry_after = login_limiter.retry_after(limiter_key)
        if retry_after:
            response = error_response("too_many_attempts", 429)
            response.headers["Retry-After"] = str(retry_after)
            return response
        try:
            token, identity = auth_service.login(username, str(body.get("password") or ""))
        except AuthenticationError:
            login_limiter.record_failure(limiter_key)
            return error_response("invalid_credentials", 401)
        except IdentityRepositoryError:
            return error_response("identity_store_unavailable", 503)
        login_limiter.clear(limiter_key)
        response = JSONResponse({"ok": True, **identity_payload(identity)})
        set_auth_cookie(response, token)
        return response

    @app.post("/auth/change-password")
    def change_password(
        request: Request,
        body: dict[str, Any] = Depends(authenticated_json),
    ) -> JSONResponse:
        new_password = str(body.get("new_password") or "")
        if new_password != str(body.get("confirm_password") or ""):
            return error_response("password_confirmation_mismatch", 400)
        try:
            token, identity = auth_service.change_password(
                require_identity(request),
                str(body.get("current_password") or ""),
                new_password,
            )
        except AuthenticationError:
            return error_response("invalid_current_password", 401)
        except PasswordPolicyError as error:
            return error_response(str(error), 400)
        except IdentityRepositoryError:
            return error_response("identity_store_unavailable", 503)
        response = JSONResponse({"ok": True, "reason": "password_changed", **identity_payload(identity)})
        set_auth_cookie(response, token)
        return response

    @app.post("/auth/logout")
    def logout(
        request: Request,
        _: dict[str, Any] = Depends(authenticated_json),
    ) -> JSONResponse:
        try:
            auth_service.logout(str(request.cookies.get(AUTH_SESSION_COOKIE) or ""))
        except IdentityRepositoryError:
            return error_response("identity_store_unavailable", 503)
        response = JSONResponse({"ok": True, "reason": "logged_out"})
        response.delete_cookie(
            AUTH_SESSION_COOKIE,
            path="/",
            secure=config.public_origin.casefold().startswith("https://"),
            httponly=True,
            samesite="strict",
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        response = HTMLResponse(render_html(config.title, config.api_token))
        history_session_id = str(request.cookies.get(HISTORY_SESSION_COOKIE) or secrets.token_urlsafe(24))
        response.set_cookie(
            HISTORY_SESSION_COOKIE,
            history_session_id,
            httponly=True,
            secure=config.public_origin.casefold().startswith("https://"),
            samesite="strict",
            path="/",
        )
        return response

    @app.get("/static/{name:path}")
    def static(name: str) -> Response:
        asset = static_asset(name)
        if not asset:
            return error_response("static_asset_not_found", 404)
        body, content_type = asset
        return Response(body, headers={"Content-Type": content_type})

    @app.get("/api/session", dependencies=[Depends(require_token)])
    def session(request: Request) -> JSONResponse:
        return JSONResponse(identity_payload(require_identity(request)))

    @app.get("/api/members", dependencies=[Depends(require_token)])
    def members(request: Request) -> JSONResponse:
        identity = require_owner(request)
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

    @app.post("/api/members")
    def create_member(
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_owner(request)
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

    @app.post("/api/members/{user_id}/status")
    def member_status(
        user_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_owner(request)
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

    @app.post("/api/members/{user_id}/password-reset")
    def reset_member_password(
        user_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_owner(request)
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

    @app.post("/api/members/{user_id}/profile")
    def update_member_profile(
        user_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_owner(request)
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

    @app.post("/api/members/{user_id}/archive")
    def archive_member(
        user_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_owner(request)
        try:
            archived = member_service.archive_member(
                identity.user,
                user_id,
                confirmed_username=str(body.get("confirmed_username") or ""),
            )
            return JSONResponse(
                {"ok": True, "reason": "member_archived", "archived": archived_member_payload(archived)}
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

    @app.post("/api/member-archives/{archive_id}/restore")
    def restore_member(
        archive_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_owner(request)
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

    @app.get("/api/libraries", dependencies=[Depends(require_token)])
    def managed_libraries(request: Request) -> JSONResponse:
        require_owner(request)
        try:
            return JSONResponse(
                {
                    "configured": library_service.configured,
                    "allowed_roots": [str(path) for path in library_service.allowed_roots],
                    "libraries": library_service.list_libraries(),
                    "queue_count": len(library_service.review_queue()),
                }
            )
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.post("/api/libraries")
    def create_managed_library(
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_owner(request)
        try:
            library = library_service.create_library(identity.user.id, body)
            return JSONResponse(
                {"ok": True, "reason": "library_created", "library": library_service.library_payload(library)},
                status_code=201,
            )
        except (ValueError, LibraryValidationError, LibraryPathError) as error:
            return error_response(str(error), 400)
        except LibraryRepositoryError as error:
            return error_response(str(error), 409 if "already" in str(error).casefold() else 503)

    @app.get("/api/libraries/{library_id}", dependencies=[Depends(require_token)])
    def managed_library_detail(library_id: str, request: Request) -> JSONResponse:
        require_owner(request)
        try:
            return JSONResponse({"library": library_service.library_detail(library_id)})
        except LibraryNotFound:
            return error_response("library_not_found", 404)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.post("/api/libraries/{library_id}/update")
    def update_managed_library(
        library_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        require_owner(request)
        try:
            library = library_service.update_library(library_id, body)
            return JSONResponse(
                {"ok": True, "reason": "library_updated", "library": library_service.library_payload(library)}
            )
        except LibraryNotFound:
            return error_response("library_not_found", 404)
        except LibraryRunBusy:
            return error_response("library_scan_busy", 409)
        except (ValueError, LibraryValidationError) as error:
            return error_response(str(error), 400)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.post("/api/libraries/{library_id}/status")
    def update_managed_library_status(
        library_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        require_owner(request)
        if not isinstance(body.get("active"), bool):
            return error_response("active_must_be_boolean", 400)
        try:
            library = library_service.set_active(library_id, body["active"])
            return JSONResponse(
                {"ok": True, "reason": "library_status_updated", "library": library_service.library_payload(library)}
            )
        except LibraryNotFound:
            return error_response("library_not_found", 404)
        except LibraryRunBusy:
            return error_response("library_scan_busy", 409)
        except LibraryValidationError as error:
            return error_response(str(error), 409)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.post("/api/libraries/{library_id}/delete")
    def delete_managed_library(
        library_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        require_owner(request)
        if body.get("confirmed") is not True:
            return error_response("confirmation_required", 409)
        try:
            if not library_service.delete_library(library_id):
                return error_response("library_not_found", 404)
            return JSONResponse({"ok": True, "reason": "library_deleted"})
        except LibraryRunBusy:
            return error_response("library_scan_busy", 409)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.post("/api/libraries/{library_id}/runs")
    def run_managed_library(
        library_id: str,
        background_tasks: BackgroundTasks,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        require_owner(request)
        try:
            run = library_service.queue_scan(library_id, str(body.get("mode") or "dry_run"))
            background_tasks.add_task(library_service.execute_run, run.id)
            return JSONResponse(
                {"ok": True, "reason": "library_scan_queued", "run": library_service.run_payload(run)},
                status_code=202,
            )
        except LibraryNotFound:
            return error_response("library_not_found", 404)
        except LibraryRunBusy:
            return error_response("library_scan_busy", 409)
        except (ValueError, LibraryValidationError, LibraryPathError) as error:
            return error_response(str(error), 409)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.get("/api/library-runs/{run_id}", dependencies=[Depends(require_token)])
    def managed_library_run(run_id: str, request: Request) -> JSONResponse:
        require_owner(request)
        try:
            run = library_repository.get_run(run_id)
            if run is None:
                return error_response("library_run_not_found", 404)
            return JSONResponse({"run": library_service.run_payload(run)})
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.get("/api/scanner/queue", dependencies=[Depends(require_token)])
    def scanner_review_queue(request: Request) -> JSONResponse:
        require_owner(request)
        try:
            queue = library_service.review_queue()
            return JSONResponse({"items": queue, "count": len(queue)})
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.post("/api/scanner/queue/{file_id}")
    def review_scanner_item(
        file_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        require_owner(request)
        try:
            item = library_service.review_file(file_id, body)
            return JSONResponse({"ok": True, "reason": "scanner_item_reviewed", "item": item})
        except LibraryNotFound:
            return error_response("scanner_item_not_found", 404)
        except ValueError as error:
            return error_response(str(error), 400)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)

    @app.get("/api/privacy", dependencies=[Depends(require_token)])
    def privacy(request: Request) -> JSONResponse:
        identity = require_ready_identity(request)
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

    @app.post("/api/privacy")
    def update_privacy(
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_ready_identity(request)
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

    @app.post("/api/privacy/items/{item_id}")
    def update_item_privacy(
        item_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_ready_identity(request)
        try:
            catalog = SessionCatalog.from_identity(config, identity)
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

    @app.get("/api/community", dependencies=[Depends(require_token)])
    def community(request: Request) -> JSONResponse:
        try:
            identity = require_ready_identity(request)
            return JSONResponse({"catalogs": privacy_service.shared_catalogs(identity)})
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)
        except IdentityRepositoryError:
            return error_response("identity_store_unavailable", 503)

    @app.get("/api/community/{user_id}", dependencies=[Depends(require_token)])
    def shared_catalog(user_id: str, request: Request) -> JSONResponse:
        try:
            identity = require_ready_identity(request)
            payload = privacy_service.shared_catalog(identity, user_id)
            image_warmer.register_items(
                f"shared:{payload.get('catalog', {}).get('id', user_id)}",
                payload.get("items", []),
            )
            return JSONResponse(payload)
        except SharedCatalogUnavailable:
            return error_response("shared_catalog_not_found", 404)
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)
        except IdentityRepositoryError:
            return error_response("identity_store_unavailable", 503)

    @app.get("/api/imports", dependencies=[Depends(require_token)])
    def import_drafts(request: Request) -> JSONResponse:
        identity = require_ready_identity(request)
        try:
            return JSONResponse({"drafts": import_service.list_drafts(identity.user.id)})
        except ImportRepositoryError:
            return error_response("import_store_unavailable", 503)

    @app.post("/api/imports")
    def create_import_draft(
        request: Request,
        body: dict[str, Any] = Depends(authorized_import_json),
    ) -> JSONResponse:
        identity = require_ready_identity(request)
        column_map = body.get("column_map")
        if column_map is not None and (
            not isinstance(column_map, dict)
            or any(not isinstance(key, str) or not isinstance(value, str) for key, value in column_map.items())
        ):
            return error_response("column_map_must_be_an_object_of_strings", 400)
        try:
            catalog = SessionCatalog.from_identity(config, identity)
            draft = import_service.create_draft(
                identity.user.id,
                str(body.get("source_name") or "importacion"),
                str(body.get("source_format") or "auto"),
                body.get("content") if isinstance(body.get("content"), str) else "",
                column_map,
                load_items(catalog.config.patterns),
            )
            return JSONResponse(draft, status_code=201)
        except ImportParseError as error:
            return error_response(str(error), 422)
        except ImportDraftLimit:
            return error_response("import_draft_limit_reached", 409)
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except ImportRepositoryError:
            return error_response("import_store_unavailable", 503)

    @app.get("/api/imports/{draft_id}", dependencies=[Depends(require_token)])
    def import_draft_detail(draft_id: str, request: Request) -> JSONResponse:
        identity = require_ready_identity(request)
        try:
            catalog = SessionCatalog.from_identity(config, identity)
            return JSONResponse(
                import_service.draft_detail(
                    identity.user.id,
                    draft_id,
                    load_items(catalog.config.patterns),
                )
            )
        except ImportDraftNotFound:
            return error_response("import_draft_not_found", 404)
        except ImportDraftExpired:
            return error_response("import_draft_expired", 410)
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except ImportRepositoryError:
            return error_response("import_store_unavailable", 503)

    @app.post("/api/imports/{draft_id}/delete")
    def delete_import_draft(
        draft_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_ready_identity(request)
        try:
            deleted = import_service.delete_draft(
                identity.user.id,
                draft_id,
                body.get("confirmed") is True,
            )
            return JSONResponse({"ok": deleted, "reason": "deleted" if deleted else "not_found"})
        except ImportDraftNotFound:
            return error_response("import_draft_not_found", 404)
        except ImportDraftBusy:
            return error_response("import_draft_busy", 409)
        except ValueError as error:
            return error_response(str(error), 400)
        except ImportRepositoryError:
            return error_response("import_store_unavailable", 503)

    @app.post("/api/imports/{draft_id}/apply")
    def apply_import_draft(
        draft_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_ready_identity(request)
        item_ids = body.get("item_ids")
        personal_options = body.get("personal_options")
        if not isinstance(item_ids, list) or any(not isinstance(value, str) for value in item_ids):
            return error_response("item_ids_must_be_an_array_of_strings", 400)
        if personal_options is not None and not isinstance(personal_options, dict):
            return error_response("personal_options_must_be_an_object", 400)
        try:
            catalog = SessionCatalog.from_identity(config, identity)
            result = import_service.apply_draft(
                identity.user.id,
                draft_id,
                str(body.get("destination") or "catalog"),
                item_ids,
                catalog_service(Path(catalog.config.write_json)),
                load_items(catalog.config.patterns),
                personal_options=personal_options,
                collection_title=str(body.get("collection_title") or ""),
                collection_description=str(body.get("collection_description") or ""),
                can_create_collection=identity.user.is_owner,
            )
            return JSONResponse(result)
        except ImportDraftNotFound:
            return error_response("import_draft_not_found", 404)
        except ImportDraftExpired:
            return error_response("import_draft_expired", 410)
        except ImportDraftBusy:
            return error_response("import_draft_busy", 409)
        except ImportPermissionError:
            return error_response("owner_required_for_collection_import", 403)
        except (ValueError, CollectionRepositoryError) as error:
            if isinstance(error, CollectionRepositoryError):
                return error_response("collection_store_unavailable", 503)
            return error_response(str(error), 400)
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except ImportRepositoryError:
            return error_response("import_store_unavailable", 503)

    @app.get("/api/collections", dependencies=[Depends(require_token)])
    def collections(request: Request) -> JSONResponse:
        identity = require_ready_identity(request)
        try:
            return JSONResponse({"collections": collection_service.list_collections(identity.user.id)})
        except CollectionRepositoryError:
            return error_response("collection_store_unavailable", 503)

    @app.get("/api/collections/{collection_id}", dependencies=[Depends(require_token)])
    def collection_detail(collection_id: str, request: Request) -> JSONResponse:
        identity = require_ready_identity(request)
        try:
            catalog = SessionCatalog.from_identity(config, identity)
            rows = load_items(catalog.config.patterns)
            payload = collection_service.collection_detail(identity.user.id, collection_id, rows)
            image_warmer.register_items(f"collection:{collection_id}", payload.get("items", []))
            return JSONResponse(payload)
        except CollectionNotFound:
            return error_response("collection_not_found", 404)
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except CollectionRepositoryError:
            return error_response("collection_store_unavailable", 503)

    @app.post("/api/collections/{collection_id}/follow")
    def follow_collection(
        collection_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_ready_identity(request)
        if not isinstance(body.get("following"), bool):
            return error_response("following_must_be_boolean", 400)
        try:
            return JSONResponse(
                collection_service.set_following(
                    identity.user.id,
                    collection_id,
                    bool(body["following"]),
                )
            )
        except CollectionNotFound:
            return error_response("collection_not_found", 404)
        except CollectionRepositoryError:
            return error_response("collection_store_unavailable", 503)

    @app.post("/api/collections/{collection_id}/add")
    def add_collection_items(
        collection_id: str,
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        identity = require_ready_identity(request)
        item_ids = body.get("item_ids")
        if not isinstance(item_ids, list) or any(not isinstance(value, str) for value in item_ids):
            return error_response("item_ids_must_be_an_array_of_strings", 400)
        try:
            catalog = SessionCatalog.from_identity(config, identity)
            result = collection_service.add_to_catalog(
                identity.user.id,
                collection_id,
                item_ids,
                catalog_service(Path(catalog.config.write_json)),
                load_items(catalog.config.patterns),
            )
            return JSONResponse(result)
        except CollectionNotFound:
            return error_response("collection_not_found", 404)
        except CollectionItemNotFound:
            return error_response("collection_item_not_found", 404)
        except ValueError as error:
            return error_response(str(error), 400)
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except CollectionRepositoryError:
            return error_response("collection_store_unavailable", 503)

    @app.get("/api/items", dependencies=[Depends(require_token)])
    def items(request: Request) -> JSONResponse:
        try:
            identity = require_ready_identity(request)
            catalog = SessionCatalog.from_identity(config, identity)
            catalog_rows = load_items(catalog.config.patterns)
            rows = availability_service.decorate_items(
                catalog.public_rows(catalog_rows),
                include_sources=identity.user.is_owner,
            )
            preferences = privacy_service.preferences(identity)
            overrides = privacy_service.item_overrides(identity)
            for row in rows:
                row["_privacy"] = overrides.get(
                    str(row.get("id") or ""),
                    ItemPrivacyOverride(),
                ).to_dict()
        except CatalogRepositoryError as error:
            return repository_error_response(error)
        except LibraryRepositoryError:
            return error_response("library_store_unavailable", 503)
        except IdentityRepositoryError:
            return error_response("identity_store_unavailable", 503)
        with_link = sum(1 for item in rows if has_external_link(item))
        duplicate_items = sum(1 for item in rows if int(item.get("_duplicate_count") or 0) > 0)
        scanner_pending = 0
        if identity.user.is_owner:
            try:
                scanner_pending = len(library_service.review_queue())
            except LibraryRepositoryError:
                scanner_pending = 0
        image_warmer.register_items(f"catalog:{identity.catalog.id}", catalog_rows)
        print(
            f"[catalog-viewer] items loaded total={len(rows)} with_link={with_link} "
            f"without_link={len(rows) - with_link} duplicate_items={duplicate_items}",
            flush=True,
        )
        return JSONResponse(
            {
                "items": rows,
                "sources": list(catalog.source_names),
                "write_json": catalog.write_name,
                "schema_version": SCHEMA_VERSION,
                "duplicate_items": duplicate_items,
                "curation": {"counts": {**curation_counts(rows), "scanner": scanner_pending}},
                "external": external_sources_snapshot(),
                "privacy": preferences.to_dict(),
            }
        )

    @app.get("/api/image-cache/status", dependencies=[Depends(require_token)])
    def image_cache_status(request: Request) -> JSONResponse:
        identity = require_ready_identity(request)
        return JSONResponse(
            image_warmer.status(
                f"catalog:{identity.catalog.id}",
                include_global=identity.user.is_owner,
            )
        )

    @app.get("/api/catalog/export", dependencies=[Depends(require_token)])
    def export_catalog(
        request: Request,
        export_format: str = Query(default="json", alias="format"),
    ) -> Response:
        export_format = export_format.strip().casefold()
        if export_format not in {"json", "csv"}:
            return error_response("unsupported_export_format", 400)
        try:
            identity = require_ready_identity(request)
            catalog = SessionCatalog.from_identity(config, identity)
            rows = [
                item
                for source_path in resolved_files(catalog.config.patterns)
                for item in catalog_service(Path(source_path)).list_items()
            ]
        except CatalogRepositoryError as error:
            return repository_error_response(error)

        stamp = datetime.now(timezone.utc).date().isoformat()
        filename = f"movie-inbox-{identity.user.username.casefold()}-{stamp}.{export_format}"
        headers = {
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        if export_format == "csv":
            # The BOM keeps accented titles readable in spreadsheet apps on Windows.
            return Response(
                content="\ufeff" + catalog_csv_text(rows),
                media_type="text/csv",
                headers=headers,
            )
        document = catalog_document([item.to_dict() for item in rows])
        return Response(
            content=json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            media_type="application/json",
            headers=headers,
        )

    @app.get("/api/curation", dependencies=[Depends(require_token)])
    def curation(request: Request) -> JSONResponse:
        try:
            catalog = session_catalog(request)
            rows = catalog.public_rows(load_items(catalog.config.patterns))
            return JSONResponse(build_curation_payload(rows))
        except CatalogRepositoryError as error:
            return repository_error_response(error)

    @app.get("/api/curation/history", dependencies=[Depends(require_token)])
    def curation_history(request: Request, mode: str = "persistent") -> JSONResponse:
        try:
            return JSONResponse(request_workflow(request).history(mode, history_session_id(request)))
        except (ValueError, CurationHistoryError) as error:
            return curation_application_error_response(error)

    @app.post("/api/curation/compare")
    def compare_curation(
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        try:
            catalog = session_catalog(request)
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

    @app.post("/api/curation/merge")
    def merge_curation(
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        try:
            catalog = session_catalog(request)
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

    @app.post("/api/curation/undo")
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

    @app.post("/api/curation/history/clear")
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

    @app.get("/api/search", dependencies=[Depends(require_token)])
    def search(q: str = "", source: str = "all") -> JSONResponse:
        results = search_sources(q, source)
        print(
            f"[catalog-viewer] search query={q!r} source={source} "
            f"count={len(results)} result_sources={sorted(set(str(result.get('source') or '') for result in results))}",
            flush=True,
        )
        return JSONResponse({"results": results, "external": external_sources_snapshot()})

    @app.get("/api/source-health", dependencies=[Depends(require_token)])
    def source_health() -> JSONResponse:
        return JSONResponse({"external": external_sources_snapshot()})

    @app.get("/image-cache")
    def image_cache(request: Request, url: str = "") -> Response:
        if not url:
            return error_response("missing_image_url", 400)
        if not config.image_cache:
            try:
                validated_url = validate_public_http_url(url, allowed_hosts=config.image_allowed_hosts)
            except UnsafeRemoteUrl:
                return error_response("invalid_image_url", 400)
            return RedirectResponse(validated_url, status_code=302)
        try:
            with image_warmer.foreground(url):
                body, content_type = cached_image(config, url)
        except UnsafeRemoteUrl:
            return error_response("invalid_image_url", 400)
        except (ValueError, HTTPError, URLError, TimeoutError, OSError):
            return error_response("image_fetch_failed", 502)
        return Response(
            body,
            headers={
                "Content-Type": content_type,
                "Cache-Control": "public, max-age=31536000, immutable",
            },
        )

    @app.post("/api/add")
    def add(
        request: Request,
        background_tasks: BackgroundTasks,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        try:
            catalog = session_catalog(request)
            result = body.get("result") if isinstance(body.get("result"), dict) else body
            result = enrich_selected_result(result)
            item = item_from_search_result(result)
            write_path = write_path_for(
                catalog.config,
                catalog.source_path(str(body.get("target_source_file") or "")),
            )
            target_id = str(body.get("target_id") or "")
            added, reason, extra = append_item(
                write_path,
                item,
                action=str(body.get("action") or "check"),
                target_id=target_id,
                expected_source=str(body.get("expected_source") or ""),
            )
            background_enrichment = "not_needed"
            if added and reason in {"added", "merged"} and needs_background_title_enrichment(item):
                effective_item_id = target_id if reason == "merged" else str(item.get("id") or "")
                background_tasks.add_task(
                    background_enrich_catalog_item,
                    write_path,
                    effective_item_id,
                    item,
                )
                background_enrichment = "scheduled"
            return JSONResponse(
                {
                    "ok": added,
                    "reason": reason,
                    "item": item,
                    "background_enrichment": background_enrichment,
                    **extra,
                },
                status_code=operation_status(added, reason),
            )
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/delete")
    def delete(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            catalog = session_catalog(request)
            deleted, reason = delete_item_anywhere(
                catalog.config,
                source_file=catalog.source_path(str(body.get("source_file") or "")),
                item_id=str(body.get("id") or ""),
                item_url=str(body.get("url") or ""),
                title=str(body.get("title") or ""),
                year=str(body.get("year") or ""),
                local_name=str(body.get("local_name") or ""),
                confirmed=bool(body.get("confirmed")),
            )
            return operation_response(deleted, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/status")
    def status(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            catalog = session_catalog(request)
            updated, reason = update_item_status(
                write_path_for(
                    catalog.config,
                    catalog.source_path(str(body.get("source_file") or "")),
                ),
                item_id=str(body.get("id") or ""),
                status=str(body.get("status") or ""),
                watched_at=str(body.get("watched_at") or ""),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/kind")
    def kind(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            catalog = session_catalog(request)
            updated, reason = update_item_kind(
                write_path_for(
                    catalog.config,
                    catalog.source_path(str(body.get("source_file") or "")),
                ),
                item_id=str(body.get("id") or ""),
                kind=str(body.get("kind") or ""),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/catalog")
    def catalog(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            session = session_catalog(request)
            updated, reason = update_item_catalog_status(
                write_path_for(
                    session.config,
                    session.source_path(str(body.get("source_file") or "")),
                ),
                item_id=str(body.get("id") or ""),
                en_catalogo=body.get("en_catalogo"),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/personal")
    def personal(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            catalog = session_catalog(request)
            updated, reason = update_item_personal(
                write_path_for(
                    catalog.config,
                    catalog.source_path(str(body.get("source_file") or "")),
                ),
                item_id=str(body.get("id") or ""),
                watched_at=str(body.get("watched_at") or ""),
                rating=body.get("rating"),
                review=str(body.get("review") or ""),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    @app.post("/api/curation/link")
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

    @app.post("/api/curation/duplicate")
    def curate_duplicate(
        request: Request,
        body: dict[str, Any] = Depends(authorized_json),
    ) -> JSONResponse:
        try:
            catalog = session_catalog(request)
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

    @app.post("/api/metadata")
    def metadata(request: Request, body: dict[str, Any] = Depends(authorized_json)) -> JSONResponse:
        try:
            catalog = session_catalog(request)
            updated, reason = update_item_metadata(
                write_path_for(
                    catalog.config,
                    catalog.source_path(str(body.get("source_file") or "")),
                ),
                item_id=str(body.get("id") or ""),
                values=body.get("values") if isinstance(body.get("values"), dict) else {},
                locked_fields=body.get("locked_fields"),
            )
            return operation_response(updated, reason)
        except (ValueError, CatalogRepositoryError) as error:
            return application_error_response(error)

    return app


def _requires_authentication(path: str) -> bool:
    return (
        path == "/"
        or path == "/password-change"
        or path == "/image-cache"
        or path == "/auth/change-password"
        or path == "/auth/logout"
        or path.startswith("/api/")
    )


def _blocked_until_password_change(path: str) -> bool:
    if path.startswith("/static/") or path == "/healthz":
        return False
    return path not in {
        "/login",
        "/password-change",
        "/auth/change-password",
        "/auth/logout",
        "/api/session",
    }


def _resolved_path(value: str) -> str:
    path = Path(str(value or ""))
    try:
        return str(path.resolve())
    except OSError:
        return str(path.absolute())


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
        "catalog_available": bool(member.sources) and all(Path(source.path).exists() for source in member.sources),
    }


async def read_json_object(
    request: Request,
    max_bytes: int = MAX_JSON_BODY_BYTES,
) -> dict[str, Any]:
    content_type = str(request.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
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
