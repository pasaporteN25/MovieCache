"""Shared HTTP and result helpers for external catalog clients."""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from movie_inbox import __version__

# What every source that is not Wikimedia has always been sent.
GENERIC_USER_AGENT = "MovieInbox/0.2 (+local personal catalog)"

# [B2.4]: Wikimedia asks every client for a User-Agent that says what it is and
# where to reach whoever runs it, and answers generic ones with 429 far sooner.
# Measured on 2026-09-20 at one search every 12 seconds: 5 of 14 searches were
# limited with the generic string and 0 of 9 with this one.
PROJECT_URL = "https://github.com/pasaporteN25/MovieCache"
WIKIMEDIA_HOSTS = ("wikipedia.org", "wikidata.org", "wikimedia.org")
MAX_CONTACT_LENGTH = 120

_operator_contact = ""


def validated_operator_contact(contact: str) -> str:
    """The contact the person running this instance chose, or refuse it.

    It goes into a request header on every call to Wikimedia, so it is limited to
    printable ASCII with no parentheses -- the header's comment syntax -- rather
    than cleaned up: a value that would need cleaning is a mistake worth
    reporting.
    """

    value = str(contact or "").strip()
    if len(value) > MAX_CONTACT_LENGTH:
        raise ValueError(f"The operator contact is longer than {MAX_CONTACT_LENGTH} characters")
    if any(not 32 <= ord(char) <= 126 or char in "()" for char in value):
        raise ValueError(
            "The operator contact must be printable ASCII without parentheses, "
            "for example an email address or a URL"
        )
    return value


def configure_operator_contact(contact: str) -> None:
    global _operator_contact
    _operator_contact = validated_operator_contact(contact)


def is_wikimedia_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").casefold()
    except ValueError:
        return False
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in WIKIMEDIA_HOSTS)


def user_agent_for(url: str, default: str = GENERIC_USER_AGENT) -> str:
    """Identify the project to Wikimedia, and keep the old string for everyone else.

    Only Wikimedia's hosts get it: it is their policy, and telling a site that
    dislikes scrapers exactly who is scraping it is not a favour to anyone.
    """

    if not is_wikimedia_url(url):
        return default
    details = f"{PROJECT_URL}; {_operator_contact}" if _operator_contact else PROJECT_URL
    return f"MovieInbox/{__version__} (+{details})"


def fetch_json(
    url: str,
    timeout: float = 8,
    headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    fetch_options: dict[str, Any] = {"accept": "application/json", "timeout": timeout}
    if headers is not None:
        fetch_options["headers"] = headers
    raw = json.loads(fetch_text(url, **fetch_options) or "{}")
    return raw if isinstance(raw, dict) else {}


def fetch_json_safe(url: str, timeout: float = 5) -> dict[str, Any]:
    try:
        return fetch_json(url, timeout=timeout)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return {}


def fetch_text(
    url: str,
    accept: str = "text/html,application/xhtml+xml",
    timeout: float = 8,
    headers: Mapping[str, str] | None = None,
) -> str:
    request_headers = {
        "User-Agent": user_agent_for(url),
        "Accept": accept,
    }
    request_headers.update(headers or {})
    request = Request(
        url,
        headers=request_headers,
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        text: str = response.read(800_000).decode(charset, errors="replace")
        return text


def object_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def object_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def string_list(value: Any) -> list[str]:
    return [str(row) for row in object_list(value)]


def dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse rows that name the same thing, however they spell its address.

    Percent-encoding is part of how a URL is written, not of what it points at,
    and two paths through the same source can write it differently: Wikipedia's
    own canonicalurl keeps the parentheses of "The Fly (1986 film)" literal,
    while a URL built from the article title encodes them. Comparing the two as
    text left one article in the shelf twice -- which is most film articles,
    since almost all of them are disambiguated that way.
    """

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for result in results:
        url = unquote(str(result.get("url") or "").strip()).rstrip("/").casefold()
        key = url or f"{result.get('source')}:{result.get('title')}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def interleave_batches(batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        batch[index]
        for index in range(max((len(batch) for batch in batches), default=0))
        for batch in batches
        if index < len(batch)
    ]


def result_index(row: Any) -> int:
    try:
        return int(row.get("index") or 999) if isinstance(row, dict) else 999
    except (TypeError, ValueError):
        return 999


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
