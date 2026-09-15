"""Minting and redeeming the one-time ticket that pairs a phone with an account.

Two authorities meet here and must not be confused, the same way they do not get
confused in the streaming back office:

* **Minting** is done by someone already authenticated in the browser, and only
  ever for **their own** account. The web session is the proof of authorization.
* **Redeeming** is done by a device with no session at all -- that is the whole
  point -- so the ticket itself has to carry every bit of authority, which is
  why it is single-use, short-lived and stored only as a hash.

The ticket never grants more than the account it was minted for. There is no
form of it that pairs "as the owner" or elevates anything.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Any

from movie_inbox.application.auth_service import (
    SESSION_TOKEN_BYTES,
    AuthService,
    DeviceSession,
    session_token_hash,
    validate_device_name,
)
from movie_inbox.application.identity_repository import IdentityRepository
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.domain.pairing import (
    PAIRING_TICKET_RETENTION_SECONDS,
    PAIRING_TICKET_TTL_SECONDS,
    PairingError,
    instance_public_id,
    pairing_payload,
    payload_fits_in_a_qr,
)

# Name of the persistent instance secret the public instance id is derived from.
# The same one [A1.4] created for the device sync key: an instance has one
# identity, not two that can drift apart.
DEVICE_SYNC_SECRET = "device_sync_key"


class PairingRejected(PermissionError):
    """Raised when a ticket cannot be redeemed, without saying which reason."""


class PairingService:
    def __init__(
        self,
        repository: IdentityRepository,
        auth_service: AuthService,
        *,
        origin: str = "",
        certificate_pin: str = "",
        clock: Callable[[], float] | None = None,
        ttl_seconds: int = PAIRING_TICKET_TTL_SECONDS,
    ) -> None:
        self.repository = repository
        self.auth_service = auth_service
        self.origin = origin
        self.certificate_pin = certificate_pin
        self.clock = clock or auth_service.clock
        self.ttl_seconds = max(30, int(ttl_seconds))

    def create_ticket(self, identity: AuthenticatedIdentity) -> dict[str, Any]:
        """Mint a ticket for the caller's own account and return the QR payload.

        The plaintext ticket is in the return value and nowhere else: it is not
        logged, not stored and not recoverable. A lost QR is re-minted, never
        looked up.
        """

        now = int(self.clock())
        expires_at = now + self.ttl_seconds
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        # Opportunistic sweep, so used and expired tickets do not accumulate in
        # an instance nobody administers by hand.
        self.repository.purge_pairing_tickets(now - PAIRING_TICKET_RETENTION_SECONDS)
        self.repository.save_pairing_ticket(
            session_token_hash(token), identity.user.id, now, expires_at
        )
        payload = pairing_payload(
            origin=self.origin,
            token=token,
            expires_at=expires_at,
            instance_id=instance_public_id(self.repository.instance_secret(DEVICE_SYNC_SECRET)),
            account_username=identity.user.username,
            certificate_pin=self.certificate_pin,
        )
        if not payload_fits_in_a_qr(payload):
            raise PairingError("Pairing payload does not fit in a QR")
        return {"payload": payload, "expires_at": expires_at, "expires_in": self.ttl_seconds}

    def redeem(self, token: str, device_name: str) -> DeviceSession:
        """Trade a ticket for a device session, once.

        Every failure raises the same error on purpose. A device that guesses,
        replays or arrives late learns only "no": telling it apart would say
        whether a ticket ever existed, and for whom.
        """

        if not token or len(token) > 512:
            raise PairingRejected("pairing_rejected")
        name = validate_device_name(device_name)
        user_id = self.repository.redeem_pairing_ticket(
            session_token_hash(token), int(self.clock())
        )
        if not user_id:
            raise PairingRejected("pairing_rejected")
        try:
            return self.auth_service.create_paired_device_session(user_id, name)
        except ValueError as error:
            # The account was archived, deactivated or left without a catalogue
            # between minting and redeeming. The ticket is already spent, which
            # is the safe direction: it cannot be retried against a changed
            # account.
            raise PairingRejected("pairing_rejected") from error


__all__ = ["DEVICE_SYNC_SECRET", "PairingRejected", "PairingService"]
