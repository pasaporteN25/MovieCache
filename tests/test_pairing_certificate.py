"""Deriving the certificate pin a phone checks, without a certificate library.

The two certificates below are real, throwaway and self-signed, generated with
OpenSSL 3.5.7 on 2026-09-09. Their expected pins were produced by the canonical
pipeline and pasted here, so these tests compare this project's parser against
OpenSSL rather than against itself:

    openssl x509 -in CERT -pubkey -noout \\
      | openssl pkey -pubin -outform der \\
      | openssl dgst -sha256 -binary | openssl enc -base64

Only the certificates are here. No private key was ever committed, and neither
key exists any more.

The pair is chosen to cover both DER length encodings: the P-256 key's
SubjectPublicKeyInfo is short enough for a single length byte, and the RSA-2048
one is not, which is where a hand-written parser is most likely to be wrong.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from movie_inbox.domain.pairing import (
    PairingError,
    certificate_pin_from_pem,
    normalize_certificate_pin,
)
from movie_inbox.web.server import resolve_pairing_pin

# P-256, CN=casa.local. SPKI fits a short-form DER length.
EC_CERTIFICATE = """-----BEGIN CERTIFICATE-----
MIIBlTCCATygAwIBAgIUScBmTJog26kQOeqdhK5fME0ISZgwCgYIKoZIzj0EAwIw
FTETMBEGA1UEAwwKY2FzYS5sb2NhbDAeFw0yNjA5MDkwNDMzMDlaFw0yNjEwMDkw
NDMzMDlaMBUxEzARBgNVBAMMCmNhc2EubG9jYWwwWTATBgcqhkjOPQIBBggqhkjO
PQMBBwNCAATY3AR3PXLUYKApdiIIV6oKFtlUqNkJScAaYIoE3ekGIC3pOw1TW6i0
dNK1wTkENlBSB8AKXwjTWoZSwZ2cMZ2Qo2owaDAdBgNVHQ4EFgQU65Bw1CdjbW6d
ADdH+196beXrZNgwHwYDVR0jBBgwFoAU65Bw1CdjbW6dADdH+196beXrZNgwDwYD
VR0TAQH/BAUwAwEB/zAVBgNVHREEDjAMggpjYXNhLmxvY2FsMAoGCCqGSM49BAMC
A0cAMEQCIANca0jJBrjiqfYzgufQTpAjs2mp44mT6U9cmoDg1tjlAiBXxP34rdwO
qOQxH+srr20r4Nn3YoCX0r0o2NJOSXuudw==
-----END CERTIFICATE-----"""
EC_PIN = "F8vo74MFdMBlfc3rAORbve09MS+A4TvZGHEhVA7vVWs="

# RSA-2048, CN=192.168.1.50 with an IP SAN: the shape a home network needs.
# Its SPKI needs a long-form DER length, which the EC one does not exercise.
RSA_CERTIFICATE = """-----BEGIN CERTIFICATE-----
MIIDIDCCAgigAwIBAgIUe1mlfJ1MKVZhtU8z7tc/0paGma4wDQYJKoZIhvcNAQEL
BQAwFzEVMBMGA1UEAwwMMTkyLjE2OC4xLjUwMB4XDTI2MDkwOTA0MzIzM1oXDTI4
MTIxMjA0MzIzM1owFzEVMBMGA1UEAwwMMTkyLjE2OC4xLjUwMIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuqUicb9zUrzObPgcqEJAIlMPgOsb2eFgSHQ+
M2C1GybykhvLiD438H8pqHsh698hshYWJ2CRN6sQgN7D8GgkmRwvKdqo6jrc8lP9
C6bZMLx6kSCXUHygqFbbBp5+5HxpWXwP2xyrjSZqgqPAtC1de7n+0J6Kosln22JL
xFJ9maxr+8kggVQauM+GIrjDmSqHSr6ftT01prEpfbogTilaPgh/XeYgD1wEApH5
vXEq3cBf5LwC68s8Y5hWoXJAYtLrDUU8whNQ6ZQvIW+hNTtKfP+a0mM33or76kHS
iwbXYmlPoYWDslAvqMBK+c7Xgg6l5x7MnkMvFUtzz45FKwkD1wIDAQABo2QwYjAd
BgNVHQ4EFgQUFnJDwQ0nthdgDta9km4dSoPM624wHwYDVR0jBBgwFoAUFnJDwQ0n
thdgDta9km4dSoPM624wDwYDVR0TAQH/BAUwAwEB/zAPBgNVHREECDAGhwTAqAEy
MA0GCSqGSIb3DQEBCwUAA4IBAQCxX4x9psLN1orKMIIMcE//EFwv0mAWVe/jk5hO
PfjgXAy0U+UMWqa9/gl2vfNyv9lw7V/qnvx2JZ3dbLj1ueMg/hjRrshNpUkqdjRy
1q5Yf7RFgSF1fpnLkVZWNRkaLdYHwsZbrlS0qcjhGejCeabP9Rezy/p/WC7JOA/0
/ErPu40Ids1/ZCgygOsHtcASeJXozWS+/WTFDSe6Dfjmg3g0PyNSs8HdzbvW+oBW
Q03ZLdYmexi1evnMtvI1mbClKpHQWB4NSZEUqTh4MWrdSxwGIYZTmJ/K2mrivS5O
ap4lQ15fNi4Kppxsqtihl+woUiDxq0nmNZxiMVSnan4ZWzp2
-----END CERTIFICATE-----"""
RSA_PIN = "v3AM6ArSTRz3oSt/9ca+8gwPTn5C43Xs5DdpUz+fOps="


class CertificatePinTests(unittest.TestCase):
    def test_it_agrees_with_openssl_on_both_der_length_encodings(self) -> None:
        self.assertEqual(certificate_pin_from_pem(EC_CERTIFICATE), EC_PIN)
        self.assertEqual(certificate_pin_from_pem(RSA_CERTIFICATE), RSA_PIN)

    def test_the_derived_pin_is_the_shape_the_payload_accepts(self) -> None:
        # A pin that derives correctly but fails validation would be found only
        # when a phone refused to connect, so the two are checked together.
        for pin in (EC_PIN, RSA_PIN):
            with self.subTest(pin=pin):
                self.assertEqual(normalize_certificate_pin(pin), pin)

    def test_surrounding_noise_and_missing_armour_do_not_change_the_answer(self) -> None:
        noisy = f"# comentario\n{EC_CERTIFICATE}\n\n"
        self.assertEqual(certificate_pin_from_pem(noisy), EC_PIN)
        bare = "\n".join(
            line for line in EC_CERTIFICATE.splitlines() if not line.startswith("-----")
        )
        self.assertEqual(certificate_pin_from_pem(bare), EC_PIN)

    def test_a_chain_file_pins_the_leaf_and_not_an_issuer(self) -> None:
        # A fullchain.pem puts the leaf first and its issuers after it. Pinning
        # an issuer would be silently wrong: the phone checks the leaf.
        chain = "\n".join([EC_CERTIFICATE, RSA_CERTIFICATE, ""])
        self.assertEqual(certificate_pin_from_pem(chain), EC_PIN)

    def test_the_openssl_text_dump_above_the_block_is_ignored(self) -> None:
        # `openssl x509 -text` prints a human-readable certificate above the
        # armour, and people paste the whole thing.
        dump = "\n".join(
            [
                "Certificate:",
                "    Data:",
                "        Version: 3 (0x2)",
                EC_CERTIFICATE,
                "",
            ]
        )
        self.assertEqual(certificate_pin_from_pem(dump), EC_PIN)

    def test_what_is_not_a_certificate_is_refused_rather_than_hashed(self) -> None:
        # Hashing whatever was handed over would produce a pin-shaped string
        # that no phone can ever match, which is the worst possible outcome:
        # it looks like it worked.
        for bad in ("", "   ", "-----BEGIN CERTIFICATE-----\n-----END CERTIFICATE-----"):
            with self.subTest(content=bad[:20]):
                with self.assertRaises(PairingError):
                    certificate_pin_from_pem(bad)
        with self.assertRaises(PairingError):
            certificate_pin_from_pem("no es base64 en absoluto ***")
        # Valid base64 that is not a certificate.
        with self.assertRaises(PairingError):
            certificate_pin_from_pem("aGVsbG8gd29ybGQ=")


class ResolvePairingPinTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.certificate = Path(self.temporary.name) / "lan.crt"
        self.certificate.write_text(RSA_CERTIFICATE, encoding="utf-8")

    def test_serving_tls_here_derives_the_pin_without_anyone_typing_it(self) -> None:
        self.assertEqual(resolve_pairing_pin("", str(self.certificate)), RSA_PIN)

    def test_an_explicit_pin_wins_because_a_proxy_holds_a_certificate_we_cannot_see(
        self,
    ) -> None:
        self.assertEqual(resolve_pairing_pin(EC_PIN, str(self.certificate)), EC_PIN)

    def test_no_certificate_and_no_pin_is_the_ordinary_case(self) -> None:
        # An instance behind a publicly trusted certificate needs neither.
        self.assertEqual(resolve_pairing_pin("", ""), "")

    def test_a_bad_pin_or_an_unreadable_certificate_fails_at_startup(self) -> None:
        # Loudly, and before anyone mints a QR nobody can use.
        with self.assertRaises(PairingError):
            resolve_pairing_pin("no-es-una-huella", "")
        with self.assertRaises(OSError):
            resolve_pairing_pin("", str(Path(self.temporary.name) / "no-existe.crt"))


if __name__ == "__main__":
    unittest.main()
