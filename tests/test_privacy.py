from __future__ import annotations

import unittest

from movie_inbox.domain.privacy import (
    ItemPrivacyOverride,
    PrivacyPreferences,
    field_is_shared,
    shared_catalog_item,
    shared_watch_history,
)


class PrivacyTests(unittest.TestCase):
    def test_catalog_is_private_by_default(self) -> None:
        preferences = PrivacyPreferences()

        self.assertFalse(preferences.catalog_shared)
        self.assertFalse(field_is_shared("rating", preferences))
        self.assertFalse(field_is_shared("review", preferences))
        self.assertEqual(shared_watch_history([], preferences), [])

    def test_shared_item_uses_allowlist_and_per_item_overrides(self) -> None:
        item = {
            "id": "heat",
            "title": "Heat",
            "year": "1995",
            "status": "watched",
            "watched_at": "2026-07-15",
            "rating": 9,
            "review": "Una favorita",
            "en_catalogo": True,
            "notes": "Private note",
            "local_path": "D:/Movies/Heat.mkv",
            "local_files": [{"path": "D:/Movies/Heat.mkv"}],
            "_source_file": "C:/private/catalog.db",
        }
        preferences = PrivacyPreferences(
            catalog_shared=True,
            share_status=True,
            share_watched_at=False,
            share_rating=False,
            share_review=True,
        )
        override = ItemPrivacyOverride(rating="shared", review="private")

        public = shared_catalog_item(item, preferences, override)

        self.assertEqual(public["status"], "watched")
        self.assertEqual(public["rating"], 9)
        self.assertNotIn("watched_at", public)
        self.assertNotIn("review", public)
        self.assertNotIn("notes", public)
        self.assertNotIn("local_path", public)
        self.assertNotIn("local_files", public)
        self.assertNotIn("_source_file", public)

    def test_shared_history_is_explicit_and_respects_date_visibility(self) -> None:
        items = [
            {"id": "heat", "title": "Heat", "status": "watched", "watched_at": "2026-07-15"},
            {"id": "alien", "title": "Alien", "status": "watched", "watched_at": "2026-07-20"},
            {"id": "arrival", "title": "Arrival", "status": "to_watch", "watched_at": ""},
        ]
        hidden_dates = PrivacyPreferences(catalog_shared=True, share_history=True)
        visible_dates = PrivacyPreferences(
            catalog_shared=True,
            share_history=True,
            share_watched_at=True,
        )

        private_history = shared_watch_history(items, hidden_dates)
        public_history = shared_watch_history(items, visible_dates)

        self.assertEqual([row["id"] for row in private_history], ["alien", "heat"])
        self.assertNotIn("watched_at", private_history[0])
        self.assertEqual(public_history[0]["watched_at"], "2026-07-20")


if __name__ == "__main__":
    unittest.main()
