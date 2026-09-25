"""[X1.1]: recompute docs/briefs/pairing-certificate-v1-vectors.json.

The vectors are a client-portable slice of what tests/test_pairing_certificate.py
and PairingPayloadTests (tests/test_device_pairing.py) already cover against the
server's own functions. This suite proves the JSON matches those functions today,
so a server change that would change what a phone accepts fails here first.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from movie_inbox.domain.pairing import (
    certificate_pin_from_pem,
    pairing_payload,
    payload_fits_in_a_qr,
)

VECTORS = (
    Path(__file__).resolve().parents[1] / "docs" / "briefs" / "pairing-certificate-v1-vectors.json"
)


class PairingCertificateVectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vectors: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_the_documented_limit_is_the_domain_module_s(self) -> None:
        from movie_inbox.domain.pairing import MAX_PAIRING_PAYLOAD_BYTES

        self.assertEqual(self.vectors["max_payload_bytes"], MAX_PAIRING_PAYLOAD_BYTES)

    def test_certificate_pins(self) -> None:
        for case in self.vectors["certificates"]:
            with self.subTest(certificate=case["label"]):
                self.assertEqual(certificate_pin_from_pem(case["pem"]), case["spki_pin"])

    def test_qr_payloads(self) -> None:
        for case in self.vectors["qr_payloads"]:
            with self.subTest(payload=case["label"]):
                raw = dict(case["input"])
                if "token_length" in raw:
                    raw["token"] = "x" * raw.pop("token_length")
                payload = pairing_payload(
                    origin=raw["origin"],
                    token=raw["token"],
                    expires_at=raw["expires_at"],
                    instance_id=raw["instance_id"],
                    account_username=raw["account_username"],
                    certificate_pin=raw.get("certificate_pin", ""),
                )
                expect = case["expect"]
                for field, value in expect.get("fields", {}).items():
                    self.assertEqual(payload.get(field), value)
                for field in expect.get("absent_fields", ()):
                    self.assertNotIn(field, payload)
                self.assertEqual(payload_fits_in_a_qr(payload), expect["fits_in_qr"])


if __name__ == "__main__":
    unittest.main()
