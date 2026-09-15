"""Assemble a charades deck from the works a viewer can actually play with.

Two stores feed it, because following a collection does not copy its works
(`PRODUCT.md`): the personal catalogue and the followed Club collections. Nothing
here writes to a work; the deck is built and handed over.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from movie_inbox.application.charades_repository import CharadesRepository
from movie_inbox.domain.charades import (
    DIFFICULTIES,
    MIN_ELIGIBLE_WORKS,
    MIN_PER_DIFFICULTY,
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

# Returns the public vote count for a work, or None. Injected so this service
# never learns which upstream provides it and `application/` stays clean.
VoteLookup = Callable[[Mapping[str, Any]], int | None]


def _summary(works: Sequence[CharadeWork]) -> dict[str, Any]:
    counts = {name: 0 for name in DIFFICULTIES}
    unclassified = 0
    for work in works:
        if work.difficulty:
            counts[work.difficulty] += 1
        else:
            unclassified += 1
    playable = playable_difficulties(counts)
    return {
        "eligible": len(works),
        "unclassified": unclassified,
        "counts": counts,
        "playable_difficulties": playable,
        "fingerprint": deck_fingerprint(work.key for work in works),
        "minimums": {"eligible": MIN_ELIGIBLE_WORKS, "per_difficulty": MIN_PER_DIFFICULTY},
        "timer_options": {name: list(TIMER_OPTIONS[name]) for name in DIFFICULTIES},
        "ready": len(works) >= MIN_ELIGIBLE_WORKS and bool(playable),
    }


class CharadesNotReady(RuntimeError):
    """Raised when there are not enough works to play with."""


class CharadesService:
    def __init__(
        self,
        repository: CharadesRepository,
        *,
        catalog_loader: Callable[[AuthenticatedIdentity], Sequence[Mapping[str, Any]]],
        collection_loader: Callable[[AuthenticatedIdentity], Sequence[Mapping[str, Any]]],
        vote_lookup: VoteLookup | None = None,
    ) -> None:
        self.repository = repository
        self.catalog_loader = catalog_loader
        self.collection_loader = collection_loader
        self.vote_lookup = vote_lookup

    def eligible_works(self, identity: AuthenticatedIdentity) -> list[CharadeWork]:
        """Every playable work, deduplicated across both stores.

        Dedup here is looser than `decide_match` on purpose, and that does not
        weaken invariant 3: a wrong merge in the catalogue loses personal data,
        while a wrong merge in a deck costs one entry in a game list. Nothing is
        written either way. A tie goes to the personal catalogue copy, which is
        the one its owner maintains.
        """

        manual = self.repository.difficulties_for(identity.user.id)
        found: dict[str, CharadeWork] = {}
        for source, rows in (
            ("collection", self.collection_loader(identity)),
            ("catalog", self.catalog_loader(identity)),
        ):
            for row in rows:
                key = work_key(row)
                title = playable_title(row)
                if not key or not title:
                    # A work with no usable title cannot be acted out.
                    continue
                votes = self.vote_lookup(row) if self.vote_lookup else None
                found[key] = CharadeWork(
                    key=key,
                    title=title,
                    year=str(row.get("year") or "")[:4],
                    difficulty=resolve_difficulty(manual.get(key), suggest_difficulty(votes)),
                    source=source,
                )
        return sorted(found.values(), key=lambda work: work.key)

    def status(self, identity: AuthenticatedIdentity) -> dict[str, Any]:
        """What the surface needs to know before offering a game."""

        return _summary(self.eligible_works(identity))

    def snapshot(self, identity: AuthenticatedIdentity) -> dict[str, Any]:
        """Everything a device needs to deal the same decks offline ([A2.4]).

        The status plus every eligible work, from one pass over both stores. The
        works are the deck's whole input: a device holding them and running the
        documented generator deals exactly the deck `deck()` would, and can check
        the fingerprint before a game instead of finding out halfway through.
        Unclassified works travel too, because the fingerprint covers them.
        """

        works = self.eligible_works(identity)
        return {**_summary(works), "works": [work.to_dict() for work in works]}

    def deck(
        self,
        identity: AuthenticatedIdentity,
        difficulty: str,
        size: int = 0,
    ) -> dict[str, Any]:
        """A deterministic deck: same options plus same works means same order."""

        if difficulty not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {difficulty}")
        works = self.eligible_works(identity)
        fingerprint = deck_fingerprint(work.key for work in works)
        chosen = [work for work in works if work.difficulty == difficulty]
        if len(chosen) < MIN_PER_DIFFICULTY:
            raise CharadesNotReady(
                f"{difficulty} has {len(chosen)} works, needs {MIN_PER_DIFFICULTY}"
            )
        # The fingerprint covers every eligible work, not just the chosen
        # category: adding a work anywhere changes the deck two players compare.
        seed = deck_seed([difficulty, size], fingerprint)
        ordered = build_deck(chosen, seed, size)
        return {
            "difficulty": difficulty,
            "fingerprint": fingerprint,
            "timer_options": list(TIMER_OPTIONS[difficulty]),
            "works": [work.to_dict() for work in ordered],
        }

    def pending_review(self, identity: AuthenticatedIdentity, limit: int = 50) -> dict[str, Any]:
        """Works nobody classified yet.

        This is the main path, not a fallback: the vote count is only decisive
        at the extremes, and a real catalogue lives in the middle.
        """

        works = [work for work in self.eligible_works(identity) if not work.difficulty]
        return {
            "pending": len(works),
            "works": [work.to_dict() for work in works[: max(1, limit)]],
            "difficulties": list(DIFFICULTIES),
        }

    def classify(self, identity: AuthenticatedIdentity, key: str, difficulty: str) -> None:
        normalized = str(difficulty or "").strip()
        if normalized and normalized not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty: {difficulty}")
        work = str(key or "").strip()
        if not work:
            raise ValueError("Missing work key")
        if normalized:
            self.repository.set_difficulty(identity.user.id, work, normalized)
        else:
            self.repository.clear_difficulty(identity.user.id, work)
