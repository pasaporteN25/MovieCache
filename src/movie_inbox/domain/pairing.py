"""Rules for pairing a phone with an account that already exists.

Pure domain: no I/O, no HTTP, no persistence.

ADR-0005, as amended on 2026-09-07, makes an account created on the web the only
way in. Pairing is therefore not a convenience on top of the device API -- it is
the front door, and the ticket that opens it is a bearer credential for a very
short window. Everything here exists to keep that window small and single-use.

The QR is scanned off the owner's own screen, which makes it a trustworthy
out-of-band channel. That is what lets it carry the instance's certificate
fingerprint: a phone can then trust a self-hosted certificate that no public CA
vouches for, without the application ever having to accept certificates blindly.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

# A pairing ticket is meant to be scanned off a screen that is in front of you
# right now. Minutes, not hours: a QR left open in a browser tab should stop
# working long before anyone walks past it.
PAIRING_TICKET_TTL_SECONDS = 5 * 60

# Tickets are kept after redemption only long enough to answer "was this already
# used?" honestly. Past this they are swept, and a replay simply finds nothing.
PAIRING_TICKET_RETENTION_SECONDS = 24 * 60 * 60

# The payload the QR carries. Deliberately tiny: a QR tops out at 2953 bytes and
# the catalogue never goes in it. The QR pairs; HTTPS transfers.
MAX_PAIRING_PAYLOAD_BYTES = 1024

# SHA-256 of a SubjectPublicKeyInfo, base64. 32 bytes -> 44 characters with one
# padding character. Same shape OkHttp and Chrome use for pin reporting.
_SPKI_PIN = re.compile(r"^[A-Za-z0-9+/]{43}=$")

# Label kept out of the payload builder so the derivation is impossible to
# change by accident: a different label yields a different public id, and the
# phone would think it is a different instance.
_INSTANCE_ID_LABEL = b"movie-inbox/instance-public-id/v1"


class PairingError(ValueError):
    """Raised when a pairing ticket or its payload is not usable."""


@dataclass(frozen=True)
class PairingTicket:
    """A one-time invitation for one device to adopt one account.

    Only ``token_hash`` is ever stored. The plaintext exists once, travels
    through the QR, and is never written down -- the same treatment sessions
    already get in `auth_service`.
    """

    token_hash: str
    user_id: str
    created_at: int
    expires_at: int
    redeemed_at: int = 0

    @property
    def redeemed(self) -> bool:
        return self.redeemed_at > 0

    def usable_at(self, now: int) -> bool:
        return not self.redeemed and self.expires_at > int(now)


def instance_public_id(instance_secret: str) -> str:
    """A stable identifier for this instance that is safe to put in a QR.

    Derived from the durable sync secret rather than stored separately, so an
    instance has exactly one identity and no second thing to keep in sync. The
    derivation is one-way: publishing the result tells an observer nothing about
    the secret, which is what makes reusing it here safe rather than sloppy.

    A phone uses it to tell "the instance I already know" from "a different one"
    before it has any session -- which is what makes re-pairing able to keep the
    local replica instead of starting over.
    """

    secret = str(instance_secret or "").encode("utf-8")
    if not secret:
        raise PairingError("An instance secret is required to derive a public id")
    return hmac.new(secret, _INSTANCE_ID_LABEL, hashlib.sha256).hexdigest()[:32]


def normalize_certificate_pin(value: Any) -> str:
    """Validate an SPKI pin, or return empty when none is configured.

    Empty is the normal case: an instance behind a publicly trusted certificate
    needs no pin, because the phone's own trust store already vouches for it.
    A malformed pin is not empty, though -- it is a misconfiguration that would
    silently leave the phone unable to connect, so it raises.
    """

    pin = str(value or "").strip()
    if not pin:
        return ""
    if not _SPKI_PIN.match(pin):
        raise PairingError("Certificate pin must be a base64 SHA-256 SPKI digest")
    try:
        decoded = base64.b64decode(pin, validate=True)
    except (binascii.Error, ValueError) as error:
        raise PairingError("Certificate pin is not valid base64") from error
    if len(decoded) != 32:
        raise PairingError("Certificate pin must decode to 32 bytes")
    return pin


# Where the SubjectPublicKeyInfo sits among the children of tbsCertificate, once
# the optional [0] EXPLICIT version has been skipped: serialNumber, signature,
# issuer, validity, subject, subjectPublicKeyInfo.
_SPKI_FIELD_INDEX = 5
_DER_CONTEXT_ZERO = 0xA0
_PEM_BEGIN = "-----BEGIN CERTIFICATE-----"
_PEM_END = "-----END CERTIFICATE-----"


def _first_pem_body(pem: str) -> str:
    """Base64 of the first certificate in a PEM file.

    The **first** matters: a `fullchain.pem` puts the leaf before the issuers,
    and the pin a phone checks is the leaf's.

    Text outside the armour is ignored rather than treated as an error, because
    `openssl x509 -text` prints a human-readable dump above the block and people
    do paste that. A file with no armour at all is taken as bare base64, which
    is what `-----`-stripped copies from a terminal look like.
    """

    start = pem.find(_PEM_BEGIN)
    if start >= 0:
        after = start + len(_PEM_BEGIN)
        end = pem.find(_PEM_END, after)
        pem = pem[after:end] if end >= 0 else pem[after:]
    return "".join(
        line.strip() for line in pem.splitlines() if line.strip() and not line.startswith("-----")
    )


def certificate_pin_from_pem(pem: Any) -> str:
    """Derive the SPKI pin a phone will check, from a PEM certificate.

    Written against the standard library rather than pulling in a certificate
    library, because the walk it needs is small and fully specified: an X.509
    ``Certificate`` is a SEQUENCE whose first element is ``tbsCertificate``, and
    ``subjectPublicKeyInfo`` is a fixed position inside that. The pin is the
    SHA-256 of that whole substructure, base64 -- the same value
    ``openssl x509 -pubkey | openssl pkey -pubin -outform der | openssl dgst
    -sha256 -binary | openssl enc -base64`` prints, which is what
    ``tests/test_device_pairing.py`` pins it against.

    Deriving it beats asking a person to paste it: that pipeline is four
    commands long, and a wrong pin fails as "my phone will not connect", with
    nothing on screen to say why.
    """

    body = _first_pem_body(str(pem or ""))
    if not body:
        raise PairingError("No PEM certificate found")
    try:
        certificate = base64.b64decode(body, validate=True)
    except (binascii.Error, ValueError) as error:
        raise PairingError("Certificate is not valid base64") from error
    digest = hashlib.sha256(_subject_public_key_info(certificate)).digest()
    return base64.b64encode(digest).decode("ascii")


def _subject_public_key_info(certificate: bytes) -> bytes:
    try:
        _, outer_start, outer_end = _der_value(certificate, 0)
        _, tbs_start, tbs_end = _der_value(certificate, outer_start)
        fields: list[tuple[int, int]] = []
        for tag, tlv_start, value_end in _der_children(certificate, tbs_start, tbs_end):
            # The version is optional and, when present, comes first. Skipping
            # it here is what keeps the field index below correct for both v1
            # and v3 certificates.
            if tag == _DER_CONTEXT_ZERO and not fields:
                continue
            fields.append((tlv_start, value_end))
            if len(fields) > _SPKI_FIELD_INDEX:
                break
        start, end = fields[_SPKI_FIELD_INDEX]
    except (IndexError, ValueError) as error:
        raise PairingError("Certificate is not a readable X.509 structure") from error
    if outer_end < tbs_end:
        raise PairingError("Certificate is not a readable X.509 structure")
    return certificate[start:end]


def _der_value(data: bytes, offset: int) -> tuple[int, int, int]:
    """Return (tag, value start, value end) of one DER element."""

    tag = data[offset]
    length_byte = data[offset + 1]
    if length_byte < 0x80:
        length, header = length_byte, 2
    else:
        count = length_byte & 0x7F
        if not 0 < count <= 4:
            raise ValueError("Unsupported DER length")
        length = int.from_bytes(data[offset + 2 : offset + 2 + count], "big")
        header = 2 + count
    start = offset + header
    end = start + length
    if end > len(data):
        raise ValueError("DER element runs past the end of the certificate")
    return tag, start, end


def _der_children(data: bytes, start: int, end: int) -> Any:
    offset = start
    while offset < end:
        tag, value_start, value_end = _der_value(data, offset)
        yield tag, offset, value_end
        offset = value_end


def normalize_pairing_origin(value: Any) -> str:
    """The origin the phone will talk to, HTTPS only.

    No plain HTTP, ever: the ticket travels in the request body and a session
    comes back, so an origin that is not encrypted would hand both to anyone on
    the network. `http://10.0.2.2` for the emulator is a client-side debug
    concession and has no business being advertised by a server.
    """

    origin = str(value or "").strip().rstrip("/")
    if not origin:
        raise PairingError("Pairing requires a public origin")
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.hostname:
        raise PairingError(f"Pairing origin must be an https:// origin: {origin!r}")
    if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise PairingError("Pairing origin must be a bare scheme, host and port")
    return origin


def pairing_payload(
    *,
    origin: Any,
    token: str,
    expires_at: int,
    instance_id: str,
    account_username: str,
    certificate_pin: Any = "",
) -> dict[str, Any]:
    """What the QR encodes. Four things, and none of them is the catalogue."""

    ticket = str(token or "")
    if not ticket:
        raise PairingError("A pairing payload needs a ticket")
    payload = {
        "v": 1,
        "origin": normalize_pairing_origin(origin),
        "ticket": ticket,
        "expires_at": int(expires_at),
        "instance_id": str(instance_id or ""),
        "account": str(account_username or ""),
    }
    pin = normalize_certificate_pin(certificate_pin)
    if pin:
        payload["certificate_pin"] = pin
    return payload


def payload_fits_in_a_qr(payload: Any) -> bool:
    """Whether the encoded payload stays inside what a QR can hold comfortably.

    Checked rather than assumed: the payload gains fields over time, and the
    failure mode of an oversized QR is one nobody can debug from a phone camera.
    """

    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    return len(encoded.encode("utf-8")) <= MAX_PAIRING_PAYLOAD_BYTES


__all__ = [
    "MAX_PAIRING_PAYLOAD_BYTES",
    "PAIRING_TICKET_RETENTION_SECONDS",
    "PAIRING_TICKET_TTL_SECONDS",
    "PairingError",
    "PairingTicket",
    "certificate_pin_from_pem",
    "instance_public_id",
    "normalize_certificate_pin",
    "normalize_pairing_origin",
    "pairing_payload",
    "payload_fits_in_a_qr",
]
