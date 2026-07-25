"""Configuration shared by the local web server components."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_IMAGE_CACHE_TOTAL_BYTES = 512 * 1024 * 1024
DEFAULT_IMAGE_ALLOWED_HOSTS = (
    "upload.wikimedia.org",
    "m.media-amazon.com",
    "ia.media-imdb.com",
    "images.filmaffinity.com",
    "pics.filmaffinity.com",
)


@dataclass(frozen=True)
class ViewerConfig:
    patterns: list[str]
    title: str
    write_json: str
    image_cache: bool
    image_cache_dir: str
    image_cache_max_bytes: int
    port: int
    api_token: str
    host: str = "127.0.0.1"
    public_origin: str = ""
    forwarded_allow_ips: str = "127.0.0.1"
    image_cache_total_bytes: int = DEFAULT_IMAGE_CACHE_TOTAL_BYTES
    image_allowed_hosts: tuple[str, ...] = DEFAULT_IMAGE_ALLOWED_HOSTS
