"""Configuration shared by the local web server components."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_IMAGE_CACHE_TOTAL_BYTES = 512 * 1024 * 1024
DEFAULT_IMAGE_CACHE_WARM_INTERVAL_SECONDS = 3.0
DEFAULT_SESSION_TTL_SECONDS = 14 * 24 * 60 * 60
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
    instance_db: str = ""
    member_catalog_dir: str = ""
    session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS
    host: str = "127.0.0.1"
    public_origin: str = ""
    forwarded_allow_ips: str = "127.0.0.1"
    image_cache_total_bytes: int = DEFAULT_IMAGE_CACHE_TOTAL_BYTES
    image_cache_warm: bool = True
    image_cache_warm_interval_seconds: float = DEFAULT_IMAGE_CACHE_WARM_INTERVAL_SECONDS
    image_allowed_hosts: tuple[str, ...] = DEFAULT_IMAGE_ALLOWED_HOSTS
    library_allowed_roots: tuple[str, ...] = ()
    library_scheduler_poll_seconds: float = 15.0
