from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from catalog_http_security import UnsafeRemoteUrl, open_public_url, validate_public_http_url


def resolver_for(address: str):
    def resolve(host: str, port: int, **_: object):
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
        return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]

    return resolve


class HttpSecurityTests(unittest.TestCase):
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

        with patch("catalog_http_security.build_opener", return_value=RedirectingOpener()):
            with self.assertRaises(UnsafeRemoteUrl):
                open_public_url("https://images.example.com/a.jpg", headers={}, timeout=1, resolver=resolver)


if __name__ == "__main__":
    unittest.main()
