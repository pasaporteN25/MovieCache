"""Validated image downloading and size-bounded on-disk cache."""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.security import open_public_url, validate_http_url


IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
}

IMAGE_CONTENT_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}

_CACHE_LOCK = threading.RLock()


@dataclass(frozen=True)
class ImageCacheInfo:
    path: Path
    files: int
    total_bytes: int
    max_bytes: int | None = None
    removed_files: int = 0
    removed_bytes: int = 0


def cached_image(config: ViewerConfig, image_url: str) -> tuple[bytes, str]:
    image_url = validate_http_url(image_url, config.image_allowed_hosts)
    cache_dir = Path(config.image_cache_dir)
    key = hashlib.sha256(image_url.encode("utf-8")).hexdigest()
    with _CACHE_LOCK:
        cached = _cached_path(cache_dir, key)
        if cached is None:
            legacy_key = hashlib.sha1(image_url.encode("utf-8"), usedforsecurity=False).hexdigest()
            legacy = _cached_path(cache_dir, legacy_key)
            if legacy:
                migrated = cache_dir / f"{key}{legacy.suffix.casefold()}"
                os.replace(legacy, migrated)
                cached = migrated
        if cached:
            body = cached.read_bytes()
            os.utime(cached, None)
            return body, image_content_type(cached.suffix)

    body, content_type = download_image(
        image_url,
        config.image_cache_max_bytes,
        config.image_allowed_hosts,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{key}{IMAGE_CONTENT_EXTENSIONS[content_type]}"
    with _CACHE_LOCK:
        existing = _cached_path(cache_dir, key)
        if existing:
            existing_body = existing.read_bytes()
            os.utime(existing, None)
            return existing_body, image_content_type(existing.suffix)
        _atomic_write(cache_path, body)
        prune_image_cache(cache_dir, config.image_cache_total_bytes, protected={cache_path})
    return body, content_type


def download_image(
    image_url: str,
    max_bytes: int,
    allowed_hosts: tuple[str, ...],
) -> tuple[bytes, str]:
    response = open_public_url(
        image_url,
        headers={
            "User-Agent": "MovieInboxViewer/0.2 (+local personal catalog)",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif",
        },
        timeout=10,
        allowed_hosts=allowed_hosts,
    )
    with response:
        content_type = response.headers.get_content_type().casefold()
        if content_type not in IMAGE_CONTENT_EXTENSIONS:
            raise ValueError("URL did not return a supported raster image")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("Image is too large")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("Image is too large")
        if not _matches_image_signature(body, content_type):
            raise ValueError("Image content does not match its declared type")
        return body, content_type


def image_content_type(suffix: str) -> str:
    return IMAGE_EXTENSIONS.get(suffix.casefold(), "application/octet-stream")


def image_cache_info(cache_dir: Path, max_bytes: int | None = None) -> ImageCacheInfo:
    cache_dir = Path(cache_dir)
    with _CACHE_LOCK:
        paths = _cache_files(cache_dir)
        sizes = [_file_size(path) for path in paths]
        return ImageCacheInfo(cache_dir, len(paths), sum(sizes), max_bytes)


def prune_image_cache(
    cache_dir: Path,
    max_bytes: int,
    protected: set[Path] | None = None,
) -> ImageCacheInfo:
    cache_dir = Path(cache_dir)
    protected_paths = {path.resolve() for path in (protected or set())}
    with _CACHE_LOCK:
        paths = _cache_files(cache_dir)
        total = sum(_file_size(path) for path in paths)
        removed_files = 0
        removed_bytes = 0
        for path in sorted(paths, key=_last_used):
            if total <= max_bytes:
                break
            if path.resolve() in protected_paths:
                continue
            size = _file_size(path)
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            total -= size
            removed_files += 1
            removed_bytes += size
        remaining = _cache_files(cache_dir)
        return ImageCacheInfo(
            cache_dir,
            len(remaining),
            sum(_file_size(path) for path in remaining),
            max_bytes,
            removed_files,
            removed_bytes,
        )


def clear_image_cache(cache_dir: Path) -> ImageCacheInfo:
    cache_dir = Path(cache_dir)
    with _CACHE_LOCK:
        paths = _cache_files(cache_dir)
        removed_files = 0
        removed_bytes = 0
        for path in paths:
            size = _file_size(path)
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            removed_files += 1
            removed_bytes += size
        return ImageCacheInfo(cache_dir, 0, 0, removed_files=removed_files, removed_bytes=removed_bytes)


def _cached_path(cache_dir: Path, key: str) -> Path | None:
    if not cache_dir.is_dir():
        return None
    return next(
        (
            path
            for suffix in IMAGE_EXTENSIONS
            if (path := cache_dir / f"{key}{suffix}").is_file()
        ),
        None,
    )


def _cache_files(cache_dir: Path) -> list[Path]:
    if not cache_dir.is_dir():
        return []
    return [path for path in cache_dir.iterdir() if path.is_file()]


def _atomic_write(path: Path, body: bytes) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass


def _matches_image_signature(body: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return body.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return body.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/gif":
        return body.startswith((b"GIF87a", b"GIF89a"))
    if content_type == "image/webp":
        return len(body) >= 12 and body.startswith(b"RIFF") and body[8:12] == b"WEBP"
    if content_type == "image/avif":
        return len(body) >= 12 and body[4:8] == b"ftyp" and any(
            brand in body[8:32] for brand in (b"avif", b"avis")
        )
    return False


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _last_used(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0
