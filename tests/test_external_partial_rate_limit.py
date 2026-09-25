"""[B2.4b] A 429 that an adapter carries on past still counts against its source.

Seen by the live measurement of [B2.2]: when only one of Wikipedia's two
languages, or only the Wikidata alias lookup, was rate limited, the adapter went
on with what it had and the registry saw a success -- no cooldown, so the next
search walked straight into the same wall, and the partial answer was cached for
15 minutes as if it were whole. A 429 from every request already opened a
cooldown; a 429 from some of them did not.
"""

from __future__ import annotations

import json
import time
import unittest
from datetime import UTC, datetime, timedelta
from email.message import Message
from email.utils import format_datetime
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError

from movie_inbox.external import common
from movie_inbox.external.common import (
    DEFAULT_RETRY_AFTER_SECONDS,
    note_rate_limit,
    rate_limited_seconds,
    retry_after_seconds,
)
from movie_inbox.external.registry import ExternalSourceService
from movie_inbox.external.wikipedia import WikipediaAdapter

WIKI = "https://en.wikipedia.org/w/api.php?action=query"
HEAT = {
    "source": "fake",
    "title": "Heat",
    "year": "1995",
    "url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
}


def _headers(**values: str) -> Message:
    headers = Message()
    for key, value in values.items():
        headers[key.replace("_", "-")] = value
    return headers


def _too_many(url: str, retry_after: str | None = "30") -> HTTPError:
    headers = _headers(Retry_After=retry_after) if retry_after is not None else _headers()
    return HTTPError(url, 429, "Too Many Requests", headers, None)


class Clean(unittest.TestCase):
    """The notes are process-wide: every test starts without any."""

    def setUp(self) -> None:
        common._rate_limit_notes.clear()
        self.addCleanup(common._rate_limit_notes.clear)


class RetryAfterTests(unittest.TestCase):
    def test_a_number_of_seconds(self) -> None:
        self.assertEqual(retry_after_seconds(_headers(Retry_After="17")), 17)

    def test_a_fraction_rounds_up_and_zero_still_waits_a_second(self) -> None:
        self.assertEqual(retry_after_seconds(_headers(Retry_After="1.2")), 2)
        self.assertEqual(retry_after_seconds(_headers(Retry_After="0")), 1)

    def test_a_date(self) -> None:
        soon = format_datetime(datetime.now(UTC) + timedelta(seconds=60), usegmt=True)

        self.assertTrue(55 <= retry_after_seconds(_headers(Retry_After=soon)) <= 61)

    def test_nothing_usable_falls_back_to_the_default(self) -> None:
        for headers in (None, _headers(), _headers(Retry_After="soon"), _headers(Retry_After="")):
            with self.subTest(headers=str(headers)):
                self.assertEqual(retry_after_seconds(headers), DEFAULT_RETRY_AFTER_SECONDS)

    def test_the_caller_can_choose_that_default(self) -> None:
        self.assertEqual(retry_after_seconds(None, default=7), 7)


class NoteTests(Clean):
    def _fetch(self, url: str, error: HTTPError) -> None:
        def fake_urlopen(request: Any, timeout: float | None = None) -> Any:
            raise error

        with patch.object(common, "urlopen", fake_urlopen), self.assertRaises(HTTPError):
            common.fetch_text(url)

    def test_a_429_is_noted_against_its_host_with_the_time_it_asked_for(self) -> None:
        started = time.monotonic()

        self._fetch(WIKI, _too_many(WIKI, "17"))

        self.assertEqual(rate_limited_seconds(("wikipedia.org",), started), 17)

    def test_it_is_still_raised_for_whoever_called(self) -> None:
        # The note is on the side: what the adapter sees is unchanged.
        self._fetch(WIKI, _too_many(WIKI))

    def test_only_a_429_is_noted(self) -> None:
        started = time.monotonic()

        self._fetch(WIKI, HTTPError(WIKI, 503, "Unavailable", _headers(), None))
        self._fetch(WIKI, HTTPError(WIKI, 404, "Not found", _headers(), None))

        self.assertEqual(rate_limited_seconds(("wikipedia.org",), started), 0)

    def test_a_subdomain_counts_and_a_lookalike_does_not(self) -> None:
        started = time.monotonic()
        note_rate_limit("https://es.wikipedia.org/w/api.php", 9)
        note_rate_limit("https://notwikipedia.org/", 99)

        self.assertEqual(rate_limited_seconds(("wikipedia.org",), started), 9)

    def test_the_longest_wait_asked_for_is_the_one_reported(self) -> None:
        started = time.monotonic()
        note_rate_limit("https://en.wikipedia.org/a", 5)
        note_rate_limit("https://www.wikidata.org/b", 40)

        self.assertEqual(rate_limited_seconds(("wikipedia.org", "wikidata.org"), started), 40)

    def test_a_429_from_before_the_question_was_asked_is_not_this_ones(self) -> None:
        note_rate_limit("https://en.wikipedia.org/a", 30)
        started = time.monotonic()

        self.assertEqual(rate_limited_seconds(("wikipedia.org",), started), 0)

    def test_a_source_that_names_no_hosts_is_never_limited_by_this(self) -> None:
        started = time.monotonic()
        note_rate_limit("https://en.wikipedia.org/a", 30)

        self.assertEqual(rate_limited_seconds((), started), 0)


class FakeAdapter:
    name = "fake"
    label = "Fake"

    def __init__(
        self, *, hosts: tuple[str, ...] | None = ("wikipedia.org",), limited_by: str = ""
    ) -> None:
        if hosts is not None:
            self.rate_limit_hosts = hosts
        self.limited_by = limited_by
        self.calls = 0

    def search(self, query: str) -> list[dict[str, Any]]:
        self.calls += 1
        if self.limited_by:
            note_rate_limit(self.limited_by, 20)
        return [dict(HEAT)]


class RegistryTests(Clean):
    def _service(self, adapter: FakeAdapter) -> ExternalSourceService:
        return ExternalSourceService(adapters=[adapter])

    def _health(self, service: ExternalSourceService) -> dict[str, Any]:
        health: dict[str, Any] = service.snapshot()["sources"]["fake"]
        return health

    def test_the_rows_it_found_are_kept_and_the_source_is_put_on_cooldown(self) -> None:
        service = self._service(FakeAdapter(limited_by=WIKI))

        rows, _ = service.search("Heat")

        self.assertEqual([row["title"] for row in rows], ["Heat"])
        health = self._health(service)
        self.assertEqual((health["status"], health["error_code"]), ("cooldown", "rate_limited"))
        self.assertTrue(1 <= health["retry_after_seconds"] <= 20)
        self.assertEqual(health["result_count"], 1)

    def test_a_partial_answer_is_not_remembered_as_a_whole_one(self) -> None:
        adapter = FakeAdapter(limited_by=WIKI)
        service = self._service(adapter)
        service.search("Heat")
        service._cooldowns.clear()
        adapter.limited_by = ""

        service.search("Heat")

        self.assertEqual(adapter.calls, 2)

    def test_a_whole_answer_still_is(self) -> None:
        adapter = FakeAdapter()
        service = self._service(adapter)

        service.search("Heat")
        service.search("Heat")

        self.assertEqual(adapter.calls, 1)

    def test_the_source_is_left_alone_while_it_cools_down(self) -> None:
        adapter = FakeAdapter(limited_by=WIKI)
        service = self._service(adapter)
        service.search("Heat")

        rows, _ = service.search("Ran")

        self.assertEqual((rows, adapter.calls), ([], 1))

    def test_a_429_from_some_other_host_is_not_this_sources_business(self) -> None:
        service = self._service(FakeAdapter(limited_by="https://www.imdb.com/x"))

        service.search("Heat")

        self.assertEqual(self._health(service)["status"], "ok")

    def test_an_adapter_that_names_no_hosts_is_left_as_it_was(self) -> None:
        service = self._service(FakeAdapter(hosts=None, limited_by=WIKI))

        service.search("Heat")

        self.assertEqual(self._health(service)["status"], "ok")

    def test_a_429_from_before_the_search_does_not_cool_it_down(self) -> None:
        note_rate_limit(WIKI, 30)
        service = self._service(FakeAdapter())

        service.search("Heat")

        self.assertEqual(self._health(service)["status"], "ok")


class FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")
        self.headers = self

    def get_content_charset(self) -> str:
        return "utf-8"

    def read(self, size: int = -1) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class WikipediaTests(Clean):
    """The real adapter, with Wikidata refusing the alias lookup."""

    def _search(self, query: str, pages: list[dict[str, Any]]) -> ExternalSourceService:
        def fake_urlopen(request: Any, timeout: float | None = None) -> Any:
            url = request.full_url
            if "wikidata.org" in url:
                raise _too_many(url, "30")
            return FakeResponse(json.dumps({"query": {"pages": pages}}))

        service = ExternalSourceService(adapters=[WikipediaAdapter()])
        with patch.object(common, "urlopen", fake_urlopen):
            service.search(query, source="wikipedia")
        return service

    def _health(self, service: ExternalSourceService) -> dict[str, Any]:
        health: dict[str, Any] = service.snapshot()["sources"]["wikipedia"]
        return health

    def test_a_refused_alias_lookup_puts_wikipedia_on_cooldown(self) -> None:
        # Nothing usable in either edition, so the alias retry runs -- and Wikidata
        # answers 429. The adapter swallows that and returns what it had: nothing.
        service = self._search("Addio zio Tom", pages=[])

        health = self._health(service)
        self.assertEqual((health["status"], health["error_code"]), ("cooldown", "rate_limited"))
        self.assertEqual(health["retry_after_seconds"], 30)

    def test_no_429_means_no_cooldown(self) -> None:
        # The first pass finds the film, so the alias lookup is never made.
        page = {
            "title": "Heat (1995 film)",
            "canonicalurl": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
            "extract": "Heat is a 1995 American film directed by Michael Mann.",
        }

        service = self._search("Heat", pages=[page])

        self.assertEqual(self._health(service)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
