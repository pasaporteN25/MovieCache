"""[A2.4]: the vectors a phone's charades generator is tested against.

A phone deals charades offline with its own port of the generator, and two players
only share a deck if both ports agree byte for byte. The vectors in
docs/briefs/charades-v1-vectors.json are that agreement. This test recomputes every
one of them from the server's generator, so a change here that would make installed
phones deal different decks fails loudly instead of silently.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from movie_inbox.domain import charades as generator
from movie_inbox.domain.charades import CharadeWork, build_deck, deck_fingerprint, deck_seed

VECTORS = Path(__file__).resolve().parents[1] / "docs" / "briefs" / "charades-v1-vectors.json"


class CharadesVectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vectors: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_the_documented_constants_are_the_generator_s(self) -> None:
        documented = self.vectors["generator"]
        self.assertEqual(documented["fnv1a_32"]["offset_basis"], generator._FNV_OFFSET)
        self.assertEqual(documented["fnv1a_32"]["prime"], generator._FNV_PRIME)
        self.assertEqual(documented["lcg"]["multiplier"], generator._LCG_MULTIPLIER)
        self.assertEqual(documented["lcg"]["increment"], generator._LCG_INCREMENT)
        self.assertEqual(documented["lcg"]["modulus"], generator._MASK32 + 1)

    def test_fnv1a(self) -> None:
        for case in self.vectors["fnv1a"]:
            with self.subTest(text=case["input"]):
                # With no options, the seed is FNV-1a over the fingerprint alone.
                self.assertEqual(deck_seed([], case["input"]), case["output"])

    def test_fingerprints(self) -> None:
        for case in self.vectors["fingerprints"]:
            with self.subTest(keys=case["keys"]):
                self.assertEqual(deck_fingerprint(case["keys"]), case["output"])

    def test_seeds(self) -> None:
        for case in self.vectors["seeds"]:
            with self.subTest(options=case["options"]):
                self.assertEqual(deck_seed(case["options"], case["fingerprint"]), case["output"])

    def test_decks(self) -> None:
        for case in self.vectors["decks"]:
            with self.subTest(size=case["size"], keys=len(case["keys"])):
                works = [CharadeWork(key=key, title=key) for key in case["keys"]]
                dealt = build_deck(works, case["seed"], case["size"])
                self.assertEqual([work.key for work in dealt], case["output"])

    def test_the_order_trap_is_really_a_trap(self) -> None:
        # The vector is only worth having if code point order and UTF-16 order
        # disagree on it; otherwise a wrong port would pass it.
        keys = self.vectors["fingerprints"][3]["keys"]
        by_code_point = sorted(keys)
        by_utf16_unit = sorted(keys, key=lambda key: key.encode("utf-16-be"))
        self.assertNotEqual(by_code_point, by_utf16_unit)


if __name__ == "__main__":
    unittest.main()
