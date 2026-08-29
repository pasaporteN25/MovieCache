from __future__ import annotations

import unittest

from movie_inbox.domain.imdb_dataset import (
    IMDB_ATTRIBUTION_NOTICE,
    parse_title_akas_row,
    parse_title_basics_row,
)


class TitleBasicsParsingTests(unittest.TestCase):
    def test_a_well_formed_row_is_parsed_into_its_fields(self) -> None:
        row = parse_title_basics_row(
            "tt0113277\tmovie\tHeat\tHeat\t0\t1995\t\\N\t170\tAction,Crime,Drama\n"
        )
        self.assertEqual(
            row,
            {
                "tconst": "tt0113277",
                "title_type": "movie",
                "primary_title": "Heat",
                "original_title": "Heat",
                "is_adult": 0,
                "start_year": 1995,
                "end_year": None,
                "runtime_minutes": 170,
                "genres": "Action,Crime,Drama",
            },
        )

    def test_the_header_row_is_recognized_and_skipped(self) -> None:
        header = (
            "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\t"
            "startYear\tendYear\truntimeMinutes\tgenres"
        )
        self.assertIsNone(parse_title_basics_row(header))

    def test_null_marker_fields_become_none_not_the_literal_string(self) -> None:
        row = parse_title_basics_row(
            "tt0000001\tshort\tCarmencita\tCarmencita\t0\t1894\t\\N\t\\N\t\\N\n"
        )
        assert row is not None
        self.assertIsNone(row["end_year"])
        self.assertIsNone(row["runtime_minutes"])
        self.assertIsNone(row["genres"])

    def test_is_adult_only_becomes_1_for_the_literal_flag(self) -> None:
        adult_row = parse_title_basics_row("tt9999999\tmovie\tX\tX\t1\t2020\t\\N\t90\tAdult\n")
        garbage_row = parse_title_basics_row("tt9999998\tmovie\tX\tX\t\\N\t2020\t\\N\t90\tDrama\n")
        assert adult_row is not None and garbage_row is not None
        self.assertEqual(adult_row["is_adult"], 1)
        self.assertEqual(garbage_row["is_adult"], 0)

    def test_a_row_with_the_wrong_column_count_is_rejected(self) -> None:
        self.assertIsNone(parse_title_basics_row("tt0113277\tmovie\tHeat\n"))

    def test_a_row_with_an_empty_tconst_is_rejected(self) -> None:
        self.assertIsNone(
            parse_title_basics_row("\tmovie\tHeat\tHeat\t0\t1995\t\\N\t170\tAction\n")
        )

    def test_an_unparseable_year_becomes_none_instead_of_raising(self) -> None:
        row = parse_title_basics_row("tt0113277\tmovie\tHeat\tHeat\t0\tMCMXCV\t\\N\t170\tAction\n")
        assert row is not None
        self.assertIsNone(row["start_year"])


class TitleAkasParsingTests(unittest.TestCase):
    def test_a_well_formed_row_is_parsed_into_its_fields(self) -> None:
        row = parse_title_akas_row("tt0113277\t8\tCalor\tES\t\\N\t\\N\t\\N\t0\n")
        self.assertEqual(
            row,
            {
                "tconst": "tt0113277",
                "ordering": 8,
                "title": "Calor",
                "region": "ES",
                "language": None,
                "types": None,
                "attributes": None,
                "is_original_title": 0,
            },
        )

    def test_the_header_row_is_recognized_and_skipped(self) -> None:
        header = "titleId\tordering\ttitle\tregion\tlanguage\ttypes\tattributes\tisOriginalTitle"
        self.assertIsNone(parse_title_akas_row(header))

    def test_a_row_with_an_unparseable_ordering_is_rejected(self) -> None:
        self.assertIsNone(parse_title_akas_row("tt0113277\tfirst\tCalor\tES\t\\N\t\\N\t\\N\t0\n"))

    def test_a_row_with_an_empty_title_id_is_rejected(self) -> None:
        self.assertIsNone(parse_title_akas_row("\t8\tCalor\tES\t\\N\t\\N\t\\N\t0\n"))

    def test_a_row_with_the_wrong_column_count_is_rejected(self) -> None:
        self.assertIsNone(parse_title_akas_row("tt0113277\t8\tCalor\n"))


class AttributionNoticeTests(unittest.TestCase):
    def test_the_notice_matches_imdbs_required_wording_exactly(self) -> None:
        self.assertEqual(
            IMDB_ATTRIBUTION_NOTICE,
            "Information courtesy of IMDb (https://www.imdb.com). Used with permission.",
        )


if __name__ == "__main__":
    unittest.main()
