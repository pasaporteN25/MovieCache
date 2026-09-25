"""[X1.2]: recompute docs/briefs/title-normalization-v1-vectors.json.

The vectors let a client reimplement normalize_search_text, title_match_key and
title_similarity with results identical to the server's, to flag a possible
duplicate the same way the server would. This suite recomputes every value from
the real domain functions, so a change that would change a phone's answer fails
here first.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from movie_inbox.domain.catalog import title_match_key, title_similarity
from movie_inbox.domain.normalization import normalize_search_text

VECTORS = (
    Path(__file__).resolve().parents[1] / "docs" / "briefs" / "title-normalization-v1-vectors.json"
)


class TitleNormalizationVectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vectors: dict[str, Any] = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_normalize_search_text(self) -> None:
        for case in self.vectors["normalize_search_text"]:
            with self.subTest(input=case["input"]):
                self.assertEqual(normalize_search_text(case["input"]), case["output"])

    def test_title_match_key(self) -> None:
        for case in self.vectors["title_match_key"]:
            with self.subTest(input=case["input"]):
                self.assertEqual(title_match_key(case["input"]), case["output"])

    def test_title_similarity(self) -> None:
        for case in self.vectors["title_similarity"]:
            with self.subTest(left=case["left"], right=case["right"]):
                self.assertEqual(title_similarity(case["left"], case["right"]), case["output"])


if __name__ == "__main__":
    unittest.main()
