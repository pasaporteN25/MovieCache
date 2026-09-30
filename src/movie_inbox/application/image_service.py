"""[U7 B] Fill a work's two images from TMDb, reached only through ids it already has.

Contract: `docs/analisis/u7b-contrato-imagenes-2026-09-26.md` (option A plus the id
crosswalk, owner decisions 2026-09-26). Three rules carry the whole service:

* **Identity by id, never by title** (invariant 3). A work's TMDb identity is its
  own `tmdb_url`/`tmdb_id`, or a translation of its IMDb or Wikidata id that
  passes `crosswalk_decision`; anything doubtful is reported, not written.
* **Fill-only** (invariant 5). Empty, unlocked fields are written; a present
  value -- manual or from any source -- and a locked field are never touched.
* **Nothing runs by itself.** The service answers one work on request or a batch
  with an explicit limit; it never warms a whole catalogue.

The source arrives through `ImageSource`, so `application/` never imports the
clients that answer it.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.domain.catalog import metadata_source_record, themoviedb_media_reference
from movie_inbox.domain.images import (
    ROLE_FIELDS,
    CrosswalkDecision,
    ImageCandidate,
    ImageSourceUnavailable,
    TmdbMatch,
    best_images,
    crosswalk_decision,
    fill_empty_fields,
    missing_image_fields,
    tmdb_public_url,
)
from movie_inbox.domain.metadata import normalize_locked_fields
from movie_inbox.domain.normalization import normalize_kind

NEGATIVE_RESULT_TTL = timedelta(days=7)

# Statuses a caller can act on.
OK = "ok"
COMPLETE = "complete"
NO_IDENTITY = "no_identity"
NEEDS_REVIEW = "needs_review"
NO_IMAGES = "no_images"
UNAVAILABLE = "unavailable"
RATE_LIMITED = "rate_limited"
NOT_FOUND = "not_found"


class ImageSource(Protocol):
    def candidates(self, media_type: str, tmdb_id: str) -> list[ImageCandidate]: ...

    def matches_for_imdb(self, imdb_id: str) -> list[TmdbMatch]: ...

    def matches_for_wikidata(self, entity_id: str) -> list[TmdbMatch]: ...


@dataclass(frozen=True)
class TmdbIdentity:
    media_type: str
    tmdb_id: str
    crosswalked: bool

    @property
    def url(self) -> str:
        return tmdb_public_url(self.media_type, self.tmdb_id)


@dataclass
class FillPlan:
    """What one work would receive, decided before anything is written."""

    status: str
    identity: TmdbIdentity | None = None
    crosswalk: str = ""
    images: dict[str, str] = field(default_factory=dict)

    @property
    def writes(self) -> bool:
        return bool(self.images) or bool(self.identity and self.identity.crosswalked)


class ImageService:
    def __init__(
        self,
        source: ImageSource | None,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.source = source
        self.clock = clock
        # (media_type, tmdb_id) -> until when "TMDb has nothing more" is trusted.
        self._negative: dict[tuple[str, str], datetime] = {}
        self._item_locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    @property
    def configured(self) -> bool:
        return self.source is not None

    # -- one work -----------------------------------------------------------

    def candidates(self, item: Mapping[str, Any]) -> dict[str, Any]:
        """Candidates for the correction UI; asked live, never stored."""

        identity = existing_identity(item)
        answer: dict[str, Any] = {
            "item_id": str(item.get("id") or ""),
            "identity": _identity_dict(identity),
            "selected": _selected(item),
            "candidates": [],
        }
        if identity is None:
            return {**answer, "status": NO_IDENTITY}
        if self.source is None:
            return {**answer, "status": UNAVAILABLE}
        try:
            rows = self.source.candidates(identity.media_type, identity.tmdb_id)
        except ImageSourceUnavailable as error:
            return {**answer, "status": RATE_LIMITED if error.rate_limited else UNAVAILABLE}
        return {**answer, "status": OK, "candidates": [row.to_dict() for row in rows]}

    def fill(self, catalog: CatalogService, item_id: str) -> dict[str, Any]:
        """Complete one work's missing images; one fill in flight per work.

        Only for a work that already has its TMDb identity: the id crosswalk runs
        in the explicit batch alone, as the contract fixes.
        """

        with self._lock_for(item_id):
            item = catalog.repository.get(item_id)
            if item is None:
                return {"status": NOT_FOUND}
            plan = self.plan(item, crosswalk=False)
            answer = _plan_dict(plan)
            if not plan.writes:
                return answer
            applied: dict[str, Any] = {}

            def update(row: Any) -> None:
                applied.update(_apply(row, plan, self.clock()))

            catalog.repository.update_item(item_id, update)
            return {**answer, **applied}

    def plan(self, item: Mapping[str, Any], *, crosswalk: bool = True) -> FillPlan:
        missing = missing_image_fields(item)
        if not missing:
            return FillPlan(COMPLETE)
        if self.source is None:
            return FillPlan(UNAVAILABLE)
        try:
            identity, outcome = self._identity(item, crosswalk=crosswalk)
        except ImageSourceUnavailable as error:
            return FillPlan(RATE_LIMITED if error.rate_limited else UNAVAILABLE)
        if identity is None:
            return FillPlan(NEEDS_REVIEW if outcome else NO_IDENTITY, crosswalk=outcome)
        key = (identity.media_type, identity.tmdb_id)
        now = self.clock()
        if self._negative.get(key, now) > now:
            return FillPlan(NO_IMAGES, identity, outcome)
        try:
            rows = self.source.candidates(identity.media_type, identity.tmdb_id)
        except ImageSourceUnavailable as error:
            return FillPlan(RATE_LIMITED if error.rate_limited else UNAVAILABLE, identity, outcome)
        chosen = {name: url for name, url in best_images(rows).items() if name in missing}
        if not chosen:
            self._negative[key] = now + NEGATIVE_RESULT_TTL
            # A confirmed crosswalk is still worth keeping without images.
            return FillPlan(NO_IMAGES, identity, outcome)
        return FillPlan(OK, identity, outcome, chosen)

    # -- explicit batch -----------------------------------------------------

    def fill_batch(
        self,
        catalog: CatalogService,
        *,
        limit: int,
        dry_run: bool = False,
        progress: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """At most `limit` works that could gain an image, in catalogue order.

        Network first, then one write for the whole batch, so a large JSON
        catalogue is not rewritten once per work.
        """

        limit = max(0, int(limit))
        eligible = [item for item in catalog.list_items() if _batch_candidate(item)][:limit]
        plans: dict[str, FillPlan] = {}
        for position, item in enumerate(eligible, start=1):
            plan = self.plan(item)
            plans[str(item.get("id") or "")] = plan
            if progress is not None:
                progress(position, len(eligible))
            if plan.status == RATE_LIMITED:
                break
        summary = _summary(plans.values(), considered=len(eligible))
        if dry_run or not any(plan.writes for plan in plans.values()):
            return {**summary, "dry_run": dry_run}
        now = self.clock()

        def mutation(items: list[Any]) -> tuple[bool, dict[str, int]]:
            counts = {"filled_fields": 0, "identities_added": 0}
            for row in items:
                plan = plans.get(str(row.get("id") or ""))
                if plan is None or not plan.writes:
                    continue
                applied = _apply(row, plan, now)
                counts["filled_fields"] += len(applied["filled"])
                counts["identities_added"] += int(applied["identity_added"])
            return bool(counts["filled_fields"] or counts["identities_added"]), counts

        return {**summary, **catalog.repository.mutate(mutation), "dry_run": False}

    # -- internals ----------------------------------------------------------

    def _identity(
        self, item: Mapping[str, Any], *, crosswalk: bool
    ) -> tuple[TmdbIdentity | None, str]:
        identity = existing_identity(item)
        if identity is not None or not crosswalk:
            return identity, ""
        locked = set(normalize_locked_fields(item.get("locked_fields")))
        if {"tmdb_id", "tmdb_url"} & locked:
            return None, ""
        assert self.source is not None
        # IMDb first; Wikidata only for a work without an IMDb id.
        imdb_id = imdb_id_of(item)
        wikidata_id = str(item.get("wikidata_id") or "").strip().upper()
        if imdb_id:
            matches = self.source.matches_for_imdb(imdb_id)
        elif wikidata_id.startswith("Q") and wikidata_id[1:].isdigit():
            matches = self.source.matches_for_wikidata(wikidata_id)
        else:
            return None, ""
        decision: CrosswalkDecision = crosswalk_decision(item, matches)
        if not decision.accepted or decision.match is None:
            return None, decision.status
        return TmdbIdentity(
            decision.match.media_type, decision.match.tmdb_id, True
        ), decision.status

    def _lock_for(self, item_id: str) -> threading.Lock:
        with self._guard:
            return self._item_locks.setdefault(item_id, threading.Lock())


def existing_identity(item: Mapping[str, Any]) -> TmdbIdentity | None:
    reference = themoviedb_media_reference(str(item.get("tmdb_url") or ""))
    if reference is not None:
        return TmdbIdentity(reference[0], reference[1], False)
    tmdb_id = str(item.get("tmdb_id") or "").strip()
    if tmdb_id.isdigit() and int(tmdb_id) > 0:
        media_type = "tv" if normalize_kind(item.get("kind")) == "serie" else "movie"
        return TmdbIdentity(media_type, str(int(tmdb_id)), False)
    return None


def imdb_id_of(item: Mapping[str, Any]) -> str:
    match = re.search(r"\btt\d{7,9}\b", str(item.get("imdb_url") or ""), flags=re.IGNORECASE)
    return match.group(0).lower() if match else ""


def _batch_candidate(item: Mapping[str, Any]) -> bool:
    if not missing_image_fields(item):
        return False
    return bool(
        existing_identity(item)
        or imdb_id_of(item)
        or str(item.get("wikidata_id") or "").strip().upper().startswith("Q")
    )


def _apply(row: Any, plan: FillPlan, now: datetime) -> dict[str, Any]:
    """Write a plan into a catalogue row, fill-only, with TMDb provenance."""

    identity = plan.identity
    identity_added = False
    filled: list[str] = []
    kept: list[str] = []
    skipped: list[str] = []
    if identity is None:
        return {"filled": filled, "kept": kept, "skipped_locked": skipped, "identity_added": False}
    stamp = now.isoformat()
    if identity.crosswalked:
        # Marked inferred: a translated id, not one the owner chose by hand.
        result = fill_empty_fields(
            row,
            {"tmdb_id": identity.tmdb_id, "tmdb_url": identity.url},
            metadata_source_record("tmdb", identity.url, True, stamp),
        )
        identity_added = "tmdb_id" in result.filled
        filled += result.filled
    if plan.images:
        result = fill_empty_fields(
            row,
            plan.images,
            metadata_source_record("tmdb", identity.url, identity.crosswalked, stamp),
        )
        filled += result.filled
        kept += result.kept
        skipped += result.skipped_locked
    return {
        "filled": filled,
        "kept": kept,
        "skipped_locked": skipped,
        "identity_added": identity_added,
    }


def _identity_dict(identity: TmdbIdentity | None) -> dict[str, Any] | None:
    if identity is None:
        return None
    return {"source": "tmdb", "media_type": identity.media_type, "tmdb_id": identity.tmdb_id}


def _selected(item: Mapping[str, Any]) -> dict[str, Any]:
    locked = set(normalize_locked_fields(item.get("locked_fields")))
    sources = item.get("metadata_sources")
    sources = sources if isinstance(sources, Mapping) else {}
    selected: dict[str, Any] = {}
    for name in ROLE_FIELDS.values():
        record = sources.get(name)
        selected[name] = {
            "url": str(item.get(name) or ""),
            "source": str(record.get("source") or "") if isinstance(record, Mapping) else "",
            "locked": name in locked,
        }
    return selected


def _plan_dict(plan: FillPlan) -> dict[str, Any]:
    return {
        "status": plan.status,
        "crosswalk": plan.crosswalk,
        "identity": _identity_dict(plan.identity),
        "filled": [],
        "kept": [],
        "skipped_locked": [],
        "identity_added": False,
    }


def _summary(plans: Iterable[FillPlan], *, considered: int) -> dict[str, Any]:
    plans = list(plans)
    by_status: dict[str, int] = {}
    crosswalks: dict[str, int] = {}
    for plan in plans:
        by_status[plan.status] = by_status.get(plan.status, 0) + 1
        if plan.crosswalk:
            crosswalks[plan.crosswalk] = crosswalks.get(plan.crosswalk, 0) + 1
    return {
        "considered": considered,
        "by_status": by_status,
        "crosswalk": crosswalks,
        "would_fill": sum(len(plan.images) for plan in plans),
        "would_add_identity": sum(
            1 for plan in plans if plan.identity is not None and plan.identity.crosswalked
        ),
    }
