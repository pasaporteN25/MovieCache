"""Application service for the streaming back office and member choices.

Two authorities meet here and must not be confused. The **owner** decides which
markets the instance consults at all and whether members may pick their own; a
**member** only ever decides among what the owner enabled, and only for
themselves. Every method below is explicit about which of the two it serves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from movie_inbox.application.streaming_repository import (
    StreamingRegionNotFound,
    StreamingRepository,
)
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.domain.streaming import (
    MemberStreamingPreferences,
    RegionPolicy,
    StreamingConfigurationError,
    StreamingProvider,
    StreamingRegion,
    effective_region,
    member_preferences,
    normalize_region_code,
    region_policy,
    streaming_provider,
    streaming_region,
    visible_providers,
)


class StreamingAuthorizationError(PermissionError):
    """Raised when a member attempts an owner-only configuration change."""


class StreamingSourceUnavailable(RuntimeError):
    """Raised when no upstream catalogue is configured to refresh from."""


# Returns the raw region and provider catalogues for one market. Injected by the
# presentation layer so this service never learns which upstream serves it, and
# `application/` keeps its hands off `external/`.
RegionCatalogueLoader = Callable[[], list[dict[str, Any]]]
ProviderCatalogueLoader = Callable[[str], list[dict[str, Any]]]


class StreamingService:
    def __init__(
        self,
        repository: StreamingRepository,
        *,
        region_loader: RegionCatalogueLoader | None = None,
        provider_loader: ProviderCatalogueLoader | None = None,
    ) -> None:
        self.repository = repository
        self.region_loader = region_loader
        self.provider_loader = provider_loader

    @property
    def upstream_configured(self) -> bool:
        return self.region_loader is not None and self.provider_loader is not None

    # --- owner-only configuration -------------------------------------------------

    def configuration(self) -> dict[str, Any]:
        regions = self.repository.list_regions()
        policy = self.repository.region_policy()
        return {
            "regions": [region.to_dict() for region in regions],
            "policy": policy.to_dict(),
            "providers": {
                region.code: [provider.to_dict() for provider in self.list_providers(region.code)]
                for region in regions
                if region.enabled
            },
        }

    def add_region(self, payload: dict[str, Any]) -> StreamingRegion:
        return self.repository.upsert_region(streaming_region(payload))

    def set_region_enabled(self, code: str, enabled: bool) -> StreamingRegion:
        region = self.repository.set_region_enabled(code, enabled)
        if not enabled:
            # A disabled region must not stay the instance default, or every
            # member silently falls back to a market nobody consults.
            policy = self.repository.region_policy()
            if policy.default_region == region.code:
                self.repository.set_region_policy(
                    RegionPolicy(default_region="", members_may_choose=policy.members_may_choose)
                )
        return region

    def set_policy(self, payload: dict[str, Any]) -> RegionPolicy:
        enabled = [region.code for region in self.repository.list_regions() if region.enabled]
        return self.repository.set_region_policy(region_policy(payload, enabled_regions=enabled))

    def replace_providers(
        self,
        region_code: str,
        rows: list[dict[str, Any]],
    ) -> list[StreamingProvider]:
        region = self._require_region(region_code)
        providers = [
            streaming_provider({**row, "region_code": region.code})
            for row in rows
            if isinstance(row, dict)
        ]
        seen: set[str] = set()
        for provider in providers:
            if provider.provider_id in seen:
                raise StreamingConfigurationError(f"Duplicate provider: {provider.provider_id}")
            seen.add(provider.provider_id)
        return self.repository.replace_providers(region.code, providers)

    def list_providers(self, region_code: str) -> list[StreamingProvider]:
        return self.repository.list_providers(self._require_region(region_code).code)

    def available_upstream_regions(self) -> list[dict[str, Any]]:
        """The markets the upstream can answer for, so the owner picks from real ones."""

        if self.region_loader is None:
            raise StreamingSourceUnavailable("No streaming catalogue is configured")
        regions = [streaming_region(row) for row in self.region_loader() if isinstance(row, dict)]
        return [region.to_dict() for region in sorted(regions, key=lambda row: row.code)]

    def refresh_providers(self, region_code: str) -> list[StreamingProvider]:
        """Replace a market's platform list with the upstream's own names.

        ADR-0004 requires the stored names to be the literal ones the upstream
        uses, never typed from memory, so this is the only sanctioned way to
        populate the catalogue.
        """

        if self.provider_loader is None:
            raise StreamingSourceUnavailable("No streaming catalogue is configured")
        region = self._require_region(region_code)
        return self.replace_providers(region.code, list(self.provider_loader(region.code)))

    # --- member scope --------------------------------------------------------------

    def preferences_for(self, identity: AuthenticatedIdentity) -> dict[str, Any]:
        policy = self.repository.region_policy()
        preferences = self.repository.member_preferences(identity.user.id)
        enabled = [region.code for region in self.repository.list_regions() if region.enabled]
        resolved = effective_region(policy, preferences, enabled_regions=enabled)
        providers = self.repository.list_providers(resolved) if resolved else []
        return {
            "preferences": preferences.to_dict(),
            "effective_region": resolved,
            "may_choose": policy.members_may_choose,
            "available_regions": enabled,
            "visible_providers": [
                provider.to_dict() for provider in visible_providers(providers, preferences)
            ],
        }

    def update_preferences(
        self,
        identity: AuthenticatedIdentity,
        payload: dict[str, Any],
    ) -> MemberStreamingPreferences:
        policy = self.repository.region_policy()
        regions = self.repository.list_regions()
        enabled = {region.code for region in regions if region.enabled}
        requested = member_preferences(payload)
        if requested.region and requested.region not in enabled:
            raise StreamingConfigurationError(f"Region is not enabled: {requested.region}")
        if requested.region and not policy.members_may_choose:
            raise StreamingAuthorizationError("This instance does not let members choose a region")
        known = {
            provider.provider_id
            for code in enabled
            for provider in self.repository.list_providers(code)
        }
        validated = member_preferences(payload, known_providers=known)
        return self.repository.set_member_preferences(identity.user.id, validated)

    def _require_region(self, code: str) -> StreamingRegion:
        normalized = normalize_region_code(code)
        for region in self.repository.list_regions():
            if region.code == normalized:
                return region
        raise StreamingRegionNotFound(f"Region is not configured: {normalized}")
