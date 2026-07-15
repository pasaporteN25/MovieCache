#!/usr/bin/env python3
"""Security helpers for the local HTTP viewer and its image proxy."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError


MAX_REDIRECTS = 3
Resolver = Callable[..., list[tuple[object, ...]]]


class UnsafeRemoteUrl(ValueError):
    pass


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # type: ignore[no-untyped-def]
        return None


def validate_public_http_url(url: str, resolver: Resolver = socket.getaddrinfo) -> str:
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
        hostname = hostname_value.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise UnsafeRemoteUrl("Invalid remote hostname") from error
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
            raise UnsafeRemoteUrl("Private, loopback, link-local and reserved destinations are blocked")
    return parsed.geturl()


def open_public_url(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    resolver: Resolver = socket.getaddrinfo,
):
    opener = build_opener(NoRedirectHandler())
    current_url = validate_public_http_url(url, resolver)
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
            current_url = validate_public_http_url(urljoin(current_url, location), resolver)
    raise UnsafeRemoteUrl("Remote image redirect could not be resolved")

