"""Public scores shown beside the viewer's own, never merged into it.

Owner decision, 2026-09-07: show several public scores rather than picking one,
so a viewer can weigh them against their own rating instead of having a single
number imposed. That makes the separation load-bearing — these are other
people's opinions about a work, and the viewer's `rating` is theirs. [F3.2]
already fixed the rule this module enforces: a public score never reaches the
personal rating, by any path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

IMDB_SOURCE = "imdb"
TMDB_SOURCE = "tmdb"

# The field a public score must never end up in, by any route.
PERSONAL_RATING_FIELD = "rating"

# A work rated by a handful of people carries a number but not an opinion.
MEANINGFUL_VOTES = 50

# Both upstreams score out of ten, but that is their choice and not ours to
# assume, so the scale travels with the value instead of being implied.
_SCALES = {IMDB_SOURCE: 10.0, TMDB_SOURCE: 10.0}


@dataclass(frozen=True)
class PublicRating:
    """One source's aggregate score for a work."""

    source: str
    average: float
    votes: int
    scale: float = 10.0

    @property
    def is_meaningful(self) -> bool:
        """Whether the score rests on enough opinions to be worth showing.

        A work rated by three people carries a number but not an opinion, and
        showing it next to one backed by half a million invites a comparison
        that is not there.
        """

        return self.votes >= MEANINGFUL_VOTES

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "average": self.average,
            "votes": self.votes,
            "scale": self.scale,
            "is_meaningful": self.is_meaningful,
        }


def public_rating(source: Any, average: Any, votes: Any) -> PublicRating | None:
    """Build a rating, or nothing when the numbers cannot be trusted."""

    name = str(source or "").strip().casefold()
    if name not in _SCALES:
        return None
    try:
        score = float(average)
        count = int(votes)
    except (TypeError, ValueError):
        return None
    scale = _SCALES[name]
    if count <= 0 or not 0.0 < score <= scale:
        return None
    return PublicRating(source=name, average=round(score, 1), votes=count, scale=scale)


def strip_public_ratings(item: Mapping[str, Any]) -> dict[str, Any]:
    """Guarantee no public score is riding along inside a catalogue item.

    Used where an item crosses into storage. The rule is enforced structurally
    rather than by remembering not to write the field.
    """

    return {key: value for key, value in item.items() if key not in PUBLIC_RATING_FIELDS}


# Names a public score could plausibly arrive under from an upstream payload.
PUBLIC_RATING_FIELDS = frozenset(
    {
        "vote_average",
        "vote_count",
        "average_rating",
        "num_votes",
        "public_ratings",
        "imdb_rating",
        "tmdb_rating",
    }
)


def sorted_ratings(ratings: Sequence[PublicRating]) -> list[PublicRating]:
    """Most-supported score first, so the sturdiest opinion leads."""

    return sorted(ratings, key=lambda row: (-row.votes, row.source))


__all__ = [
    "IMDB_SOURCE",
    "MEANINGFUL_VOTES",
    "PERSONAL_RATING_FIELD",
    "PUBLIC_RATING_FIELDS",
    "TMDB_SOURCE",
    "PublicRating",
    "public_rating",
    "sorted_ratings",
    "strip_public_ratings",
]
