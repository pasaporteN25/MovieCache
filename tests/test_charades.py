"""[G2]: deterministic decks, difficulty rules and the two-store deck."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.charades_service import CharadesNotReady, CharadesService
from movie_inbox.domain.charades import (
    DIFFICULTIES,
    EASY,
    FAMOUS_ABOVE_VOTES,
    HARD,
    MEDIUM,
    MIN_PER_DIFFICULTY,
    OBSCURE_BELOW_VOTES,
    TIMER_OPTIONS,
    CharadeWork,
    build_deck,
    deck_fingerprint,
    deck_seed,
    playable_difficulties,
    playable_title,
    resolve_difficulty,
    suggest_difficulty,
    work_key,
)
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.infrastructure.charades_repository import SqliteCharadesRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository


class TitleAndIdentityTests(unittest.TestCase):
    def test_the_acted_title_follows_a_fixed_order(self) -> None:
        # Two players seeing different titles for the same work breaks the game
        # exactly as surely as different works would.
        self.assertEqual(
            playable_title({"title": "Heat", "spanish_title": "Fuego contra fuego"}),
            "Fuego contra fuego",
        )
        self.assertEqual(playable_title({"title": "Heat", "original_title": "Heat!"}), "Heat")
        self.assertEqual(playable_title({"original_title": "Ran"}), "Ran")
        self.assertEqual(playable_title({"title": "   "}), "")

    def test_identity_prefers_strong_external_ids(self) -> None:
        # Works arrive from two stores that do not share ids.
        self.assertEqual(work_key({"tmdb_id": "78"}), "tmdb:78")
        self.assertEqual(
            work_key({"imdb_url": "https://www.imdb.com/title/tt0113277/"}), "imdb:tt0113277"
        )
        self.assertEqual(work_key({"wikidata_id": "Q184843"}), "wikidata:Q184843")

    def test_identity_falls_back_to_a_normalised_title_and_year(self) -> None:
        left = work_key({"title": "El Ángel Exterminador", "year": "1962"})
        right = work_key({"title": "el angel exterminador!", "year": "1962"})
        self.assertEqual(left, right)
        self.assertNotEqual(left, work_key({"title": "El Angel Exterminador", "year": "1970"}))

    def test_a_work_without_any_usable_title_has_no_identity(self) -> None:
        self.assertEqual(work_key({"year": "1962"}), "")


class DifficultyRuleTests(unittest.TestCase):
    def test_only_the_extremes_are_classified_automatically(self) -> None:
        # Measured in [G1]: between the thresholds the vote count cannot separate
        # Seven Samurai (370k, few know it) from Batman (400k, everyone does).
        self.assertEqual(suggest_difficulty(OBSCURE_BELOW_VOTES - 1), HARD)
        self.assertEqual(suggest_difficulty(FAMOUS_ABOVE_VOTES + 1), EASY)
        for votes in (370_000, 400_000, 190_000, 180_000):
            with self.subTest(votes=votes):
                self.assertEqual(suggest_difficulty(votes), "", "la banda media va a revisión")

    def test_missing_or_nonsense_vote_counts_produce_no_suggestion(self) -> None:
        for votes in (None, 0, -5, "muchos", ""):
            with self.subTest(votes=votes):
                self.assertEqual(suggest_difficulty(votes), "")

    def test_a_person_outranks_any_recomputation(self) -> None:
        # Same guarantee locked_fields gives against enrichment.
        self.assertEqual(resolve_difficulty(HARD, EASY), HARD)
        self.assertEqual(resolve_difficulty("", EASY), EASY)
        self.assertEqual(resolve_difficulty("inventada", EASY), EASY)
        self.assertEqual(resolve_difficulty("", ""), "")

    def test_every_difficulty_offers_three_escalating_times(self) -> None:
        previous = (0, 0, 0)
        for name in DIFFICULTIES:
            options = TIMER_OPTIONS[name]
            with self.subTest(difficulty=name):
                self.assertEqual(len(options), 3)
                self.assertEqual(list(options), sorted(options))
                self.assertGreaterEqual(options[0], previous[0])
            previous = options

    def test_a_category_below_the_minimum_is_not_offered(self) -> None:
        counts = {EASY: MIN_PER_DIFFICULTY, MEDIUM: MIN_PER_DIFFICULTY - 1}
        self.assertEqual(playable_difficulties(counts), [EASY])


class DeterminismTests(unittest.TestCase):
    def _works(self, count: int) -> list[CharadeWork]:
        return [CharadeWork(key=f"tmdb:{index}", title=f"Obra {index}") for index in range(count)]

    def test_the_same_seed_and_works_always_produce_the_same_order(self) -> None:
        works = self._works(40)
        seed = deck_seed([EASY, 10], "ABC123")
        first = [work.key for work in build_deck(works, seed)]
        second = [work.key for work in build_deck(list(reversed(works)), seed)]
        # The caller's ordering must not leak into the result.
        self.assertEqual(first, second)

    def test_a_different_deck_changes_the_seed_even_with_the_same_options(self) -> None:
        # This is the whole point: a phone that synced and one that did not must
        # not silently believe they hold the same deck.
        options = [EASY, 10]
        self.assertNotEqual(deck_seed(options, "ABC123"), deck_seed(options, "DEF456"))

    def test_different_options_change_the_order(self) -> None:
        works = self._works(40)
        easy = [work.key for work in build_deck(works, deck_seed([EASY, 10], "ABC"))]
        hard = [work.key for work in build_deck(works, deck_seed([HARD, 10], "ABC"))]
        self.assertNotEqual(easy, hard)

    def test_the_fingerprint_ignores_ordering_and_duplicates(self) -> None:
        self.assertEqual(
            deck_fingerprint(["tmdb:1", "tmdb:2"]),
            deck_fingerprint(["tmdb:2", "tmdb:1", "tmdb:1", ""]),
        )
        self.assertNotEqual(deck_fingerprint(["tmdb:1"]), deck_fingerprint(["tmdb:1", "tmdb:2"]))

    def test_the_shuffle_actually_shuffles_and_keeps_every_work(self) -> None:
        works = self._works(60)
        ordered = build_deck(works, deck_seed([EASY], "ABC"))
        self.assertEqual(len(ordered), 60)
        self.assertEqual({work.key for work in ordered}, {work.key for work in works})
        self.assertNotEqual([work.key for work in ordered], [work.key for work in works])

    def test_a_size_limit_takes_a_prefix_of_the_same_order(self) -> None:
        works = self._works(40)
        seed = deck_seed([EASY, 5], "ABC")
        full = [work.key for work in build_deck(works, seed)]
        self.assertEqual([work.key for work in build_deck(works, seed, 5)], full[:5])


class CharadesServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name) / "instance.db"
        identity_repository = SqliteIdentityRepository(path)
        identity_repository.initialize()
        AuthService(identity_repository).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(Path(self.temporary.name) / "catalog.json")],
            write_path=str(Path(self.temporary.name) / "catalog.json"),
        )
        owner = identity_repository.owner()
        catalog = identity_repository.default_catalog_for(owner.id) if owner else None
        assert owner is not None and catalog is not None
        self.identity = AuthenticatedIdentity(user=owner, catalog=catalog, expires_at=0)
        self.repository = SqliteCharadesRepository(path)
        self.catalog: list[dict[str, Any]] = []
        self.collections: list[dict[str, Any]] = []
        self.votes: dict[str, int] = {}
        self.service = CharadesService(
            self.repository,
            catalog_loader=lambda _identity: self.catalog,
            collection_loader=lambda _identity: self.collections,
            vote_lookup=lambda row: self.votes.get(str(row.get("tmdb_id") or "")),
        )

    def test_a_work_in_both_stores_appears_once_with_the_catalogue_winning(self) -> None:
        self.collections = [{"tmdb_id": "78", "title": "Blade Runner (de la colección)"}]
        self.catalog = [{"tmdb_id": "78", "title": "Blade Runner"}]
        works = self.service.eligible_works(self.identity)
        self.assertEqual(len(works), 1)
        self.assertEqual(works[0].title, "Blade Runner")
        self.assertEqual(works[0].source, "catalog")

    def test_works_are_deduplicated_by_title_and_year_across_stores(self) -> None:
        self.collections = [{"title": "El Ángel Exterminador", "year": "1962"}]
        self.catalog = [{"title": "el angel exterminador", "year": "1962"}]
        self.assertEqual(len(self.service.eligible_works(self.identity)), 1)

    def test_a_work_without_a_usable_title_never_enters_the_deck(self) -> None:
        self.catalog = [{"tmdb_id": "78"}, {"tmdb_id": "79", "title": "Heat"}]
        self.assertEqual([w.title for w in self.service.eligible_works(self.identity)], ["Heat"])

    def test_status_does_not_filter_which_works_enter(self) -> None:
        # Owner decision: a pending work can be perfectly well known to the room.
        self.catalog = [
            {"tmdb_id": "1", "title": "Pendiente", "status": "to_watch"},
            {"tmdb_id": "2", "title": "Vista", "status": "watched"},
        ]
        self.assertEqual(len(self.service.eligible_works(self.identity)), 2)

    def test_a_stored_decision_survives_a_contradicting_suggestion(self) -> None:
        self.catalog = [{"tmdb_id": "78", "title": "Blade Runner"}]
        self.votes = {"78": FAMOUS_ABOVE_VOTES + 1}  # would suggest EASY
        self.repository.set_difficulty(self.identity.user.id, "tmdb:78", HARD)
        self.assertEqual(self.service.eligible_works(self.identity)[0].difficulty, HARD)

    def test_clearing_a_decision_returns_the_work_to_the_suggestion(self) -> None:
        self.catalog = [{"tmdb_id": "78", "title": "Blade Runner"}]
        self.votes = {"78": FAMOUS_ABOVE_VOTES + 1}
        self.repository.set_difficulty(self.identity.user.id, "tmdb:78", HARD)
        self.service.classify(self.identity, "tmdb:78", "")
        self.assertEqual(self.service.eligible_works(self.identity)[0].difficulty, EASY)

    def test_the_middle_band_lands_in_the_review_queue(self) -> None:
        self.catalog = [{"tmdb_id": "1", "title": "Los siete samuráis"}]
        self.votes = {"1": 370_000}
        review = self.service.pending_review(self.identity)
        self.assertEqual(review["pending"], 1)
        self.assertEqual(review["works"][0]["difficulty"], "")

    def test_a_thin_category_refuses_to_deal_instead_of_repeating(self) -> None:
        self.catalog = [{"tmdb_id": str(i), "title": f"Obra {i}"} for i in range(5)]
        self.votes = {str(i): FAMOUS_ABOVE_VOTES + 1 for i in range(5)}
        with self.assertRaises(CharadesNotReady):
            self.service.deck(self.identity, EASY)

    def test_a_deck_is_reproducible_and_only_carries_its_category(self) -> None:
        self.catalog = [{"tmdb_id": str(i), "title": f"Obra {i}"} for i in range(60)]
        self.votes = {str(i): FAMOUS_ABOVE_VOTES + 1 for i in range(60)}
        first = self.service.deck(self.identity, EASY)
        second = self.service.deck(self.identity, EASY)
        self.assertEqual(first["works"], second["works"])
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertTrue(all(work["difficulty"] == EASY for work in first["works"]))
        self.assertEqual(first["timer_options"], list(TIMER_OPTIONS[EASY]))

    def test_adding_a_work_anywhere_changes_the_fingerprint(self) -> None:
        self.catalog = [{"tmdb_id": str(i), "title": f"Obra {i}"} for i in range(60)]
        self.votes = {str(i): FAMOUS_ABOVE_VOTES + 1 for i in range(60)}
        before = self.service.deck(self.identity, EASY)["fingerprint"]
        # The new work is not even in the played category, and the deck two
        # players compare still has to change.
        self.catalog.append({"tmdb_id": "999", "title": "Obra nueva"})
        self.votes["999"] = 500
        self.assertNotEqual(self.service.deck(self.identity, EASY)["fingerprint"], before)

    def test_an_unknown_difficulty_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            self.service.deck(self.identity, "imposible")
        with self.assertRaises(ValueError):
            self.service.classify(self.identity, "tmdb:1", "imposible")

    def test_status_reports_what_the_surface_needs_before_offering_a_game(self) -> None:
        self.catalog = [{"tmdb_id": str(i), "title": f"Obra {i}"} for i in range(30)]
        self.votes = {str(i): FAMOUS_ABOVE_VOTES + 1 for i in range(30)}
        status = self.service.status(self.identity)
        self.assertEqual(status["eligible"], 30)
        self.assertEqual(status["counts"][EASY], 30)
        self.assertEqual(status["playable_difficulties"], [EASY])
        # 30 works clear the per-category minimum but not the overall one.
        self.assertFalse(status["ready"])


if __name__ == "__main__":
    unittest.main()
