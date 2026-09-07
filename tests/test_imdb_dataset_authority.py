"""[F6.1]: the local IMDb index acting as the authority [Q5] assigned it."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from movie_inbox.domain.imdb_dataset import (
    AKA_REGIONS,
    dataset_akas,
    dataset_metadata,
    kind_from_title_type,
)
from movie_inbox.domain.normalization import normalize_kind
from movie_inbox.external.imdb_dataset_source import (
    DATASET_FIELDS,
    ImdbDatasetSource,
    apply_dataset_authority,
)
from movie_inbox.infrastructure.imdb_dataset_index import AkaEntry, TitleLookupResult


def lookup(**overrides: Any) -> TitleLookupResult:
    base: dict[str, Any] = {
        "tconst": "tt0113277",
        "title_type": "movie",
        "primary_title": "Heat",
        "original_title": "Heat",
        "start_year": 1995,
        "end_year": None,
        "runtime_minutes": 170,
        "genres": "Action,Crime,Drama",
        "akas": (
            AkaEntry("Fuego contra fuego", "AR", None, False),
            AkaEntry("Heat", "US", None, True),
            AkaEntry("Hiito", "JP", None, False),
            AkaEntry("Sin region", None, None, False),
        ),
    }
    base.update(overrides)
    return TitleLookupResult(**base)


class TitleTypeTranslationTests(unittest.TestCase):
    def test_the_translation_table_fixes_what_normalize_kind_gets_wrong(self) -> None:
        # Measured 2026-09-07: normalize_kind maps tvMiniSeries, tvEpisode,
        # videoGame and outright garbage all to "pelicula", silently. Feeding
        # IMDb's raw title_type through it would mislabel works, which is why
        # [Q5] made this translation mandatory.
        self.assertEqual(normalize_kind("tvMiniSeries"), "pelicula")
        self.assertEqual(kind_from_title_type("tvMiniSeries"), "serie")

        for raw in ("tvEpisode", "tvPilot", "videoGame", "basura", ""):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_kind(raw), "pelicula")
                # Abstaining is the point: a single episode must never decide
                # the kind of a whole work.
                self.assertEqual(kind_from_title_type(raw), "")

    def test_films_and_series_translate_as_the_matrix_specifies(self) -> None:
        for raw in ("movie", "tvMovie", "short", "tvShort", "tvSpecial"):
            with self.subTest(raw=raw):
                self.assertEqual(kind_from_title_type(raw), "pelicula")
        for raw in ("tvSeries", "tvMiniSeries"):
            with self.subTest(raw=raw):
                self.assertEqual(kind_from_title_type(raw), "serie")

    def test_translation_is_case_insensitive(self) -> None:
        self.assertEqual(kind_from_title_type("TVMINISERIES"), "serie")


class DatasetMetadataTests(unittest.TestCase):
    def test_akas_are_filtered_by_region_never_by_language(self) -> None:
        # [Q5] verified against real rows that language was empty and only the
        # region distinguished them.
        titles = dataset_akas(lookup().akas)
        self.assertIn("Fuego contra fuego", titles)
        self.assertIn("Heat", titles)
        self.assertNotIn("Hiito", titles)
        self.assertNotIn("Sin region", titles)
        self.assertIn("AR", AKA_REGIONS)
        self.assertNotIn("JP", AKA_REGIONS)

    def test_it_contributes_only_the_fields_the_matrix_assigns_it(self) -> None:
        metadata = dataset_metadata(lookup())
        self.assertTrue(set(metadata) <= DATASET_FIELDS, set(metadata) - DATASET_FIELDS)
        # Explicitly out of scope for the index: credits, images, descriptions,
        # release dates, and the per-language title scalars it cannot fill.
        for field in (
            "spanish_title",
            "english_title",
            "directors",
            "cast",
            "page_image",
            "description",
            "release_dates",
            "countries",
        ):
            self.assertNotIn(field, metadata)

    def test_structured_fields_map_across(self) -> None:
        metadata = dataset_metadata(lookup())
        self.assertEqual(metadata["year"], "1995")
        self.assertEqual(metadata["duration_minutes"], 170)
        self.assertEqual(metadata["kind"], "pelicula")
        # Left as the raw comma string: merge_lists/normalize_tags already split it.
        self.assertEqual(metadata["genres"], "Action,Crime,Drama")

    def test_absent_or_empty_values_contribute_nothing(self) -> None:
        self.assertEqual(dataset_metadata(None), {})
        sparse = dataset_metadata(
            lookup(start_year=None, runtime_minutes=None, genres=None, akas=(), title_type="short")
        )
        self.assertNotIn("year", sparse)
        self.assertNotIn("duration_minutes", sparse)
        self.assertNotIn("genres", sparse)
        self.assertNotIn("alternative_titles", sparse)

    def test_a_zero_runtime_is_not_reported_as_a_duration(self) -> None:
        self.assertNotIn("duration_minutes", dataset_metadata(lookup(runtime_minutes=0)))


class _StubSource:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def metadata_for(self, imdb_id: str) -> dict[str, Any]:
        return dict(self.payload) if imdb_id else {}


class DatasetAuthorityTests(unittest.TestCase):
    def test_the_index_wins_for_its_own_fields(self) -> None:
        # [Q5] puts the index first. Downstream merges only fill empty fields,
        # so "first" has to mean its value is already in the returned mapping.
        live = {"year": "1996", "title": "Heat (en vivo)", "description": "de Wikipedia"}
        merged = apply_dataset_authority(
            live,
            _StubSource({"year": "1995", "title": "Heat"}),
            "tt0113277",
        )
        self.assertEqual(merged["year"], "1995")
        self.assertEqual(merged["title"], "Heat")
        # Fields outside the index's lane are untouched.
        self.assertEqual(merged["description"], "de Wikipedia")

    def test_alternate_titles_are_merged_not_replaced(self) -> None:
        live = {"alternative_titles": ["Heat", "Fuego"]}
        merged = apply_dataset_authority(
            live,
            _StubSource({"alternative_titles": ["Fuego", "Fuego contra fuego"]}),
            "tt1",
        )
        self.assertEqual(merged["alternative_titles"], ["Heat", "Fuego", "Fuego contra fuego"])

    def test_without_an_index_or_an_id_the_live_metadata_passes_through(self) -> None:
        live = {"year": "1996"}
        self.assertEqual(apply_dataset_authority(live, None, "tt0113277"), live)
        self.assertEqual(
            apply_dataset_authority(live, _StubSource({"year": "1995"}), ""),
            live,
        )

    def test_the_original_mapping_is_not_mutated(self) -> None:
        live = {"year": "1996"}
        apply_dataset_authority(live, _StubSource({"year": "1995"}), "tt1")
        self.assertEqual(live, {"year": "1996"})


class MissingIndexTests(unittest.TestCase):
    def test_a_missing_index_yields_nothing_instead_of_raising(self) -> None:
        # The index is an optional accelerator: an instance that never ran
        # `imdb-dataset sync` has to keep enriching exactly as before.
        with tempfile.TemporaryDirectory() as temporary:
            source = ImdbDatasetSource(Path(temporary) / "no-existe.db")
            self.assertEqual(source.metadata_for("tt0113277"), {})

    def test_only_well_formed_imdb_ids_are_looked_up(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = ImdbDatasetSource(Path(temporary) / "no-existe.db")
            for value in ("", "0113277", "ttabc", "https://imdb.com/"):
                with self.subTest(value=value):
                    self.assertEqual(source.metadata_for(value), {})


if __name__ == "__main__":
    unittest.main()
