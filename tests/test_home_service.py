from __future__ import annotations

import unittest

from movie_inbox.application.home_service import EditorialHomeService, home_image_items
from movie_inbox.domain.collections import CollectionItem, CuratedCollection


class EditorialHomeServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = EditorialHomeService()

    def test_programming_is_stable_bounded_and_does_not_repeat_catalog_items(self) -> None:
        catalog = [
            movie(
                f"pending-{index}",
                en_catalogo=True,
                page_image=f"https://upload.wikimedia.org/poster-{index}.jpg",
                directors=["Director comun"],
                genres=["Drama"],
                year=str(1980 + index),
            )
            for index in range(16)
        ]

        first = self.service.build("lucas", "2026-08-10", catalog)
        second = self.service.build("lucas", "2026-08-10", list(reversed(catalog)))

        self.assertEqual(first, second)
        self.assertEqual(len(first["featured"]), 4)
        self.assertEqual(first["hero"], first["featured"][0])
        self.assertEqual(first["hero"]["reason"]["code"], "available_pending")
        self.assertTrue(all(entry["item"]["en_catalogo"] for entry in first["featured"]))
        self.assertTrue(all(entry["item"]["status"] == "to_watch" for entry in first["featured"]))
        self.assertLessEqual(len(first["sections"]), 5)
        self.assertTrue(all(len(section["items"]) <= 6 for section in first["sections"]))

        personal_keys = [entry["key"] for entry in first["featured"]]
        personal_keys.extend(
            entry["key"]
            for section in first["sections"]
            for entry in section["items"]
            if entry["origin"]["kind"] == "catalog"
        )
        self.assertEqual(len(personal_keys), len(set(personal_keys)))
        self.assertLessEqual(len(home_image_items(first)), 34)

        available = next(row for row in first["sections"] if row["id"] == "available")
        self.assertEqual(
            available["action"]["filters"],
            {"status": ["to_watch"], "availability": ["available"]},
        )

    def test_release_anniversary_requires_a_complete_date(self) -> None:
        exact = movie(
            "anniversary",
            release_dates=[
                {
                    "date": "1998-08-10",
                    "precision": "day",
                    "country": "",
                    "release_type": "publication",
                    "source": "wikidata",
                    "source_url": "https://www.wikidata.org/wiki/Q1",
                    "is_primary": True,
                }
            ],
        )
        year_only = movie(
            "year-only",
            release_dates=[
                {
                    "date": "1998",
                    "precision": "year",
                    "country": "",
                    "release_type": "publication",
                    "source": "wikidata",
                    "source_url": "https://www.wikidata.org/wiki/Q2",
                    "is_primary": True,
                }
            ],
        )

        payload = self.service.build("lucas", "2026-08-10", [exact, year_only])

        section = next(row for row in payload["sections"] if row["id"] == "anniversary")
        self.assertEqual([entry["item"]["id"] for entry in section["items"]], ["anniversary"])
        self.assertEqual(section["items"][0]["reason"]["code"], "release_anniversary")
        self.assertEqual(section["action"]["filters"], {"release_day": ["08-10"]})

    def test_followed_collections_only_offer_missing_deduplicated_works(self) -> None:
        catalog = [movie("present", title="Present")]
        followed = collection(
            "followed",
            True,
            [
                movie("present", title="Present"),
                movie("missing", title="Missing", year="1999"),
                movie("missing", title="Missing", year="1999"),
            ],
        )
        ignored = collection("ignored", False, [movie("other", title="Other")])

        payload = self.service.build(
            "lucas",
            "2026-08-10",
            catalog,
            [followed, ignored],
        )

        section = next(row for row in payload["sections"] if row["id"] == "followed")
        self.assertEqual(len(section["items"]), 1)
        entry = section["items"][0]
        self.assertEqual(entry["item"]["id"], "missing")
        self.assertEqual(entry["origin"]["collection_id"], "followed")
        self.assertEqual(entry["origin"]["collection_item_id"], "missing-2")
        self.assertEqual(entry["reason"]["code"], "followed_collection")

    def test_memory_reasons_distinguish_missing_rating_and_review(self) -> None:
        catalog = [
            movie("both", status="watched", rating=0, review=""),
            movie("rating", status="watched", rating=0, review="Guardada"),
            movie("review", status="watched", rating=8, review=""),
            movie("complete", status="watched", rating=8, review="Completa"),
        ]

        payload = self.service.build("lucas", "2026-08-10", catalog)

        section = next(row for row in payload["sections"] if row["id"] == "memory")
        reasons = {entry["item"]["id"]: entry["reason"]["code"] for entry in section["items"]}
        self.assertEqual(reasons["both"], "watched_without_record")
        self.assertEqual(reasons["rating"], "watched_without_rating")
        self.assertEqual(reasons["review"], "watched_without_review")
        self.assertNotIn("complete", reasons)
        self.assertEqual(
            section["action"]["filters"],
            {"status": ["watched"], "record": ["unrated", "unreviewed"]},
        )

    def test_route_uses_existing_metadata_and_recent_items_are_the_fallback(self) -> None:
        routed = [
            movie(
                f"route-{index}",
                title=f"Route {index}",
                directors=["Ada Directora"],
                genres=["Misterio"],
                year=str(1971 + index),
                rating=8,
                review="Completa",
            )
            for index in range(4)
        ]
        payload = self.service.build("lucas", "2026-08-10", routed)
        route = next(row for row in payload["sections"] if row["id"] == "route")
        self.assertGreaterEqual(len(route["items"]), 3)
        self.assertTrue(
            all(entry["reason"]["code"] in {"shared_director", "shared_genre"} for entry in route["items"])
        )
        route_reason = route["items"][0]["reason"]["code"]
        expected_filter = "director" if route_reason == "shared_director" else "genre"
        self.assertEqual(list(route["action"]["filters"]), [expected_filter])

        recent_payload = self.service.build(
            "lucas",
            "2026-08-10",
            [
                movie("older", title="Older", added_at="2026-01-01T00:00:00+00:00"),
                movie("newer", title="Newer", added_at="2026-08-01T00:00:00+00:00"),
            ],
        )
        recent = next(row for row in recent_payload["sections"] if row["id"] == "recent")
        self.assertEqual([entry["item"]["id"] for entry in recent["items"]], ["newer", "older"])
        self.assertEqual(recent["action"]["filters"], {"sort": "added-desc"})

    def test_available_watched_item_is_a_valid_hero_fallback(self) -> None:
        payload = self.service.build(
            "lucas",
            "2026-08-10",
            [movie("watched", status="watched", en_catalogo=True, rating=8, review="Completa")],
        )

        self.assertEqual(payload["hero"]["item"]["id"], "watched")
        self.assertEqual(payload["hero"]["reason"]["code"], "available_revisit")
        self.assertEqual(len(payload["featured"]), 1)

    def test_invalid_local_date_is_rejected(self) -> None:
        for value in ("", "10-08-2026", "2026-02-30", "2026-8-10"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid_home_date"):
                self.service.build("lucas", value, [])


def movie(item_id: str, **changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": item_id,
        "title": item_id.title(),
        "kind": "pelicula",
        "status": "to_watch",
        "watched_at": "",
        "rating": 0,
        "review": "",
        "year": "",
        "genres": [],
        "directors": [],
        "en_catalogo": False,
        "page_image": "",
        "backdrop_image": "",
        "added_at": "",
    }
    row.update(changes)
    return row


def collection(
    collection_id: str,
    followed: bool,
    items: list[dict[str, object]],
) -> CuratedCollection:
    entries = tuple(
        CollectionItem(
            id=f"{str(item['id'])}-{index}",
            position=index,
            item=dict(item),
        )
        for index, item in enumerate(items, start=1)
    )
    return CuratedCollection(
        id=collection_id,
        slug=collection_id,
        title=collection_id.title(),
        description="Collection",
        owner_user_id="owner",
        visibility="published",
        followed=followed,
        items=entries,
    )


if __name__ == "__main__":
    unittest.main()
