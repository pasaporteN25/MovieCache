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


if __name__ == "__main__":
    unittest.main()
