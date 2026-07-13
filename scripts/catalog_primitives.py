#!/usr/bin/env python3
"""Shared scalar normalization rules for catalog data."""

from __future__ import annotations

from typing import Any


VALID_KINDS = ("pelicula", "serie", "anime", "documental")
VALID_STATUSES = ("to_watch", "watched")


def normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().casefold() in {"1", "true", "yes", "si", "s\u00ed"}


def normalize_kind(value: Any) -> str:
    text = str(value or "pelicula").strip().casefold()
    mapping = {
        "movie": "pelicula",
        "film": "pelicula",
        "pelicula": "pelicula",
        "pel\u00edcula": "pelicula",
        "series": "serie",
        "tvseries": "serie",
        "tv series": "serie",
        "episode": "serie",
        "tv episode": "serie",
        "serie": "serie",
        "anime": "anime",
        "documentary": "documental",
        "documental": "documental",
    }
    return mapping.get(text, "pelicula")


def normalize_status(value: Any) -> str:
    text = str(value or "to_watch").strip().casefold()
    return text if text in VALID_STATUSES else "to_watch"


def normalize_rating(value: Any) -> int:
    try:
        rating = int(float(str(value or 0).strip()))
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, rating))
