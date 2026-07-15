from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch


SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from movie_inbox.web.security import (
    InvalidPublicOrigin,
    UnsafeRemoteUrl,
    normalize_public_origin,
    open_public_url,
    validate_public_http_url,
    viewer_allowed_hosts,
    viewer_allowed_origins,
)


def resolver_for(address: str):
    def resolve(host: str, port: int, **_: object):
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
        return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]

    return resolve


class HttpSecurityTests(unittest.TestCase):
    def test_public_origin_is_normalized_for_proxy_validation(self) -> None:
        self.assertEqual(normalize_public_origin("HTTPS://Movies.Example.com:443/"), "https://movies.example.com")
        self.assertIn("movies.example.com", viewer_allowed_hosts("https://movies.example.com"))
        self.assertIn("https://movies.example.com", viewer_allowed_origins(8765, "https://movies.example.com"))
        with self.assertRaises(InvalidPublicOrigin):
            normalize_public_origin("https://movies.example.com/path")

    def test_public_destination_is_allowed(self) -> None:
        self.assertEqual(
            validate_public_http_url("https://images.example.com/poster.jpg", resolver_for("8.8.8.8")),
            "https://images.example.com/poster.jpg",
        )

    def test_private_and_nonstandard_destinations_are_blocked(self) -> None:
        for address in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "::1"):
            with self.subTest(address=address), self.assertRaises(UnsafeRemoteUrl):
                validate_public_http_url("https://images.example.com/poster.jpg", resolver_for(address))
        with self.assertRaises(UnsafeRemoteUrl):
            validate_public_http_url("https://images.example.com:8443/poster.jpg", resolver_for("8.8.8.8"))

    def test_redirect_target_is_validated_again(self) -> None:
        class RedirectingOpener:
            def open(self, request, timeout=0):
                raise HTTPError(
                    request.full_url,
                    302,
                    "Found",
                    {"Location": "http://127.0.0.1/private"},
                    None,
                )

        def resolver(host: str, port: int, **_: object):
            address = "127.0.0.1" if host == "127.0.0.1" else "8.8.8.8"
            return resolver_for(address)(host, port)

        with patch("movie_inbox.web.security.build_opener", return_value=RedirectingOpener()):
            with self.assertRaises(UnsafeRemoteUrl):
                open_public_url("https://images.example.com/a.jpg", headers={}, timeout=1, resolver=resolver)


if __name__ == "__main__":
    unittest.main()
