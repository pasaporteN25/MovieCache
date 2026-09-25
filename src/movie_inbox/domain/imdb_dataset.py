"""Pure parsing for IMDb's official non-commercial bulk TSV datasets.

Scope: [F1] in tareas.md. This module only turns one raw TSV line into a
structured row or `None` (header row / malformed line). It never touches the
real catalog, `metadata_sources`, or any merge logic — that authority/merge
decision belongs to [Q5].
"""

from __future__ import annotations

from typing import Any

IMDB_ATTRIBUTION_NOTICE = (
    "Information courtesy of IMDb (https://www.imdb.com). Used with permission."
)

_NULL = "\\N"
_TITLE_BASICS_COLUMNS = 9
_TITLE_AKAS_COLUMNS = 8
_TITLE_RATINGS_COLUMNS = 3


def _field(value: str) -> str | None:
    return None if value == _NULL else value


def _int_field(value: str) -> int | None:
    text = _field(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_title_basics_row(line: str) -> dict[str, Any] | None:
    columns = line.rstrip("\r\n").split("\t")
    if len(columns) != _TITLE_BASICS_COLUMNS or columns[0] == "tconst":
        return None
    (
        tconst,
        title_type,
        primary_title,
        original_title,
        is_adult,
        start_year,
        end_year,
        runtime_minutes,
        genres,
    ) = columns
    if not tconst:
        return None
    return {
        "tconst": tconst,
        "title_type": title_type,
        "primary_title": primary_title,
        "original_title": original_title,
        "is_adult": 1 if is_adult == "1" else 0,
        "start_year": _int_field(start_year),
        "end_year": _int_field(end_year),
        "runtime_minutes": _int_field(runtime_minutes),
        "genres": _field(genres),
    }


def parse_title_ratings_row(line: str) -> dict[str, Any] | None:
    columns = line.rstrip("\r\n").split("\t")
    if len(columns) != _TITLE_RATINGS_COLUMNS or columns[0] == "tconst":
        return None
    tconst, average_rating, num_votes = columns
    votes = _int_field(num_votes)
    if not tconst or votes is None:
        return None
    try:
        rating = float(average_rating)
    except ValueError:
        return None
    return {"tconst": tconst, "average_rating": rating, "num_votes": votes}


def parse_title_akas_row(line: str) -> dict[str, Any] | None:
    columns = line.rstrip("\r\n").split("\t")
    if len(columns) != _TITLE_AKAS_COLUMNS or columns[0] == "titleId":
        return None
    (
        title_id,
        ordering,
        title,
        region,
        language,
        types,
        attributes,
        is_original_title,
    ) = columns
    ordering_value = _int_field(ordering)
    if not title_id or ordering_value is None:
        return None
    return {
        "tconst": title_id,
        "ordering": ordering_value,
        "title": title,
        "region": _field(region),
        "language": _field(language),
        "types": _field(types),
        "attributes": _field(attributes),
        "is_original_title": _int_field(is_original_title),
    }


# --- [Q5] authority rules for the local index --------------------------------------

# `domain/normalization.py::normalize_kind()` has its own vocabulary and never says
# "no opinion": measured on 2026-09-07 it maps `tvMiniSeries`, `tvEpisode`, `videoGame`
# and outright garbage all to `pelicula`. Feeding IMDb's raw `title_type` through it
# would therefore mislabel works silently, so the translation is explicit here and a
# type outside the table contributes no `kind` at all.
_TITLE_TYPE_KINDS = {
    "movie": "pelicula",
    "tvmovie": "pelicula",
    "short": "pelicula",
    "tvshort": "pelicula",
    "tvspecial": "pelicula",
    "tvseries": "serie",
    "tvminiseries": "serie",
}

# Alternate titles are filtered by `region`, not `language`: verified during [Q5] that
# real rows for "Heat" carried no `language` at all and were only distinguishable by
# region. Restricted to the markets this catalogue actually reads in.
AKA_REGIONS = frozenset(
    {
        "AR",
        "AU",
        "BO",
        "CA",
        "CL",
        "CO",
        "CR",
        "CU",
        "DO",
        "EC",
        "ES",
        "GB",
        "GT",
        "HN",
        "IE",
        "MX",
        "NI",
        "NZ",
        "PA",
        "PE",
        "PR",
        "PY",
        "SV",
        "US",
        "UY",
        "VE",
        "XWW",
    }
)


def kind_from_title_type(title_type: Any) -> str:
    """Translate IMDb's `title_type` into this catalogue's `kind`.

    Returns "" for episodes, pilots, video games and anything unknown: a single
    episode must never decide the kind of a whole work, and guessing is worse
    than abstaining.
    """

    return _TITLE_TYPE_KINDS.get(str(title_type or "").strip().casefold(), "")


def dataset_akas(akas: Any) -> list[str]:
    """Alternate titles from index akas, filtered to the markets we read in."""

    titles: list[str] = []
    for entry in akas or ():
        title = str(getattr(entry, "title", "") or "").strip()
        region = str(getattr(entry, "region", "") or "").strip().upper()
        if title and region in AKA_REGIONS and title not in titles:
            titles.append(title)
    return titles


def dataset_metadata(result: Any) -> dict[str, Any]:
    """Map one index lookup onto exactly the fields [Q5] gives the local index.

    Deliberately narrow. The matrix assigns the index identity fragments,
    classification and structured data only: credits, images, descriptions and
    release dates stay with the sources that actually carry them, and
    `spanish_title`/`english_title` are excluded because the index exposes no
    per-language scalars to fill them with.
    """

    if result is None:
        return {}
    metadata: dict[str, Any] = {}
    original_title = str(getattr(result, "original_title", "") or "").strip()
    primary_title = str(getattr(result, "primary_title", "") or "").strip()
    if primary_title:
        metadata["title"] = primary_title
    if original_title:
        metadata["original_title"] = original_title
    aliases = dataset_akas(getattr(result, "akas", ()))
    if aliases:
        metadata["alternative_titles"] = aliases

    kind = kind_from_title_type(getattr(result, "title_type", ""))
    if kind:
        metadata["kind"] = kind
    start_year = getattr(result, "start_year", None)
    if isinstance(start_year, int) and not isinstance(start_year, bool) and start_year > 0:
        metadata["year"] = str(start_year)

    runtime = getattr(result, "runtime_minutes", None)
    if isinstance(runtime, int) and not isinstance(runtime, bool) and runtime > 0:
        metadata["duration_minutes"] = runtime
    genres = str(getattr(result, "genres", "") or "").strip()
    if genres:
        # Left as the raw comma string on purpose: merge_lists/normalize_tags
        # already split it, so no parsing is duplicated here.
        metadata["genres"] = genres
    return metadata
