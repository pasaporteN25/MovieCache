"""[X5] Remember which works a person removed, and say so when a device asks.

ADR-0005's amendment of 2026-09-14 lets removals travel, on three conditions
this service is where they are kept: a removal is an explicit record and never
an inference from a work being absent; a removal never outranks a work that
still exists; and merging duplicates counts as removing the one that went away,
with a pointer to the one that stayed.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass

from movie_inbox.application.removal_repository import RemovalRepository
from movie_inbox.domain.removals import DeviceRemoval

# A phone's key stops working a month after it last synced, and a phone that
# pairs again with the same account keeps its data, so the record has to
# outlive the worst gap that is still reasonable. Past this it is forgotten,
# and the answer becomes "unknown" -- which already means "do not delete it".
REMOVAL_RETENTION_SECONDS = 365 * 24 * 3600

# A merge chain is followed until it reaches a work that exists or one that was
# deleted. The bound is only a guard against a record that loops.
MAX_MERGE_HOPS = 16

PRESENT = "present"
REMOVED = "removed"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class RemovalStatus:
    """What a device is told about one id it asked about."""

    state: str
    reason: str = ""
    merged_into: str = ""
    removed_at: int = 0


class RemovalService:
    def __init__(
        self,
        repository: RemovalRepository,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.repository = repository
        self._clock = clock

    def _now(self) -> int:
        return int(self._clock())

    def record(self, catalog_id: str, removals: Sequence[DeviceRemoval]) -> None:
        """Remember these works as removed, and forget records past retention."""

        now = self._now()
        self.repository.purge(now - REMOVAL_RETENTION_SECONDS)
        if removals:
            self.repository.save(catalog_id, removals, now)

    def forget(self, catalog_id: str, device_ids: Sequence[str]) -> None:
        """A removal was undone: the works are back, so there is nothing to tell."""

        if device_ids:
            self.repository.forget(catalog_id, device_ids)

    def statuses(
        self,
        catalog_id: str,
        device_ids: Sequence[str],
        present: Collection[str],
    ) -> dict[str, RemovalStatus]:
        """Answer for every id asked about, including the ones nobody knows.

        `present` is every id a device could see in the catalogue right now.
        A work that exists is `present` even if a stale record says otherwise.
        """

        asked = list(dict.fromkeys(device_ids))
        known = self.repository.get_many(catalog_id, asked)
        answers: dict[str, RemovalStatus] = {}
        for device_id in asked:
            if device_id in present:
                answers[device_id] = RemovalStatus(PRESENT)
                continue
            first = known.get(device_id)
            if first is None:
                answers[device_id] = RemovalStatus(UNKNOWN)
                continue
            answers[device_id] = self._settled(catalog_id, first, present)
        return answers

    def _settled(
        self,
        catalog_id: str,
        first: DeviceRemoval,
        present: Collection[str],
    ) -> RemovalStatus:
        """Follow a merge to where it ended, so a device is not left mid-chain."""

        current = first
        seen = {first.device_id}
        for _ in range(MAX_MERGE_HOPS):
            if current.reason == "deleted":
                # Either it was deleted outright, or the work it was merged into
                # was deleted afterwards: in both, nothing took its place.
                return RemovalStatus(REMOVED, "deleted", "", first.removed_at)
            target = current.merged_into
            if target in present or target in seen:
                return RemovalStatus(REMOVED, "merged", target, first.removed_at)
            following = self.repository.get_many(catalog_id, [target]).get(target)
            if following is None:
                # Its fate is not on record; the device can ask about it in turn.
                return RemovalStatus(REMOVED, "merged", target, first.removed_at)
            seen.add(target)
            current = following
        return RemovalStatus(REMOVED, "merged", current.merged_into, first.removed_at)
