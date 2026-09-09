"""Guard the frozen API description before a native client consumes it."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


class DeviceApiContractTests(unittest.TestCase):
    def test_v1_contract_is_valid_json_and_limits_the_native_surface(self) -> None:
        root = Path(__file__).resolve().parents[1]
        document: dict[str, Any] = json.loads(
            (root / "docs" / "openapi" / "device-api-v1.openapi.json").read_text(encoding="utf-8")
        )

        self.assertEqual(document["openapi"], "3.1.0")
        self.assertEqual(document["info"]["version"], "1.0.0")
        self.assertEqual(document["servers"][0]["url"], "https://{baseUrl}")
        self.assertEqual(
            set(document["paths"]),
            {
                "/api/v1/auth/login",
                "/api/v1/auth/refresh",
                "/api/v1/auth/session",
                "/api/v1/pair",
                "/api/v1/me",
                "/api/v1/availability",
                "/api/v1/catalog/drafts",
                "/api/v1/ratings",
                "/api/v1/collections",
                "/api/v1/collections/{collectionId}/items",
                "/api/v1/catalog/items",
                "/api/v1/catalog/items/{itemId}",
                "/api/v1/catalog/items/{itemId}/personal",
                "/api/v1/search",
            },
        )
        # [A2.1]: pairing is additive -- a new path, no existing meaning changed --
        # so it belongs inside v1 by ADR-0003's own versioning rule.
        pair = document["paths"]["/api/v1/pair"]["post"]
        self.assertEqual(pair["operationId"], "redeemPairingTicket")
        self.assertEqual(pair["security"], [], "a device pairing has no session yet")
        self.assertIn("429", pair["responses"], "redemption is rate limited like login")
        # [A2.3]: adding offline is an import, not a merge, so the contract
        # says plainly that nothing here reaches the catalogue.
        drafts = document["paths"]["/api/v1/catalog/drafts"]["post"]
        self.assertEqual(drafts["operationId"], "addOfflineDrafts")
        self.assertIn("200", drafts["responses"])
        self.assertNotIn("201", drafts["responses"], "appending is not creating")
        item = document["components"]["schemas"]["OfflineDraftItem"]
        self.assertEqual(sorted(item["required"]), ["id", "title"])
        # [A2.6]: a collection work carries identity and nothing personal --
        # following a collection does not copy anything into your catalogue.
        work = document["components"]["schemas"]["CollectionWork"]
        for field in ("personal", "status", "rating", "review", "path", "local_files"):
            self.assertNotIn(field, work["properties"])
        # [A2.6]: the two conditions ADR-0004 attached to this source have to
        # survive on the wire, not just in a document.
        result = document["components"]["schemas"]["AvailabilityResult"]
        self.assertIn("attribution", result["required"])
        self.assertIn("justwatch", result["properties"]["attribution"]["required"])
        row = document["components"]["schemas"]["WorkAvailability"]["properties"]
        self.assertIn("expires_at", row, "a replica has to know when to stop showing it")
        # [F3.2] on the wire: a public score is somebody else's opinion, so
        # the shape has no room for the viewer's own rating to be written into.
        rating = document["components"]["schemas"]["PublicRating"]["properties"]
        self.assertIn("source", rating)
        self.assertNotIn("personal", rating)
        self.assertNotIn("/api/scanner", document["paths"])
        self.assertNotIn("/api/admin", document["paths"])

    def test_v1_contract_requires_bearer_tokens_and_hides_server_paths(self) -> None:
        root = Path(__file__).resolve().parents[1]
        document: dict[str, Any] = json.loads(
            (root / "docs" / "openapi" / "device-api-v1.openapi.json").read_text(encoding="utf-8")
        )

        scheme = document["components"]["securitySchemes"]["deviceBearer"]
        self.assertEqual(scheme, {"type": "http", "scheme": "bearer", "bearerFormat": "opaque"})
        item = document["components"]["schemas"]["CatalogItem"]
        self.assertNotIn("source_file", item["properties"])
        self.assertNotIn("_source_file", item["properties"])
        self.assertEqual(
            document["paths"]["/api/v1/catalog/items/{itemId}/personal"]["patch"]["operationId"],
            "patchPersonalItemState",
        )
