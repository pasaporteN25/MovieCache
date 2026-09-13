"""[U7.1]: counting, by cause, why a work cannot fill the console's two image windows.

The diagnosis exists so [U7.2] and [U7.3] start from numbers instead of a guess,
which puts three obligations on it that these tests hold. It must not call two
sizes of one picture two images, or it promises a second window that is not
there. It must never reach the network, because the board forbids downloading a
catalogue to measure it. And it must print counts only, because its output is
meant to be shared without sharing the catalogue.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

from movie_inbox.application.auth_service import AuthService
from movie_inbox.cli import images
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.collections import CollectionItem, CuratedCollection
from movie_inbox.domain.image_coverage import (
    CACHED,
    CATALOG_ORIGIN,
    CLUB_ORIGIN,
    EMPTY,
    NO_IDENTITY,
    OTHER_IDENTITY,
    REJECTED,
    TMDB_IDENTITY,
    UNCACHED,
    classify_work,
    image_asset_key,
    image_identity,
    summarize,
)
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.image_proxy import image_cache_key

HEAT_POSTER = "https://image.tmdb.org/t/p/w500/heat-poster.jpg"
HEAT_BACKDROP = "https://image.tmdb.org/t/p/w780/heat-backdrop.jpg"


def _allowed(url: str) -> bool:
    return "rejected.example" not in url


def _never_cached(url: str) -> bool:
    return False


class AssetKeyTests(unittest.TestCase):
    def test_one_tmdb_picture_at_two_sizes_is_one_image(self) -> None:
        self.assertEqual(
            image_asset_key("https://image.tmdb.org/t/p/w500/abc.jpg"),
            image_asset_key("https://image.tmdb.org/t/p/original/abc.jpg"),
        )

    def test_a_wikimedia_thumbnail_is_the_file_it_was_cut_from(self) -> None:
        original = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Heat_poster.jpg"
        thumbnail = (
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Heat_poster.jpg/"
            "500px-Heat_poster.jpg"
        )
        self.assertEqual(image_asset_key(original), image_asset_key(thumbnail))

    def test_amazon_rendition_suffixes_do_not_make_a_new_image(self) -> None:
        base = "https://m.media-amazon.com/images/M/MV5BYjZjNTJlZGUtZTE1Ny00ZDc4LTgwYjUtMzk0NDgwYzZjYTk1XkEyXkFqcGdeQXVyNjU0OTQ0OTY@"
        self.assertEqual(
            image_asset_key(f"{base}._V1_.jpg"),
            image_asset_key(f"{base}._V1_QL75_UX380_CR0,0,380,562_.jpg"),
        )
        self.assertEqual(image_asset_key(f"{base}._V1_SX300.jpg"), image_asset_key(f"{base}.jpg"))

    def test_filmaffinity_and_myanimelist_sizes_are_one_image(self) -> None:
        self.assertEqual(
            image_asset_key("https://pics.filmaffinity.com/heat-120866914-large.jpg"),
            image_asset_key("https://pics.filmaffinity.com/heat-120866914-mmed.jpg"),
        )
        self.assertEqual(
            image_asset_key("https://cdn.myanimelist.net/images/anime/1/2.jpg"),
            image_asset_key("https://cdn.myanimelist.net/images/anime/1/2l.jpg"),
        )

    def test_different_pictures_stay_different(self) -> None:
        pairs = (
            ("https://image.tmdb.org/t/p/w500/abc.jpg", "https://image.tmdb.org/t/p/w500/def.jpg"),
            (
                "https://upload.wikimedia.org/wikipedia/commons/a/ab/One.jpg",
                "https://upload.wikimedia.org/wikipedia/commons/a/ab/Two.jpg",
            ),
            (
                "https://cdn.myanimelist.net/images/anime/1/2.jpg",
                "https://cdn.myanimelist.net/images/anime/1/3.jpg",
            ),
        )
        for first, second in pairs:
            with self.subTest(first=first):
                self.assertNotEqual(image_asset_key(first), image_asset_key(second))

    def test_an_unknown_host_is_never_folded(self) -> None:
        # Guessing that a suffix means a size on a host nobody measured would
        # merge two real images; keeping them apart only overstates coverage.
        self.assertNotEqual(
            image_asset_key("https://images.example.org/a-120866914-large.jpg"),
            image_asset_key("https://images.example.org/a-120866914-mmed.jpg"),
        )


class ClassificationTests(unittest.TestCase):
    def test_each_slot_names_its_cause(self) -> None:
        work = classify_work(
            {"page_image": HEAT_POSTER, "backdrop_image": ""},
            CATALOG_ORIGIN,
            allowed=_allowed,
            cached=lambda url: url == HEAT_POSTER,
        )
        self.assertEqual((work.poster, work.backdrop), (CACHED, EMPTY))

        work = classify_work(
            {"page_image": "https://rejected.example/p.jpg", "backdrop_image": HEAT_BACKDROP},
            CATALOG_ORIGIN,
            allowed=_allowed,
            cached=_never_cached,
        )
        self.assertEqual((work.poster, work.backdrop), (REJECTED, UNCACHED))

    def test_one_picture_in_both_fields_fills_one_window(self) -> None:
        work = classify_work(
            {
                "page_image": "https://image.tmdb.org/t/p/w500/same.jpg",
                "backdrop_image": "https://image.tmdb.org/t/p/original/same.jpg",
            },
            CATALOG_ORIGIN,
            allowed=_allowed,
            cached=_never_cached,
        )
        self.assertEqual(work.distinct, 1)

    def test_an_address_the_proxy_refuses_fills_nothing(self) -> None:
        work = classify_work(
            {"page_image": "https://rejected.example/p.jpg", "backdrop_image": HEAT_BACKDROP},
            CATALOG_ORIGIN,
            allowed=_allowed,
            cached=_never_cached,
        )
        self.assertEqual(work.distinct, 1)

    def test_identity_says_whether_a_provider_could_be_asked(self) -> None:
        cases: tuple[tuple[dict[str, Any], str], ...] = (
            ({"tmdb_id": "949"}, TMDB_IDENTITY),
            ({"tmdb_url": "https://www.themoviedb.org/movie/949"}, TMDB_IDENTITY),
            ({"imdb_url": "https://www.imdb.com/title/tt0113277/"}, OTHER_IDENTITY),
            ({"wikidata_id": "Q1136"}, OTHER_IDENTITY),
            ({"myanimelist_url": "https://myanimelist.net/anime/199/"}, OTHER_IDENTITY),
            # A title that looks right is not identity: [U7.2] may not ask on it.
            ({"title": "Heat", "year": "1995"}, NO_IDENTITY),
        )
        for item, expected in cases:
            with self.subTest(item=item):
                self.assertEqual(image_identity(item), expected)


class SummaryTests(unittest.TestCase):
    def test_counts_split_by_origin_and_kind_and_add_up(self) -> None:
        rows = [
            classify_work(
                {
                    "kind": "pelicula",
                    "tmdb_id": "1",
                    "page_image": HEAT_POSTER,
                    "backdrop_image": HEAT_BACKDROP,
                },
                CATALOG_ORIGIN,
                allowed=_allowed,
                cached=_never_cached,
            ),
            classify_work(
                {"kind": "serie", "page_image": HEAT_POSTER},
                CATALOG_ORIGIN,
                allowed=_allowed,
                cached=_never_cached,
            ),
            classify_work(
                {"kind": "pelicula"}, CLUB_ORIGIN, allowed=_allowed, cached=_never_cached
            ),
        ]
        report = summarize(rows)

        self.assertEqual(report["totals"]["works"], 3)
        self.assertEqual(
            [
                (segment["origin"], segment["kind"], segment["works"])
                for segment in report["segments"]
            ],
            [
                (CATALOG_ORIGIN, "pelicula", 1),
                (CATALOG_ORIGIN, "serie", 1),
                (CLUB_ORIGIN, "pelicula", 1),
            ],
        )
        self.assertEqual(report["totals"]["distinct_images"], {"0": 1, "1": 1, "2": 1})
        # Only works that cannot fill both windows count toward what [U7.2] has to find.
        self.assertEqual(
            report["totals"]["short_by_identity"],
            {TMDB_IDENTITY: 0, OTHER_IDENTITY: 0, NO_IDENTITY: 2},
        )


class CoverageCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog = root / "catalog.json"
        self.works = [
            {
                "id": "heat",
                "title": "Heat",
                "year": "1995",
                "kind": "pelicula",
                "tmdb_id": "949",
                "page_image": HEAT_POSTER,
                "backdrop_image": HEAT_BACKDROP,
            },
            {
                "id": "mismo-poster",
                "title": "Mismo poster",
                "kind": "pelicula",
                "tmdb_id": "1",
                "page_image": "https://image.tmdb.org/t/p/w500/same.jpg",
                "backdrop_image": "https://image.tmdb.org/t/p/original/same.jpg",
            },
            {
                "id": "sin-nada",
                "title": "Sin nada todavia",
                "kind": "serie",
            },
        ]
        JsonCatalogRepository(self.catalog, normalize_item).write(
            [normalize_item(work) for work in self.works]
        )
        self.cache_dir = root / "images"
        self.cache_dir.mkdir()
        (self.cache_dir / f"{image_cache_key(HEAT_POSTER)}.jpg").write_bytes(b"\xff\xd8\xff")

        self.instance_db = root / "instance.db"
        identity = SqliteIdentityRepository(self.instance_db)
        AuthService(identity).bootstrap_owner(
            "lucas",
            "a-long-local-password",
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog)],
            write_path=str(self.catalog),
        )
        owner = identity.owner()
        assert owner is not None
        collections = SqliteCollectionRepository(self.instance_db)
        heat_in_club = {"id": "heat", "title": "Heat", "year": "1995", "tmdb_id": "949"}
        only_in_club = {"id": "solo-club", "title": "Solo en Club", "year": "1954", "tmdb_id": "5"}
        for slug, rows in (("una", [heat_in_club, only_in_club]), ("otra", [heat_in_club])):
            collections.create_private(
                CuratedCollection(
                    id=slug,
                    slug=slug,
                    title=f"Lista {slug}",
                    description="",
                    owner_user_id=owner.id,
                    source_kind="import",
                    items=tuple(
                        CollectionItem(id=f"{slug}-{index}", position=index, item=dict(row))
                        for index, row in enumerate(rows)
                    ),
                )
            )

    def _run(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = images.main(
                ["coverage", str(self.catalog), "--image-cache-dir", str(self.cache_dir), *extra]
            )
        return code, out.getvalue(), err.getvalue()

    def test_the_report_counts_each_cause(self) -> None:
        code, out, _err = self._run("--json")
        self.assertEqual(code, 0)
        totals = json.loads(out)["totals"]

        self.assertEqual(totals["works"], 3)
        self.assertEqual(totals["poster"], {EMPTY: 1, REJECTED: 0, UNCACHED: 1, CACHED: 1})
        self.assertEqual(totals["backdrop"], {EMPTY: 1, REJECTED: 0, UNCACHED: 2, CACHED: 0})
        # Heat fills both windows; one picture twice fills one; nothing fills none.
        self.assertEqual(totals["distinct_images"], {"0": 1, "1": 1, "2": 1})
        self.assertEqual(
            totals["short_by_identity"], {TMDB_IDENTITY: 1, OTHER_IDENTITY: 0, NO_IDENTITY: 1}
        )

    def test_a_host_serve_does_not_allow_is_rejected_unless_it_is_passed_the_same_way(self) -> None:
        JsonCatalogRepository(self.catalog, normalize_item).write(
            [
                normalize_item(
                    {
                        "id": "ajena",
                        "title": "Ajena",
                        "page_image": "https://images.example.org/a.jpg",
                    }
                )
            ]
        )
        _code, out, _err = self._run("--json")
        self.assertEqual(json.loads(out)["totals"]["poster"][REJECTED], 1)

        _code, out, _err = self._run("--json", "--image-host", "images.example.org")
        self.assertEqual(json.loads(out)["totals"]["poster"][UNCACHED], 1)

    def test_club_counts_each_work_once_however_many_lists_carry_it(self) -> None:
        code, out, _err = self._run("--json", "--instance-db", str(self.instance_db))
        self.assertEqual(code, 0)
        club = [
            segment for segment in json.loads(out)["segments"] if segment["origin"] == CLUB_ORIGIN
        ]

        self.assertEqual(
            [(segment["kind"], segment["works"]) for segment in club], [("pelicula", 2)]
        )

    def test_it_never_reaches_the_network(self) -> None:
        refuse = mock.Mock(side_effect=AssertionError("the diagnosis must not download"))
        with (
            mock.patch("urllib.request.urlopen", refuse),
            mock.patch("movie_inbox.web.security.open_public_url", refuse),
            mock.patch("movie_inbox.web.image_proxy.download_image", refuse),
        ):
            code, _out, _err = self._run("--instance-db", str(self.instance_db))
        self.assertEqual(code, 0)
        refuse.assert_not_called()

    def test_the_output_names_no_title_address_or_path(self) -> None:
        for extra in ((), ("--json",)):
            with self.subTest(extra=extra):
                _code, out, _err = self._run(*extra, "--instance-db", str(self.instance_db))
                for secret in (
                    "Heat",
                    "Solo en Club",
                    "heat-poster",
                    "image.tmdb.org",
                    self.temporary.name,
                ):
                    self.assertNotIn(secret, out)

    def test_a_missing_catalogue_is_an_error_not_an_empty_report(self) -> None:
        self.catalog.unlink()
        code, out, err = self._run()
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("catalog not found", err)


if __name__ == "__main__":
    unittest.main()
