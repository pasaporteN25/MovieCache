"""[F6.2]: several public scores shown beside the viewer's own, never merged in.

The TMDb half arrives as a dated snapshot, with the treatment [S3] gave
availability: refreshed lazily, expired by the contractual ceiling, and read
without a network call while it is fresh.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from movie_inbox.application.public_ratings_service import PublicRatingsService
from movie_inbox.domain.public_ratings import (
    IMDB_SOURCE,
    MEANINGFUL_VOTES,
    PERSONAL_RATING_FIELD,
    PUBLIC_RATING_FIELDS,
    RATING_MAX_RETENTION_DAYS,
    RATING_STALE_AFTER_DAYS,
    TMDB_SOURCE,
    PublicRatingSnapshot,
    public_rating,
    rating_snapshot,
    rating_snapshot_is_expired,
    rating_snapshot_is_stale,
    sorted_ratings,
    strip_public_ratings,
    tmdb_work_key,
    visible_rating,
)
from movie_inbox.domain.streaming import work_key as streaming_work_key
from movie_inbox.external.imdb_dataset_source import ImdbDatasetSource
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.public_ratings_repository import SqlitePublicRatingsRepository
from tests.test_imdb_dataset_gateway import write_dataset


def _stamp(days_ago: float) -> str:
    moment = datetime.now(UTC) - timedelta(days=days_ago)
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


class RatingSnapshotTests(unittest.TestCase):
    def test_the_work_key_matches_the_one_availability_snapshots_use(self) -> None:
        # Both tables key the same works from the same upstream. Two shapes
        # would be a trap for anyone reading one against the other, so the two
        # helpers are pinned together here rather than trusted to stay aligned.
        for tmdb_id, media_type in (("949", "movie"), ("1396", "tv")):
            with self.subTest(tmdb_id=tmdb_id):
                self.assertEqual(
                    tmdb_work_key(tmdb_id, media_type),
                    streaming_work_key(tmdb_id, media_type),
                )

    def test_an_unusable_identity_yields_no_key_instead_of_raising(self) -> None:
        # A work without TMDb identity is ordinary, not an error: it simply gets
        # no TMDb score.
        for tmdb_id, media_type in (("", "movie"), ("abc", "movie"), ("949", "libro")):
            with self.subTest(tmdb_id=tmdb_id, media_type=media_type):
                self.assertEqual(tmdb_work_key(tmdb_id, media_type), "")

    def test_a_snapshot_needs_a_key_a_date_and_numbers_that_hold_up(self) -> None:
        good = rating_snapshot(
            {
                "work_key": "movie:949",
                "source": TMDB_SOURCE,
                "checked_at": _stamp(0),
                "average": 7.84,
                "votes": 4321,
            }
        )
        assert good is not None
        self.assertEqual(good.average, 7.8)
        self.assertEqual(good.votes, 4321)
        for missing in ("work_key", "checked_at"):
            with self.subTest(missing=missing):
                payload: dict[str, object] = {
                    "work_key": "movie:949",
                    "source": TMDB_SOURCE,
                    "checked_at": _stamp(0),
                    "average": 7.8,
                    "votes": 10,
                }
                payload[missing] = ""
                self.assertIsNone(rating_snapshot(payload))
        self.assertIsNone(
            rating_snapshot(
                {
                    "work_key": "movie:949",
                    "source": TMDB_SOURCE,
                    "checked_at": _stamp(0),
                    "average": 7.8,
                    "votes": 0,
                }
            )
        )

    def test_staleness_and_expiry_are_separate_thresholds(self) -> None:
        fresh = PublicRatingSnapshot("movie:949", TMDB_SOURCE, _stamp(1), 7.8, 100)
        stale = PublicRatingSnapshot(
            "movie:949", TMDB_SOURCE, _stamp(RATING_STALE_AFTER_DAYS + 1), 7.8, 100
        )
        expired = PublicRatingSnapshot(
            "movie:949", TMDB_SOURCE, _stamp(RATING_MAX_RETENTION_DAYS + 1), 7.8, 100
        )
        self.assertFalse(rating_snapshot_is_stale(fresh))
        self.assertTrue(rating_snapshot_is_stale(stale))
        # Stale means "worth refreshing", not "must not be served": the owner
        # accepted a lag, so a stale row keeps answering until it expires.
        self.assertFalse(rating_snapshot_is_expired(stale))
        self.assertIsNotNone(visible_rating(stale))
        self.assertTrue(rating_snapshot_is_expired(expired))

    def test_an_expired_or_unreadable_snapshot_is_not_shown(self) -> None:
        expired = PublicRatingSnapshot(
            "movie:949", TMDB_SOURCE, _stamp(RATING_MAX_RETENTION_DAYS + 1), 7.8, 100
        )
        self.assertIsNone(visible_rating(expired))
        self.assertIsNone(visible_rating(None))
        # A timestamp we cannot read cannot be shown to be inside the retention
        # window, so it counts as expired rather than as fresh.
        self.assertIsNone(
            visible_rating(PublicRatingSnapshot("movie:949", TMDB_SOURCE, "ayer", 7.8, 1))
        )


class PublicRatingsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / "instance.db"
        SqliteIdentityRepository(path).initialize()
        self.repository = SqlitePublicRatingsRepository(path)
        self.calls: list[tuple[str, str]] = []

    def _loader(self, average: float = 7.8, votes: int = 4321):
        def load(media_type: str, tmdb_id: str) -> dict[str, object]:
            self.calls.append((media_type, tmdb_id))
            return {"average": average, "votes": votes}

        return load

    def _service(self, **kwargs: object) -> PublicRatingsService:
        return PublicRatingsService(self.repository, **kwargs)  # type: ignore[arg-type]

    def test_a_score_is_fetched_once_and_then_served_from_the_snapshot(self) -> None:
        service = self._service(tmdb_loader=self._loader())
        items = [{"id": "heat", "tmdb_id": "949", "kind": "pelicula"}]

        first = service.ratings_for(items)
        second = service.ratings_for(items)

        self.assertEqual(len(self.calls), 1, "una lectura fresca no vuelve a la red")
        self.assertEqual([row.source for row in first["heat"]], [TMDB_SOURCE])
        self.assertEqual(first["heat"][0].average, 7.8)
        self.assertEqual(second["heat"][0].to_dict(), first["heat"][0].to_dict())

    def test_a_stale_snapshot_is_refreshed_and_an_expired_one_is_not_served(self) -> None:
        self.repository.save_rating(
            PublicRatingSnapshot(
                "movie:949", TMDB_SOURCE, _stamp(RATING_STALE_AFTER_DAYS + 1), 6.0, 10
            )
        )
        items = [{"id": "heat", "tmdb_id": "949", "kind": "pelicula"}]

        found = self._service(tmdb_loader=self._loader()).ratings_for(items)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(found["heat"][0].average, 7.8)

        self.repository.save_rating(
            PublicRatingSnapshot(
                "movie:949", TMDB_SOURCE, _stamp(RATING_MAX_RETENTION_DAYS + 1), 6.0, 10
            )
        )
        # With no loader there is nothing to fetch, so the expired row is all
        # there is -- and it is withheld rather than served past the ceiling.
        self.assertEqual(self._service().ratings_for(items), {})

    def test_an_upstream_failure_keeps_serving_what_is_already_stored(self) -> None:
        self.repository.save_rating(
            PublicRatingSnapshot(
                "movie:949", TMDB_SOURCE, _stamp(RATING_STALE_AFTER_DAYS + 1), 6.4, 900
            )
        )

        def failing(media_type: str, tmdb_id: str) -> dict[str, object]:
            raise RuntimeError("TMDb no responde")

        found = self._service(tmdb_loader=failing).ratings_for(
            [{"id": "heat", "tmdb_id": "949", "kind": "pelicula"}]
        )
        self.assertEqual(found["heat"][0].average, 6.4)

    def test_an_unrated_work_upstream_is_not_stored_as_a_zero(self) -> None:
        def unrated(media_type: str, tmdb_id: str) -> dict[str, object]:
            self.calls.append((media_type, tmdb_id))
            return {}

        service = self._service(tmdb_loader=unrated)
        items = [{"id": "rara", "tmdb_id": "949", "kind": "pelicula"}]
        self.assertEqual(service.ratings_for(items), {})
        # Nothing was remembered, so a later read asks again instead of
        # repeating a zero forever.
        service.ratings_for(items)
        self.assertEqual(len(self.calls), 2)

    def test_refreshes_are_capped_so_one_page_is_not_hundreds_of_calls(self) -> None:
        items = [
            {"id": f"obra-{position}", "tmdb_id": str(900 + position), "kind": "pelicula"}
            for position in range(30)
        ]
        service = self._service(tmdb_loader=self._loader(), max_refresh_per_request=5)
        found = service.ratings_for(items)
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(len(found), 5, "el resto se resuelve en lecturas siguientes")

    def test_a_series_and_a_film_with_the_same_number_do_not_share_a_score(self) -> None:
        service = self._service(tmdb_loader=self._loader())
        service.ratings_for(
            [
                {"id": "pelicula", "tmdb_id": "1396", "kind": "pelicula"},
                {"id": "serie", "tmdb_id": "1396", "kind": "serie"},
            ]
        )
        self.assertEqual(sorted(self.calls), [("movie", "1396"), ("tv", "1396")])

    def test_both_sources_answer_together_with_the_sturdiest_first(self) -> None:
        def imdb(imdb_id: str) -> object:
            return public_rating(IMDB_SOURCE, 8.3, 700_000) if imdb_id == "tt0113277" else None

        service = self._service(
            imdb_lookup=imdb,
            imdb_id_reader=lambda row: str(row.get("imdb_id") or ""),
            tmdb_loader=self._loader(votes=900),
        )
        found = service.ratings_for(
            [{"id": "heat", "tmdb_id": "949", "kind": "pelicula", "imdb_id": "tt0113277"}]
        )
        self.assertEqual([row.source for row in found["heat"]], [IMDB_SOURCE, TMDB_SOURCE])

    def test_a_work_without_any_score_is_absent_rather_than_empty(self) -> None:
        # An empty list would read as "nobody rated this"; absence says only
        # that we hold nothing, which is the honest answer.
        service = self._service(tmdb_loader=self._loader())
        self.assertEqual(service.ratings_for([{"id": "sin-identidad", "kind": "pelicula"}]), {})
        self.assertEqual(self.calls, [])

    def test_retiring_tmdb_drops_its_snapshots_and_leaves_the_imdb_index_alone(self) -> None:
        self.repository.save_rating(
            PublicRatingSnapshot("movie:949", TMDB_SOURCE, _stamp(1), 7.8, 100)
        )
        self.repository.save_rating(
            PublicRatingSnapshot("movie:680", TMDB_SOURCE, _stamp(1), 8.5, 200)
        )
        service = self._service(
            imdb_lookup=lambda _id: public_rating(IMDB_SOURCE, 8.3, 700_000),
            imdb_id_reader=lambda row: str(row.get("imdb_id") or ""),
        )
        self.assertEqual(service.purge_all_tmdb_ratings(), 2)
        # The IMDb index is not TMDb's data to reclaim, so it keeps answering.
        found = service.ratings_for(
            [{"id": "heat", "tmdb_id": "949", "kind": "pelicula", "imdb_id": "tt0113277"}]
        )
        self.assertEqual([row.source for row in found["heat"]], [IMDB_SOURCE])

    def test_the_retention_sweep_only_removes_what_is_past_the_ceiling(self) -> None:
        self.repository.save_rating(
            PublicRatingSnapshot("movie:949", TMDB_SOURCE, _stamp(1), 7.8, 100)
        )
        self.repository.save_rating(
            PublicRatingSnapshot(
                "movie:680", TMDB_SOURCE, _stamp(RATING_MAX_RETENTION_DAYS + 5), 8.5, 200
            )
        )
        self.assertEqual(self._service().purge_expired_ratings(), 1)
        self.assertEqual(
            list(self.repository.ratings(TMDB_SOURCE, ["movie:949", "movie:680"])),
            ["movie:949"],
        )


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
