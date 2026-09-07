"""Streaming regions, platforms and the rules that decide availability.

Pure domain: no I/O, no HTTP, no persistence. The vocabulary here deliberately
stays separate from ``en_catalogo``. Physical availability (owning a file) and
platform availability (a work being offered by a streaming service) are two
different facts about a work and never substitute for one another, exactly as
``PRODUCT.md`` requires of ``en_catalogo`` versus ``to_watch``/``watched``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

# ISO 3166-1 alpha-2. The authoritative list of *supported* regions comes from
# the provider, not from a table baked in here; this only fixes the shape.
_REGION_CODE = re.compile(r"^[A-Za-z]{2}$")

MAX_REGION_NAME = 80
MAX_PROVIDER_NAME = 120

# An offer kind describes how a platform makes a work available.
SUBSCRIPTION_OFFER = "flatrate"
FREE_OFFER = "free"
ADS_OFFER = "ads"
RENT_OFFER = "rent"
BUY_OFFER = "buy"

OFFER_KINDS = (SUBSCRIPTION_OFFER, FREE_OFFER, ADS_OFFER, RENT_OFFER, BUY_OFFER)

# Owner decision, 2026-09-07 (ADR-0004): only offers a viewer can watch without
# paying per title count as "available on a platform". Renting and buying are
# real information, but presenting them as availability would tell the viewer
# something false, so they are carried separately and phrased differently.
AVAILABILITY_OFFERS = frozenset({SUBSCRIPTION_OFFER, FREE_OFFER, ADS_OFFER})
ACQUISITION_OFFERS = frozenset({RENT_OFFER, BUY_OFFER})


class StreamingConfigurationError(ValueError):
    """Raised when a region or platform definition is not usable."""


@dataclass(frozen=True)
class StreamingRegion:
    """A market whose availability an instance is willing to consult."""

    code: str
    name: str
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "name": self.name, "enabled": self.enabled}


@dataclass(frozen=True)
class StreamingProvider:
    """A platform as the upstream source names it.

    ``name`` is stored verbatim. ADR-0004 measured why: the API calls Apple's
    subscription service ``Apple TV`` while ``Apple TV Store`` is rent/buy and
    ``Apple TV Amazon Channel`` is a resold channel. Matching those by substring
    conflates three different things, so the literal name and the upstream id
    are the identity, never a guessed label.
    """

    region_code: str
    provider_id: str
    name: str
    display_priority: int = 0
    logo_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_code": self.region_code,
            "provider_id": self.provider_id,
            "name": self.name,
            "display_priority": self.display_priority,
            "logo_path": self.logo_path,
        }


@dataclass(frozen=True)
class RegionPolicy:
    """How an instance lets its members pick the market they care about.

    The credential belongs to the instance ([F4.1]) but the market does not: the
    owner accepts the terms and manages the quota, while each member may care
    about a different country. ``members_may_choose`` lets the owner keep that
    decision centralised when they would rather not.
    """

    default_region: str = ""
    members_may_choose: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_region": self.default_region,
            "members_may_choose": self.members_may_choose,
        }


@dataclass(frozen=True)
class MemberStreamingPreferences:
    """What one member chose for themselves.

    ``ignored_providers`` is deliberately weak information: hiding a platform
    says nothing about whether the member subscribes to it. That is the whole
    point — it personalises the view without ever building a model of what
    somebody pays for, which would be personal data under the privacy invariant.
    """

    region: str = ""
    ignored_providers: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {"region": self.region, "ignored_providers": list(self.ignored_providers)}


def normalize_region_code(value: Any) -> str:
    code = str(value or "").strip()
    if not _REGION_CODE.match(code):
        raise StreamingConfigurationError(f"Region must be an ISO 3166-1 alpha-2 code: {value!r}")
    return code.upper()


def normalize_region_name(value: Any, *, fallback: str = "") -> str:
    name = " ".join(str(value or "").split())[:MAX_REGION_NAME]
    return name or fallback


def normalize_provider_id(value: Any) -> str:
    provider_id = str(value or "").strip()
    if not provider_id or not provider_id.isascii() or not provider_id.replace("-", "").isalnum():
        raise StreamingConfigurationError(f"Invalid provider id: {value!r}")
    return provider_id


def normalize_provider_name(value: Any) -> str:
    name = " ".join(str(value or "").split())[:MAX_PROVIDER_NAME]
    if not name:
        raise StreamingConfigurationError("Provider name cannot be empty")
    return name


def streaming_region(value: Mapping[str, Any]) -> StreamingRegion:
    code = normalize_region_code(value.get("code"))
    return StreamingRegion(
        code=code,
        name=normalize_region_name(value.get("name"), fallback=code),
        enabled=_bool(value.get("enabled"), default=True),
    )


def streaming_provider(value: Mapping[str, Any]) -> StreamingProvider:
    return StreamingProvider(
        region_code=normalize_region_code(value.get("region_code")),
        provider_id=normalize_provider_id(value.get("provider_id")),
        name=normalize_provider_name(value.get("name")),
        display_priority=_non_negative_int(value.get("display_priority")),
        logo_path=str(value.get("logo_path") or "").strip()[:200],
    )


def region_policy(
    value: Mapping[str, Any] | None, *, enabled_regions: Iterable[str]
) -> RegionPolicy:
    row = value or {}
    available = {normalize_region_code(code) for code in enabled_regions}
    raw_default = str(row.get("default_region") or "").strip()
    default = normalize_region_code(raw_default) if raw_default else ""
    if default and default not in available:
        raise StreamingConfigurationError(f"Default region is not enabled: {default}")
    return RegionPolicy(
        default_region=default,
        members_may_choose=_bool(row.get("members_may_choose")),
    )


def member_preferences(
    value: Mapping[str, Any] | None,
    *,
    known_providers: Iterable[str] = (),
) -> MemberStreamingPreferences:
    row = value or {}
    raw_region = str(row.get("region") or "").strip()
    known = {str(provider) for provider in known_providers}
    ignored: list[str] = []
    for candidate in _as_list(row.get("ignored_providers")):
        provider_id = normalize_provider_id(candidate)
        if known and provider_id not in known:
            raise StreamingConfigurationError(f"Unknown provider: {provider_id}")
        if provider_id not in ignored:
            ignored.append(provider_id)
    return MemberStreamingPreferences(
        region=normalize_region_code(raw_region) if raw_region else "",
        ignored_providers=tuple(sorted(ignored)),
    )


def effective_region(
    policy: RegionPolicy,
    preferences: MemberStreamingPreferences,
    *,
    enabled_regions: Iterable[str],
) -> str:
    """Resolve which market one viewer actually sees.

    A member's own choice only counts while the owner allows it and the region
    is still enabled; disabling a region must not leave somebody pinned to a
    market the instance no longer consults.
    """

    available = {normalize_region_code(code) for code in enabled_regions}
    if policy.members_may_choose and preferences.region in available:
        return preferences.region
    if policy.default_region in available:
        return policy.default_region
    return ""


def is_available_offer(kind: Any) -> bool:
    """Whether an offer kind means "you can watch this now"."""

    return str(kind or "").strip().casefold() in AVAILABILITY_OFFERS


def visible_providers(
    providers: Sequence[StreamingProvider],
    preferences: MemberStreamingPreferences,
) -> list[StreamingProvider]:
    """Apply a member's ignore list as a view filter.

    The filter is applied on read, per viewer. The stored availability snapshot
    stays raw and shared: filtering at the source would make the cached fact
    depend on who asked for it and stop it being shareable at all.
    """

    ignored = set(preferences.ignored_providers)
    return [provider for provider in providers if provider.provider_id not in ignored]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return list(value)
    raise StreamingConfigurationError(f"Expected a list of providers: {value!r}")


def _bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value).strip().casefold() in {"1", "true", "yes", "si"}


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
