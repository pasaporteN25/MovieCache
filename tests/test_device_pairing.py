"""[A2.1] server side: the one-time ticket a phone scans to adopt an account.

ADR-0005, as amended on 2026-09-07, makes an account created on the web the only
way into the Android client. That makes this the front door, so the tests care
much more about what it refuses than about what it allows.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ElementTree
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService, session_token_hash
from movie_inbox.application.pairing_service import (
    DEVICE_SYNC_SECRET,
    PairingRejected,
    PairingService,
)
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.pairing import (
    MAX_PAIRING_PAYLOAD_BYTES,
    PAIRING_TICKET_TTL_SECONDS,
    PairingError,
    instance_public_id,
    normalize_certificate_pin,
    normalize_pairing_origin,
    pairing_payload,
    payload_fits_in_a_qr,
)
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.infrastructure.qr_code import (
    MAX_SCANNABLE_VERSION,
    QR_BORDER_MODULES,
    QrCodeError,
    qr_data_uri,
)
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

# A real-shaped SPKI pin: 32 zero bytes, base64. Shape is what is validated.
_PIN = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
_ORIGIN = "https://peliculas.example.com"


class PairingPayloadTests(unittest.TestCase):
    def test_the_origin_must_be_https_and_bare(self) -> None:
        self.assertEqual(
            normalize_pairing_origin("https://casa.example.com/"),
            _ORIGIN[:0] or "https://casa.example.com",
        )
        self.assertEqual(
            normalize_pairing_origin("https://casa.example.com:8443"),
            "https://casa.example.com:8443",
        )
        for bad in (
            "",
            "http://casa.example.com",
            "https://casa.example.com/instancia",
            "https://usuario:clave@casa.example.com",
            "https://",
        ):
            with self.subTest(origin=bad):
                # Plain HTTP would hand the ticket and the session it buys to
                # anyone on the network, so it is refused rather than warned about.
                with self.assertRaises(PairingError):
                    normalize_pairing_origin(bad)

    def test_no_pin_is_normal_but_a_broken_pin_is_a_misconfiguration(self) -> None:
        # An instance behind a publicly trusted certificate needs no pin.
        self.assertEqual(normalize_certificate_pin(""), "")
        self.assertEqual(normalize_certificate_pin(_PIN), _PIN)
        for bad in ("no-es-base64!", "AAAA=", "a" * 44, _PIN.replace("=", "")):
            with self.subTest(pin=bad):
                # Silently dropping this would leave the phone unable to connect
                # with no way to find out why.
                with self.assertRaises(PairingError):
                    normalize_certificate_pin(bad)

    def test_the_payload_carries_four_things_and_never_the_catalogue(self) -> None:
        payload = pairing_payload(
            origin=_ORIGIN,
            token="un-ticket",
            expires_at=1_800_000_000,
            instance_id="abc123",
            account_username="lucas",
            certificate_pin=_PIN,
        )
        self.assertEqual(payload["origin"], _ORIGIN)
        self.assertEqual(payload["ticket"], "un-ticket")
        self.assertEqual(payload["certificate_pin"], _PIN)
        self.assertEqual(payload["account"], "lucas")
        self.assertTrue(payload_fits_in_a_qr(payload))
        encoded = json.dumps(payload, separators=(",", ":"))
        self.assertLess(len(encoded), MAX_PAIRING_PAYLOAD_BYTES)

    def test_the_pin_is_absent_rather_than_empty_when_there_is_none(self) -> None:
        payload = pairing_payload(
            origin=_ORIGIN,
            token="t",
            expires_at=1,
            instance_id="abc",
            account_username="lucas",
        )
        self.assertNotIn("certificate_pin", payload)

    def test_a_payload_that_outgrew_a_qr_is_caught_rather_than_shipped(self) -> None:
        payload = pairing_payload(
            origin=_ORIGIN,
            token="x" * (MAX_PAIRING_PAYLOAD_BYTES + 10),
            expires_at=1,
            instance_id="abc",
            account_username="lucas",
        )
        self.assertFalse(payload_fits_in_a_qr(payload))

    def test_the_public_instance_id_is_stable_and_does_not_reveal_the_secret(self) -> None:
        first = instance_public_id("un-secreto-de-instancia")
        self.assertEqual(first, instance_public_id("un-secreto-de-instancia"))
        self.assertNotEqual(first, instance_public_id("otro-secreto"))
        self.assertNotIn("un-secreto-de-instancia", first)
        with self.assertRaises(PairingError):
            instance_public_id("")


def _svg_from_data_uri(uri: str) -> ElementTree.Element:
    head, _, body = uri.partition(",")
    if head != "data:image/svg+xml;charset=utf-8":
        raise AssertionError(f"unexpected data uri header: {head!r}")
    return ElementTree.fromstring(urllib.parse.unquote(body))


class QrCodeTests(unittest.TestCase):
    """What this file can honestly check, and what it cannot.

    It checks that the encoder is fed the right thing and gives back a
    well-formed SVG of a plausible size. It does **not** check that a phone
    reads it: there is no decoder here, so the only real proof is a camera.
    That check belongs to [A2.1] on a real device, and claiming it here would
    be exactly the mistake [F5.4] taught -- code-complete is not verified.
    """

    def test_it_returns_a_data_uri_holding_a_real_svg(self) -> None:
        root = _svg_from_data_uri(qr_data_uri("hola"))
        self.assertTrue(root.tag.endswith("svg"))
        self.assertTrue(list(root), "an empty SVG would scan as nothing")

    def test_the_image_grows_with_the_payload_and_keeps_the_full_quiet_zone(self) -> None:
        small = _svg_from_data_uri(qr_data_uri("hola"))
        large = _svg_from_data_uri(qr_data_uri("x" * 400))
        self.assertLess(int(small.attrib["width"]), int(large.attrib["width"]))
        self.assertEqual(small.attrib["width"], small.attrib["height"])
        # Two things this pins, both found by measuring rather than assuming.
        # The quiet zone: segno defaults to two modules and the specification
        # asks for four, and two usually scans and sometimes does not. And the
        # symbol kind: left alone segno encodes "hola" as a Micro QR of 15
        # modules, which many phone cameras do not read. With micro disabled it
        # is a standard version 1 symbol, 21 modules.
        self.assertEqual(int(small.attrib["width"]), (21 + 2 * QR_BORDER_MODULES) * 5)

    def test_content_too_dense_to_scan_is_refused_rather_than_drawn(self) -> None:
        # The failure mode of an over-dense QR is "my phone just does not read
        # it", which is miserable to debug from a camera.
        with self.assertRaises(QrCodeError):
            qr_data_uri("x" * 3000)
        with self.assertRaises(QrCodeError):
            qr_data_uri("")

    def test_a_real_pairing_payload_lands_well_inside_the_scannable_range(self) -> None:
        payload = pairing_payload(
            origin=_ORIGIN,
            token="x" * 64,
            expires_at=1_800_000_000,
            instance_id="a" * 32,
            account_username="lucas",
            certificate_pin=_PIN,
        )
        root = _svg_from_data_uri(qr_data_uri(json.dumps(payload, separators=(",", ":"))))
        modules = int(root.attrib["width"]) // 5 - 2 * QR_BORDER_MODULES
        version = (modules - 17) // 4
        self.assertEqual(
            modules, 4 * version + 17, "el ancho tiene que cerrar con una version real"
        )
        self.assertLessEqual(version, MAX_SCANNABLE_VERSION)
        self.assertGreater(version, 0)


class PairingTicketStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "instance.db"
        self.repository = SqliteIdentityRepository(self.path)
        self.repository.initialize()
        AuthService(self.repository).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(Path(self.temporary.name) / "catalog.json")],
            write_path=str(Path(self.temporary.name) / "catalog.json"),
        )
        self.user_id = self.repository.owner().id  # type: ignore[union-attr]

    def test_a_ticket_can_only_be_redeemed_once(self) -> None:
        self.repository.save_pairing_ticket(session_token_hash("t"), self.user_id, 100, 400)
        self.assertEqual(
            self.repository.redeem_pairing_ticket(session_token_hash("t"), 200), self.user_id
        )
        # Two phones scanning the same QR is not exotic; the second gets nothing.
        self.assertEqual(self.repository.redeem_pairing_ticket(session_token_hash("t"), 201), "")

    def test_an_expired_ticket_is_not_redeemable(self) -> None:
        self.repository.save_pairing_ticket(session_token_hash("t"), self.user_id, 100, 400)
        self.assertEqual(self.repository.redeem_pairing_ticket(session_token_hash("t"), 400), "")
        self.assertEqual(
            self.repository.redeem_pairing_ticket(session_token_hash("t"), 399), self.user_id
        )

    def test_only_the_hash_is_stored(self) -> None:
        self.repository.save_pairing_ticket(session_token_hash("secreto"), self.user_id, 1, 2)
        raw = self.path.read_bytes()
        self.assertNotIn(b"secreto", raw)

    def test_the_sweep_removes_what_nobody_can_use(self) -> None:
        self.repository.save_pairing_ticket(session_token_hash("viejo"), self.user_id, 1, 100)
        self.repository.save_pairing_ticket(session_token_hash("nuevo"), self.user_id, 1, 900)
        self.assertEqual(self.repository.purge_pairing_tickets(500), 1)
        self.assertEqual(
            self.repository.redeem_pairing_ticket(session_token_hash("nuevo"), 600), self.user_id
        )


class PairingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.repository = SqliteIdentityRepository(root / "instance.db")
        self.repository.initialize()
        self.now = 1_000_000
        self.auth = AuthService(self.repository, clock=lambda: self.now)
        self.auth.bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(root / "catalog.json")],
            write_path=str(root / "catalog.json"),
        )
        (root / "catalog.json").write_text(
            json.dumps({"schema_version": 9, "items": []}), encoding="utf-8"
        )
        self.service = PairingService(
            self.repository, self.auth, origin=_ORIGIN, clock=lambda: self.now
        )
        _, self.identity = self.auth.login("lucas", "a-long-enough-password")

    def _ticket(self) -> str:
        return str(self.service.create_ticket(self.identity)["payload"]["ticket"])

    def test_a_ticket_buys_a_working_device_session(self) -> None:
        session = self.service.redeem(self._ticket(), "Pixel de Lucas")
        self.assertTrue(session.access_token)
        self.assertEqual(session.identity.user.username, "lucas")
        self.assertIsNotNone(self.auth.authenticate_device(session.access_token))

    def test_the_payload_says_when_it_dies_and_it_is_soon(self) -> None:
        ticket = self.service.create_ticket(self.identity)
        self.assertEqual(ticket["expires_in"], PAIRING_TICKET_TTL_SECONDS)
        self.assertEqual(ticket["payload"]["expires_at"], self.now + PAIRING_TICKET_TTL_SECONDS)
        self.assertLessEqual(ticket["expires_in"], 15 * 60, "un QR no puede quedar vivo horas")

    def test_replaying_expiring_and_guessing_all_give_the_same_answer(self) -> None:
        used = self._ticket()
        self.service.redeem(used, "Pixel")
        for token, label in (
            (used, "replay"),
            ("no-existe", "invento"),
            ("", "vacio"),
            ("x" * 600, "absurdamente largo"),
        ):
            with self.subTest(case=label):
                with self.assertRaises(PairingRejected):
                    self.service.redeem(token, "Pixel")

        late = self._ticket()
        self.now += PAIRING_TICKET_TTL_SECONDS + 1
        with self.assertRaises(PairingRejected):
            self.service.redeem(late, "Pixel")

    def _member(self, username: str, password: str, *, settled: bool = True):
        member, _ = self.repository.create_member(
            username,
            self.auth.hasher.hash(password),
            f"Catalogo de {username}",
            [str(Path(self.temporary.name) / f"{username}.json")],
            str(Path(self.temporary.name) / f"{username}.json"),
        )
        if settled:
            self.repository.replace_password(
                member.id, self.auth.hasher.hash(password), must_change_password=False
            )
        return self.auth.login(username, password)[1]

    def test_a_member_pairs_their_own_account_and_only_their_own(self) -> None:
        # Pairing is not owner-only: each account has its own catalogue, so each
        # account pairs its own phone. The ticket carries exactly that account.
        ana = self._member("ana", "otra-clave-bastante-larga")
        ticket = str(self.service.create_ticket(ana)["payload"]["ticket"])
        session = self.service.redeem(ticket, "Telefono de Ana")
        self.assertEqual(session.identity.user.id, ana.user.id)
        self.assertNotEqual(session.identity.user.id, self.identity.user.id)

    def test_a_pending_password_change_cannot_be_walked_around_with_a_qr(self) -> None:
        # A freshly created member owes a password change. Pairing must not be
        # the way around it -- device login already refuses, and so does this.
        nueva = self._member("nueva", "clave-inicial-bastante-larga", settled=False)
        ticket = str(self.service.create_ticket(nueva)["payload"]["ticket"])
        with self.assertRaises(PairingRejected):
            self.service.redeem(ticket, "Telefono nuevo")

    def test_a_ticket_does_not_survive_the_account_being_deactivated(self) -> None:
        # Minted while the account was fine; redeemed after it was not. The
        # ticket says nothing about the account's state now, so the state is
        # checked at redemption rather than trusted from minting time.
        ana = self._member("ana", "otra-clave-bastante-larga")
        token = str(self.service.create_ticket(ana)["payload"]["ticket"])
        self.repository.set_user_active(ana.user.id, False)
        with self.assertRaises(PairingRejected):
            self.service.redeem(token, "Pixel")

    def test_a_ticket_does_not_survive_a_password_change(self) -> None:
        # Changing the password is how an account revokes every credential, and
        # for the owner it is the only way: the owner cannot be deactivated. A
        # ticket minted before the change is a credential too, so it goes with
        # the sessions instead of opening a new one after them.
        token = self._ticket()
        self.auth.change_password(
            self.identity, "a-long-enough-password", "another-long-enough-password"
        )
        with self.assertRaises(PairingRejected):
            self.service.redeem(token, "Pixel")

    def test_a_ticket_does_not_come_back_once_a_reset_member_sets_a_password(self) -> None:
        # An admin reset blocks redemption on its own, through the pending
        # change. The ticket must not come back to life when the member
        # completes that change inside its five minutes. The reset is done the
        # way MemberService.reset_password does it.
        ana = self._member("ana", "otra-clave-bastante-larga")
        token = str(self.service.create_ticket(ana)["payload"]["ticket"])
        temporary = "clave-temporal-bastante-larga"
        self.repository.replace_password(
            ana.user.id, self.auth.hasher.hash(temporary), must_change_password=True
        )
        _, pending = self.auth.login("ana", temporary)
        self.auth.change_password(pending, temporary, "clave-definitiva-bastante-larga")
        with self.assertRaises(PairingRejected):
            self.service.redeem(token, "Pixel")

    def test_a_ticket_does_not_survive_deactivation_even_if_the_account_returns(self) -> None:
        ana = self._member("ana", "otra-clave-bastante-larga")
        token = str(self.service.create_ticket(ana)["payload"]["ticket"])
        self.repository.set_user_active(ana.user.id, False)
        self.repository.set_user_active(ana.user.id, True)
        with self.assertRaises(PairingRejected):
            self.service.redeem(token, "Pixel")

    def test_a_device_name_is_required_and_bounded(self) -> None:
        for name in ("", "   ", "x" * 200, "salto\nde linea"):
            with self.subTest(name=name):
                with self.assertRaises((PairingRejected, ValueError)):
                    self.service.redeem(self._ticket(), name)

    def test_an_instance_without_https_cannot_offer_pairing(self) -> None:
        # Not a bad request from the member: the instance is not set up for it.
        service = PairingService(self.repository, self.auth, origin="", clock=lambda: self.now)
        with self.assertRaises(PairingError):
            service.create_ticket(self.identity)

    def test_the_instance_id_travels_and_matches_the_durable_secret(self) -> None:
        payload = self.service.create_ticket(self.identity)["payload"]
        expected = instance_public_id(self.repository.instance_secret(DEVICE_SYNC_SECRET))
        self.assertEqual(payload["instance_id"], expected)


class PairingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write(
            [normalize_item({"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"})]
        )
        self.instance_path = root / "instance.db"
        self.password = "a-long-local-password"
        AuthService(SqliteIdentityRepository(self.instance_path)).bootstrap_owner(
            "lucas",
            self.password,
            catalog_name="Catalogo de Lucas",
            source_paths=[str(self.catalog_path)],
            write_path=str(self.catalog_path),
        )
        media = root / "media"
        media.mkdir()
        self.config = ViewerConfig(
            patterns=[str(self.catalog_path)],
            title="Movie Inbox Test",
            write_json=str(self.catalog_path),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=8765,
            api_token="test-token",
            instance_db=str(self.instance_path),
            member_catalog_dir=str(root / "member-catalogs"),
            library_allowed_roots=(str(media),),
            library_scheduler_poll_seconds=3600,
            public_origin=_ORIGIN,
            device_pairing_certificate_pin=_PIN,
        )
        self.app = create_app(self.config)
        # Served on the real public origin: with HTTPS configured the session
        # cookie is Secure, so a plain-http client would silently drop it.
        self.context = TestClient(self.app, base_url=_ORIGIN)
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Movie-Inbox-Token": self.config.api_token,
            "Origin": _ORIGIN,
            "Content-Type": "application/json",
        }

    def _login(self) -> None:
        response = self.client.post(
            "/auth/login",
            content=json.dumps({"username": "lucas", "password": self.password}),
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_a_stranger_cannot_mint_a_pairing_ticket(self) -> None:
        # Without a browser session there is no proof of authorization, and the
        # ticket is the only thing standing between a phone and the account.
        response = self.client.post("/api/device-pairing")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["reason"], "authentication_required")

    def test_pairing_end_to_end_produces_a_session_that_reads_the_catalogue(self) -> None:
        self._login()
        minted = self.client.post("/api/device-pairing", headers=self._headers())
        self.assertEqual(minted.status_code, 201, minted.content)
        payload = minted.json()["payload"]
        self.assertEqual(payload["origin"], _ORIGIN)
        self.assertEqual(payload["certificate_pin"], _PIN)

        paired = self.client.post(
            "/api/v1/pair",
            content=json.dumps(
                {"pairing_token": payload["ticket"], "device_name": "Pixel de Lucas"}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(paired.status_code, 201, paired.content)
        access = paired.json()["access_token"]

        # The session is a real device session: it reads the device API without
        # ever having seen the password.
        bearer = {"Authorization": f"Bearer {access}"}
        me = self.client.get("/api/v1/me", headers=bearer)
        self.assertEqual(me.status_code, 200, me.content)
        items = self.client.get("/api/v1/catalog/items", headers=bearer)
        self.assertEqual(items.status_code, 200, items.content)
        self.assertEqual([row["title"] for row in items.json()["items"]], ["Heat"])

    def test_the_same_qr_cannot_pair_two_phones(self) -> None:
        self._login()
        payload = self.client.post("/api/device-pairing", headers=self._headers()).json()["payload"]
        body = json.dumps({"pairing_token": payload["ticket"], "device_name": "Pixel"})
        headers = {"Content-Type": "application/json"}
        self.assertEqual(
            self.client.post("/api/v1/pair", content=body, headers=headers).status_code, 201
        )
        second = self.client.post("/api/v1/pair", content=body, headers=headers)
        self.assertEqual(second.status_code, 401)
        self.assertEqual(second.json()["error"]["code"], "pairing_rejected")

    def test_an_instance_without_https_says_so_instead_of_half_working(self) -> None:
        # The likely first encounter: an instance still served over plain http.
        # Pairing cannot be offered there, and saying "not configured" beats
        # minting a ticket for an origin the phone must refuse anyway.
        plain = create_app(
            replace(self.config, public_origin="", device_pairing_certificate_pin="")
        )
        with TestClient(plain, base_url="http://127.0.0.1:8765") as client:
            headers = {
                "X-Movie-Inbox-Token": self.config.api_token,
                "Origin": "http://127.0.0.1:8765",
                "Content-Type": "application/json",
            }
            login = client.post(
                "/auth/login",
                content=json.dumps({"username": "lucas", "password": self.password}),
                headers=headers,
            )
            self.assertEqual(login.status_code, 200, login.content)
            response = client.post("/api/device-pairing", headers=headers)
            self.assertEqual(response.status_code, 409, response.content)
            self.assertEqual(response.json()["reason"], "pairing_not_configured")

    def test_the_response_carries_the_qr_and_the_payload_it_encodes(self) -> None:
        self._login()
        body = self.client.post("/api/device-pairing", headers=self._headers()).json()
        self.assertTrue(body["qr_image"].startswith("data:image/svg+xml"))
        # The payload travels beside the image on purpose: a surface can offer a
        # manual fallback, and this test can read what the QR encodes without a
        # decoder.
        self.assertEqual(body["payload"]["origin"], _ORIGIN)
        root = _svg_from_data_uri(body["qr_image"])
        self.assertTrue(root.tag.endswith("svg"))

    def test_the_ticket_never_appears_in_a_get(self) -> None:
        # Minting is a POST on purpose: a GET would put a bearer credential
        # somewhere it could be logged, cached or shared as a URL.
        self._login()
        self.assertEqual(
            self.client.get("/api/device-pairing", headers=self._headers()).status_code, 405
        )

    # [X4.4]: listing and revoking the paired phones.

    def _pair_a_phone(self, name: str = "Pixel de Lucas") -> dict[str, Any]:
        response = self.client.post(
            "/api/v1/auth/login",
            content=json.dumps(
                {"username": "lucas", "password": self.password, "device_name": name}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        session: dict[str, Any] = response.json()
        return session

    def test_a_stranger_can_neither_list_nor_revoke_phones(self) -> None:
        listed = self.client.get("/api/device-sessions", headers=self._headers())
        revoked = self.client.delete("/api/device-sessions/anything", headers=self._headers())

        self.assertEqual(listed.status_code, 401)
        self.assertEqual(revoked.status_code, 401)

    def test_the_list_needs_the_page_token_like_any_other_web_api(self) -> None:
        self._login()

        response = self.client.get("/api/device-sessions")

        self.assertEqual(response.status_code, 403)

    def test_the_account_sees_its_phone_and_nothing_that_could_authenticate_one(self) -> None:
        session = self._pair_a_phone()
        self._login()

        response = self.client.get("/api/device-sessions", headers=self._headers())

        self.assertEqual(response.status_code, 200, response.content)
        (device,) = response.json()["devices"]
        self.assertEqual(device["device_name"], "Pixel de Lucas")
        self.assertEqual(
            set(device), {"id", "device_name", "created_at", "last_seen_at", "expires_at"}
        )
        self.assertTrue(device["created_at"].endswith("Z"))
        for secret in (session["access_token"], session["refresh_token"]):
            self.assertNotIn(secret, response.text)
            self.assertNotIn(session_token_hash(secret), response.text)

    def test_revoking_a_phone_puts_it_out_on_its_next_call(self) -> None:
        session = self._pair_a_phone()
        self._login()
        (device,) = self.client.get("/api/device-sessions", headers=self._headers()).json()[
            "devices"
        ]

        revoked = self.client.delete(
            f"/api/device-sessions/{device['id']}", headers=self._headers()
        )

        self.assertEqual(revoked.status_code, 200, revoked.content)
        bearer = {"Authorization": f"Bearer {session['access_token']}"}
        self.assertEqual(self.client.get("/api/v1/me", headers=bearer).status_code, 401)
        refreshed = self.client.post(
            "/api/v1/auth/refresh",
            content=json.dumps({"refresh_token": session["refresh_token"]}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(refreshed.status_code, 401)
        listed = self.client.get("/api/device-sessions", headers=self._headers())
        self.assertEqual(listed.json()["devices"], [])

    def test_revoking_needs_the_page_origin(self) -> None:
        # A DELETE from another site must not be able to sign a phone out.
        self._pair_a_phone()
        self._login()
        (device,) = self.client.get("/api/device-sessions", headers=self._headers()).json()[
            "devices"
        ]
        headers = self._headers()
        headers["Origin"] = "https://elsewhere.example"

        response = self.client.delete(f"/api/device-sessions/{device['id']}", headers=headers)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            len(self.client.get("/api/device-sessions", headers=self._headers()).json()["devices"]),
            1,
        )

    def test_an_unknown_phone_is_a_404(self) -> None:
        self._login()

        response = self.client.delete("/api/device-sessions/no-such-phone", headers=self._headers())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["reason"], "device_not_found")


if __name__ == "__main__":
    unittest.main()
