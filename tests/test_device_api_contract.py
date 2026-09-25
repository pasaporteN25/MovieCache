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
                "/api/v1/catalog/drafts/receipts",
                "/api/v1/ratings",
                "/api/v1/charades",
                "/api/v1/collections",
                "/api/v1/collections/{collectionId}/items",
                "/api/v1/catalog/items",
                "/api/v1/catalog/items/status",
                "/api/v1/catalog/items/{itemId}",
                "/api/v1/catalog/items/{itemId}/personal",
                "/api/v1/catalog/items/{itemId}/removal",
                "/api/v1/search",
            },
        )
        # [A2.1]: pairing is additive -- a new path, no existing meaning changed --
        # so it belongs inside v1 by ADR-0003's own versioning rule.
        pair = document["paths"]["/api/v1/pair"]["post"]
        self.assertEqual(pair["operationId"], "redeemPairingTicket")
        self.assertEqual(pair["security"], [], "a device pairing has no session yet")
        self.assertIn("429", pair["responses"], "redemption is rate limited like login")
        # [X4.1]: a lost refresh response is recoverable, and a client has to
        # be told so or it will re-pair a phone that only needed a retry.
        refresh = document["paths"]["/api/v1/auth/refresh"]["post"]
        self.assertIn("try again", refresh["description"])
        # [A2.3]: adding offline is an import, not a merge, so the contract
        # says plainly that nothing here reaches the catalogue.
        drafts = document["paths"]["/api/v1/catalog/drafts"]["post"]
        self.assertEqual(drafts["operationId"], "addOfflineDrafts")
        self.assertIn("200", drafts["responses"])
        self.assertNotIn("201", drafts["responses"], "appending is not creating")
        # [X7]: draft_busy, device_draft_full and draft_limit_reached are 409s the
        # server already answers on this route; the contract has to say so.
        self.assertIn("409", drafts["responses"])
        conflict = document["components"]["responses"]["DraftConflict"]
        for code in ("draft_busy", "device_draft_full", "draft_limit_reached"):
            self.assertIn(code, conflict["description"])
        # [X9]/[X7]: a restart-invalidated or tampered cursor answers 400
        # invalid_request on this route, same as the other cursor-paged ones.
        items_page = document["paths"]["/api/v1/catalog/items"]["get"]
        self.assertIn("400", items_page["responses"])
        # [X6.3]: after sending works the device can ask what became of them, and
        # an id the server has no record of is answered, not left out.
        receipts = document["paths"]["/api/v1/catalog/drafts/receipts"]["post"]
        self.assertEqual(receipts["operationId"], "getOfflineDraftReceipts")
        receipt = document["components"]["schemas"]["Receipt"]
        self.assertEqual(
            receipt["properties"]["state"]["enum"], ["pending", "applied", "discarded", "unknown"]
        )
        self.assertEqual(sorted(receipt["required"]), ["item_id", "reason", "state"])
        # [X5.5]: a device is told what became of a work it holds, and "unknown" is
        # an answer of its own -- absence is never a removal.
        statuses = document["paths"]["/api/v1/catalog/items/status"]["post"]
        assert statuses["operationId"] == "getItemStatuses"
        self.assertIn("NOT a removal", statuses["description"])
        status = document["components"]["schemas"]["ItemStatus"]
        self.assertEqual(status["properties"]["state"]["enum"], ["present", "removed", "unknown"])
        self.assertEqual(
            sorted(status["required"]), ["merged_into", "reason", "removed_at", "state"]
        )
        self.assertEqual(status["properties"]["reason"]["enum"], ["deleted", "merged", None])
        # [X5.6]: a phone can remove a work, but not over a personal edit it never
        # saw: without force the request has to say what the phone saw, all of it.
        removal = document["paths"]["/api/v1/catalog/items/{itemId}/removal"]["post"]
        assert removal["operationId"] == "removeCatalogItem"
        self.assertIn("409", removal["responses"])
        self.assertIn(
            "removal_conflict",
            document["components"]["responses"]["RemovalConflict"]["description"],
        )
        removal_base = document["components"]["schemas"]["RemovalBase"]
        self.assertEqual(
            sorted(removal_base["required"]), ["rating", "review", "status", "watched_at"]
        )
        self.assertEqual(
            sorted(document["components"]["schemas"]["RemovalRequest"]["properties"]),
            ["base", "force"],
        )
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
        # [A2.4]: a phone deals the same deck offline only if it holds the deck's
        # whole input, keys included -- and nothing personal travels with it.
        charades = document["paths"]["/api/v1/charades"]["get"]
        self.assertEqual(charades["operationId"], "getCharadesSnapshot")
        charade = document["components"]["schemas"]["CharadeWork"]
        self.assertEqual(
            sorted(charade["required"]), ["difficulty", "key", "source", "title", "year"]
        )
        for field in ("personal", "status", "rating", "review", "notes", "path", "local_files"):
            self.assertNotIn(field, charade["properties"])
        snapshot = document["components"]["schemas"]["CharadesSnapshot"]
        for field in ("works", "fingerprint", "counts", "timer_options"):
            self.assertIn(field, snapshot["required"])
        self.assertNotIn("/api/scanner", document["paths"])
        self.assertNotIn("/api/admin", document["paths"])
        # [X3.3]: a device knows when a field was last personally edited.
        personal_state = document["components"]["schemas"]["PersonalState"]
        self.assertIn("changed_at", personal_state["required"])
        changed_at = document["components"]["schemas"]["PersonalChangedAt"]
        self.assertEqual(set(changed_at["properties"]), {"status", "rating", "review"})

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
        personal = document["paths"]["/api/v1/catalog/items/{itemId}/personal"]["patch"]
        self.assertEqual(personal["operationId"], "patchPersonalItemState")
        # [X2]: a declared, stale base turns the patch into a conflict rather
        # than a silent overwrite.
        self.assertIn("409", personal["responses"])
        patch = document["components"]["schemas"]["PersonalPatch"]
        self.assertIn("base", patch["properties"])
        base = document["components"]["schemas"]["PersonalPatchBase"]
        self.assertEqual(set(base["properties"]), {"status", "watched_at", "rating", "review"})
