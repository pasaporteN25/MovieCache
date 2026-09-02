"""FastAPI application exposing the Movie Inbox viewer and catalog API."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.routing import _IncludedRouter
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.routing import BaseRoute

from movie_inbox.application.auth_service import (
    AuthenticationError,
    AuthService,
    PasswordPolicyError,
)
from movie_inbox.application.collection_service import CollectionService
from movie_inbox.application.external_retirement import (
    RetirementCatalog,
    TmdbRetirementService,
    retirement_history_path,
)
from movie_inbox.application.home_service import EditorialHomeService
from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.application.import_service import ImportService
from movie_inbox.application.library_service import (
    AvailabilityService,
    ManagedLibraryScheduler,
    ManagedLibraryService,
)
from movie_inbox.application.member_service import MemberService
from movie_inbox.application.privacy_service import PrivacyService
from movie_inbox.application.public_presentation_service import PublicPresentationService
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.application.scanner_workflow import ScannerWorkflowService
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.curation_history import (
    JsonCurationHistoryRepository,
    MemoryCurationHistoryRepository,
)
from movie_inbox.infrastructure.external_catalog import configure_external_catalog
from movie_inbox.infrastructure.home_snapshot_repository import SqliteHomeSnapshotRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.import_parsers import parse_import_content
from movie_inbox.infrastructure.import_repository import SqliteImportDraftRepository
from movie_inbox.infrastructure.library_repository import SqliteLibraryRepository
from movie_inbox.infrastructure.library_scanner import scan_media_files
from movie_inbox.infrastructure.personal_catalogs import SqlitePersonalCatalogProvisioner
from movie_inbox.infrastructure.public_presentation_repository import (
    SqlitePublicPresentationRepository,
)
from movie_inbox.infrastructure.scanner_history import SqliteScannerHistoryRepository
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
from movie_inbox.web.catalog_api import catalog_service, load_items
from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.dependencies import (
    AUTH_SESSION_COOKIE,
    HISTORY_SESSION_COOKIE,
    authenticated_json,
    blocked_until_password_change,
    login_json,
    require_identity,
    require_token,
    requires_authentication,
    set_auth_cookie,
)
from movie_inbox.web.image_warmer import ImageCacheWarmer
from movie_inbox.web.responses import (
    ApiRequestError,
    DeviceApiRequestError,
    device_error_response,
    error_response,
    identity_payload,
)
from movie_inbox.web.routers import (
    admin,
    catalog,
    club,
    curation,
    device_auth,
    home,
    imports,
    integrations,
    public_presentations,
    scanner,
    search,
)
from movie_inbox.web.security import LoginAttemptLimiter, PublicReadLimiter, viewer_allowed_hosts

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

# Static JS/CSS carry no user data and are identical for every request, unlike the
# no-store default the security middleware applies elsewhere for privacy. Filenames
# aren't content-hashed, so this revalidates via ETag rather than going immutable.
STATIC_CACHE_CONTROL = "public, max-age=3600, must-revalidate"


def create_app(config: ViewerConfig) -> FastAPI:
    if not config.instance_db:
        raise RuntimeError("ViewerConfig.instance_db is required")
    configure_external_catalog(
        config.external_credentials.tmdb_read_access_token,
        config.anime_offline_index,
    )
    instance_db = Path(config.instance_db)
    identity_repository = SqliteIdentityRepository(instance_db)
    identity_repository.initialize()
    if not identity_repository.has_users():
        raise RuntimeError("Movie Inbox owner account has not been bootstrapped")
    auth_service = AuthService(
        identity_repository,
        session_ttl_seconds=config.session_ttl_seconds,
    )
    member_catalog_dir = Path(config.member_catalog_dir or instance_db.parent / "catalogs")
    member_service = MemberService(
        identity_repository,
        SqlitePersonalCatalogProvisioner(member_catalog_dir),
    )
    library_repository = SqliteLibraryRepository(instance_db)
    owner = identity_repository.owner()
    if owner is None:
        raise RuntimeError("Movie Inbox owner account is unavailable")

    def retirement_catalogs() -> list[RetirementCatalog]:
        catalogs: list[RetirementCatalog] = []
        for account_position, (_user, personal_catalog) in enumerate(
            identity_repository.list_accounts(), start=1
        ):
            for source_position, source in enumerate(personal_catalog.sources, start=1):
                catalogs.append(
                    RetirementCatalog(
                        f"active-{account_position}-source-{source_position}",
                        Path(source.path),
                        source.writable,
                    )
                )
        for archive_position, archived in enumerate(
            identity_repository.list_archived_members(), start=1
        ):
            for source_position, source in enumerate(archived.sources, start=1):
                catalogs.append(
                    RetirementCatalog(
                        f"archive-{archive_position}-source-{source_position}",
                        Path(source.path),
                        source.writable,
                    )
                )
        return catalogs

    tmdb_retirement_service = TmdbRetirementService(
        lambda path: catalog_service(path).repository,
        JsonCurationHistoryRepository(retirement_history_path(instance_db)),
        retirement_catalogs,
    )

    def catalog_universe() -> list[dict[str, Any]]:
        universe: list[dict[str, Any]] = []
        for user, personal_catalog in identity_repository.list_accounts():
            if not user.active:
                continue
            if user.id != owner.id and not identity_repository.privacy_for(user.id).catalog_shared:
                continue
            try:
                rows = load_items([source.path for source in personal_catalog.sources])
            except CatalogRepositoryError:
                if user.id == owner.id:
                    raise
                continue
            for row in rows:
                row["_scope_owner"] = user.id == owner.id
            universe.extend(rows)
        return universe

    collection_repository = SqliteCollectionRepository(instance_db)
    collection_repository.install_once(
        AKIRA_KUROSAWA_SEED_KEY,
        akira_kurosawa_collection(owner.id),
    )
    library_service = ManagedLibraryService(
        library_repository,
        allowed_roots=config.library_allowed_roots,
        catalog_universe=catalog_universe,
        scanner=scan_media_files,
        collection_repository=collection_repository,
    )
    availability_service = AvailabilityService(library_repository)
    scanner_workflow = ScannerWorkflowService(
        library_service,
        library_repository,
        SqliteScannerHistoryRepository(instance_db),
        MemoryCurationHistoryRepository(),
        catalog_service_factory=catalog_service,
    )
    privacy_service = PrivacyService(
        identity_repository,
        lambda patterns: availability_service.decorate_items(
            load_items(patterns),
            include_sources=False,
        ),
    )
    collection_service = CollectionService(collection_repository)
    public_presentation_service = PublicPresentationService(
        SqlitePublicPresentationRepository(instance_db), collection_repository
    )
    home_service = EditorialHomeService()
    home_snapshot_repository = SqliteHomeSnapshotRepository(instance_db)
    import_repository = SqliteImportDraftRepository(instance_db)
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
    public_presentation_limiter = PublicReadLimiter()
    image_warmer = ImageCacheWarmer(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
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
    app.state.public_presentation_service = public_presentation_service
    app.state.public_presentation_limiter = public_presentation_limiter
    app.state.home_service = home_service
    app.state.home_snapshot_repository = home_snapshot_repository
    app.state.import_repository = import_repository
    app.state.import_service = import_service
    app.state.library_repository = library_repository
    app.state.library_service = library_service
    app.state.availability_service = availability_service
    app.state.scanner_workflow = scanner_workflow
    app.state.library_scheduler = library_scheduler
    app.state.image_warmer = image_warmer
    app.state.tmdb_retirement_service = tmdb_retirement_service
    app.state.device_login_limiter = login_limiter
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=viewer_allowed_hosts(config.public_origin, config.public_presentation_origin),
    )

    @app.middleware("http")
    async def security_and_authentication(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        identity: AuthenticatedIdentity | None = None
        response: Response
        is_public_presentation = path.startswith("/public/") or path.startswith("/p/")
        token = (
            "" if is_public_presentation else str(request.cookies.get(AUTH_SESSION_COOKIE) or "")
        )
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
        elif (
            path == "/password-change"
            and identity is not None
            and not identity.user.must_change_password
        ):
            response = RedirectResponse("/", status_code=303)
        elif path == "/" and identity is None:
            response = RedirectResponse("/login", status_code=303)
        elif path == "/" and identity is not None and identity.user.must_change_password:
            response = RedirectResponse("/password-change", status_code=303)
        elif (
            identity is not None
            and identity.user.must_change_password
            and blocked_until_password_change(path)
        ):
            response = error_response("password_change_required", 403)
        elif requires_authentication(path) and identity is None:
            response = error_response("authentication_required", 401)
        else:
            response = await call_next(request)
        if path.startswith("/api/v1/"):
            response.headers.setdefault("X-Movie-Inbox-Api-Version", "1")
        return apply_security_headers(response)

    def apply_security_headers(response: Response) -> Response:
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(ApiRequestError)
    async def api_request_error(_: Request, error: ApiRequestError) -> JSONResponse:
        if isinstance(error, DeviceApiRequestError):
            return device_error_response(error)
        return error_response(error.reason, error.status_code)

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
        set_auth_cookie(response, token, config)
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
        response = JSONResponse(
            {"ok": True, "reason": "password_changed", **identity_payload(identity)}
        )
        set_auth_cookie(response, token, config)
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
        history_session_id = str(
            request.cookies.get(HISTORY_SESSION_COOKIE) or secrets.token_urlsafe(24)
        )
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
    def static(name: str, request: Request) -> Response:
        asset = static_asset(name)
        if not asset:
            return error_response("static_asset_not_found", 404)
        body, content_type = asset
        etag = f'"{hashlib.sha256(body).hexdigest()[:16]}"'
        headers = {"Cache-Control": STATIC_CACHE_CONTROL, "ETag": etag}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        headers["Content-Type"] = content_type
        return Response(body, headers=headers)

    @app.get("/api/session", dependencies=[Depends(require_token)])
    def session(request: Request) -> JSONResponse:
        return JSONResponse(identity_payload(require_identity(request)))

    app.include_router(home.router)
    app.include_router(catalog.router)
    app.include_router(scanner.router)
    app.include_router(curation.router)
    app.include_router(imports.router)
    app.include_router(club.router)
    app.include_router(admin.router)
    app.include_router(integrations.router)
    app.include_router(search.router)
    app.include_router(device_auth.router)
    app.include_router(public_presentations.router)
    # FastAPI >=0.139's include_router is lazy: app.routes holds _IncludedRouter
    # wrappers instead of the included APIRoute objects. Flatten once so app.routes
    # stays a real route list for callers (openapi, tests, ...).
    app.router.routes = _flattened_routes(app.router.routes)

    return app


def _flattened_routes(routes: list[BaseRoute]) -> list[BaseRoute]:
    flattened: list[BaseRoute] = []
    for route in routes:
        if isinstance(route, _IncludedRouter):
            flattened.extend(context.original_route for context in route.effective_route_contexts())
        else:
            flattened.append(route)
    return flattened
