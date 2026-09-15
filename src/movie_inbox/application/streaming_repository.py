"""Persistence contract for streaming regions, platforms and member choices."""

from __future__ import annotations

from typing import Protocol

from movie_inbox.domain.streaming import (
    AvailabilitySnapshot,
    MemberStreamingPreferences,
    RegionPolicy,
    StreamingProvider,
    StreamingRegion,
)


class StreamingRepositoryError(RuntimeError):
    """Raised when the streaming configuration cannot be persisted."""


class StreamingRegionNotFound(LookupError):
    """Raised when a region is not part of this instance's configuration."""


class StreamingRepository(Protocol):
    def list_regions(self) -> list[StreamingRegion]: ...

    def upsert_region(self, region: StreamingRegion) -> StreamingRegion: ...

    def set_region_enabled(self, code: str, enabled: bool) -> StreamingRegion: ...

    def region_policy(self) -> RegionPolicy: ...

    def set_region_policy(self, policy: RegionPolicy) -> RegionPolicy: ...

    def list_providers(self, region_code: str) -> list[StreamingProvider]: ...

    def replace_providers(
        self,
        region_code: str,
        providers: list[StreamingProvider],
    ) -> list[StreamingProvider]: ...

    def member_preferences(self, user_id: str) -> MemberStreamingPreferences: ...

    def set_member_preferences(
        self,
        user_id: str,
        preferences: MemberStreamingPreferences,
    ) -> MemberStreamingPreferences: ...

    def availability(
        self,
        region_code: str,
        work_keys: list[str],
    ) -> dict[str, AvailabilitySnapshot]: ...

    def save_availability(self, snapshot: AvailabilitySnapshot) -> AvailabilitySnapshot: ...

    def purge_availability(self, *, before: str = "") -> int:
        """Drop snapshots, or only those checked before an ISO timestamp."""
        ...
