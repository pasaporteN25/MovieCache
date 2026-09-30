"""[U7 B] Rules for a work's two images: candidates, identity crosswalk, fill-only.

Contract: `docs/analisis/u7b-contrato-imagenes-2026-09-26.md` (option A, owner
decision 2026-09-26). The two scalars `page_image` and `backdrop_image` stay the
selection; nothing here adds a stored gallery. Everything is pure: the network
answers arrive already parsed, and the item is a plain mapping.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import asdict, dataclass
from typing import Any

from movie_inbox.domain.image_coverage import image_asset_key
from movie_inbox.domain.metadata import normalize_locked_fields, normalize_metadata_sources
from movie_inbox.domain.normalization import normalize_kind

POSTER = "poster"
BACKDROP = "backdrop"
ROLE_FIELDS = {POSTER: "page_image", BACKDROP: "backdrop_image"}
MAX_CANDIDATES_PER_ROLE = 8

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
_ROLE_SIZES = {POSTER: "w500", BACKDROP: "w780"}
_TMDB_FILE_PATH = re.compile(r"/[A-Za-z0-9._-]+\.(?:jpe?g|png|webp)")
# Posters read best in the viewer's language; backdrops read best with no text.
_LANGUAGE_RANK = {
    POSTER: {"es": 0, "en": 1, None: 2},
    BACKDROP: {None: 0, "es": 1, "en": 2},
}

ACCEPTED = "accepted"
NO_RESULT = "no_result"
AMBIGUOUS = "ambiguous"
KIND_MISMATCH = "kind_mismatch"
YEAR_MISMATCH = "year_mismatch"
NO_YEAR = "no_year"
YEAR_TOLERANCE = 1


class ImageSourceUnavailable(Exception):
    """The image source could not answer now: no credential, down, or limiting."""

    def __init__(self, message: str = "", *, rate_limited: bool = False) -> None:
        super().__init__(message or "image source unavailable")
        self.rate_limited = rate_limited


@dataclass(frozen=True)
class ImageCandidate:
    role: str
    url: str
    key: str
    width: int
    height: int
    language: str | None
    votes: int
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tmdb_image_candidates(images: Mapping[str, Any]) -> list[ImageCandidate]:
    """TMDb's `/images` answer as ordered candidates, one per picture.

    Stable order: language rank for the role, then votes, score and width. Two
    rows naming the same file collapse into one, and each role keeps at most
    `MAX_CANDIDATES_PER_ROLE`.
    """

    candidates: list[ImageCandidate] = []
    for role, key in ((BACKDROP, "backdrops"), (POSTER, "posters")):
        rows = images.get(key) if isinstance(images, Mapping) else None
        parsed: list[ImageCandidate] = []
        seen: set[str] = set()
        for row in rows if isinstance(rows, list) else []:
            candidate = _tmdb_candidate(role, row)
            if candidate is None or candidate.key in seen:
                continue
            seen.add(candidate.key)
            parsed.append(candidate)
        ranks = _LANGUAGE_RANK[role]
        parsed.sort(
            key=lambda item: (
                ranks.get(item.language, len(ranks)),
                -item.votes,
                -item.score,
                -item.width,
            )
        )
        candidates.extend(parsed[:MAX_CANDIDATES_PER_ROLE])
    return candidates


def _tmdb_candidate(role: str, row: Any) -> ImageCandidate | None:
    if not isinstance(row, Mapping):
        return None
    path = str(row.get("file_path") or "").strip()
    if not _TMDB_FILE_PATH.fullmatch(path):
        return None
    url = f"{TMDB_IMAGE_BASE_URL}/{_ROLE_SIZES[role]}{path}"
    language = str(row.get("iso_639_1") or "").strip().casefold() or None
    return ImageCandidate(
        role=role,
        url=url,
        key=image_asset_key(url),
        width=_non_negative_int(row.get("width")),
        height=_non_negative_int(row.get("height")),
        language=language,
        votes=_non_negative_int(row.get("vote_count")),
        score=round(_non_negative_float(row.get("vote_average")), 2),
    )


@dataclass(frozen=True)
class TmdbMatch:
    """One work TMDb names for an external id, reduced to what the rule checks."""

    media_type: str
    tmdb_id: str
    year: str


@dataclass(frozen=True)
class CrosswalkDecision:
    status: str
    match: TmdbMatch | None = None

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED and self.match is not None


def crosswalk_decision(item: Mapping[str, Any], matches: Iterable[TmdbMatch]) -> CrosswalkDecision:
    """Whether an id-only translation to TMDb may be written without review.

    Invariant 3: a doubtful match is a human decision. The translation is kept
    only with exactly one result whose type fits the work's kind and whose year
    is within one of the work's; everything else goes to Curaduría.
    """

    rows = [match for match in matches if match.tmdb_id and match.media_type in {"movie", "tv"}]
    if not rows:
        return CrosswalkDecision(NO_RESULT)
    if len({(match.media_type, match.tmdb_id) for match in rows}) > 1:
        return CrosswalkDecision(AMBIGUOUS)
    match = rows[0]
    if match.media_type not in _media_types_for(item.get("kind")):
        return CrosswalkDecision(KIND_MISMATCH, match)
    item_year = _year(item.get("year"))
    if item_year is None:
        return CrosswalkDecision(NO_YEAR, match)
    match_year = _year(match.year)
    if match_year is None or abs(match_year - item_year) > YEAR_TOLERANCE:
        return CrosswalkDecision(YEAR_MISMATCH, match)
    return CrosswalkDecision(ACCEPTED, match)


def _media_types_for(kind: Any) -> set[str]:
    normalized = normalize_kind(kind)
    if normalized == "serie":
        return {"tv"}
    if normalized == "anime":
        return {"movie", "tv"}
    return {"movie"}


def tmdb_public_url(media_type: str, tmdb_id: str) -> str:
    return f"https://www.themoviedb.org/{media_type}/{tmdb_id}"


@dataclass
class FillResult:
    filled: list[str]
    kept: list[str]
    skipped_locked: list[str]

    def to_dict(self) -> dict[str, list[str]]:
        return asdict(self)


def fill_empty_fields(
    item: MutableMapping[str, Any],
    values: Mapping[str, str],
    record: Mapping[str, Any],
) -> FillResult:
    """Write `values` only into empty, unlocked fields, with their provenance.

    Invariant 5: a locked field is never touched, and a value already present --
    manual or from another source -- is never replaced. `record` is the
    provenance entry every written field receives.
    """

    locked = set(normalize_locked_fields(item.get("locked_fields")))
    sources = normalize_metadata_sources(item.get("metadata_sources"))
    result = FillResult([], [], [])
    for field, value in values.items():
        text = str(value or "").strip()
        if not text:
            continue
        if field in locked:
            result.skipped_locked.append(field)
        elif str(item.get(field) or "").strip():
            result.kept.append(field)
        else:
            item[field] = text
            sources[field] = dict(record)
            result.filled.append(field)
    if result.filled:
        item["metadata_sources"] = sources
    return result


def missing_image_fields(item: Mapping[str, Any]) -> list[str]:
    """Image fields a fill could still write: empty and not locked."""

    locked = set(normalize_locked_fields(item.get("locked_fields")))
    return [
        field
        for field in ROLE_FIELDS.values()
        if field not in locked and not str(item.get(field) or "").strip()
    ]


def best_images(candidates: Iterable[ImageCandidate]) -> dict[str, str]:
    """The first candidate of each role, keyed by the field it would fill."""

    chosen: dict[str, str] = {}
    for candidate in candidates:
        chosen.setdefault(ROLE_FIELDS[candidate.role], candidate.url)
    return chosen


def _year(value: Any) -> int | None:
    match = re.match(r"^\s*(\d{4})", str(value or ""))
    return int(match.group(1)) if match else None


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _non_negative_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0
