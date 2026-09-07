"""[F6.2]: several public scores shown beside the viewer's own, never merged in."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.domain.public_ratings import (
    IMDB_SOURCE,
    MEANINGFUL_VOTES,
    PERSONAL_RATING_FIELD,
    PUBLIC_RATING_FIELDS,
    TMDB_SOURCE,
    public_rating,
    sorted_ratings,
    strip_public_ratings,
)
from movie_inbox.external.imdb_dataset_source import ImdbDatasetSource
from tests.test_imdb_dataset_gateway import write_dataset


class PublicRatingRulesTests(unittest.TestCase):
    def test_a_public_score_is_never_the_personal_rating_field(self) -> None:
        # [F3.2] fixed this rule and the owner's decision to show several scores
        # makes it load-bearing: these are other people's opinions, the viewer's
        # `rating` is theirs.
        self.assertNotIn(PERSONAL_RATING_FIELD, PUBLIC_RATING_FIELDS)
        item = {
            "id": "heat",
            "rating": 9,
            "review": "mia",
            "vote_average": 8.3,
            "vote_count": 712345,
            "imdb_rating": 8.3,
        }
        stripped = strip_public_ratings(item)
        self.assertEqual(stripped["rating"], 9, "el puntaje propio no se toca")
        self.assertEqual(stripped["review"], "mia")
        for field in ("vote_average", "vote_count", "imdb_rating"):
            self.assertNotIn(field, stripped)

    def test_scores_outside_their_scale_or_without_votes_are_refused(self) -> None:
        self.assertIsNone(public_rating(IMDB_SOURCE, 47, 100))
        self.assertIsNone(public_rating(IMDB_SOURCE, 0, 100))
        self.assertIsNone(public_rating(IMDB_SOURCE, 8.3, 0))
        self.assertIsNone(public_rating(IMDB_SOURCE, "no es un numero", 100))
        self.assertIsNone(public_rating(IMDB_SOURCE, 8.3, None))

    def test_only_known_sources_produce_a_rating(self) -> None:
        # An unknown source has an unknown scale, so its number cannot be placed.
        self.assertIsNone(public_rating("rottentomatoes", 8.0, 100))
        self.assertIsNone(public_rating("", 8.0, 100))
        self.assertIsNotNone(public_rating(TMDB_SOURCE, 8.0, 100))

    def test_a_score_from_a_handful_of_people_is_marked_as_thin(self) -> None:
        # It still carries a number, but showing it next to one backed by half a
        # million without saying so would invite a comparison that is not there.
        thin = public_rating(IMDB_SOURCE, 9.9, MEANINGFUL_VOTES - 1)
        solid = public_rating(IMDB_SOURCE, 8.3, MEANINGFUL_VOTES)
        assert thin is not None and solid is not None
        self.assertFalse(thin.is_meaningful)
        self.assertTrue(solid.is_meaningful)
        self.assertFalse(thin.to_dict()["is_meaningful"])

    def test_the_best_supported_score_leads(self) -> None:
        tmdb = public_rating(TMDB_SOURCE, 7.8, 900)
        imdb = public_rating(IMDB_SOURCE, 8.3, 700_000)
        assert tmdb is not None and imdb is not None
        self.assertEqual([row.source for row in sorted_ratings([tmdb, imdb])], ["imdb", "tmdb"])


class ImdbRatingLookupTests(unittest.TestCase):
    def test_ratings_come_from_the_index_and_never_from_the_catalogue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index = write_dataset(Path(temporary))
            source = ImdbDatasetSource(index)

            found = source.rating_for("tt0113277")
            assert found is not None
            self.assertEqual(found.source, IMDB_SOURCE)
            self.assertGreater(found.votes, 0)

            # Ratings are deliberately absent from what gets merged into a work,
            # so the catalogue never stores a number that goes stale.
            self.assertNotIn("rating", source.metadata_for("tt0113277"))
            for field in PUBLIC_RATING_FIELDS:
                self.assertNotIn(field, source.metadata_for("tt0113277"))

    def test_an_unknown_work_or_a_missing_index_yields_no_rating(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            index = write_dataset(Path(temporary))
            self.assertIsNone(ImdbDatasetSource(index).rating_for("tt9999999"))
            missing = ImdbDatasetSource(Path(temporary) / "no-existe.db")
            self.assertIsNone(missing.rating_for("tt0113277"))
            for value in ("", "0113277", "ttabc"):
                with self.subTest(value=value):
                    self.assertIsNone(ImdbDatasetSource(index).rating_for(value))


if __name__ == "__main__":
    unittest.main()
