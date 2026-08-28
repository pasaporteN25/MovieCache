"""Replay recorded HTTP responses through the real external adapters.

Lets Search Lab exercise IMDb/Wikipedia/Wikidata/FilmAffinity's actual
query construction and fallback logic against canned responses, with the
exact URL requested captured for a diagnostic trace -- no real network
call, and no changes to the adapters themselves.

Patches `fetch_text` in two places, not one. `imdb.py`/`wikipedia.py` only
call `fetch_json`/`fetch_json_safe`, whose bodies resolve `fetch_text` via
`external.common`'s own module globals at call time, so patching
`external.common.fetch_text` alone covers them. `filmaffinity.py` instead
does `from movie_inbox.external.common import fetch_text` and calls that
bare name directly -- a separate binding, fixed at import time, that
`external.common`'s own attribute reassignment can't reach (confirmed by
how `tests/test_external_filmaffinity.py` already has to patch
`movie_inbox.external.filmaffinity.fetch_text` specifically). Both need
their own patch.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Protocol
from unittest import mock

from movie_inbox.external import common as external_common
from movie_inbox.external import filmaffinity as external_filmaffinity


class UnrecordedRequestError(RuntimeError):
    """A replay session saw a URL with no recorded response."""

    def __init__(self, url: str) -> None:
        super().__init__(f"No recorded response for URL: {url}")
        self.url = url


class FetchText(Protocol):
    def __call__(self, url: str, accept: str = ..., timeout: float = ...) -> str: ...


class RequestLog:
    """Every URL actually requested through a session, in request order.
    May contain the same URL more than once. Thread-safe: adapters fan
    requests out across a ThreadPoolExecutor (Wikipedia's en/es search,
    IMDb's Wikidata alias bridge)."""

    def __init__(self) -> None:
        self._urls: list[str] = []
        self._lock = threading.Lock()

    def record(self, url: str) -> None:
        with self._lock:
            self._urls.append(url)

    @property
    def urls(self) -> list[str]:
        with self._lock:
            return list(self._urls)


def _as_response_text(value: Any) -> str:
    """Corpus fixtures may write a JSON-API response as a native JSON
    object/list for readability; write it back out as the string
    fetch_text() would have returned. A FilmAffinity fixture (raw HTML)
    is already a string and passes through unchanged."""
    return value if isinstance(value, str) else json.dumps(value)


@contextmanager
def _patched(replacement: FetchText) -> Iterator[None]:
    with (
        mock.patch.object(external_common, "fetch_text", replacement),
        mock.patch.object(external_filmaffinity, "fetch_text", replacement),
    ):
        yield


@contextmanager
def replay_recorded_responses(responses: Mapping[str, Any]) -> Iterator[RequestLog]:
    """Serve every fetch_text() call from a fixed {url: body} table.

    A URL that isn't in the table raises UnrecordedRequestError instead of
    reaching the network -- required both to run the corpus offline and to
    never leak a real search query to a third party during a CI run.
    """
    table = {url: _as_response_text(body) for url, body in responses.items()}
    log = RequestLog()

    def _replay(url: str, accept: str = "", timeout: float = 0) -> str:
        log.record(url)
        try:
            return table[url]
        except KeyError:
            raise UnrecordedRequestError(url) from None

    with _patched(_replay):
        yield log


@contextmanager
def record_live_responses() -> Iterator[tuple[RequestLog, dict[str, str]]]:
    """Call the real fetch_text() and capture every (url, response) pair.

    Manual authoring aid, never used by the CI gate: run this against a
    query you can verify against the real source, then trim and paste the
    captured pairs into a corpus fixture's recorded_responses table.
    """
    real_fetch_text = external_common.fetch_text
    log = RequestLog()
    captured: dict[str, str] = {}
    capture_lock = threading.Lock()

    def _record(
        url: str, accept: str = "text/html,application/xhtml+xml", timeout: float = 8
    ) -> str:
        log.record(url)
        body = real_fetch_text(url, accept=accept, timeout=timeout)
        with capture_lock:
            captured[url] = body
        return body

    with _patched(_record):
        yield log, captured


__all__ = [
    "RequestLog",
    "UnrecordedRequestError",
    "record_live_responses",
    "replay_recorded_responses",
]
