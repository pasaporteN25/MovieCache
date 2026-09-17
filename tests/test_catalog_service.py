"""[Q6]: CatalogService.append_item's strong-identity auto-merge gate.

Scope: a new external result that decide_match() (the same conservative,
zero-false-positive gate already trusted for Scanner auto-accept and the
CLI batch tools) recognizes as the SAME work as an existing catalog item
should fold into that item instead of prompting for a manual merge or
silently creating a second, unlinked entry. Anything decide_match doesn't
accept keeps today's exact behavior (the lexical possible-duplicate
interstitial, or a plain create) unchanged.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.models import CatalogItem
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository


class AppendItemStrongMatchTests(unittest.TestCase):
    def service(self, catalog_path: Path) -> tuple[CatalogService, JsonCatalogRepository]:
        repository = JsonCatalogRepository(catalog_path, normalize_item)
        return CatalogService(repository), repository

    def test_a_shared_wikidata_id_reports_a_strong_match_instead_of_creating_a_second_item(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-wikipedia",
                            "title": "Heat",
                            "year": "1995",
                            "source": "wikipedia",
                            "wikidata_id": "Q846982",
                        }
                    )
                ]
            )

            added, reason, extra = service.append_item(
                {
                    "id": "heat-imdb",
                    "title": "Heat",
                    "spanish_title": "Fuego contra fuego",
                    "source": "imdb",
                    "wikidata_id": "Q846982",
                }
            )

            self.assertFalse(added)
            self.assertEqual(reason, "strong_match")
            self.assertEqual(extra["existing_id"], "heat-wikipedia")
            self.assertEqual(len(repository.read()), 1)

    def test_an_exact_title_and_year_match_from_a_different_source_is_a_strong_match(self) -> None:
        # A shared external URL is already caught by append_item's pre-existing
        # exact-duplicate check before decide_match ever runs -- this exercises
        # decide_match's OTHER real acceptance path (exact title key + exact
        # year), which the old lexical possible_duplicate_candidates check
        # would only have flagged for manual review, not auto-combined.
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-wikipedia",
                            "title": "Heat",
                            "year": "1995",
                            "source": "wikipedia",
                        }
                    )
                ]
            )

            added, reason, extra = service.append_item(
                {
                    "id": "heat-filmaffinity",
                    "title": "Heat",
                    "year": "1995",
                    "source": "filmaffinity",
                }
            )

            self.assertFalse(added)
            self.assertEqual(reason, "strong_match")
            self.assertEqual(extra["existing_id"], "heat-wikipedia")

    def test_a_year_mismatch_keeps_the_existing_lexical_interstitial_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)
            repository.write([normalize_item({"id": "heat-1995", "title": "Heat", "year": "1995"})])

            added, reason, extra = service.append_item(
                {"id": "heat-1996-guess", "title": "Heat", "year": "1996"}
            )

            self.assertFalse(added)
            self.assertEqual(reason, "possible_duplicate")
            self.assertEqual(extra["candidates"][0]["id"], "heat-1995")

    def test_a_genuinely_unrelated_title_is_added_normally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)
            repository.write([normalize_item({"id": "heat-1995", "title": "Heat", "year": "1995"})])

            added, reason, extra = service.append_item(
                {"id": "arrival-2016", "title": "Arrival", "year": "2016"}
            )

            self.assertTrue(added)
            self.assertEqual(reason, "added")
            self.assertEqual(len(repository.read()), 2)

    def test_forcing_an_add_skips_the_strong_match_check_and_creates_a_second_item(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)
            repository.write(
                [
                    normalize_item(
                        {"id": "heat-wikipedia", "title": "Heat", "wikidata_id": "Q846982"}
                    )
                ]
            )

            added, reason, extra = service.append_item(
                {"id": "heat-imdb", "title": "Heat", "wikidata_id": "Q846982"},
                action="force",
            )

            self.assertTrue(added)
            self.assertEqual(reason, "added")
            self.assertEqual(len(repository.read()), 2)

    def test_conflicting_tmdb_ids_never_trigger_the_title_year_auto_merge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)
            repository.write(
                [
                    normalize_item(
                        {
                            "id": "heat-tmdb",
                            "title": "Heat",
                            "year": "1995",
                            "kind": "pelicula",
                            "tmdb_id": "949",
                        }
                    )
                ]
            )

            added, reason, extra = service.append_item(
                {
                    "id": "heat-wrong-tmdb",
                    "title": "Heat",
                    "year": "1995",
                    "kind": "pelicula",
                    "tmdb_id": "950",
                }
            )

            self.assertFalse(added)
            self.assertEqual(reason, "possible_duplicate")
            self.assertEqual(extra["candidates"][0]["id"], "heat-tmdb")
            self.assertEqual(len(repository.read()), 1)


class PatchPersonalPreconditionTests(unittest.TestCase):
    """[X2]: an optional `base` on patch_personal guards against a lost update.

    Reproduces the case ADR-0005's sync matrix ([A5.1] case 8, confirmed
    2026-09-15 against a real instance by the client harness [A5.3]): a phone
    uploads what it saw when it last downloaded, without looking at the
    server again first, silently overwriting a change made elsewhere in the
    meantime. With `base` declared, that upload is refused instead.
    """

    def service(self, catalog_path: Path) -> tuple[CatalogService, JsonCatalogRepository]:
        repository = JsonCatalogRepository(catalog_path, normalize_item)
        repository.write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        return CatalogService(repository), repository

    def _get(self, repository: JsonCatalogRepository, item_id: str = "heat") -> CatalogItem:
        item = repository.get(item_id)
        assert item is not None
        return item

    def test_without_a_base_the_last_write_still_wins_as_before(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service, repository = self.service(Path(temporary) / "catalog.json")

            updated, reason = service.patch_personal("heat", {"rating": 8})

            self.assertTrue(updated)
            self.assertEqual(reason, "updated")
            self.assertEqual(self._get(repository).rating, 8)

    def test_a_base_matching_the_stored_value_applies_normally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service, repository = self.service(Path(temporary) / "catalog.json")

            updated, reason = service.patch_personal(
                "heat", {"rating": 8, "base": {"status": "to_watch", "rating": None}}
            )

            self.assertTrue(updated)
            self.assertEqual(reason, "updated")
            self.assertEqual(self._get(repository).rating, 8)

    def test_the_lost_update_a_phone_reproduced_is_refused_instead_of_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)

            # The web (or another phone) rates it while this phone is offline.
            first = service.patch_personal("heat", {"rating": 9})
            self.assertEqual(first, (True, "updated"))

            # This phone uploads a review, believing rating is still unset --
            # its own base is what it downloaded before going offline.
            second = service.patch_personal(
                "heat", {"review": "Buenisima.", "base": {"rating": None}}
            )

            self.assertEqual(second, (False, "conflict"))
            after = self._get(repository)
            self.assertEqual(after.rating, 9, "the web's rating must survive")
            self.assertEqual(after.review, "", "the phone's review must not apply either")

    def test_a_base_field_that_is_not_being_changed_still_guards_the_patch(self) -> None:
        # A conflict is about anything the caller declared it still trusts,
        # not only the fields this particular call is writing.
        with tempfile.TemporaryDirectory() as temporary:
            catalog_path = Path(temporary) / "catalog.json"
            service, repository = self.service(catalog_path)
            service.patch_personal("heat", {"status": "watched", "watched_at": "2026-09-14"})

            updated, reason = service.patch_personal(
                "heat", {"rating": 7, "base": {"status": "to_watch"}}
            )

            self.assertEqual((updated, reason), (False, "conflict"))
            self.assertEqual(self._get(repository).rating, 0)

    def test_an_unrecognized_base_field_is_refused_up_front(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service, _ = self.service(Path(temporary) / "catalog.json")

            with self.assertRaises(ValueError):
                service.patch_personal("heat", {"rating": 7, "base": {"tmdb_id": "949"}})

    def test_a_base_that_is_not_an_object_is_refused_up_front(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service, _ = self.service(Path(temporary) / "catalog.json")

            with self.assertRaises(ValueError):
                service.patch_personal("heat", {"rating": 7, "base": "rating:0"})


if __name__ == "__main__":
    unittest.main()
