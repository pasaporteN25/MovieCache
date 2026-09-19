"""[A2.3] server side: works a phone recorded with no connection.

The use case, in the owner's words: saving a film to the collection without
being at the computer or at home.

The design rests on a distinction the Android client's brief v3 makes
explicit, and most of these tests are about holding it: editing a work that
exists on both sides has a shared base and merges, while **adding** one has no
base at all. That is not a merge, it is an import -- so it lands in review, and
the phone never decides identity.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from movie_inbox.application.auth_service import AuthService
from movie_inbox.application.catalog_service import CatalogService
from movie_inbox.application.import_service import (
    DEVICE_RECEIPT_RETENTION_SECONDS,
    MAX_DEVICE_ITEMS_PER_REQUEST,
    ImportService,
)
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.domain.imports import (
    DEVICE_ORIGIN,
    WEB_ORIGIN,
    DeviceReceipt,
    ImportDraft,
    ImportDraftItem,
)
from movie_inbox.infrastructure.collection_repository import SqliteCollectionRepository
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.import_parsers import parse_import_content
from movie_inbox.infrastructure.import_repository import SqliteImportDraftRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig

HEAT: dict[str, Any] = {
    "id": "heat",
    "title": "Heat",
    "year": "1995",
    "kind": "pelicula",
    "tmdb_id": "949",
}


class DeviceDraftServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.instance = root / "instance.db"
        repository = SqliteIdentityRepository(self.instance)
        repository.initialize()
        AuthService(repository).bootstrap_owner(
            "lucas",
            "a-long-enough-password",
            catalog_name="Catalogo",
            source_paths=[str(root / "catalog.json")],
            write_path=str(root / "catalog.json"),
        )
        owner = repository.owner()
        assert owner is not None
        self.user_id = owner.id
        self.now = 1_000_000
        self.service = ImportService(
            SqliteImportDraftRepository(self.instance),
            SqliteCollectionRepository(self.instance),
            parser=parse_import_content,
            clock=lambda: self.now,
        )
        self.catalog: list[Mapping[str, Any]] = [normalize_item(HEAT).to_dict()]

    def _add(self, *entries: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = self.service.append_device_items(
            self.user_id, list(entries), self.catalog
        )
        return result

    def test_a_work_added_offline_waits_in_review_instead_of_entering_the_catalogue(
        self,
    ) -> None:
        result = self._add({"id": "local-1", "title": "El boton de nacar", "year": "2015"})
        self.assertEqual([row["state"] for row in result["accepted"]], ["new"])
        # Nothing was written to the catalogue: the draft is the whole point.
        self.assertEqual(len(self.catalog), 1)
        draft = self.service.draft_detail(self.user_id, str(result["draft_id"]), self.catalog)
        self.assertEqual(draft["origin"], DEVICE_ORIGIN)
        # Nothing counts down on a phone draft: it waits as long as it has to.
        self.assertEqual(draft["expires_at"], "")
        self.assertIsNone(draft["remaining_seconds"])

    def test_a_title_that_looks_like_one_you_have_goes_to_review_not_to_certainty(
        self,
    ) -> None:
        # The catalogue's Heat carries a tmdb_id and the phone's typed entry
        # carries none, so title and year alone are all there is to compare.
        # That is a resemblance, not proof, and invariant 3 sends it to a human
        # rather than letting the phone decide it is the same film.
        result = self._add({"id": "local-2", "title": "Heat", "year": "1995"})
        self.assertEqual(result["accepted"][0]["state"], "review")
        self.assertEqual(result["accepted"][0]["reason"], "possible_catalog_match")

    def test_everything_lands_in_one_pile_rather_than_a_draft_per_film(self) -> None:
        first = self._add({"id": "local-1", "title": "Stalker", "year": "1979"})
        self.now += 60
        second = self._add({"id": "local-2", "title": "Solaris", "year": "1972"})
        self.assertEqual(first["draft_id"], second["draft_id"])
        self.assertEqual(len(self.service.list_drafts(self.user_id)), 1)
        self.assertEqual(second["counts"]["total"], 2)

    def test_a_retried_sync_does_not_duplicate_the_film(self) -> None:
        # The failure this prevents is ordinary: the server stores the work and
        # the response is lost on the way back, so the phone tries again.
        entry: dict[str, Any] = {"id": "local-1", "title": "Persona", "year": "1966"}
        self._add(entry)
        again = self._add(entry)
        self.assertEqual(again["accepted"], [])
        self.assertEqual(again["duplicates"], ["local-1"])
        self.assertEqual(again["counts"]["total"], 1)

    def test_adding_the_same_film_twice_on_different_days_is_caught(self) -> None:
        # Different client ids, same work: the second is classified against what
        # the draft already holds, not only against the catalogue.
        self._add({"id": "local-1", "title": "Solaris", "year": "1972"})
        self.now += 86_400
        second = self._add({"id": "local-2", "title": "Solaris", "year": "1972"})
        self.assertEqual(second["accepted"][0]["state"], "present")

    def test_a_work_with_no_title_is_kept_as_invalid_rather_than_dropped(self) -> None:
        # Losing it silently would be the failure the whole feature exists to
        # avoid; the person decides what to do with it.
        result = self._add({"id": "local-1", "title": "   "})
        self.assertEqual(result["accepted"][0]["state"], "invalid")

    def test_a_work_without_a_client_id_is_refused(self) -> None:
        # Without it a retry cannot be told from a second film.
        with self.assertRaises(ValueError):
            self._add({"title": "Sin id"})

    def test_a_request_cannot_be_unbounded(self) -> None:
        entries: list[dict[str, Any]] = [
            {"id": f"local-{position}", "title": f"Obra {position}"}
            for position in range(MAX_DEVICE_ITEMS_PER_REQUEST + 1)
        ]
        with self.assertRaises(ValueError):
            self.service.append_device_items(self.user_id, entries, self.catalog)

    def test_the_device_draft_never_expires_while_a_web_import_still_does(self) -> None:
        # ADR-0005: a work added offline may wait days for a network, so
        # expiring it would be exactly the loss the decision prevents.
        result = self._add({"id": "local-1", "title": "Ran", "year": "1985"})
        self.service.create_draft(
            self.user_id, "lista.txt", "txt", "Rashomon (1950)\n", None, self.catalog
        )
        self.assertEqual(len(self.service.list_drafts(self.user_id)), 2)

        self.now += 90 * 24 * 60 * 60
        self.service.repository.purge_expired(self.now)
        remaining = self.service.list_drafts(self.user_id)
        self.assertEqual([row["origin"] for row in remaining], [DEVICE_ORIGIN])
        self.assertEqual(remaining[0]["id"], result["draft_id"])

    def test_a_phone_draft_can_be_applied_in_the_browser(self) -> None:
        # A phone draft carries expires_at = 0, meaning "never". Claiming a draft
        # for apply compared that against the clock as if it were a real deadline,
        # found it already past, and refused with "being applied" -- so a work a
        # phone had sent could be received but never applied.
        first = self._add({"id": "local-1", "title": "Stalker", "year": "1979"})
        repository = JsonCatalogRepository(
            Path(self.temporary.name) / "catalog.json", normalize_item
        )
        repository.write([])

        result = self.service.apply_draft(
            self.user_id,
            str(first["draft_id"]),
            "catalog",
            ["local-1"],
            CatalogService(repository),
            [],
        )

        self.assertEqual(result["summary"]["added"], 1)
        self.assertEqual([item.title for item in repository.read()], ["Stalker"])
        (summary,) = self.service.list_drafts(self.user_id)
        self.assertEqual(summary["status"], "applied")

    # [X6.1]: a receipt outlives the draft, so a retry is judged against it.

    def _receipt(self, client_id: str, user_id: str = "") -> Any:
        found = self.service.repository.receipts_for(user_id or self.user_id, [client_id])
        return found.get(client_id)

    def _apply(self, draft_id: str, *client_ids: str) -> dict[str, Any]:
        repository = JsonCatalogRepository(
            Path(self.temporary.name) / "catalog.json", normalize_item
        )
        repository.write([])
        result: dict[str, Any] = self.service.apply_draft(
            self.user_id, draft_id, "catalog", list(client_ids), CatalogService(repository), []
        )
        return result

    def test_every_work_sent_leaves_a_pending_receipt_naming_its_draft(self) -> None:
        result = self._add({"id": "local-1", "title": "Stalker", "year": "1979"})

        receipt = self._receipt("local-1")

        self.assertEqual(receipt.state, "pending")
        self.assertEqual(receipt.draft_id, result["draft_id"])

    def test_a_work_with_no_title_gets_a_discarded_receipt_so_the_phone_stops_waiting(
        self,
    ) -> None:
        self._add({"id": "local-1", "title": "   "})

        receipt = self._receipt("local-1")

        self.assertEqual((receipt.state, receipt.reason), ("discarded", "invalid"))

    def test_a_retry_after_the_draft_was_deleted_does_not_add_the_work_again(self) -> None:
        entry: dict[str, Any] = {"id": "local-1", "title": "Persona", "year": "1966"}
        first = self._add(entry)
        self.service.delete_draft(self.user_id, str(first["draft_id"]), True)

        again = self._add(entry)

        self.assertEqual(again["accepted"], [])
        self.assertEqual(again["duplicates"], ["local-1"])
        self.assertEqual(self.service.list_drafts(self.user_id), [])

    def test_a_retry_after_the_draft_was_applied_does_not_add_the_work_again(self) -> None:
        entry: dict[str, Any] = {"id": "local-1", "title": "Persona", "year": "1966"}
        first = self._add(entry)
        self._apply(str(first["draft_id"]), "local-1")

        again = self._add(entry)

        self.assertEqual(again["accepted"], [])
        self.assertEqual(again["duplicates"], ["local-1"])
        self.assertEqual(len(self.service.list_drafts(self.user_id)), 1)

    def test_receipts_belong_to_the_account_that_sent_the_work(self) -> None:
        self._add({"id": "local-1", "title": "Stalker", "year": "1979"})

        self.assertIsNone(self._receipt("local-1", user_id="someone-else"))

    def test_a_work_in_the_draft_with_no_receipt_gets_one_when_the_phone_retries(self) -> None:
        # Works are stored before their receipts, so a failure in between leaves
        # a work with none. The retry finds it in the draft and repairs that.
        entry: dict[str, Any] = {"id": "local-1", "title": "Stalker", "year": "1979"}
        self._add(entry)

        with closing(sqlite3.connect(self.instance)) as connection:
            connection.execute("DELETE FROM device_receipts")
            connection.commit()
        self.assertIsNone(self._receipt("local-1"))

        again = self._add(entry)

        self.assertEqual(again["duplicates"], ["local-1"])
        self.assertEqual(self._receipt("local-1").state, "pending")

    def test_a_resolved_receipt_is_forgotten_after_the_retention_but_a_pending_one_is_not(
        self,
    ) -> None:
        repository = self.service.repository
        repository.save_receipts(
            self.user_id,
            [
                DeviceReceipt("resolved", "discarded", "deleted"),
                DeviceReceipt("waiting", "pending"),
            ],
            self.now,
        )
        self.now += DEVICE_RECEIPT_RETENTION_SECONDS + 1

        self._add({"id": "local-1", "title": "Stalker", "year": "1979"})

        self.assertIsNone(self._receipt("resolved"))
        self.assertEqual(self._receipt("waiting").state, "pending")

    def test_discarding_a_draft_s_receipts_only_touches_what_was_still_pending(self) -> None:
        repository = self.service.repository
        repository.save_receipts(
            self.user_id,
            [
                DeviceReceipt("waiting", "pending", draft_id="draft-a"),
                DeviceReceipt("done", "applied", "added", "item-1", "draft-a"),
                DeviceReceipt("elsewhere", "pending", draft_id="draft-b"),
            ],
            self.now,
        )

        changed = repository.discard_pending_receipts(self.user_id, "draft-a", "deleted", self.now)

        self.assertEqual(changed, 1)
        self.assertEqual(
            (self._receipt("waiting").state, self._receipt("waiting").reason),
            ("discarded", "deleted"),
        )
        self.assertEqual(self._receipt("done").item_id, "item-1")
        self.assertEqual(self._receipt("elsewhere").state, "pending")

    # [X6.2]: applying or deleting the draft tells the phone what became of each work.

    def _catalog_service(self) -> tuple[CatalogService, JsonCatalogRepository]:
        repository = JsonCatalogRepository(
            Path(self.temporary.name) / "catalog.json", normalize_item
        )
        repository.write([])
        return CatalogService(repository), repository

    def test_an_added_work_is_applied_and_names_the_catalogue_item_it_became(self) -> None:
        first = self._add({"id": "local-1", "title": "Stalker", "year": "1979"})
        service, repository = self._catalog_service()

        self.service.apply_draft(
            self.user_id, str(first["draft_id"]), "catalog", ["local-1"], service, []
        )

        receipt = self._receipt("local-1")
        (created,) = repository.read()
        self.assertEqual((receipt.state, receipt.reason), ("applied", "added"))
        self.assertEqual(receipt.item_id, created.id)

    def test_a_work_nobody_selected_is_discarded_because_the_draft_is_not_reopened(self) -> None:
        first = self._add(
            {"id": "local-1", "title": "Stalker", "year": "1979"},
            {"id": "local-2", "title": "Solaris", "year": "1972"},
        )
        service, _ = self._catalog_service()

        self.service.apply_draft(
            self.user_id, str(first["draft_id"]), "catalog", ["local-1"], service, []
        )

        self.assertEqual(self._receipt("local-1").state, "applied")
        self.assertEqual(
            (self._receipt("local-2").state, self._receipt("local-2").reason),
            ("discarded", "not_applied"),
        )

    def test_a_work_that_stayed_in_review_is_not_linked_to_a_catalogue_guess(self) -> None:
        # Invariant 3: a doubtful match is a person's decision, so the phone is
        # never pointed at the candidate. It learns the work was not applied.
        self.catalog.append(normalize_item({"id": "persona", "title": "Persona", "year": "1966"}))
        first = self._add({"id": "local-1", "title": "Persona", "year": "1966"})
        self.assertEqual(first["accepted"][0]["state"], "review")
        service, repository = self._catalog_service()

        self.service.apply_draft(
            self.user_id, str(first["draft_id"]), "catalog", ["local-1"], service, self.catalog
        )

        receipt = self._receipt("local-1")
        self.assertEqual(
            (receipt.state, receipt.reason, receipt.item_id), ("discarded", "not_applied", "")
        )
        self.assertEqual(repository.read(), [])

    def test_a_draft_put_into_a_collection_leaves_no_catalogue_work_to_link(self) -> None:
        first = self._add(
            {"id": "local-1", "title": "Stalker", "year": "1979"},
            {"id": "local-2", "title": "Solaris", "year": "1972"},
        )
        service, repository = self._catalog_service()

        self.service.apply_draft(
            self.user_id,
            str(first["draft_id"]),
            "collection",
            ["local-1"],
            service,
            [],
            collection_title="Del telefono",
            can_create_collection=True,
        )

        self.assertEqual(self._receipt("local-1").reason, "collection")
        self.assertEqual(self._receipt("local-2").reason, "not_applied")
        self.assertEqual(repository.read(), [])

    def test_deleting_the_draft_discards_what_was_still_waiting_in_it(self) -> None:
        first = self._add({"id": "local-1", "title": "Stalker", "year": "1979"})

        self.service.delete_draft(self.user_id, str(first["draft_id"]), True)

        receipt = self._receipt("local-1")
        self.assertEqual((receipt.state, receipt.reason), ("discarded", "deleted"))

    def test_deleting_a_draft_leaves_an_applied_work_applied(self) -> None:
        first = self._add({"id": "local-1", "title": "Stalker", "year": "1979"})
        service, _ = self._catalog_service()
        self.service.apply_draft(
            self.user_id, str(first["draft_id"]), "catalog", ["local-1"], service, []
        )

        self.service.delete_draft(self.user_id, str(first["draft_id"]), True)

        self.assertEqual(self._receipt("local-1").state, "applied")

    def test_an_apply_that_failed_resolves_nothing(self) -> None:
        class Failing(CatalogService):
            def append_items(self, incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
                raise RuntimeError("the catalogue could not be written")

        first = self._add({"id": "local-1", "title": "Stalker", "year": "1979"})
        _, repository = self._catalog_service()

        with self.assertRaises(RuntimeError):
            self.service.apply_draft(
                self.user_id,
                str(first["draft_id"]),
                "catalog",
                ["local-1"],
                Failing(repository),
                [],
            )

        self.assertEqual(self._receipt("local-1").state, "pending")

    def test_a_work_the_catalogue_already_held_names_that_existing_item(self) -> None:
        # Reachable only through a strong match, which a phone entry -- no
        # identifiers, only what was typed -- almost never has; kept honest here.
        draft = ImportDraft(
            id="draft-1",
            user_id=self.user_id,
            source_name="x",
            source_format="json",
            source_hash="h",
            status="applied",
            created_at=1,
            updated_at=1,
            expires_at=0,
            origin=DEVICE_ORIGIN,
            items=(
                ImportDraftItem(
                    "local-1",
                    0,
                    "present",
                    "already_in_catalog",
                    "Heat",
                    {"id": "draft-side-id", "title": "Heat"},
                    ({"id": "catalogue-side-id", "title": "Heat"},),
                    True,
                ),
            ),
        )
        result = {
            "destination": "catalog",
            "results": [
                {"draft_item_id": "local-1", "outcome": "present", "item_id": "draft-side-id"}
            ],
        }

        self.service._resolve_device_receipts(self.user_id, draft, result, {"local-1"}, self.now)

        receipt = self._receipt("local-1")
        self.assertEqual(
            (receipt.state, receipt.reason, receipt.item_id),
            ("applied", "already_in_catalog", "catalogue-side-id"),
        )

    def test_a_web_import_still_says_it_came_from_the_web(self) -> None:
        created = self.service.create_draft(
            self.user_id, "lista.txt", "txt", "Rashomon (1950)\n", None, self.catalog
        )
        self.assertEqual(created["origin"], WEB_ORIGIN)


class DeviceDraftApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.catalog_path = root / "catalog.json"
        JsonCatalogRepository(self.catalog_path, normalize_item).write([normalize_item(HEAT)])
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
        )
        self.context = TestClient(create_app(self.config), base_url="http://127.0.0.1:8765")
        self.client = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        session = self.client.post(
            "/api/v1/auth/login",
            content=json.dumps(
                {"username": "lucas", "password": self.password, "device_name": "Pixel"}
            ),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(session.status_code, 201, session.content)
        self.bearer = {
            "Authorization": f"Bearer {session.json()['access_token']}",
            "Content-Type": "application/json",
        }

    def _post(self, payload: dict[str, Any]) -> Any:
        return self.client.post(
            "/api/v1/catalog/drafts", content=json.dumps(payload), headers=self.bearer
        )

    def test_the_whole_path_works_over_the_device_api(self) -> None:
        response = self._post(
            {
                "items": [
                    {"id": "local-1", "title": "El boton de nacar", "year": "2015"},
                    {"id": "local-2", "title": "Heat", "year": "1995"},
                ]
            }
        )
        self.assertEqual(response.status_code, 200, response.content)
        states = {row["id"]: row["state"] for row in response.json()["accepted"]}
        # "review" for Heat, not "present": the phone sent a title and a year,
        # and the catalogue entry is identified by tmdb_id. A resemblance is not
        # proof, so it goes to a person.
        self.assertEqual(states, {"local-1": "new", "local-2": "review"})

        # The catalogue file is untouched: this endpoint only ever parks work
        # for review.
        stored = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in stored["items"]], ["heat"])

    def test_a_retry_over_the_wire_is_reported_rather_than_stored_twice(self) -> None:
        payload: dict[str, Any] = {"items": [{"id": "local-1", "title": "Stalker", "year": "1979"}]}
        self.assertEqual(self._post(payload).status_code, 200)
        again = self._post(payload)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["duplicates"], ["local-1"])
        self.assertEqual(again.json()["counts"]["total"], 1)

    def test_a_shapeless_body_is_refused(self) -> None:
        shapeless: list[dict[str, Any]] = [
            {},
            {"items": []},
            {"items": "Heat"},
            {"items": ["Heat"]},
        ]
        for payload in shapeless:
            with self.subTest(payload=payload):
                self.assertEqual(self._post(payload).status_code, 400)

    def test_it_needs_a_device_session(self) -> None:
        anonymous = self.client.post(
            "/api/v1/catalog/drafts",
            content=json.dumps({"items": [{"id": "x", "title": "Heat"}]}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(anonymous.status_code, 401)


if __name__ == "__main__":
    unittest.main()
