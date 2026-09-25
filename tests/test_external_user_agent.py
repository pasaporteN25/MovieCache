"""[B2.4] Say who we are to Wikimedia, and only to Wikimedia.

Measured on 2026-09-20 at one search every 12 seconds: with the generic
`User-Agent` 5 of 14 searches were rate limited, with one that names the project
0 of 9. Wikimedia asks every client for such a string, so the instances' requests
to their hosts carry one -- and requests to every other source are exactly what
they always were.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.request import Request

from movie_inbox import __version__
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.external import common
from movie_inbox.external.common import (
    GENERIC_USER_AGENT,
    MAX_CONTACT_LENGTH,
    PROJECT_URL,
    configure_operator_contact,
    is_wikimedia_url,
    user_agent_for,
    validated_operator_contact,
)
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web import image_proxy, server

WIKIMEDIA = [
    "https://en.wikipedia.org/w/api.php?action=query",
    "https://es.wikipedia.org/wiki/Heat",
    "https://www.wikidata.org/w/api.php?action=wbsearchentities",
    "https://upload.wikimedia.org/wikipedia/commons/a/a9/Poster.jpg",
    "https://wikipedia.org/",
]
NOT_WIKIMEDIA = [
    "https://www.imdb.com/title/tt0113277/",
    "https://www.filmaffinity.com/es/film599984.html",
    "https://api.jikan.moe/v4/anime/1",
    "https://api.themoviedb.org/3/movie/949",
    # Look-alikes: a suffix check has to be on the host's labels, not the string.
    "https://notwikipedia.org/",
    "https://wikipedia.org.evil.example/",
    "https://evil.example/?next=https://en.wikipedia.org/",
]


class ContactReset(unittest.TestCase):
    """The contact is process-wide state: every test starts and ends without one."""

    def setUp(self) -> None:
        configure_operator_contact("")
        self.addCleanup(configure_operator_contact, "")


class WhoWeAreTests(ContactReset):
    def test_wikimedia_is_told_the_project_its_version_and_where_to_find_it(self) -> None:
        for url in WIKIMEDIA:
            with self.subTest(url=url):
                agent = user_agent_for(url)

                self.assertTrue(is_wikimedia_url(url))
                self.assertIn(f"MovieInbox/{__version__}", agent)
                self.assertIn(PROJECT_URL, agent)

    def test_every_other_source_is_sent_what_it_always_was(self) -> None:
        for url in NOT_WIKIMEDIA:
            with self.subTest(url=url):
                self.assertFalse(is_wikimedia_url(url))
                self.assertEqual(user_agent_for(url), GENERIC_USER_AGENT)

    def test_the_caller_can_keep_its_own_default_for_other_hosts(self) -> None:
        agent = user_agent_for("https://www.imdb.com/", default="MovieInboxViewer/0.2")

        self.assertEqual(agent, "MovieInboxViewer/0.2")

    def test_no_contact_means_no_contact_in_the_string(self) -> None:
        self.assertEqual(user_agent_for(WIKIMEDIA[0]), f"MovieInbox/{__version__} (+{PROJECT_URL})")

    def test_the_contact_of_whoever_runs_the_instance_is_added_for_wikimedia_only(self) -> None:
        configure_operator_contact("ops@example.org")

        self.assertEqual(
            user_agent_for(WIKIMEDIA[0]),
            f"MovieInbox/{__version__} (+{PROJECT_URL}; ops@example.org)",
        )
        self.assertNotIn("ops@example.org", user_agent_for(NOT_WIKIMEDIA[0]))

    def test_a_contact_that_is_only_spaces_is_no_contact(self) -> None:
        configure_operator_contact("   ")

        self.assertEqual(user_agent_for(WIKIMEDIA[0]), f"MovieInbox/{__version__} (+{PROJECT_URL})")


class ContactValidationTests(unittest.TestCase):
    def test_an_email_and_a_url_are_fine(self) -> None:
        self.assertEqual(validated_operator_contact(" ops@example.org "), "ops@example.org")
        self.assertEqual(
            validated_operator_contact("https://inbox.example.com/about"),
            "https://inbox.example.com/about",
        )

    def test_nothing_is_fine_too(self) -> None:
        self.assertEqual(validated_operator_contact(""), "")

    def test_a_value_that_would_break_the_header_is_refused_not_cleaned(self) -> None:
        refused = [
            "ops@example.org\r\nX-Injected: 1",
            "ops@example.org\nbad",
            "tab\tseparated",
            "ops (at) example.org",
            "cafe@ejemplo.org ñ",
            "a" * (MAX_CONTACT_LENGTH + 1),
        ]
        for value in refused:
            with self.subTest(value=value[:30]):
                with self.assertRaises(ValueError):
                    validated_operator_contact(value)

    def test_the_longest_allowed_contact_is_accepted(self) -> None:
        self.assertEqual(validated_operator_contact("a" * MAX_CONTACT_LENGTH), "a" * 120)


class OnTheWireTests(ContactReset):
    def _sent(self, url: str, **kwargs: Any) -> Request:
        seen: list[Request] = []

        def fake_urlopen(request: Request, timeout: float | None = None) -> Any:
            seen.append(request)
            raise OSError("stop here: only the request matters")

        with patch.object(common, "urlopen", fake_urlopen):
            with self.assertRaises(OSError):
                common.fetch_text(url, **kwargs)
        return seen[0]

    def test_fetch_text_sends_the_identifying_string_to_wikipedia(self) -> None:
        configure_operator_contact("ops@example.org")

        request = self._sent(WIKIMEDIA[0])

        self.assertEqual(
            request.get_header("User-agent"),
            f"MovieInbox/{__version__} (+{PROJECT_URL}; ops@example.org)",
        )

    def test_fetch_text_sends_the_old_string_to_everyone_else(self) -> None:
        configure_operator_contact("ops@example.org")

        request = self._sent(NOT_WIKIMEDIA[0])

        self.assertEqual(request.get_header("User-agent"), GENERIC_USER_AGENT)

    def test_a_caller_that_sets_its_own_user_agent_still_wins(self) -> None:
        request = self._sent(WIKIMEDIA[0], headers={"User-Agent": "Custom/1"})

        self.assertEqual(request.get_header("User-agent"), "Custom/1")

    def test_the_image_proxy_identifies_itself_to_wikimedia_hosts_too(self) -> None:
        captured: dict[str, Any] = {}

        def stop(url: str, **kwargs: Any) -> Any:
            captured.update(kwargs["headers"])
            raise OSError("stop here")

        with patch.object(image_proxy, "open_public_url", stop):
            with self.assertRaises(OSError):
                image_proxy.download_image(WIKIMEDIA[3], 1024, ("upload.wikimedia.org",))

        self.assertIn(PROJECT_URL, captured["User-Agent"])

    def test_the_image_proxy_keeps_its_own_string_for_other_hosts(self) -> None:
        captured: dict[str, Any] = {}

        def stop(url: str, **kwargs: Any) -> Any:
            captured.update(kwargs["headers"])
            raise OSError("stop here")

        with patch.object(image_proxy, "open_public_url", stop):
            with self.assertRaises(OSError):
                image_proxy.download_image(
                    "https://m.media-amazon.com/images/x.jpg", 1024, ("m.media-amazon.com",)
                )

        self.assertEqual(captured["User-Agent"], "MovieInboxViewer/0.2 (+local personal catalog)")


class ServerConfigurationTests(ContactReset):
    def test_the_flag_defaults_to_the_environment_variable(self) -> None:
        with patch.dict(os.environ, {"MOVIE_INBOX_OPERATOR_CONTACT": "ops@example.org"}):
            parsed = server.build_parser().parse_args(["catalog.json"])

        self.assertEqual(parsed.operator_contact, "ops@example.org")

    def test_without_either_there_is_no_contact(self) -> None:
        with patch.dict(os.environ):
            os.environ.pop("MOVIE_INBOX_OPERATOR_CONTACT", None)
            parsed = server.build_parser().parse_args(["catalog.json"])

        self.assertEqual(parsed.operator_contact, "")

    def test_a_bad_contact_stops_the_server_from_starting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog.json"
            JsonCatalogRepository(catalog, normalize_item).write([])

            with redirect_stderr(StringIO()) as stderr, self.assertRaises(SystemExit) as raised:
                server.main(
                    [str(catalog), "--operator-contact", "ops (at) example.org", "--no-open"]
                )

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--operator-contact", stderr.getvalue())

    def test_a_running_server_uses_the_contact_it_was_started_with(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog = Path(temporary) / "catalog.json"
            password_file = Path(temporary) / "owner-password.txt"
            password_file.write_text("a-long-local-password\n", encoding="utf-8")
            (Path(temporary) / "media").mkdir()
            JsonCatalogRepository(catalog, normalize_item).write([])

            with patch("movie_inbox.web.server.uvicorn.run"), redirect_stdout(StringIO()):
                server.main(
                    [
                        str(catalog),
                        "--owner-username",
                        "lucas",
                        "--owner-password-file",
                        str(password_file),
                        "--library-root",
                        str(Path(temporary) / "media"),
                        "--operator-contact",
                        "ops@example.org",
                        "--no-open",
                    ]
                )

        self.assertIn("ops@example.org", user_agent_for(WIKIMEDIA[0]))


if __name__ == "__main__":
    unittest.main()
