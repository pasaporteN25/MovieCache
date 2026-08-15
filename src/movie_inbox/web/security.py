#!/usr/bin/env python3
"""Security helpers for the local HTTP viewer and its image proxy."""

from __future__ import annotations

import ipaddress
import socket
import threading
import time
from collections import deque
from collections.abc import Callable, Collection
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_REDIRECTS = 3
Resolver = Callable[..., list[tuple[object, ...]]]


class UnsafeRemoteUrl(ValueError):
    pass


class InvalidPublicOrigin(ValueError):
    pass


class LoginAttemptLimiter:
    """Small in-memory limiter for a single-process self-hosted login."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 5 * 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max(1, max_failures)
        self.window_seconds = max(1, window_seconds)
        self.clock = clock
        self._attempts: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        now = self.clock()
        with self._lock:
            attempts = self._active_attempts(key, now)
            if len(attempts) < self.max_failures:
                return 0
            return max(1, int(self.window_seconds - (now - attempts[0])))

    def record_failure(self, key: str) -> None:
        now = self.clock()
        with self._lock:
            attempts = self._active_attempts(key, now)
            attempts.append(now)

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def _active_attempts(self, key: str, now: float) -> deque[float]:
        attempts = self._attempts.setdefault(key, deque())
        cutoff = now - self.window_seconds
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if not attempts:
            self._attempts[key] = attempts
        return attempts


def normalize_public_origin(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        scheme = parsed.scheme.casefold()
        hostname_value = parsed.hostname or ""
        port = parsed.port
    except ValueError as error:
        raise InvalidPublicOrigin("Malformed public origin") from error
    if scheme not in {"http", "https"} or not hostname_value:
        raise InvalidPublicOrigin("Public origin must use http:// or https://")
    if parsed.username or parsed.password:
        raise InvalidPublicOrigin("Public origin cannot contain credentials")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise InvalidPublicOrigin("Public origin cannot contain a path, query or fragment")
    try:
        hostname = hostname_value.encode("idna").decode("ascii").casefold().rstrip(".")
    except UnicodeError as error:
        raise InvalidPublicOrigin("Invalid public origin hostname") from error
    authority = f"[{hostname}]" if ":" in hostname else hostname
    default_port = 443 if scheme == "https" else 80
    if port and port != default_port:
        authority = f"{authority}:{port}"
    return f"{scheme}://{authority}"


def viewer_allowed_origins(port: int, public_origin: str = "") -> set[str]:
    origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    normalized = normalize_public_origin(public_origin)
    if normalized:
        origins.add(normalized)
    return {origin.casefold() for origin in origins}


def viewer_allowed_hosts(public_origin: str = "") -> list[str]:
    hosts = {"127.0.0.1", "localhost"}
    normalized = normalize_public_origin(public_origin)
    if normalized:
        hostname = urlparse(normalized).hostname
        if hostname:
            hosts.add(hostname.casefold())
    return sorted(hosts)


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # type: ignore[no-untyped-def]
        return None


def validate_public_http_url(
    url: str,
    resolver: Resolver = socket.getaddrinfo,
    allowed_hosts: Collection[str] | None = None,
) -> str:
    validated_url = validate_http_url(url, allowed_hosts)
    parsed = urlparse(validated_url)
    hostname = (parsed.hostname or "").encode("idna").decode("ascii").casefold().rstrip(".")
    port = parsed.port or (443 if parsed.scheme.casefold() == "https" else 80)
    try:
        addresses = resolver(hostname, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise UnsafeRemoteUrl("Remote hostname could not be resolved") from error
    if not addresses:
        raise UnsafeRemoteUrl("Remote hostname did not resolve")
    for address in addresses:
        sockaddr = address[4]
        ip_text = str(sockaddr[0]).split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError as error:
            raise UnsafeRemoteUrl("Remote hostname resolved to an invalid address") from error
        if not ip.is_global:
            raise UnsafeRemoteUrl(
                "Private, loopback, link-local and reserved destinations are blocked"
            )
    return validated_url


def validate_http_url(url: str, allowed_hosts: Collection[str] | None = None) -> str:
    try:
        parsed = urlparse(str(url or "").strip())
        scheme = parsed.scheme.lower()
        hostname_value = parsed.hostname or ""
    except ValueError as error:
        raise UnsafeRemoteUrl("Malformed remote URL") from error
    if scheme not in {"http", "https"} or not hostname_value:
        raise UnsafeRemoteUrl("Only public HTTP(S) URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeRemoteUrl("Credentials in remote URLs are not allowed")
    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as error:
        raise UnsafeRemoteUrl("Invalid remote URL port") from error
    if port not in {80, 443}:
        raise UnsafeRemoteUrl("Only standard HTTP(S) ports are allowed")

    try:
        hostname = hostname_value.encode("idna").decode("ascii").casefold().rstrip(".")
    except UnicodeError as error:
        raise UnsafeRemoteUrl("Invalid remote hostname") from error
    if allowed_hosts is not None:
        try:
            normalized_allowed = {
                str(host).strip().encode("idna").decode("ascii").casefold().rstrip(".")
                for host in allowed_hosts
                if str(host).strip()
            }
        except UnicodeError as error:
            raise UnsafeRemoteUrl("Invalid image allowlist hostname") from error
        if hostname not in normalized_allowed:
            raise UnsafeRemoteUrl("Remote image host is not allowed")
    return parsed.geturl()


def open_public_url(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    resolver: Resolver = socket.getaddrinfo,
    allowed_hosts: Collection[str] | None = None,
):
    opener = build_opener(NoRedirectHandler())
    current_url = validate_public_http_url(url, resolver, allowed_hosts)
    for redirect_count in range(MAX_REDIRECTS + 1):
        request = Request(current_url, headers=headers)
        try:
            return opener.open(request, timeout=timeout)
        except HTTPError as error:
            if error.code not in {301, 302, 303, 307, 308}:
                error.close()
                raise
            location = error.headers.get("Location")
            error.close()
            if not location or redirect_count >= MAX_REDIRECTS:
                raise UnsafeRemoteUrl("Remote image redirected too many times") from error
            current_url = validate_public_http_url(
                urljoin(current_url, location), resolver, allowed_hosts
            )
    raise UnsafeRemoteUrl("Remote image redirect could not be resolved")
