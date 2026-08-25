"""Shared HTTP and result helpers for external catalog clients."""

from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch_json(url: str, timeout: float = 8) -> dict[str, Any]:
    raw = json.loads(fetch_text(url, accept="application/json", timeout=timeout) or "{}")
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
) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "MovieInbox/0.2 (+local personal catalog)",
            "Accept": accept,
        },
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
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for result in results:
        url = str(result.get("url") or "").strip().rstrip("/").casefold()
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
