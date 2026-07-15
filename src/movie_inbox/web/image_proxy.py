"""Validated image downloading and bounded on-disk cache."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

from movie_inbox.web.config import ViewerConfig
from movie_inbox.web.security import open_public_url, validate_public_http_url


IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}

IMAGE_CONTENT_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
}


def cached_image(config: ViewerConfig, image_url: str) -> tuple[bytes, str]:
    image_url = validate_public_http_url(image_url)
    parsed = urlparse(image_url)
    cache_dir = Path(config.image_cache_dir)
    key = hashlib.sha1(image_url.encode("utf-8")).hexdigest()
    cached = next((path for path in cache_dir.glob(f"{key}.*") if path.is_file()), None) if cache_dir.exists() else None
    if cached:
        return cached.read_bytes(), image_content_type(cached.suffix)

    body, content_type = download_image(image_url, config.image_cache_max_bytes)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{key}{image_extension(parsed.path, content_type)}"
    cache_path.write_bytes(body)
    return body, content_type


def download_image(image_url: str, max_bytes: int) -> tuple[bytes, str]:
    response = open_public_url(
        image_url,
        headers={
            "User-Agent": "MovieInboxViewer/0.2 (+local personal catalog)",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        },
        timeout=10,
    )
    with response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            raise ValueError("URL did not return an image")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("Image is too large")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("Image is too large")
        return body, content_type


def image_extension(path: str, content_type: str) -> str:
    suffix = Path(urlparse(path).path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return ".jpg" if suffix == ".jpeg" else suffix
    return IMAGE_CONTENT_EXTENSIONS.get(content_type, ".img")


def image_content_type(suffix: str) -> str:
    return IMAGE_EXTENSIONS.get(suffix.lower(), "application/octet-stream")

