"""Public scores for a viewer's catalogue, from two sources at once.

Owner decision, 2026-09-07: show several public scores side by side instead of
picking one, so the reader compares rather than being handed a single yardstick,
with their own rating next to them. That makes this service a merger, not a
chooser -- it never ranks one upstream above another and never collapses them
into an average.

The two sources are read very differently, and the difference is the whole
reason this service exists:

* **IMDb** comes out of the local index the owner built and re-syncs on their
  own schedule. No network, no ageing, nothing to expire.
* **TMDb** is a moving number behind an HTTP call, so it is kept as a dated
  snapshot with the same treatment [S3] gave streaming availability: refreshed
  lazily once stale, dropped once past the contractual retention ceiling.

The rule [F3.2] fixed still holds and is structural here: nothing this service
returns ever reaches the personal `rating` field. It only ever reads items.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from movie_inbox.application.public_ratings_repository import PublicRatingsRepository
from movie_inbox.domain.public_ratings import (
    RATING_MAX_RETENTION_DAYS,
    TMDB_SOURCE,
    PublicRating,
    PublicRatingSnapshot,
    rating_snapshot,
    rating_snapshot_is_stale,
    sorted_ratings,
    tmdb_work_key,
    visible_rating,
)

# imdb_id -> that source's score, or nothing. Injected by the presentation layer
# so this service never learns which index answers it and `application/` keeps
# its hands off `external/`.
ImdbRatingLookup = Callable[[str], PublicRating | None]
# (media_type, tmdb_id) -> {"average": float, "votes": int}, empty when unknown.
TmdbRatingLoader = Callable[[str, str], dict[str, Any]]
# An item's IMDb id, however the catalogue happens to record it.
ImdbIdReader = Callable[[dict[str, Any]], str]


class PublicRatingsService:
    def __init__(
        self,
        repository: PublicRatingsRepository,
        *,
        imdb_lookup: ImdbRatingLookup | None = None,
        imdb_id_reader: ImdbIdReader | None = None,
        tmdb_loader: TmdbRatingLoader | None = None,
        max_refresh_per_request: int = 12,
    ) -> None:
        self.repository = repository
        self.imdb_lookup = imdb_lookup
        self.imdb_id_reader = imdb_id_reader
        self.tmdb_loader = tmdb_loader
        # Same budget streaming availability uses, for the same reason: a page
        # can show a whole catalogue, and refreshing every stale row inline
        # would turn one navigation into hundreds of upstream calls. The rest
        # keep serving their snapshot and get refreshed on later reads.
        self.max_refresh_per_request = max(0, int(max_refresh_per_request))

    @property
    def sources_configured(self) -> bool:
        return self.imdb_lookup is not None or self.tmdb_loader is not None

    def ratings_for(self, items: Sequence[dict[str, Any]]) -> dict[str, list[PublicRating]]:
        """Every public score we hold for these items, by item id.

        An item with no score at all is left out of the map entirely rather than
        carrying an empty list, so a caller cannot mistake "nobody rated this"
        for "we have no source configured".
        """

        keys: dict[str, str] = {}
        for item in items:
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            key = tmdb_work_key(item.get("tmdb_id"), _media_type(item))
            if key:
                keys[item_id] = key

        stored = self.repository.ratings(TMDB_SOURCE, sorted(set(keys.values())))
        stored = self._refresh_stale(keys, stored)

        found: dict[str, list[PublicRating]] = {}
        for item in items:
            item_id = str(item.get("id") or "")
            if not item_id:
                continue
            ratings: list[PublicRating] = []
            imdb = self._imdb_rating(item)
            if imdb is not None:
                ratings.append(imdb)
            tmdb = visible_rating(stored.get(keys.get(item_id, "")))
            if tmdb is not None:
                ratings.append(tmdb)
            if ratings:
                found[item_id] = sorted_ratings(ratings)
        return found

    def purge_expired_ratings(self) -> int:
        """Discard TMDb snapshots past the contractual retention ceiling."""

        cutoff = datetime.now(UTC) - timedelta(days=RATING_MAX_RETENTION_DAYS)
        return self.repository.purge_ratings(
            source=TMDB_SOURCE,
            before=cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )

    def purge_all_tmdb_ratings(self) -> int:
        """Drop every TMDb snapshot, for the retirement flow.

        Scoped to TMDb on purpose: retiring one upstream must not take away the
        IMDb index the owner built, which is not TMDb's data to reclaim.
        """

        return self.repository.purge_ratings(source=TMDB_SOURCE)

    def _imdb_rating(self, item: dict[str, Any]) -> PublicRating | None:
        if self.imdb_lookup is None or self.imdb_id_reader is None:
            return None
        imdb_id = self.imdb_id_reader(item)
        return self.imdb_lookup(imdb_id) if imdb_id else None

    def _refresh_stale(
        self,
        keys: dict[str, str],
        stored: dict[str, PublicRatingSnapshot],
    ) -> dict[str, PublicRatingSnapshot]:
        if self.tmdb_loader is None:
            return stored
        budget = self.max_refresh_per_request
        for key in dict.fromkeys(keys.values()):
            if budget <= 0:
                break
            snapshot = stored.get(key)
            if snapshot is not None and not rating_snapshot_is_stale(snapshot):
                continue
            media_type, _, tmdb_id = key.partition(":")
            try:
                raw = self.tmdb_loader(media_type, tmdb_id)
            except Exception:
                # A public score is supplementary: an upstream outage or rate
                # limit must not break the surface that asked. Any existing
                # snapshot keeps being served until it expires on its own.
                budget -= 1
                continue
            budget -= 1
            fresh = rating_snapshot(
                {
                    "work_key": key,
                    "source": TMDB_SOURCE,
                    "checked_at": _timestamp(),
                    "average": raw.get("average"),
                    "votes": raw.get("votes"),
                }
            )
            if fresh is None:
                # An unrated work upstream is a normal answer, not a failure.
                # Nothing is stored, so it is retried on a later read instead of
                # being remembered as a zero.
                continue
            stored[key] = self.repository.save_rating(fresh)
        return stored


def _media_type(item: dict[str, Any]) -> str:
    """Map a catalogue `kind` onto the upstream's movie/tv split."""

    kind = str(item.get("kind") or "").strip().casefold()
    return "tv" if kind in {"serie", "series", "anime_serie"} else "movie"


def _timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
