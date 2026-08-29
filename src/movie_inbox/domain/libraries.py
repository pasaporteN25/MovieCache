"""Managed media library and shared availability models."""

from __future__ import annotations

import fnmatch
import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

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
MAX_EXCLUSION_PATTERN_LENGTH = 255
MAX_EXCLUSION_RULES_PER_LIBRARY = 50


class LibraryValidationError(ValueError):
    """Raised when managed library data is invalid."""


class ExclusionPatternError(LibraryValidationError):
    """Raised when a [L1] per-library exclusion pattern is invalid.

    `reason` is a stable code (never the raw message) so callers -- the HTTP
    layer in particular -- can report exactly which pattern failed and why,
    rather than collapsing every failure to one string."""

    def __init__(self, pattern: str, reason: str) -> None:
        self.pattern = pattern
        self.reason = reason
        super().__init__(f"Invalid exclusion pattern {pattern!r}: {reason}")


class ExclusionRulesInvalid(LibraryValidationError):
    """Raised when one or more patterns in a replace-the-whole-set request
    are invalid. Carries every failing (pattern, reason) pair, not just the
    first -- nothing is saved (see application/library_service.py's
    set_exclusion_rules), so the caller should see every problem at once
    rather than fixing one and re-submitting to discover the next."""

    def __init__(self, errors: list[ExclusionPatternError]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} invalid exclusion pattern(s)")


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
    exclusion_patterns: tuple[str, ...] = ()


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
    newly_excluded: tuple[Mapping[str, Any], ...] = ()


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


def validate_exclusion_pattern(value: Any) -> str:
    """[L1] tareas.md: a per-library exclusion pattern, matched against a
    single directory name via fnmatch (never a full path or a general
    regex -- fnmatch.translate() never emits nested quantifiers, so this
    can't suffer the catastrophic-backtracking a user-supplied regex
    could). Returns the cleaned pattern; never compiles or matches
    anything itself."""
    pattern = unicodedata.normalize("NFC", str(value or "")).strip()
    if not pattern:
        raise ExclusionPatternError(pattern, "empty")
    if len(pattern) > MAX_EXCLUSION_PATTERN_LENGTH:
        raise ExclusionPatternError(pattern, "too_long")
    if "/" in pattern or "\\" in pattern:
        # The scanner hook only ever sees a bare directory name (see
        # matches_excluded_pattern below) -- a pattern with a separator
        # would silently never match anything, not a path-traversal risk
        # (nothing here builds or opens a filesystem path from this string).
        raise ExclusionPatternError(pattern, "has_path_separator")
    if pattern.strip("*") == "":
        raise ExclusionPatternError(pattern, "excludes_everything")
    return pattern


def matches_excluded_pattern(name: str, patterns: Iterable[str]) -> bool:
    normalized_name = unicodedata.normalize("NFC", name).casefold()
    return any(
        fnmatch.fnmatchcase(normalized_name, unicodedata.normalize("NFC", pattern).casefold())
        for pattern in patterns
    )


def path_matches_excluded_pattern(relative_path: str, patterns: Iterable[str]) -> bool:
    """Whether any directory component of `relative_path` (as produced by
    infrastructure/library_scanner.py's `path.relative_to(root).as_posix()`,
    always forward-slash) would be excluded by `patterns` -- used to tell
    "this previously-tracked file just fell under a new exclusion rule"
    apart from "this file was actually deleted", never to open or validate
    the path itself."""
    patterns = tuple(patterns)
    if not patterns:
        return False
    parts = PurePosixPath(str(relative_path or "")).parts[:-1]
    return any(matches_excluded_pattern(part, patterns) for part in parts)


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
