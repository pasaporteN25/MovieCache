"""Rendering a QR server side, for the device pairing ticket.

Lives in `infrastructure/` because it is a rendering concern with a third-party
dependency, and `domain/` stays free of both.

Why the server draws it at all: the payload is a bearer credential with a
five-minute life. Drawing it in the browser would mean shipping an encoder and
handing the ticket to more code than necessary; serving it from a GET URL would
put that credential somewhere it can be logged, cached or shared. A data URI in
the response of the same POST that minted the ticket keeps it in one place.
"""

from __future__ import annotations

import segno

# Medium recovery: about 15% of the code can be obscured and still read. Enough
# for a screen with a reflection on it, without the density that a higher level
# would add -- and density is what makes a phone camera give up.
_ERROR_CORRECTION = "m"

# Pixels per module. Five is comfortable to scan from a laptop screen at arm's
# length without making the image enormous.
_SCALE = 5

# Quiet zone, in modules. Set explicitly because segno defaults to 2 and the QR
# specification asks for 4. Two usually scans and sometimes does not, which is
# the worst kind of bug to receive: intermittent, and reported as "my phone does
# not read it". Measured on segno 1.6.6 -- the default was verified, not assumed.
_BORDER = 4
QR_BORDER_MODULES = _BORDER

# A QR that needs a version this high is too dense to scan reliably off a
# screen, and the failure mode -- "my phone just does not read it" -- is
# miserable to debug. The pairing payload sits near version 12, so this is a
# guard against the payload growing, not a limit anyone should reach today.
MAX_SCANNABLE_VERSION = 20


class QrCodeError(RuntimeError):
    """Raised when the content cannot be turned into a scannable QR."""


def qr_data_uri(content: str) -> str:
    """Encode `content` as an SVG QR, returned as a `data:` URI.

    A data URI rather than markup so the page can use `<img src=...>` instead of
    injecting SVG into the document. The application's CSP already allows
    `img-src data:`, so this needs no policy change.
    """

    text = str(content or "")
    if not text:
        raise QrCodeError("A QR needs content")
    try:
        # micro=False matters more than it looks. Left to itself segno encodes
        # short content as a Micro QR -- "hola" comes back as M3 -- and Micro QR
        # is far less widely supported by phone cameras than the standard
        # symbol. Today's pairing payload is large enough to never trigger it,
        # but relying on the payload staying large is not a guarantee.
        code = segno.make(text, error=_ERROR_CORRECTION, micro=False)
    except (ValueError, TypeError) as error:
        raise QrCodeError("Content cannot be encoded as a QR") from error
    version = code.version
    if not isinstance(version, int) or version > MAX_SCANNABLE_VERSION:
        raise QrCodeError(f"QR version {version} is not reliably scannable from a screen")
    return str(code.svg_data_uri(scale=_SCALE, border=_BORDER))


__all__ = ["MAX_SCANNABLE_VERSION", "QR_BORDER_MODULES", "QrCodeError", "qr_data_uri"]
