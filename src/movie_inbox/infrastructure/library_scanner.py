"""Filesystem scanner shared by the managed service and legacy CLI."""

from __future__ import annotations

import hashlib
import os
import re
import stat as stat_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from movie_inbox.domain.titles import detect_media_part, strip_disc_part_marker


DEFAULT_EXTENSIONS = {
    ".3g2", ".3gp", ".asf", ".avi", ".divx", ".flv", ".m2ts", ".m4v",
    ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".mts", ".ogm", ".ogv",
    ".rmvb", ".ts", ".vob", ".webm", ".wmv",
}
DEFAULT_EXCLUDED_DIRS = {
    "$recycle.bin", "system volume information", ".catalog-cache", ".catalog-state",
    "extra", "extras", "sample", "samples",
}
SAMPLE_BYTES = 128 * 1024


class FilesystemScanError(RuntimeError):
    """Raised when a configured library cannot be scanned safely."""


def scan_media_files(
    root: Path,
    previous: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    extensions: set[str] | None = None,
    excluded_dirs: set[str] | None = None,
    scanned_at: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    resolved_root = root.resolve()
    if not resolved_root.exists() or not resolved_root.is_dir():
        raise FilesystemScanError(f"Library is offline or missing: {resolved_root}")
    if _is_link(resolved_root):
        raise FilesystemScanError("Managed library root cannot be a symbolic link or junction")

    allowed_extensions = normalize_extensions(extensions or DEFAULT_EXTENSIONS)
    excluded = DEFAULT_EXCLUDED_DIRS | normalize_excluded_dirs(excluded_dirs)
    prior = previous or {}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    def on_error(error: OSError) -> None:
        errors.append(str(error))

    for current, directories, files in os.walk(resolved_root, onerror=on_error, followlinks=False):
        current_path = Path(current)
        safe_directories: list[str] = []
        for name in directories:
            child = current_path / name
            if name.casefold() in excluded or _is_link(child):
                continue
            safe_directories.append(name)
        directories[:] = safe_directories
        for name in files:
            path = current_path / name
            if path.suffix.casefold() not in allowed_extensions or _is_link(path):
                continue
            try:
                stat = path.stat()
                if not stat_module.S_ISREG(stat.st_mode):
                    continue
                relative_path = path.relative_to(resolved_root).as_posix()
                old = prior.get(relative_path, {})
                unchanged = (
                    int(old.get("size_bytes") or -1) == stat.st_size
                    and int(old.get("modified_ns") or -1) == stat.st_mtime_ns
                    and bool(old.get("fingerprint"))
                )
                fingerprint = str(old.get("fingerprint")) if unchanged else sampled_fingerprint(path, stat.st_size)
                title, year, kind = parse_release_name(name)
                rows.append(
                    {
                        "relative_path": relative_path,
                        "name": name,
                        "size_bytes": stat.st_size,
                        "modified_ns": stat.st_mtime_ns,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                        "fingerprint": fingerprint,
                        "last_seen_at": int(scanned_at),
                        "title": title,
                        "year": year,
                        "kind": kind,
                        "part": detect_part(name),
                    }
                )
            except OSError as error:
                errors.append(f"{path}: {error}")
    rows.sort(key=lambda row: str(row.get("relative_path") or "").casefold())
    return rows, errors


def sampled_fingerprint(path: Path, size: int) -> str:
    digest = hashlib.sha256()
    digest.update(str(size).encode("ascii"))
    with path.open("rb") as handle:
        digest.update(handle.read(SAMPLE_BYTES))
        if size > SAMPLE_BYTES:
            handle.seek(max(0, size - SAMPLE_BYTES))
            digest.update(handle.read(SAMPLE_BYTES))
    return digest.hexdigest()


def parse_release_name(name: str) -> tuple[str, str, str]:
    value = Path(name).stem
    kind = "serie" if re.search(r"\bS\d{1,2}(?:E\d{1,3})?\b", value, re.IGNORECASE) else "pelicula"
    value = value.replace(".", " ").replace("_", " ").replace("-", " ")
    value = strip_disc_part_marker(value)
    value = re.sub(r"[\[\]{}]+", " ", value)
    value = re.sub(r"\bS\d{1,2}(?:E\d{1,3}(?:E\d{1,3})*)?\b.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\b(480p|576p|720p|1080p|2160p|4k|8k|bluray|blu ray|brrip|bdrip|"
        r"webrip|web dl|webdl|hdrip|dvdrip|hdtv|remux|x264|x265|h264|h265|"
        r"hevc|avc|aac|dts|ac3|yify|rarbg)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+", " ", value).strip()
    year_matches = list(re.finditer(r"\b(19\d{2}|20\d{2})\b", value))
    year = ""
    if year_matches and value != year_matches[-1].group(1):
        match = year_matches[-1]
        year = match.group(1)
        value = f"{value[:match.start()]} {value[match.end():]}".strip()
    title = re.sub(r"\s+", " ", value).strip() or Path(name).stem
    return title, year, kind


def detect_part(name: str) -> str:
    return detect_media_part(name)


def normalize_extensions(values: Any) -> set[str]:
    if isinstance(values, str):
        values = values.split(",")
    rows = values if isinstance(values, (list, tuple, set)) else DEFAULT_EXTENSIONS
    return {
        extension if extension.startswith(".") else f".{extension}"
        for value in rows
        if (extension := str(value).strip().casefold())
    }


def normalize_excluded_dirs(values: Any) -> set[str]:
    if isinstance(values, str):
        values = values.split(",")
    rows = values if isinstance(values, (list, tuple, set)) else DEFAULT_EXCLUDED_DIRS
    return {str(value).strip().casefold() for value in rows if str(value).strip()}


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
    except OSError:
        return True
