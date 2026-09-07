"""Characterisation of the device item id as a sync key ([MB1], ADR-0005).

The mobile direction stores a local replica and needs a key that survives across
syncs. These tests pin what the current opaque id actually guarantees, so the
[A1] extension ADR-0005 asks for is grounded in measured behaviour rather than
an assumption. They assert today's properties; none of them prescribes a fix.
"""

from __future__ import annotations

import unittest

from movie_inbox.web.routers.device_catalog import _opaque_item_id


class OpaqueItemIdTests(unittest.TestCase):
    def test_it_is_stable_while_nothing_around_it_changes(self) -> None:
        first = _opaque_item_id(b"secreto", "catalogo-1", "/datos/catalog.json", "heat")
        second = _opaque_item_id(b"secreto", "catalogo-1", "/datos/catalog.json", "heat")
        self.assertEqual(first, second)

    def test_it_does_not_leak_the_path_or_the_catalogue_item_id(self) -> None:
        opaque = _opaque_item_id(b"secreto", "catalogo-1", "/datos/privado/catalog.json", "heat")
        self.assertNotIn("privado", opaque)
        self.assertNotIn("catalog.json", opaque)
        self.assertNotIn("heat", opaque)

    def test_rotating_the_api_token_changes_every_id(self) -> None:
        # The secret is viewer_config.api_token. Rotating it re-keys the whole
        # catalogue, so a client that stored ids can no longer match its replica.
        # This is why ADR-0005 asks [A1] for a sync key independent of that token.
        before = _opaque_item_id(b"token-viejo", "catalogo-1", "/datos/catalog.json", "heat")
        after = _opaque_item_id(b"token-nuevo", "catalogo-1", "/datos/catalog.json", "heat")
        self.assertNotEqual(before, after)

    def test_moving_the_catalogue_file_changes_the_id_of_every_work(self) -> None:
        # The source file is part of the message, so relocating a catalogue --
        # a normal operation -- also re-keys it.
        before = _opaque_item_id(b"secreto", "catalogo-1", "/datos/catalog.json", "heat")
        after = _opaque_item_id(b"secreto", "catalogo-1", "/otro/catalog.json", "heat")
        self.assertNotEqual(before, after)

    def test_distinct_works_and_catalogues_never_collide(self) -> None:
        base = _opaque_item_id(b"secreto", "catalogo-1", "/datos/catalog.json", "heat")
        other_item = _opaque_item_id(b"secreto", "catalogo-1", "/datos/catalog.json", "akira")
        other_catalog = _opaque_item_id(b"secreto", "catalogo-2", "/datos/catalog.json", "heat")
        self.assertNotEqual(base, other_item)
        self.assertNotEqual(base, other_catalog)

    def test_the_separator_cannot_be_forged_from_field_contents(self) -> None:
        # Fields are joined with \x1f, which cannot appear in a path or an id,
        # so two different tuples cannot be made to produce the same message.
        self.assertNotEqual(
            _opaque_item_id(b"s", "a", "b", "c"),
            _opaque_item_id(b"s", "a\x1fb", "", "c"),
        )


if __name__ == "__main__":
    unittest.main()
