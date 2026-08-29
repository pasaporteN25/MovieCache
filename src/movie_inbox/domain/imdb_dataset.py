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
