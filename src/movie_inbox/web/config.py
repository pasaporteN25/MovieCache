"""Configuration shared by the local web server components."""

from __future__ import annotations

from dataclasses import dataclass


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
