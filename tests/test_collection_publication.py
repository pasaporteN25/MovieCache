"""[B1]: how a machine-built collection is assembled and ordered.

Two defects on the same surface, both found by probing the [P2] collection a
library publishes to Club, and both reproduced end to end here before being
fixed:

  1. A library holding two copies of one film -- one scanned before its
     catalogue entry was enriched, one after -- reported the same work twice,
     because identity is stored per file and the availability query grouped by
     it. Two collection items with the same primary key: the insert failed, the
     collection was never created, and enabling sharing came back quietly with
     synced=False.
  2. The published order came from `work_key`, an internal dedup id. A shelf
     read Casablanca, Alien, Blade Runner, Dune -- TMDb ids compared as text --
     and a title jumped position the moment enrichment gave it an id.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.library_service import ManagedLibraryService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.collections import CollectionItem, collection_items_in_reading_order
from movie_inbox.domain.libraries import merged_availability_records
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.library_repository import SqliteLibraryRepository
from movie_inbox.infrastructure.library_scanner import scan_media_files

RICH_IDENTITY = {"title": "Alien", "year": "1979", "spanish_title": "El octavo pasajero"}
POOR_IDENTITY = {"title": "Alien", "year": "1979"}


def _record(
    work_key: str, identity: dict[str, Any], *, library: str = "L", files: int = 1
) -> dict[str, Any]:
    return {
        "work_key": work_key,
        "identity": identity,
        "library_id": library,
        "library_name": "Peliculas",
        "file_count": files,
    }


def _entry(item_id: str, position: int, **fields: Any) -> CollectionItem:
    return CollectionItem(id=item_id, position=position, item={"id": item_id, **fields})


class MergedAvailabilityRecordTests(unittest.TestCase):
    def test_one_work_under_two_identities_becomes_one_row(self) -> None:
        rows = merged_availability_records(
            [
                _record("tmdb:movie:348", POOR_IDENTITY),
                _record("tmdb:movie:348", RICH_IDENTITY),
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["file_count"], 2)

    def test_the_most_complete_identity_survives_whichever_arrives_first(self) -> None:
        # Enrichment only ever adds fields, so the fuller blob is the newer one
        # -- and unlike a timestamp it still decides when a single scan run
        # stamped both files with the same one.
        rich_first = merged_availability_records(
            [_record("k", RICH_IDENTITY), _record("k", POOR_IDENTITY)]
        )
        poor_first = merged_availability_records(
            [_record("k", POOR_IDENTITY), _record("k", RICH_IDENTITY)]
        )

        self.assertEqual(rich_first[0]["identity"], RICH_IDENTITY)
        self.assertEqual(poor_first[0]["identity"], RICH_IDENTITY)

    def test_two_libraries_holding_the_same_film_stay_apart(self) -> None:
        # Availability is reported per library: merging them would lose which
        # shelf the copy is on.
        rows = merged_availability_records(
            [
                _record("tmdb:movie:348", POOR_IDENTITY, library="one"),
                _record("tmdb:movie:348", POOR_IDENTITY, library="two"),
            ]
        )

        self.assertEqual(len(rows), 2)

    def test_different_works_are_untouched(self) -> None:
        rows = merged_availability_records(
            [
                _record("tmdb:movie:348", {"title": "Alien"}),
                _record("tmdb:movie:78", {"title": "Blade Runner"}),
            ]
        )

        self.assertEqual([row["work_key"] for row in rows], ["tmdb:movie:348", "tmdb:movie:78"])


class CollectionReadingOrderTests(unittest.TestCase):
    def test_a_shelf_reads_alphabetically(self) -> None:
        ordered = collection_items_in_reading_order(
            [
                _entry("tmdb:movie:289", 0, title="Casablanca"),
                _entry("tmdb:movie:348", 1, title="Alien"),
                _entry("work:2fada8", 2, title="Amanecer"),
                _entry("tmdb:movie:78", 3, title="Blade Runner"),
            ]
        )

        self.assertEqual(
            [entry.item["title"] for entry in ordered],
            ["Alien", "Amanecer", "Blade Runner", "Casablanca"],
        )

    def test_positions_are_renumbered_from_zero(self) -> None:
        ordered = collection_items_in_reading_order(
            [_entry("b", 7, title="Beta"), _entry("a", 3, title="Alfa")]
        )

        self.assertEqual([entry.position for entry in ordered], [0, 1])

    def test_it_sorts_by_the_title_the_reader_sees(self) -> None:
        # The catalogue grid displays the Spanish title when there is one, so
        # sorting on anything else would read as unsorted.
        ordered = collection_items_in_reading_order(
            [
                _entry("one", 0, title="Alien", spanish_title="El octavo pasajero"),
                _entry("two", 1, title="Dune"),
            ]
        )

        self.assertEqual([entry.item["title"] for entry in ordered], ["Dune", "Alien"])

    def test_accents_and_case_do_not_decide_the_order(self) -> None:
        ordered = collection_items_in_reading_order(
            [_entry("b", 0, title="Ambar"), _entry("a", 1, title="amanecer")]
        )

        self.assertEqual([entry.item["title"] for entry in ordered], ["amanecer", "Ambar"])

    def test_two_prints_of_the_same_title_keep_a_stable_order(self) -> None:
        # Year first, then the id: nothing here may depend on the order the rows
        # happened to arrive in, or the shelf reshuffles on every sync.
        entries = [
            _entry("z", 0, title="Dune", year="2021"),
            _entry("a", 1, title="Dune", year="1984"),
            _entry("m", 2, title="Dune", year="2021"),
        ]

        forwards = [entry.id for entry in collection_items_in_reading_order(entries)]
        backwards = [entry.id for entry in collection_items_in_reading_order(reversed(entries))]

        self.assertEqual(forwards, backwards)
        self.assertEqual(forwards, ["a", "m", "z"])


class PublishedLibraryCollectionTests(unittest.TestCase):
    """The same two defects through the real scan-and-publish path."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.media = self.root / "media"
        self.media.mkdir()
        self.catalog = self.root / "catalog.json"
        self.instance = self.root / "instance.db"
        self.items: list[dict[str, Any]] = []

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _start(self, films: list[dict[str, Any]]) -> None:
        self.items = [normalize_item(row).to_dict() for row in films]
        JsonCatalogRepository(self.catalog, normalize_item).write(
            [normalize_item(row) for row in self.items]
        )
        identity = SqliteIdentityRepository(self.instance)
        self.owner, _ = AuthService(identity).bootstrap_owner(
            "lucas",
            "a-long-local-password",
            catalog_name="Catalogo",
            source_paths=[str(self.catalog)],
            write_path=str(self.catalog),
        )
        self.repository = SqliteLibraryRepository(self.instance)
        self.collections = SqliteCollectionRepository(self.instance)
        self.service = ManagedLibraryService(
            self.repository,
            allowed_roots=(str(self.media),),
            catalog_universe=lambda: list(self.items),
            scanner=scan_media_files,
            clock=lambda: 1_800_000_000,
            collection_repository=self.collections,
        )
        self.library = self.service.create_library(
            self.owner.id,
            {"name": "Peliculas principales", "root_path": str(self.media), "schedule": "manual"},
        )

    def _scan(self) -> None:
        for mode in ("dry_run", "apply"):
            run = self.service.queue_scan(self.library.id, mode)
            self.service.execute_run(run.id)

    def test_a_second_copy_of_an_enriched_film_does_not_break_publication(self) -> None:
        self._start(
            [
                {
                    "id": "alien",
                    "title": "Alien",
                    "year": "1979",
                    "kind": "pelicula",
                    "tmdb_id": "348",
                }
            ]
        )
        (self.media / "Alien.1979.1080p.mkv").write_bytes(b"one")
        self._scan()

        # The catalogue entry gains a field, and a second copy turns up.
        self.items[0] = normalize_item(
            {**self.items[0], "spanish_title": "Alien: el octavo pasajero"}
        ).to_dict()
        (self.media / "Alien.1979.2160p.mkv").write_bytes(b"two")
        self._scan()

        records = self.repository.availability_records()
        self.assertEqual([row["work_key"] for row in records], ["tmdb:movie:348"])
        self.assertEqual(records[0]["file_count"], 2)

        _, synced = self.service.set_share_availability(self.library.id, True)

        self.assertTrue(synced)
        published = self.collections.get_by_derived_library_id(self.library.id)
        assert published is not None
        self.assertEqual([entry.id for entry in published.items], ["tmdb:movie:348"])

    def test_the_published_shelf_is_not_ordered_by_an_internal_id(self) -> None:
        films = [
            {"id": "alien", "title": "Alien", "year": "1979", "tmdb_id": "348"},
            {"id": "blade", "title": "Blade Runner", "year": "1982", "tmdb_id": "78"},
            {"id": "casa", "title": "Casablanca", "year": "1942", "tmdb_id": "289"},
            {"id": "amanecer", "title": "Amanecer", "year": "1927"},
        ]
        self._start([{**row, "kind": "pelicula"} for row in films])
        for row in films:
            name = str(row["title"]).replace(" ", ".")
            (self.media / f"{name}.{row['year']}.1080p.mkv").write_bytes(b"x")
        self._scan()

        self.service.set_share_availability(self.library.id, True)

        published = self.collections.get_by_derived_library_id(self.library.id)
        assert published is not None
        # By work_key this read Casablanca, Alien, Blade Runner, and "Amanecer"
        # came last whatever its title, because it has no TMDb id.
        self.assertEqual(
            [entry.item["title"] for entry in published.items],
            ["Alien", "Amanecer", "Blade Runner", "Casablanca"],
        )
        self.assertEqual([entry.position for entry in published.items], [0, 1, 2, 3])


if __name__ == "__main__":
    unittest.main()
