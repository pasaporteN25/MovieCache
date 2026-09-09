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
from datetime import UTC, datetime, timedelta
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

# A TMDb score is a moving number obtained over the network, so it is kept as a
# dated snapshot exactly like streaming availability ([S3]): refreshed lazily
# after this long instead of on every read. The owner accepted a lag of one or
# two months there and the same tolerance applies here -- a score that moved
# from 7,4 to 7,5 last week does not justify a network call per page view.
RATING_STALE_AFTER_DAYS = 30

# Contractual ceiling from the TMDb API terms, the same one `domain/streaming.py`
# enforces: nothing obtained from them may be kept longer than six months. A row
# past this is neither served nor retained, whether or not a refresh succeeds.
RATING_MAX_RETENTION_DAYS = 180

# IMDb scores are not snapshotted here. They come out of the local index the
# owner re-syncs on their own schedule, so there is no ageing number to expire
# and no upstream retention clause to honour.


@dataclass(frozen=True)
class PublicRating:
    """One source's aggregate score for a work."""

    source: str
    average: float
    votes: int
    scale: float = 10.0
    # When this number was read, for a score that ages. Empty for IMDb, whose
    # scores come out of a local index with no upstream retention clause.
    checked_at: str = ""

    @property
    def is_meaningful(self) -> bool:
        """Whether the score rests on enough opinions to be worth showing.

        A work rated by three people carries a number but not an opinion, and
        showing it next to one backed by half a million invites a comparison
        that is not there.
        """

        return self.votes >= MEANINGFUL_VOTES

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source": self.source,
            "average": self.average,
            "votes": self.votes,
            "scale": self.scale,
            "is_meaningful": self.is_meaningful,
        }
        if self.checked_at:
            # Only a score that ages carries a date, and only then does an
            # expiry mean anything.
            payload["checked_at"] = self.checked_at
            payload["expires_at"] = rating_expires_at(self.checked_at)
        return payload


def public_rating(
    source: Any,
    average: Any,
    votes: Any,
    checked_at: Any = "",
) -> PublicRating | None:
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
    return PublicRating(
        source=name,
        average=round(score, 1),
        votes=count,
        scale=scale,
        checked_at=str(checked_at or "").strip(),
    )


def rating_expires_at(checked_at: str) -> str:
    """When a copy of a TMDb score must stop being shown, contractually.

    The same clause `domain/streaming.py` enforces for availability, and the
    same reason it is sent rather than kept: a phone holds its own copy, so the
    ceiling has to travel with the row or it only binds the server.

    Deliberately implemented here rather than imported from the streaming
    module. Public scores and streaming availability are separate concerns that
    happen to share one upstream's terms, and `tests/test_public_ratings.py`
    pins the two against each other so they cannot drift apart in silence.
    """

    stamp = str(checked_at or "").strip()
    if not stamp:
        return ""
    try:
        moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        # Unreadable cannot be shown to be inside the window, so it is already
        # over -- the direction `_age` takes, for the same reason.
        return stamp
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    expires = moment + timedelta(days=RATING_MAX_RETENTION_DAYS)
    return expires.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class PublicRatingSnapshot:
    """One source's score for a work, and when we last asked for it.

    ``checked_at`` is part of the fact rather than bookkeeping: the score keeps
    moving upstream and nobody tells us, so a stored number without its date
    would be a claim we cannot support.
    """

    work_key: str
    source: str
    checked_at: str
    average: float
    votes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_key": self.work_key,
            "source": self.source,
            "checked_at": self.checked_at,
            "average": self.average,
            "votes": self.votes,
        }


def rating_snapshot(value: Mapping[str, Any]) -> PublicRatingSnapshot | None:
    """Build a snapshot, or nothing when the numbers cannot be trusted."""

    rating = public_rating(value.get("source"), value.get("average"), value.get("votes"))
    key = str(value.get("work_key") or "").strip()
    checked_at = str(value.get("checked_at") or "").strip()
    if rating is None or not key or not checked_at:
        return None
    return PublicRatingSnapshot(
        work_key=key,
        source=rating.source,
        checked_at=checked_at,
        average=rating.average,
        votes=rating.votes,
    )


def rating_snapshot_is_stale(
    snapshot: PublicRatingSnapshot,
    *,
    now: datetime | None = None,
) -> bool:
    """Whether the snapshot is old enough to be worth refreshing."""

    return _age(snapshot.checked_at, now) >= timedelta(days=RATING_STALE_AFTER_DAYS)


def rating_snapshot_is_expired(
    snapshot: PublicRatingSnapshot,
    *,
    now: datetime | None = None,
) -> bool:
    """Whether the terms forbid serving or keeping this row any longer."""

    return _age(snapshot.checked_at, now) >= timedelta(days=RATING_MAX_RETENTION_DAYS)


def visible_rating(
    snapshot: PublicRatingSnapshot | None,
    *,
    now: datetime | None = None,
) -> PublicRating | None:
    """The score a viewer may be shown, or nothing when there is none to show.

    An expired snapshot yields nothing rather than a stale number. Unlike
    availability, where "we do not know" is itself worth saying, an absent score
    just means one fewer opinion beside the viewer's own.
    """

    if snapshot is None or rating_snapshot_is_expired(snapshot, now=now):
        return None
    return public_rating(snapshot.source, snapshot.average, snapshot.votes, snapshot.checked_at)


def tmdb_work_key(tmdb_id: Any, media_type: Any) -> str:
    """Identity of a work for rating purposes, empty when there is none.

    Deliberately the same ``media_type:id`` shape ``domain/streaming.py`` uses,
    because both snapshot tables key the same works from the same upstream and
    two shapes would be a trap for anyone reading one table against the other.
    ``tests/test_public_ratings.py`` pins the two together so they cannot drift
    apart silently.
    """

    identifier = str(tmdb_id or "").strip()
    medium = str(media_type or "").strip().casefold()
    if not identifier.isdigit() or medium not in {"movie", "tv"}:
        return ""
    return f"{medium}:{identifier}"


def _age(checked_at: str, now: datetime | None) -> timedelta:
    moment = now or datetime.now(UTC)
    try:
        stamp = datetime.fromisoformat(str(checked_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        # An unreadable timestamp cannot be shown to be inside the retention
        # window, so it counts as maximally old rather than as fresh.
        return timedelta(days=RATING_MAX_RETENTION_DAYS * 10)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return moment - stamp


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
    "RATING_MAX_RETENTION_DAYS",
    "RATING_STALE_AFTER_DAYS",
    "TMDB_SOURCE",
    "PublicRating",
    "PublicRatingSnapshot",
    "public_rating",
    "rating_expires_at",
    "rating_snapshot",
    "rating_snapshot_is_expired",
    "rating_snapshot_is_stale",
    "sorted_ratings",
    "strip_public_ratings",
    "tmdb_work_key",
    "visible_rating",
]
