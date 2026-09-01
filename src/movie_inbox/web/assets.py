"""Load the packaged HTML, CSS and JavaScript used by the viewer."""

from __future__ import annotations

import html
from importlib.resources import files
from pathlib import PurePosixPath

_CONTENT_TYPES_BY_SUFFIX = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}

# index.html is assembled from fragments, one per surface, in document order.
_INDEX_FRAGMENTS = (
    "index.shell-open.html",
    "index.home.html",
    "index.club.html",
    "index.inbox-shell.html",
    "index.inbox-curation.html",
    "index.inbox-imports.html",
    "index.inbox-scanner.html",
    "index.collection.html",
    "index.admin.html",
    "index.dialogs.html",
    "index.shell-close.html",
)


def render_html(title: str, api_token: str) -> str:
    template = b"".join(_asset(name) for name in _INDEX_FRAGMENTS).decode("utf-8")
    return template.replace("__MOVIE_INBOX_TITLE__", html.escape(title, quote=True)).replace(
        "__MOVIE_INBOX_TOKEN__", html.escape(api_token, quote=True)
    )


def render_login_html(title: str, api_token: str) -> str:
    template = _asset("login.html").decode("utf-8")
    return template.replace("__MOVIE_INBOX_TITLE__", html.escape(title, quote=True)).replace(
        "__MOVIE_INBOX_TOKEN__", html.escape(api_token, quote=True)
    )


def render_password_change_html(title: str, api_token: str) -> str:
    template = _asset("password-change.html").decode("utf-8")
    return template.replace("__MOVIE_INBOX_TITLE__", html.escape(title, quote=True)).replace(
        "__MOVIE_INBOX_TOKEN__", html.escape(api_token, quote=True)
    )


def static_asset(name: str) -> tuple[bytes, str] | None:
    content_type = _static_content_type(name)
    if content_type is None:
        return None
    try:
        return _asset(name), content_type
    except OSError:
        return None


def _static_content_type(name: str) -> str | None:
    value = str(name or "")
    if not value or "\\" in value or value.startswith("/"):
        return None
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    return _CONTENT_TYPES_BY_SUFFIX.get(PurePosixPath(parts[-1]).suffix)


def _asset(name: str) -> bytes:
    resource = files("movie_inbox.web.static")
    for part in name.split("/"):
        resource = resource.joinpath(part)
    return resource.read_bytes()
