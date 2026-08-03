"""Managed media library and shared availability models."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from movie_inbox.domain.catalog import (
    canonical_url,
    external_urls,
    normalize_tags,
    title_match_keys_for_item,
)
from movie_inbox.domain.matching import explicit_kind


LIBRARY_SCHEDULES = {"manual", "hourly", "daily"}
LIBRARY_STATUSES = {
    "unverified",
    "ready",
    "scanning",
    "paused",
    "offline",
    "warning",
    "error",
}
FILE_STATES = {"new", "matched", "review", "ignored"}
RUN_MODES = {"dry_run", "apply"}
RUN_TRIGGERS = {"manual", "scheduled"}
RUN_STATUSES = {"queued", "running", "completed", "partial", "blocked", "failed"}
KIND_LABELS = {"pelicula", "serie", "anime", "documental"}


class LibraryValidationError(ValueError):
    """Raised when managed library data is invalid."""


@dataclass(frozen=True)
class ManagedLibrary:
    id: str
    name: str
    root_path: str
    created_by_user_id: str = ""
    schedule: str = "manual"
    active: bool = False
    status: str = "unverified"
    max_missing_ratio: float = 0.5
    verified_at: int = 0
    last_scan_at: int = 0
    next_scan_at: int = 0
    created_at: int = 0
    updated_at: int = 0


@dataclass(frozen=True)
class LibraryScanRun:
    id: str
    library_id: str
    mode: str
    trigger: str
    status: str = "queued"
    created_at: int = 0
    started_at: int = 0
    finished_at: int = 0
    summary: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()
    preview: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class LibraryFile:
    id: str
    library_id: str
    relative_path: str
    name: str
    size_bytes: int
    modified_ns: int
    modified_at: str
    fingerprint: str
    detected_title: str
    detected_year: str
    detected_kind: str
    state: str = "new"
    work_key: str = ""
    identity: Mapping[str, Any] = field(default_factory=dict)
    candidates: tuple[Mapping[str, Any], ...] = ()
    available: bool = True
    first_seen_at: int = 0
    last_seen_at: int = 0
    updated_at: int = 0
    last_run_id: str = ""


def normalize_library_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "")).strip()
    if not 2 <= len(name) <= 120:
        raise LibraryValidationError("Library name must contain 2-120 characters")
    return name


def normalize_schedule(value: Any) -> str:
    schedule = str(value or "manual").strip().casefold()
    if schedule not in LIBRARY_SCHEDULES:
        raise LibraryValidationError(f"Invalid library schedule: {value}")
    return schedule


def normalize_missing_ratio(value: Any) -> float:
    try:
        ratio = float(value)
    except (TypeError, ValueError) as error:
        raise LibraryValidationError("Missing-file guard must be a number") from error
    if not 0.0 <= ratio <= 1.0:
        raise LibraryValidationError("Missing-file guard must be between 0 and 1")
    return ratio


def normalize_file_state(value: Any) -> str:
    state = str(value or "new").strip().casefold()
    if state not in FILE_STATES:
        raise LibraryValidationError(f"Invalid scanner file state: {value}")
    return state


def work_identity(item: Mapping[str, Any]) -> dict[str, Any]:
    """Return catalog-independent evidence that can be shared safely."""
    identity = {
        "title": str(item.get("title") or "").strip(),
        "original_title": str(item.get("original_title") or "").strip(),
        "spanish_title": str(item.get("spanish_title") or "").strip(),
        "english_title": str(item.get("english_title") or "").strip(),
        "alternative_titles": normalize_tags(item.get("alternative_titles")),
        "year": str(item.get("year") or "").strip(),
        "kind": explicit_kind(item) or "pelicula",
        "url": canonical_url(str(item.get("url") or "")),
        "wikipedia_url": canonical_url(str(item.get("wikipedia_url") or "")),
        "imdb_url": canonical_url(str(item.get("imdb_url") or "")),
        "filmaffinity_url": canonical_url(str(item.get("filmaffinity_url") or "")),
        "wikidata_id": str(item.get("wikidata_id") or "").strip().upper(),
    }
    return {key: value for key, value in identity.items() if value not in ("", [])}


def detected_work_identity(title: str, year: str, kind: str) -> dict[str, Any]:
    return work_identity({"title": title, "year": year, "kind": kind})


def work_identity_key(item: Mapping[str, Any]) -> str:
    wikidata = str(item.get("wikidata_id") or "").strip().upper()
    if wikidata:
        return f"wikidata:{wikidata}"
    urls = sorted(external_urls(item))
    if urls:
        return f"url:{urls[0]}"
    titles = title_match_keys_for_item(item)
    year = str(item.get("year") or "").strip()
    kind = explicit_kind(item) or "pelicula"
    seed = f"{titles[0] if titles else ''}|{year}|{kind}"
    return f"work:{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]}" if titles else ""


def identity_matches_item(identity: Mapping[str, Any], item: Mapping[str, Any]) -> bool:
    left_wikidata = str(identity.get("wikidata_id") or "").strip().upper()
    right_wikidata = str(item.get("wikidata_id") or "").strip().upper()
    if left_wikidata and left_wikidata == right_wikidata:
        return True
    if external_urls(identity) & external_urls(item):
        return True
    left_titles = set(title_match_keys_for_item(identity))
    right_titles = set(title_match_keys_for_item(item))
    left_year = str(identity.get("year") or "").strip()
    right_year = str(item.get("year") or "").strip()
    left_kind = explicit_kind(identity)
    right_kind = explicit_kind(item)
    return bool(
        left_titles
        and left_titles & right_titles
        and left_year
        and left_year == right_year
        and (not left_kind or not right_kind or left_kind == right_kind)
    )
