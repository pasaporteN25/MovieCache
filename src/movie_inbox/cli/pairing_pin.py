"""Print the SPKI pin a phone checks when pairing with a self-signed instance.

Only needed when something else terminates TLS -- a proxy, or a certificate
issued elsewhere -- because `movie-inbox serve --ssl-certfile` derives the same
value on its own.

It exists because the alternative is a four-command openssl pipeline that is
easy to mistype, and a wrong pin does not fail loudly: the phone simply refuses
to connect, with nothing on either screen saying why.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from movie_inbox.domain.pairing import PairingError, certificate_pin_from_pem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="movie-inbox pairing-pin",
        description=(
            "Print the base64 SHA-256 SPKI pin of a PEM certificate, ready to pass "
            "as --device-pairing-cert-pin."
        ),
    )
    parser.add_argument("certificate", help="Path to the PEM certificate.")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the pin, for piping into a script or an .env file.",
    )
    args = parser.parse_args(argv)

    path = Path(args.certificate)
    try:
        pin = certificate_pin_from_pem(path.read_text(encoding="utf-8"))
    except OSError as error:
        print(f"Cannot read the certificate: {error}")
        return 2
    except (PairingError, UnicodeDecodeError) as error:
        # A DER file rather than PEM is the likely mistake, and it is worth
        # naming instead of leaving someone staring at a parse error.
        print(f"Not a readable PEM certificate: {error}")
        print("If the file is DER, convert it: openssl x509 -inform der -in FILE -out FILE.pem")
        return 2

    if args.quiet:
        print(pin)
        return 0
    print(f"Certificate: {path}")
    print(f"SPKI pin:    {pin}")
    print()
    print("Pass it to the server so the pairing QR carries it:")
    print(f"  --device-pairing-cert-pin {pin}")
    print()
    print("Not needed if this same process serves TLS with --ssl-certfile: it derives it.")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual entry point
    raise SystemExit(main())
