"""Load the packaged HTML, CSS and JavaScript used by the viewer."""

from __future__ import annotations

import html
from importlib.resources import files


_STATIC_TYPES = {
    "style.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
}


def render_html(title: str, api_token: str) -> str:
    template = _asset("index.html").decode("utf-8")
    return (
        template.replace("__MOVIE_INBOX_TITLE__", html.escape(title, quote=True))
        .replace("__MOVIE_INBOX_TOKEN__", html.escape(api_token, quote=True))
    )


def static_asset(name: str) -> tuple[bytes, str] | None:
    content_type = _STATIC_TYPES.get(name)
    if not content_type:
        return None
    return _asset(name), content_type


def _asset(name: str) -> bytes:
    return files("movie_inbox.web.static").joinpath(name).read_bytes()

