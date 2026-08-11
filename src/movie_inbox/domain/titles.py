#!/usr/bin/env python3
"""Title cleanup helpers shared by import and enrichment workflows."""

from __future__ import annotations

import html
import re
import unicodedata


_MEDIA_PART_PATTERN = re.compile(r"\b(?:cd|disc|disk|part)[ ._-]?(\d{1,2})\b", re.IGNORECASE)
_DISC_PART_PATTERN = re.compile(r"\b(?:cd|disc|disk)\s*\d{1,2}\b", re.IGNORECASE)


def clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def clean_title(value: str) -> str:
    value = clean_whitespace(value)
    value = re.sub(r"\s+-\s+Wikipedia$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+-\s+IMDb$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+\(\d{4}\)\s+-\s+IMDb$", "", value, flags=re.IGNORECASE)
    return value


def clean_release_title(value: str) -> str:
    value = clean_title(value)
    value = re.sub(r"\.[a-z0-9]{2,5}$", "", value, flags=re.IGNORECASE)
    value = value.replace(".", " ").replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+(480p|576p|720p|1080p|2160p|4k|8k)\b.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\s+(bluray|blu ray|brrip|bdrip|webrip|web dl|webdl|hdrip|dvdrip|hdtv)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+(x264|x265|h264|h265|hevc|avc|aac|dts|ac3|yify|rarbg)\b.*$", "", value, flags=re.IGNORECASE)
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
    if year_match:
        value = value[: year_match.end()]
    return clean_whitespace(value)


def infer_year(*values: str) -> str:
    for value in values:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
        if match:
            return match.group(1)
    return ""


def looks_like_external_id(value: str) -> bool:
    text = str(value or "").strip()
    return bool(re.fullmatch(r"(tt|nm)\d{7,9}", text, flags=re.IGNORECASE)) or bool(
        re.fullmatch(r"film\d+", text, flags=re.IGNORECASE)
    )


def infer_kind_from_text(*values: str) -> str:
    marker_groups = {
        "anime": ("anime",),
        "documental": ("documentary", "documental"),
        "serie": (
            "television series",
            "tv series",
            "tv mini series",
            "tv miniseries",
            "miniseries",
            "mini series",
            "serie de television",
            "serie de tv",
            "serie televisiva",
            "tv show",
        ),
        "pelicula": ("feature film", "television film", "tv movie", "film", "movie", "pelicula"),
    }
    for value in values:
        text = unicodedata.normalize("NFKD", str(value or "").casefold())
        text = "".join(character for character in text if not unicodedata.combining(character))
        matches: list[tuple[int, int, str]] = []
        for priority, (kind, markers) in enumerate(marker_groups.items()):
            for marker in markers:
                index = text.find(marker)
                if index >= 0:
                    matches.append((index, priority, kind))
        if matches:
            return min(matches)[2]
    return ""


def detect_media_part(value: str) -> str:
    match = _MEDIA_PART_PATTERN.search(str(value or ""))
    return match.group(1) if match else ""


def strip_disc_part_marker(value: str) -> str:
    """Remove physical-disc markers without rewriting legitimate `Part 2` titles."""
    return clean_whitespace(_DISC_PART_PATTERN.sub(" ", str(value or "")))
