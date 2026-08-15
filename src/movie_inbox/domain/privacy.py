"""Privacy rules for sharing a personal catalog inside one instance."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

VISIBILITY_MODES = {"inherit", "shared", "private"}
OVERRIDABLE_FIELDS = {"rating", "review"}
SHARED_CATALOG_FIELDS = {
    "id",
    "url",
    "source",
    "title",
    "original_title",
    "spanish_title",
    "english_title",
    "alternative_titles",
    "kind",
    "year",
    "release_dates",
    "description",
    "wikipedia_url",
    "imdb_url",
    "filmaffinity_url",
    "wikipedia_title",
    "wikidata_id",
    "genres",
    "directors",
    "writers",
    "cast",
    "page_image",
    "backdrop_image",
    "tmdb_id",
    "wikipedia_extract",
    "en_catalogo",
    "_availability",
}


@dataclass(frozen=True)
class PrivacyPreferences:
    catalog_shared: bool = False
    share_status: bool = False
    share_watched_at: bool = False
    share_history: bool = False
    share_rating: bool = False
    share_review: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "catalog_shared": self.catalog_shared,
            "share_status": self.share_status,
            "share_watched_at": self.share_watched_at,
            "share_history": self.share_history,
            "share_rating": self.share_rating,
            "share_review": self.share_review,
        }


@dataclass(frozen=True)
class ItemPrivacyOverride:
    rating: str = "inherit"
    review: str = "inherit"

    def to_dict(self) -> dict[str, str]:
        return {"rating": self.rating, "review": self.review}


def privacy_preferences(value: Mapping[str, Any] | None) -> PrivacyPreferences:
    row = value or {}
    return PrivacyPreferences(
        catalog_shared=_bool(row.get("catalog_shared")),
        share_status=_bool(row.get("share_status")),
        share_watched_at=_bool(row.get("share_watched_at")),
        share_history=_bool(row.get("share_history")),
        share_rating=_bool(row.get("share_rating")),
        share_review=_bool(row.get("share_review")),
    )


def item_privacy_override(value: Mapping[str, Any] | None) -> ItemPrivacyOverride:
    row = value or {}
    return ItemPrivacyOverride(
        rating=normalize_visibility(row.get("rating")),
        review=normalize_visibility(row.get("review")),
    )


def normalize_visibility(value: Any) -> str:
    mode = str(value or "inherit").strip().casefold()
    if mode not in VISIBILITY_MODES:
        raise ValueError(f"Invalid visibility mode: {value}")
    return mode


def field_is_shared(
    field: str,
    preferences: PrivacyPreferences,
    override: ItemPrivacyOverride | None = None,
) -> bool:
    if field not in OVERRIDABLE_FIELDS:
        raise ValueError(f"Unsupported item privacy field: {field}")
    mode = getattr(override or ItemPrivacyOverride(), field)
    if mode == "shared":
        return True
    if mode == "private":
        return False
    return preferences.share_rating if field == "rating" else preferences.share_review


def shared_catalog_item(
    item: Mapping[str, Any],
    preferences: PrivacyPreferences,
    override: ItemPrivacyOverride | None = None,
) -> dict[str, Any]:
    public = {key: value for key, value in item.items() if key in SHARED_CATALOG_FIELDS}
    availability = item.get("_availability")
    if isinstance(availability, Mapping):
        public["_availability"] = {
            "effective": _bool(availability.get("effective")),
            "manual": _bool(availability.get("manual")),
            "server": _bool(availability.get("server")),
            "verified": _bool(availability.get("verified")),
            "file_count": _non_negative_int(availability.get("file_count")),
            "library_count": _non_negative_int(availability.get("library_count")),
        }
    if preferences.share_status:
        public["status"] = str(item.get("status") or "to_watch")
    if preferences.share_watched_at:
        public["watched_at"] = str(item.get("watched_at") or "")
    if field_is_shared("rating", preferences, override):
        public["rating"] = int(item.get("rating") or 0)
    if field_is_shared("review", preferences, override):
        public["review"] = str(item.get("review") or "")
    return public


def shared_watch_history(
    items: list[Mapping[str, Any]],
    preferences: PrivacyPreferences,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if not preferences.catalog_shared or not preferences.share_history:
        return []
    watched = [item for item in items if str(item.get("status") or "") == "watched"]
    watched.sort(
        key=lambda item: (str(item.get("watched_at") or ""), str(item.get("title") or "")),
        reverse=True,
    )
    history: list[dict[str, Any]] = []
    for item in watched[: max(0, int(limit))]:
        row = {
            key: item.get(key)
            for key in ("id", "title", "year", "kind", "page_image")
            if key in item
        }
        if preferences.share_watched_at:
            row["watched_at"] = str(item.get("watched_at") or "")
        history.append(row)
    return history


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "yes", "si"}


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
