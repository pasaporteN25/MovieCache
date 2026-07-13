#!/usr/bin/env python3
"""Title cleanup helpers shared by import and enrichment workflows."""

from __future__ import annotations

import html
import re


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
