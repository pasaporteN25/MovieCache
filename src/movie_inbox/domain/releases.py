"""Canonical release-date values with precision and provenance."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date
from typing import Any

RELEASE_DATE_PRECISIONS = {"year", "month", "day"}
RELEASE_DATE_FIELDS = {
    "date",
    "precision",
    "country",
    "release_type",
    "source",
    "source_url",
    "is_primary",
}


def normalize_release_dates(value: Any) -> list[dict[str, Any]]:
    rows = (
        value if isinstance(value, list) else [value] if isinstance(value, (str, Mapping)) else []
    )
    normalized: list[dict[str, Any]] = []
    positions: dict[tuple[str, str, str], int] = {}
    for raw_row in rows:
        row = (
            {"date": raw_row}
            if isinstance(raw_row, str)
            else dict(raw_row)
            if isinstance(raw_row, Mapping)
            else {}
        )
        release_date, precision = normalize_release_date_value(
            row.get("date"),
            str(row.get("precision") or ""),
        )
        if not release_date:
            continue
        normalized_row: dict[str, Any] = {
            "date": release_date,
            "precision": precision,
            "country": str(row.get("country") or "").strip(),
            "release_type": str(row.get("release_type") or "").strip(),
            "source": str(row.get("source") or "").strip(),
            "source_url": str(row.get("source_url") or "").strip(),
            "is_primary": bool(row.get("is_primary")),
        }
        key = (
            release_date,
            normalized_row["country"].casefold(),
            normalized_row["release_type"].casefold(),
        )
        if key in positions:
            existing = normalized[positions[key]]
            for field in ("country", "release_type", "source", "source_url"):
                existing[field] = existing[field] or normalized_row[field]
            existing["is_primary"] = existing["is_primary"] or normalized_row["is_primary"]
            continue
        positions[key] = len(normalized)
        normalized.append(normalized_row)

    primary_seen = False
    for row in normalized:
        if row["is_primary"] and not primary_seen:
            primary_seen = True
        else:
            row["is_primary"] = False
    if normalized and not primary_seen:
        normalized[0]["is_primary"] = True
    return normalized


def merge_release_dates(primary: Any, secondary: Any) -> list[dict[str, Any]]:
    return normalize_release_dates(
        [*normalize_release_dates(primary), *normalize_release_dates(secondary)]
    )


def primary_release_date(value: Any) -> dict[str, Any] | None:
    rows = normalize_release_dates(value)
    return next((row for row in rows if row["is_primary"]), rows[0] if rows else None)


def normalize_release_date_value(value: Any, precision: str = "") -> tuple[str, str]:
    raw = str(value or "").strip().lstrip("+")
    requested_precision = precision.strip().casefold()
    if requested_precision not in RELEASE_DATE_PRECISIONS:
        requested_precision = (
            "day"
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw)
            else ("month" if re.fullmatch(r"\d{4}-\d{2}", raw) else "year")
        )
    match = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", raw)
    if not match:
        return "", ""
    year, month, day = match.groups()
    if requested_precision == "year":
        return (year, "year") if 1800 <= int(year) <= 9999 else ("", "")
    if month is None or not 1 <= int(month) <= 12:
        return "", ""
    if requested_precision == "month":
        return f"{year}-{month}", "month"
    if day is None:
        return "", ""
    try:
        parsed = date(int(year), int(month), int(day))
    except ValueError:
        return "", ""
    return parsed.isoformat(), "day"
