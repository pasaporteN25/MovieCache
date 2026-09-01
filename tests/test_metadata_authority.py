"""Fixtures for [Q5]: authority = fill order, never overwrites a completed field.

Scope: this file exercises only EXISTING functions (`merge_metadata_field`,
`merge_lists`, `normalize_kind`, `normalize_item`) with synthetic multi-source
data. It changes no production code — it documents and protects the policy
the owner chose (tareas.md, [Q5]) and the two real footguns found while
designing it: calling `merge_metadata_field` with a hand-built `incoming`
dict that OMITS a key (instead of setting it to `""`) falsely attributes an
empty write to a source that never mentioned the field, and passing IMDb's
raw `title_type` straight through to `incoming["kind"]` silently mis-maps it
via `normalize_kind()`'s own separate, incomplete vocabulary.
"""

from __future__ import annotations

import unittest

from movie_inbox.domain.catalog import merge_lists, merge_metadata_field, normalize_item
from movie_inbox.domain.normalization import normalize_kind


class EmptyFieldTests(unittest.TestCase):
    def test_an_empty_field_is_filled_by_whichever_source_has_it(self) -> None:
        existing = normalize_item({"id": "x", "description": ""}).to_dict()
        incoming = normalize_item(
            {"source": "wikipedia", "description": "Un detective persigue a un ladrón."}
        ).to_dict()
        merge_metadata_field(existing, incoming, "description")
        self.assertEqual(existing["description"], "Un detective persigue a un ladrón.")
        self.assertEqual(existing["metadata_sources"]["description"]["source"], "wikipedia")


class DivergentValueTests(unittest.TestCase):
    def test_a_completed_scalar_field_never_changes_regardless_of_the_new_sources_value(
        self,
    ) -> None:
        existing = normalize_item({"id": "x", "year": "1995"}).to_dict()
        existing["metadata_sources"] = {
            "year": {"source": "filmaffinity", "url": "", "updated_at": "", "inferred": False}
        }
        incoming = normalize_item({"source": "imdb_dataset", "year": "1996"}).to_dict()
        merge_metadata_field(existing, incoming, "year")
        self.assertEqual(existing["year"], "1995")
        self.assertEqual(existing["metadata_sources"]["year"]["source"], "filmaffinity")


class ListFieldTests(unittest.TestCase):
    def test_merge_lists_unions_case_insensitively_keeping_the_first_sides_casing(self) -> None:
        self.assertEqual(
            merge_lists(["Michael Mann"], ["michael mann", "Someone Else"]),
            ["Michael Mann", "Someone Else"],
        )

    def test_two_sources_disagreeing_on_a_list_field_end_up_unioned_not_replaced(self) -> None:
        existing = normalize_item(
            {"id": "x", "source": "imdb", "directors": ["Michael Mann"]}
        ).to_dict()
        incoming = normalize_item(
            {"source": "filmaffinity", "directors": ["Michael Mann", "Someone Else"]}
        ).to_dict()
        merge_metadata_field(existing, incoming, "directors")
        self.assertEqual(existing["directors"], ["Michael Mann", "Someone Else"])
        self.assertEqual(
            existing["metadata_sources"]["directors"]["source"],
            "imdb+filmaffinity",
        )

    def test_tmdb_list_completion_records_both_contributors_for_safe_retirement(self) -> None:
        existing = normalize_item({"id": "x", "source": "imdb", "genres": ["Drama"]}).to_dict()
        incoming = normalize_item({"source": "tmdb", "genres": ["Drama", "History"]}).to_dict()

        merge_metadata_field(existing, incoming, "genres")

        self.assertEqual(existing["genres"], ["Drama", "History"])
        self.assertEqual(existing["metadata_sources"]["genres"]["source"], "imdb+tmdb")

    def test_imdb_datasets_comma_joined_genres_string_unions_with_zero_new_code(self) -> None:
        existing = normalize_item({"id": "x", "genres": ["Drama"]}).to_dict()
        incoming = normalize_item(
            {"source": "imdb_dataset", "genres": "Action,Crime,Drama"}
        ).to_dict()
        merge_metadata_field(existing, incoming, "genres")
        self.assertEqual(existing["genres"], ["Drama", "Action", "Crime"])


class SourceDownTests(unittest.TestCase):
    def test_a_source_with_nothing_to_contribute_never_disturbs_the_existing_value(self) -> None:
        existing = normalize_item({"id": "x", "description": "Ya tiene sinopsis."}).to_dict()
        existing["metadata_sources"] = {
            "description": {"source": "wikipedia", "url": "", "updated_at": "", "inferred": False}
        }
        # normalize_item() coerces the omitted "description" key to "" here,
        # exactly like the real merge_into_existing() call site does — a hand
        # -built dict that skips this step would falsely attribute an empty
        # write to "filmaffinity" (see the module docstring).
        incoming = normalize_item({"source": "filmaffinity"}).to_dict()
        merge_metadata_field(existing, incoming, "description")
        self.assertEqual(existing["description"], "Ya tiene sinopsis.")
        self.assertEqual(existing["metadata_sources"]["description"]["source"], "wikipedia")


class ManualDataTests(unittest.TestCase):
    def test_locking_an_empty_field_blocks_even_its_first_fill(self) -> None:
        existing = normalize_item(
            {"id": "x", "description": "", "locked_fields": ["description"]}
        ).to_dict()
        incoming = normalize_item(
            {"source": "wikipedia", "description": "Una sinopsis nueva."}
        ).to_dict()
        merge_metadata_field(existing, incoming, "description")
        self.assertEqual(existing["description"], "")

    def test_a_manual_edits_source_tag_survives_a_later_automated_merge(self) -> None:
        existing = normalize_item({"id": "x", "title": "Mi título corregido a mano"}).to_dict()
        existing["metadata_sources"] = {
            "title": {"source": "manual", "url": "", "updated_at": "", "inferred": False}
        }
        incoming = normalize_item(
            {"source": "imdb_dataset", "title": "A Different Title"}
        ).to_dict()
        merge_metadata_field(existing, incoming, "title")
        self.assertEqual(existing["title"], "Mi título corregido a mano")
        self.assertEqual(existing["metadata_sources"]["title"]["source"], "manual")


class ImdbDatasetShapeTests(unittest.TestCase):
    def test_an_imdb_dataset_shaped_row_merges_safely_with_no_new_code(self) -> None:
        existing = normalize_item({"id": "x"}).to_dict()
        incoming = normalize_item(
            {
                "source": "imdb_dataset",
                "original_title": "Heat",
                "year": "1995",
                "genres": "Action,Crime,Drama",
            }
        ).to_dict()
        merge_metadata_field(existing, incoming, "original_title")
        merge_metadata_field(existing, incoming, "year")
        merge_metadata_field(existing, incoming, "genres")
        self.assertEqual(existing["original_title"], "Heat")
        self.assertEqual(existing["year"], "1995")
        self.assertEqual(existing["genres"], ["Action", "Crime", "Drama"])


class KindTranslationTrapTests(unittest.TestCase):
    def test_normalize_kind_silently_mismaps_two_real_imdb_title_types(self) -> None:
        # normalize_kind() has its own separate, hardcoded, incomplete
        # vocabulary and never returns "no opinion" -- anything it doesn't
        # recognize falls through to "pelicula". This is why the family-2
        # rule in tareas.md's [Q5] closure requires translating IMDb's raw
        # title_type BEFORE it ever reaches incoming["kind"]: passing it
        # straight through does not raise, it just silently picks the wrong
        # answer for exactly the row-shapes [F1] returns (tvMiniSeries,
        # tvEpisode) that the matrix says should become "serie" or be
        # excluded entirely, never "pelicula" by accident.
        self.assertEqual(normalize_kind("tvMiniSeries"), "pelicula")
        self.assertEqual(normalize_kind("tvEpisode"), "pelicula")
        self.assertEqual(normalize_kind("tvSeries"), "serie")


if __name__ == "__main__":
    unittest.main()
