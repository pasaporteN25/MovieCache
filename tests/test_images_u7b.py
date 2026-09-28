"""[U7 B] Image candidates, id-only crosswalk to TMDb and fill-only writes.

The acceptance cases are the ones in `docs/analisis/u7b-contrato-imagenes-2026-09-26.md`;
each test names its case number. The source is a fake, so nothing here reaches
the network, and every catalogue is disposable.
"""

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.image_service import ImageService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.external_retirement import retire_tmdb_metadata
from movie_inbox.domain.images import (
    ACCEPTED,
    AMBIGUOUS,
    KIND_MISMATCH,
    NO_RESULT,
    NO_YEAR,
    YEAR_MISMATCH,
    ImageCandidate,
    ImageSourceUnavailable,
    TmdbMatch,
    crosswalk_decision,
    fill_empty_fields,
    tmdb_image_candidates,
)
from movie_inbox.external.image_sources import TmdbImageSource
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

BACKDROP_URL = "https://image.tmdb.org/t/p/w780/panoramica-a.jpg"
POSTER_URL = "https://image.tmdb.org/t/p/w500/portada-a.jpg"


def tmdb_images() -> dict[str, Any]:
    return {
        "backdrops": [
            {"file_path": "/con-texto.jpg", "iso_639_1": "en", "vote_count": 50, "width": 3840},
            {"file_path": "/panoramica-a.jpg", "iso_639_1": None, "vote_count": 9, "width": 1920},
            {"file_path": "/panoramica-b.jpg", "iso_639_1": None, "vote_count": 3, "width": 3840},
            # The same file twice is one picture.
            {"file_path": "/panoramica-a.jpg", "iso_639_1": None, "vote_count": 9, "width": 1920},
            {"file_path": "javascript:alert(1)", "iso_639_1": None},
        ],
        "posters": [
            {"file_path": "/portada-en.jpg", "iso_639_1": "en", "vote_count": 99},
            {"file_path": "/portada-a.jpg", "iso_639_1": "es", "vote_count": 2},
        ],
    }


class FakeSource:
    def __init__(self) -> None:
        self.images: dict[tuple[str, str], list[ImageCandidate]] = {}
        self.imdb: dict[str, list[TmdbMatch]] = {}
        self.wikidata: dict[str, list[TmdbMatch]] = {}
        self.calls: list[tuple[str, str]] = []
        self.error: ImageSourceUnavailable | None = None

    def candidates(self, media_type: str, tmdb_id: str) -> list[ImageCandidate]:
        self.calls.append(("images", f"{media_type}/{tmdb_id}"))
        if self.error is not None:
            raise self.error
        return self.images.get((media_type, tmdb_id), [])

    def matches_for_imdb(self, imdb_id: str) -> list[TmdbMatch]:
        self.calls.append(("imdb", imdb_id))
        if self.error is not None:
            raise self.error
        return self.imdb.get(imdb_id, [])

    def matches_for_wikidata(self, entity_id: str) -> list[TmdbMatch]:
        self.calls.append(("wikidata", entity_id))
        return self.wikidata.get(entity_id, [])


class DomainTests(unittest.TestCase):
    def test_candidates_are_ordered_deduplicated_and_sized_per_role(self) -> None:
        rows = tmdb_image_candidates(tmdb_images())
        backdrops = [row.url for row in rows if row.role == "backdrop"]
        posters = [row.url for row in rows if row.role == "poster"]
        # Textless backdrops first, by votes; the one with text last.
        self.assertEqual(
            backdrops,
            [
                BACKDROP_URL,
                "https://image.tmdb.org/t/p/w780/panoramica-b.jpg",
                "https://image.tmdb.org/t/p/w780/con-texto.jpg",
            ],
        )
        # Spanish poster before English, whatever the votes.
        self.assertEqual(posters[0], POSTER_URL)
        self.assertEqual(rows[0].key, "tmdb:/panoramica-a.jpg")

    def test_crosswalk_rule(self) -> None:
        movie = {"kind": "pelicula", "year": "1995"}
        cases = [
            ([], NO_RESULT),
            ([TmdbMatch("movie", "1", "1995"), TmdbMatch("tv", "2", "1995")], AMBIGUOUS),
            ([TmdbMatch("tv", "1", "1995")], KIND_MISMATCH),
            ([TmdbMatch("movie", "1", "1997")], YEAR_MISMATCH),
            ([TmdbMatch("movie", "1", "1996")], ACCEPTED),
        ]
        for matches, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(crosswalk_decision(movie, matches).status, expected)
        self.assertEqual(
            crosswalk_decision({"kind": "pelicula"}, [TmdbMatch("movie", "1", "1995")]).status,
            NO_YEAR,
        )
        self.assertTrue(
            crosswalk_decision(
                {"kind": "anime", "year": "1988"}, [TmdbMatch("tv", "9", "1988")]
            ).accepted
        )

    def test_fill_only_respects_locks_and_present_values(self) -> None:
        item: dict[str, Any] = {
            "page_image": "https://example.org/manual.jpg",
            "backdrop_image": "",
            "locked_fields": ["tmdb_id"],
        }
        result = fill_empty_fields(
            item,
            {"page_image": POSTER_URL, "backdrop_image": BACKDROP_URL, "tmdb_id": "1"},
            {"source": "tmdb", "url": "", "updated_at": "", "inferred": False},
        )
        self.assertEqual(result.filled, ["backdrop_image"])
        self.assertEqual(result.kept, ["page_image"])
        self.assertEqual(result.skipped_locked, ["tmdb_id"])
        self.assertEqual(item["page_image"], "https://example.org/manual.jpg")
        self.assertEqual(item["metadata_sources"]["backdrop_image"]["source"], "tmdb")


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "catalog.json"
        self.source = FakeSource()
        self.source.images[("movie", "949")] = tmdb_image_candidates(tmdb_images())
        self.now = datetime(2026, 9, 27, tzinfo=UTC)
        self.service = ImageService(self.source, clock=lambda: self.now)

    def catalog(self, *rows: dict[str, Any]) -> CatalogService:
        JsonCatalogRepository(self.path, normalize_item).write(
            [normalize_item({"kind": "pelicula", **row}) for row in rows]
        )
        return CatalogService(JsonCatalogRepository(self.path, normalize_item))

    def item(self, catalog: CatalogService, item_id: str) -> dict[str, Any]:
        found = catalog.repository.get(item_id)
        assert found is not None
        return found.to_dict()

    def test_case_1_known_tmdb_identity_gains_both_images(self) -> None:
        catalog = self.catalog(
            {
                "id": "heat",
                "title": "Heat",
                "year": "1995",
                "tmdb_url": "https://www.themoviedb.org/movie/949",
            }
        )
        result = self.service.fill(catalog, "heat")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(sorted(result["filled"]), ["backdrop_image", "page_image"])
        item = self.item(catalog, "heat")
        self.assertEqual(item["backdrop_image"], BACKDROP_URL)
        self.assertEqual(item["page_image"], POSTER_URL)
        record = item["metadata_sources"]["backdrop_image"]
        self.assertEqual(record["source"], "tmdb")
        self.assertEqual(record["url"], "https://www.themoviedb.org/movie/949")
        self.assertFalse(record["inferred"])

    def test_cases_2_and_3_locked_and_manual_images_are_never_replaced(self) -> None:
        catalog = self.catalog(
            {
                "id": "heat",
                "year": "1995",
                "tmdb_url": "https://www.themoviedb.org/movie/949",
                "page_image": "https://example.org/mi-portada.jpg",
                "locked_fields": ["backdrop_image"],
            }
        )
        result = self.service.fill(catalog, "heat")
        self.assertEqual(result["status"], "complete")
        item = self.item(catalog, "heat")
        self.assertEqual(item["page_image"], "https://example.org/mi-portada.jpg")
        self.assertEqual(item["backdrop_image"], "")
        self.assertEqual(self.source.calls, [])

    def test_case_4_crosswalk_from_imdb_writes_an_inferred_identity(self) -> None:
        self.source.imdb["tt0113277"] = [TmdbMatch("movie", "949", "1995")]
        catalog = self.catalog(
            {"id": "heat", "year": "1995", "imdb_url": "https://www.imdb.com/title/tt0113277/"}
        )
        # One work on demand never crosswalks; the explicit batch does.
        self.assertEqual(self.service.fill(catalog, "heat")["status"], "no_identity")
        self.assertEqual(self.source.calls, [])
        summary = self.service.fill_batch(catalog, limit=5)
        self.assertEqual(summary["identities_added"], 1)
        item = self.item(catalog, "heat")
        self.assertEqual(item["tmdb_id"], "949")
        self.assertEqual(item["tmdb_url"], "https://www.themoviedb.org/movie/949")
        self.assertTrue(item["metadata_sources"]["tmdb_id"]["inferred"])
        self.assertTrue(item["metadata_sources"]["backdrop_image"]["inferred"])

    def test_case_4_doubtful_crosswalk_writes_nothing_and_never_uses_the_title(self) -> None:
        self.source.imdb["tt0113277"] = [TmdbMatch("movie", "949", "2003")]
        catalog = self.catalog(
            {
                "id": "heat",
                "title": "Heat",
                "year": "1995",
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
            }
        )
        summary = self.service.fill_batch(catalog, limit=5)
        self.assertEqual(summary["by_status"], {"needs_review": 1})
        self.assertEqual(summary["crosswalk"], {YEAR_MISMATCH: 1})
        self.assertEqual(self.item(catalog, "heat")["tmdb_id"], "")
        self.assertEqual(self.source.calls, [("imdb", "tt0113277")])

    def test_wikidata_is_the_crosswalk_only_without_imdb(self) -> None:
        self.source.wikidata["Q1"] = [TmdbMatch("movie", "949", "1995")]
        catalog = self.catalog({"id": "heat", "year": "1995", "wikidata_id": "Q1"})
        self.assertEqual(self.service.fill_batch(catalog, limit=5)["by_status"], {"ok": 1})
        self.assertEqual(self.source.calls[0], ("wikidata", "Q1"))

    def test_a_work_without_ids_is_no_identity(self) -> None:
        catalog = self.catalog({"id": "x", "title": "Heat", "year": "1995"})
        self.assertEqual(self.service.fill(catalog, "x")["status"], "no_identity")
        self.assertEqual(self.source.calls, [])

    def test_case_6_unavailable_source_changes_nothing(self) -> None:
        catalog = self.catalog(
            {"id": "heat", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/949"}
        )
        self.source.error = ImageSourceUnavailable("down")
        self.assertEqual(self.service.fill(catalog, "heat")["status"], "unavailable")
        self.source.error = ImageSourceUnavailable("slow", rate_limited=True)
        self.assertEqual(self.service.fill(catalog, "heat")["status"], "rate_limited")
        self.assertEqual(self.item(catalog, "heat")["backdrop_image"], "")
        no_source = ImageService(None)
        self.assertEqual(no_source.fill(catalog, "heat")["status"], "unavailable")

    def test_case_8_no_images_is_remembered_for_seven_days(self) -> None:
        catalog = self.catalog(
            {"id": "w", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/5"}
        )
        self.assertEqual(self.service.fill(catalog, "w")["status"], "no_images")
        self.assertEqual(self.service.fill(catalog, "w")["status"], "no_images")
        self.assertEqual(len(self.source.calls), 1)
        self.now += timedelta(days=8)
        self.service.fill(catalog, "w")
        self.assertEqual(len(self.source.calls), 2)

    def test_case_9_retiring_tmdb_removes_its_images_and_keeps_manual_ones(self) -> None:
        self.source.imdb["tt0113277"] = [TmdbMatch("movie", "949", "1995")]
        catalog = self.catalog(
            {
                "id": "heat",
                "year": "1995",
                "imdb_url": "https://www.imdb.com/title/tt0113277/",
                "page_image": "https://example.org/mi-portada.jpg",
            }
        )
        self.service.fill_batch(catalog, limit=5)
        purged, _report = retire_tmdb_metadata(self.item(catalog, "heat"))
        self.assertEqual(purged["backdrop_image"], "")
        self.assertEqual(purged["tmdb_id"], "")
        self.assertEqual(purged["page_image"], "https://example.org/mi-portada.jpg")

    def test_case_10_export_import_keeps_values_provenance_and_locks(self) -> None:
        catalog = self.catalog(
            {"id": "heat", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/949"}
        )
        self.service.fill(catalog, "heat")
        exported = self.item(catalog, "heat")
        exported["locked_fields"] = ["backdrop_image"]
        reimported = normalize_item(json.loads(json.dumps(exported))).to_dict()
        for field in ("page_image", "backdrop_image", "metadata_sources", "locked_fields"):
            self.assertEqual(reimported[field], exported[field], field)

    def test_case_11_one_fill_in_flight_per_work(self) -> None:
        catalog = self.catalog(
            {"id": "heat", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/949"}
        )
        started = threading.Event()
        release = threading.Event()
        original = self.source.candidates

        def slow(media_type: str, tmdb_id: str) -> list[ImageCandidate]:
            started.set()
            release.wait(5)
            return original(media_type, tmdb_id)

        self.source.candidates = slow  # type: ignore[method-assign]
        results: list[dict[str, Any]] = []
        first = threading.Thread(target=lambda: results.append(self.service.fill(catalog, "heat")))
        first.start()
        started.wait(5)
        second = threading.Thread(target=lambda: results.append(self.service.fill(catalog, "heat")))
        second.start()
        release.set()
        first.join(5)
        second.join(5)
        self.assertEqual(sorted(result["status"] for result in results), ["complete", "ok"])
        self.assertEqual(len([call for call in self.source.calls if call[0] == "images"]), 1)

    def test_batch_is_limited_writes_once_and_dry_run_writes_nothing(self) -> None:
        self.source.imdb["tt0113277"] = [TmdbMatch("movie", "949", "1995")]
        rows = [
            {"id": "a", "year": "1995", "imdb_url": "https://www.imdb.com/title/tt0113277/"},
            {"id": "b", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/949"},
            {"id": "c", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/949"},
        ]
        catalog = self.catalog(*rows)
        dry = self.service.fill_batch(catalog, limit=2, dry_run=True)
        self.assertEqual(
            (dry["considered"], dry["would_fill"], dry["would_add_identity"]), (2, 4, 1)
        )
        self.assertEqual(self.item(catalog, "a")["backdrop_image"], "")
        with patch.object(catalog.repository, "mutate", wraps=catalog.repository.mutate) as mutate:
            written = self.service.fill_batch(catalog, limit=2)
        self.assertEqual(mutate.call_count, 1)
        self.assertEqual((written["filled_fields"], written["identities_added"]), (6, 1))
        self.assertEqual(self.item(catalog, "c")["backdrop_image"], "")

    def test_batch_stops_when_tmdb_asks_to_wait(self) -> None:
        catalog = self.catalog(
            {"id": "a", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/949"},
            {"id": "b", "year": "1995", "tmdb_url": "https://www.themoviedb.org/movie/949"},
        )
        self.source.error = ImageSourceUnavailable("429", rate_limited=True)
        summary = self.service.fill_batch(catalog, limit=10)
        self.assertEqual(summary["by_status"], {"rate_limited": 1})


class AdapterTests(unittest.TestCase):
    def test_http_errors_become_unavailable_and_404_is_an_empty_answer(self) -> None:
        class Adapter:
            def __init__(self, code: int) -> None:
                self.code = code

            def images(self, media_type: str, tmdb_id: str) -> dict[str, Any]:
                raise HTTPError(
                    "https://api.themoviedb.org",
                    self.code,
                    "x",
                    Message(),
                    io.BytesIO(b""),
                )

        self.assertEqual(TmdbImageSource(Adapter(404)).candidates("movie", "1"), [])  # type: ignore[arg-type]
        with self.assertRaises(ImageSourceUnavailable) as caught:
            TmdbImageSource(Adapter(429)).candidates("movie", "1")  # type: ignore[arg-type]
        self.assertTrue(caught.exception.rate_limited)
        with self.assertRaises(ImageSourceUnavailable) as caught:
            TmdbImageSource(Adapter(500)).candidates("movie", "1")  # type: ignore[arg-type]
        self.assertFalse(caught.exception.rate_limited)


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "heat",
                        "title": "Heat",
                        "year": "1995",
                        "kind": "pelicula",
                        "tmdb_url": "https://www.themoviedb.org/movie/949",
                    }
                )
            ]
        )
        instance = root / "instance.db"
        AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
            "lucas",
            "a-long-local-password",
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        media = root / "media"
        media.mkdir()
        config = ViewerConfig(
            patterns=[str(self.catalog_path)],
            title="Movie Inbox Test",
            write_json=str(self.catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(instance),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media),),
            library_scheduler_poll_seconds=3600,
        )
        self.app = create_app(config)
        context = TestClient(self.app, base_url="http://127.0.0.1:8765")
        self.client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.headers = {
            "X-Movie-Inbox-Token": "test-token",
            "Origin": "http://127.0.0.1:8765",
            "Content-Type": "application/json",
        }
        login = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": "a-long-local-password"}),
            headers=self.headers,
        )
        self.assertEqual(login.status_code, 200, login.content)

    def test_without_a_token_the_routes_answer_unavailable(self) -> None:
        response = self.client.get("/api/items/heat/image-candidates", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "unavailable")
        response = self.client.post(
            "/api/items/heat/images/fill", content="{}", headers=self.headers
        )
        self.assertEqual(response.json()["status"], "unavailable")

    def test_candidates_and_fill_through_the_real_routes(self) -> None:
        source = FakeSource()
        source.images[("movie", "949")] = tmdb_image_candidates(tmdb_images())
        self.app.state.image_service = ImageService(source)
        payload = self.client.get("/api/items/heat/image-candidates", headers=self.headers).json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["identity"]["tmdb_id"], "949")
        self.assertTrue(payload["attribution"])
        self.assertEqual(payload["candidates"][0]["url"], BACKDROP_URL)
        filled = self.client.post(
            "/api/items/heat/images/fill", content="{}", headers=self.headers
        ).json()
        self.assertEqual(sorted(filled["filled"]), ["backdrop_image", "page_image"])
        stored = JsonCatalogRepository(self.catalog_path, normalize_item).get("heat")
        assert stored is not None
        self.assertEqual(stored.to_dict()["backdrop_image"], BACKDROP_URL)

    def test_case_5_unknown_or_foreign_work_is_404(self) -> None:
        self.app.state.image_service = ImageService(FakeSource())
        for response in (
            self.client.get("/api/items/ajena/image-candidates", headers=self.headers),
            self.client.post("/api/items/ajena/images/fill", content="{}", headers=self.headers),
        ):
            self.assertEqual(response.status_code, 404, response.content)

    def test_page_image_is_now_editable_like_the_backdrop(self) -> None:
        response = self.client.post(
            "/api/metadata",
            content=json.dumps(
                {
                    "id": "heat",
                    "values": {"page_image": POSTER_URL},
                    "locked_fields": ["page_image"],
                }
            ),
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.content)
        stored = JsonCatalogRepository(self.catalog_path, normalize_item).get("heat")
        assert stored is not None
        self.assertEqual(stored.to_dict()["page_image"], POSTER_URL)
        self.assertIn("page_image", stored.to_dict()["locked_fields"])


if __name__ == "__main__":
    unittest.main()
