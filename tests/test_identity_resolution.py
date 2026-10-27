"""[X12 B] Completing the Wikidata id of entries that only link a Wikipedia article."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from collections.abc import Mapping, Sequence
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.identity_resolution_service import (
    IdentityResolutionService,
)
from movie_inbox.cli import identity as identity_cli
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.work_identity import annotate_duplicate_items
from movie_inbox.external.wikipedia import fetch_wikidata_ids_for_articles
from movie_inbox.infrastructure.identity_attempt_repository import (
    SqliteIdentityAttemptRepository,
)
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

EN_URL = "https://en.wikipedia.org/wiki/Kingdom_of_Heaven_(film)"
ES_URL = "https://es.wikipedia.org/wiki/El_reino_de_los_cielos"
KNOWN = {
    ("en", "Kingdom of Heaven (film)"): "Q1123433",
    ("es", "El reino de los cielos"): "Q1123433",
}


def _catalog(path: Path) -> JsonCatalogRepository:
    repository = JsonCatalogRepository(path, normalize_item)
    repository.write(
        [
            normalize_item(
                {"id": "en", "title": "Kingdom of Heaven (film)", "wikipedia_url": EN_URL}
            ),
            normalize_item({"id": "es", "title": "Kingdom of Heaven", "wikipedia_url": ES_URL}),
            normalize_item(
                {
                    "id": "locked",
                    "title": "Heat",
                    "wikipedia_url": "https://en.wikipedia.org/wiki/Heat_(1995_film)",
                    "locked_fields": ["wikidata_id"],
                }
            ),
            normalize_item(
                {
                    "id": "gone",
                    "title": "Borrada",
                    "wikipedia_url": "https://es.wikipedia.org/wiki/Articulo_borrado",
                }
            ),
        ]
    )
    return repository


class FakeLookups:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.fail = False

    def article_ids(self, language: str, titles: Sequence[str]) -> Mapping[str, str]:
        self.calls.append((language, list(titles)))
        if self.fail:
            raise OSError("network down")
        return {title: KNOWN[(language, title)] for title in titles if (language, title) in KNOWN}

    @staticmethod
    def release_years(entity_ids: Sequence[str]) -> Mapping[str, str]:
        return {"Q1123433": "2005"} if "Q1123433" in entity_ids else {}


class MemoryAttempts:
    def __init__(self) -> None:
        self.misses: dict[str, int] = {}

    def recent_misses(self, keys: Sequence[str], since: int) -> set[str]:
        return {key for key in keys if key in self.misses and self.misses[key] >= since}

    def record_misses(self, keys: Sequence[str], at: int) -> None:
        self.misses.update(dict.fromkeys(keys, at))


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repository = _catalog(Path(self.temporary.name) / "catalog.json")
        self.lookups = FakeLookups()
        self.attempts = MemoryAttempts()
        self.service = IdentityResolutionService(
            lambda: [self.repository],
            self.lookups.article_ids,
            self.lookups.release_years,
            self.attempts,
            clock=lambda: 1_000_000,
        )

    def _items(self) -> dict[str, dict[str, Any]]:
        return {item.id: item.to_dict() for item in self.repository.read()}

    def test_both_languages_get_the_id_and_then_curation_sees_one_film(self) -> None:
        report = self.service.resolve_batch()

        items = self._items()
        self.assertEqual(report.resolved, 2)
        self.assertEqual(items["en"]["wikidata_id"], "Q1123433")
        self.assertEqual(items["es"]["wikidata_id"], "Q1123433")
        self.assertEqual(items["en"]["year"], "2005")
        self.assertEqual(items["en"]["metadata_sources"]["wikidata_id"]["source"], "wikidata")
        rows = [items["en"], items["es"]]
        annotate_duplicate_items(rows)
        self.assertEqual(rows[0]["_duplicate_level"], "same")

    def test_a_locked_id_is_never_asked_about_or_written(self) -> None:
        self.service.resolve_batch()

        asked = [title for _, titles in self.lookups.calls for title in titles]
        self.assertNotIn("Heat (1995 film)", asked)
        self.assertEqual(self._items()["locked"]["wikidata_id"], "")

    def test_an_article_without_id_is_remembered_and_not_asked_again_soon(self) -> None:
        first = self.service.resolve_batch()
        self.lookups.calls.clear()
        second = self.service.resolve_batch()

        self.assertEqual(first.missing, 1)
        self.assertEqual(second.pending, 0)
        self.assertEqual(self.lookups.calls, [])

    def test_a_network_failure_is_not_taken_for_missing_ids(self) -> None:
        self.lookups.fail = True

        report = self.service.resolve_batch()

        self.assertEqual(report.failed, 3)
        self.assertEqual(report.missing, 0)
        self.assertEqual(self.attempts.misses, {})
        self.assertEqual(self._items()["en"]["wikidata_id"], "")

    def test_an_id_filled_by_hand_meanwhile_is_kept(self) -> None:
        def edit_first(language: str, titles: Sequence[str]) -> Mapping[str, str]:
            # Someone saves the entry between the read and the write.
            self.repository.update_metadata(
                "en", lambda item: item.__setitem__("wikidata_id", "Q9")
            )
            return self.lookups.article_ids(language, titles)

        self.service.article_ids = edit_first
        self.service.resolve_batch()

        self.assertEqual(self._items()["en"]["wikidata_id"], "Q9")


class WikipediaClientTests(unittest.TestCase):
    @patch("movie_inbox.external.wikipedia.fetch_json")
    def test_ids_come_back_under_the_title_asked_through_normalisation_and_redirects(
        self, fetch_json: Any
    ) -> None:
        fetch_json.return_value = {
            "query": {
                "normalized": [{"from": "el_reino_de_los_cielos", "to": "El reino de los cielos"}],
                "redirects": [
                    {"from": "El reino de los cielos", "to": "El reino de los cielos (película)"}
                ],
                "pages": {
                    "1": {
                        "title": "El reino de los cielos (película)",
                        "pageprops": {"wikibase_item": "Q1123433"},
                    },
                    "-1": {"title": "Nada", "missing": ""},
                },
            }
        }

        found = fetch_wikidata_ids_for_articles("es", ["el_reino_de_los_cielos", "Nada"])

        self.assertEqual(found, {"el_reino_de_los_cielos": "Q1123433"})
        self.assertIn("https://es.wikipedia.org/", fetch_json.call_args[0][0])

    def test_a_language_that_is_not_a_language_code_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            fetch_wikidata_ids_for_articles("evil.example.com/x?", ["A"])


class AttemptRepositoryTests(unittest.TestCase):
    def test_misses_round_trip_and_age_out(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.db"
            SqliteIdentityRepository(path).initialize()
            store = SqliteIdentityAttemptRepository(path)

            store.record_misses(["es:nada", "en:nothing"], at=100)
            store.record_misses(["es:nada"], at=500)

            self.assertEqual(
                store.recent_misses(["es:nada", "en:nothing", "x"], since=200), {"es:nada"}
            )


class HttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        catalog = root / "catalog.json"
        self.repository = _catalog(catalog)
        instance = root / "instance.db"
        password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
            "lucas",
            password,
            catalog_name="Catalogo",
            source_paths=[str(catalog)],
            write_path=str(catalog),
        )
        (root / "media").mkdir()
        self.config = ViewerConfig(
            patterns=[str(catalog)],
            title="Movie Inbox Test",
            write_json=str(catalog),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(instance),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(root / "media"),),
            library_scheduler_poll_seconds=3600,
        )
        context = TestClient(create_app(self.config), base_url="http://127.0.0.1:8765")
        self.client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        lookups = FakeLookups()
        self.client.app.state.identity_article_ids = lookups.article_ids  # type: ignore[attr-defined]
        self.client.app.state.identity_release_years = lookups.release_years  # type: ignore[attr-defined]
        login = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": password}),
            headers=self._headers(),
        )
        self.assertEqual(login.status_code, 200, login.content)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Movie-Inbox-Token": self.config.api_token,
            "Origin": "http://127.0.0.1:8765",
            "Content-Type": "application/json",
        }

    def test_the_page_sees_what_is_pending_and_resolves_it(self) -> None:
        status = self.client.get("/api/curation/identity", headers=self._headers())
        self.assertEqual(status.json(), {"pending": 3})

        resolved = self.client.post(
            "/api/curation/identity/resolve", content="{}", headers=self._headers()
        )

        self.assertEqual(resolved.status_code, 200, resolved.content)
        self.assertEqual(resolved.json()["resolved"], 2)
        self.assertEqual(resolved.json()["pending"], 0)
        curation = self.client.get("/api/curation", headers=self._headers()).json()
        duplicates = [case for case in curation["cases"] if case["type"] == "duplicate"]
        self.assertEqual([case["level"] for case in duplicates], ["same"])

    def test_resolving_requires_the_page_token(self) -> None:
        response = self.client.post(
            "/api/curation/identity/resolve",
            content="{}",
            headers={"Origin": "http://127.0.0.1:8765", "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 403)


class CliTests(unittest.TestCase):
    def test_the_command_resolves_and_prints_counts_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / "catalog.json"
            repository = _catalog(catalog)
            lookups = FakeLookups()
            output = io.StringIO()
            with (
                patch.object(identity_cli, "fetch_wikidata_ids_for_articles", lookups.article_ids),
                patch.object(identity_cli, "fetch_wikidata_release_years", lookups.release_years),
                redirect_stdout(output),
            ):
                code = identity_cli.main(["resolve", str(catalog)])

            self.assertEqual(code, 0)
            self.assertIn("Wikidata ids filled: 2", output.getvalue())
            self.assertNotIn("Kingdom", output.getvalue())
            self.assertEqual(repository.get("es").wikidata_id, "Q1123433")  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
