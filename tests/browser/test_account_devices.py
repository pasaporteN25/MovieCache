from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

import test_ui_browser as browser_fixtures

from movie_inbox.infrastructure.qr_code import qr_data_uri


class AccountDevicesTests(unittest.TestCase):
    setUpClass = classmethod(browser_fixtures.BrowserInterfaceTests.setUpClass.__func__)
    tearDownClass = classmethod(browser_fixtures.BrowserInterfaceTests.tearDownClass.__func__)
    setUp = browser_fixtures.BrowserInterfaceTests.setUp
    tearDown = browser_fixtures.BrowserInterfaceTests.tearDown

    def _open(self):
        page = self.page
        page.goto(self.base_url)
        page.wait_for_selector("#homeView:not([hidden])")
        page.locator("#systemMenu summary").click()
        page.get_by_role("button", name="Mis dispositivos", exact=True).click()
        page.wait_for_selector("#devicesDialog[open]")
        return page

    def test_not_configured_and_retry(self):
        page = self._open()
        page.get_by_role("button", name="Conectar un teléfono", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#devicesFeedback').textContent.includes('HTTPS')"
        )
        self.assertTrue(page.locator("#deviceQrPanel").is_hidden())
        page.keyboard.press("Escape")
        self.assertFalse(page.locator("#devicesDialog").is_visible())

    def test_qr_expiry_secret_cleanup_and_layout(self):
        page = self.page
        # Only the ticket response is substituted: browser authentication and list are real.
        page.route(
            "**/api/device-pairing",
            lambda route: route.fulfill(
                status=201,
                content_type="application/json",
                body=json.dumps(
                    {
                        "payload": {
                            "account": "lucas",
                            "origin": "https://casa.local",
                            "ticket": "synthetic-only",
                        },
                        "expires_at": int(time.time()) + 3,
                        "qr_image": qr_data_uri(
                            json.dumps({"origin": "https://casa.local", "ticket": "synthetic-only"})
                        ),
                    }
                ),
            ),
        )
        self._open()
        page.get_by_role("button", name="Conectar un teléfono", exact=True).click()
        page.wait_for_selector("#deviceQrPanel:not([hidden])")
        self.assertEqual(
            page.locator("#deviceQrAccount").inner_text(), "lucas · https://casa.local"
        )
        destination = Path(__file__).resolve().parents[2] / "docs/design/devices"
        destination.mkdir(parents=True, exist_ok=True)
        for width in (1280, 390):
            page.set_viewport_size({"width": width, "height": 900})
            self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            page.screenshot(path=str(destination / f"devices-{width}.png"))
        page.wait_for_function(
            "document.querySelector('#devicesFeedback').textContent.includes('venció')"
        )
        self.assertIsNone(page.locator("#deviceQr").get_attribute("src"))
        page.get_by_role("button", name="Cerrar", exact=True).click()
        self.assertEqual(page.locator("#deviceQrAccount").inner_text(), "")

    def test_named_revocation_requires_confirmation(self):
        page = self.page
        response = page.request.post(
            f"{self.base_url}/api/v1/auth/login",
            data={
                "username": "lucas",
                "password": self.owner_password,
                "device_name": "Synthetic QA phone",
            },
        )
        self.assertEqual(response.status, 201)
        access = response.json()["access_token"]
        self._open()
        page.get_by_role("button", name="Revocar acceso de Synthetic QA phone", exact=True).click()
        self.assertIn("Synthetic QA phone", page.locator("#revokeDevicePrompt").inner_text())
        page.get_by_role("button", name="Conservar acceso", exact=True).click()
        self.assertEqual(
            page.request.get(
                f"{self.base_url}/api/v1/me", headers={"Authorization": f"Bearer {access}"}
            ).status,
            200,
        )
        page.get_by_role("button", name="Revocar acceso de Synthetic QA phone", exact=True).click()
        page.get_by_role("button", name="Revocar acceso", exact=True).click()
        page.wait_for_function(
            "document.querySelector('#devicesFeedback').textContent.includes('Acceso revocado')"
        )
        self.assertEqual(
            page.request.get(
                f"{self.base_url}/api/v1/me", headers={"Authorization": f"Bearer {access}"}
            ).status,
            401,
        )
