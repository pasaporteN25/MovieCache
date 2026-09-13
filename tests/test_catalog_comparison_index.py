"""[B1]: comparing a list against a catalogue re-normalised the catalogue every time.

`possible_duplicate_candidates` compares one item against every catalogue item
and recomputes each catalogue item's title keys while doing it. Once that is
cheap. Once per item in a list it is the entire cost, and three surfaces do
exactly that: opening a collection, refreshing an import draft, and building the
home page out of followed collections.

Measured on a 5000-item catalogue before any of this existed: normalising it
takes 0.124s, and a 200-item collection did that 200 times -- 24.9s of the 28s
the page spent, against 2.3s of actual comparing. Prepared once instead, the
same work takes 2.8s.

The assertions here count calls rather than seconds, because a timing assertion
in a test suite measures the machine that runs it.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from movie_inbox.domain import catalog as catalog_module
from movie_inbox.domain.catalog import (
    CatalogComparisonIndex,
    catalog_membership,
    normalize_item,
    possible_duplicate_candidates,
)


def _catalog(count: int) -> list[dict[str, Any]]:
    return [
        normalize_item(
            {"id": f"cat-{index}", "title": f"Pelicula numero {index}", "year": "1999"}
        ).to_dict()
        for index in range(count)
    ]


class PreparedCatalogEquivalenceTests(unittest.TestCase):
    """A prepared catalogue has to answer exactly what a plain list answers."""

    def setUp(self) -> None:
        self.items = [
            normalize_item({"id": "heat", "title": "Heat", "year": "1995"}).to_dict(),
            normalize_item({"id": "fly-1986", "title": "The Fly", "year": "1986"}).to_dict(),
        ]
        self.prepared = CatalogComparisonIndex(self.items)

    def test_the_same_answer_for_a_work_already_in_the_catalogue(self) -> None:
        item = dict(self.items[0])

        self.assertEqual(
            catalog_membership(item, self.items), catalog_membership(item, self.prepared)
        )
        self.assertEqual(catalog_membership(item, self.prepared)["state"], "present")

    def test_the_same_answer_for_a_work_that_needs_review(self) -> None:
        item = normalize_item({"id": "other", "title": "The Fly", "year": ""}).to_dict()

        self.assertEqual(
            catalog_membership(item, self.items), catalog_membership(item, self.prepared)
        )
        self.assertEqual(catalog_membership(item, self.prepared)["state"], "review")

    def test_the_same_answer_for_a_work_nobody_has(self) -> None:
        item = normalize_item({"id": "new", "title": "Suspiria", "year": "1977"}).to_dict()

        self.assertEqual(
            catalog_membership(item, self.items), catalog_membership(item, self.prepared)
        )
        self.assertEqual(catalog_membership(item, self.prepared)["state"], "missing")

    def test_duplicate_candidates_are_the_same_either_way(self) -> None:
        item = normalize_item({"id": "other", "title": "The Fly", "year": "1958"}).to_dict()

        self.assertEqual(
            possible_duplicate_candidates(self.items, item),
            possible_duplicate_candidates(self.prepared, item),
        )


class PreparedCatalogWorkTests(unittest.TestCase):
    def _counted(self):
        real = catalog_module.title_match_keys_for_item
        calls: list[int] = [0]

        def counting(item):
            calls[0] += 1
            return real(item)

        return calls, patch.object(catalog_module, "title_match_keys_for_item", counting)

    def test_each_catalogue_item_is_normalised_once_however_many_comparisons(self) -> None:
        items = _catalog(20)
        collection = [
            normalize_item({"id": f"col-{index}", "title": f"Obra {index}"}).to_dict()
            for index in range(10)
        ]
        prepared = CatalogComparisonIndex(items)
        calls, counting = self._counted()

        with counting:
            for entry in collection:
                catalog_membership(entry, prepared)

        # 20 catalogue items prepared once, plus one call per compared item for
        # its own keys. Without the index it was 20 per compared item.
        self.assertEqual(calls[0], 20 + len(collection))

    def test_an_early_match_does_not_prepare_the_rest_of_the_catalogue(self) -> None:
        # catalog_membership returns as soon as it recognises an id, so a caller
        # that only ever asks once must not pay for the whole catalogue.
        items = _catalog(500)
        prepared = CatalogComparisonIndex(items)
        calls, counting = self._counted()

        with counting:
            catalog_membership(dict(items[2]), prepared)

        self.assertLessEqual(calls[0], 5)

    def test_a_catalogue_that_grows_stays_usable(self) -> None:
        # Copying a collection into the catalogue adds to it as it goes.
        prepared = CatalogComparisonIndex(_catalog(2))
        added = normalize_item({"id": "added", "title": "Suspiria", "year": "1977"}).to_dict()

        self.assertEqual(catalog_membership(added, prepared)["state"], "missing")
        prepared.add(added)

        self.assertEqual(catalog_membership(added, prepared)["state"], "present")
        self.assertEqual(len(prepared), 3)

    def test_a_plain_sequence_still_works_without_anyone_preparing_it(self) -> None:
        items = _catalog(3)

        self.assertEqual(catalog_membership(dict(items[1]), items)["state"], "present")


if __name__ == "__main__":
    unittest.main()
