from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "movie_inbox" / "web" / "static"


class ElementIndex(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, dict[str, str]]] = []
        self.elements: dict[str, tuple[dict[str, str], tuple[str, ...]]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        element_id = values.get("id")
        if element_id:
            self.elements[element_id] = (values, tuple(parent[0] for parent in self.stack))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}:
            self.stack.append((tag, values))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


class FrontendQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (STATIC / "index.html").read_text(encoding="utf-8")
        cls.login_html = (STATIC / "login.html").read_text(encoding="utf-8")
        cls.css = (STATIC / "style.css").read_text(encoding="utf-8")
        cls.javascript = (STATIC / "app.js").read_text(encoding="utf-8")
        cls.index = ElementIndex()
        cls.index.feed(cls.html)

    def test_primary_actions_have_aa_contrast_at_both_gradient_stops(self) -> None:
        tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", self.css))
        foreground = tokens["on-accent"]
        self.assertGreaterEqual(contrast_ratio(foreground, tokens["red"]), 4.5)
        self.assertGreaterEqual(contrast_ratio(foreground, tokens["action-primary-end"]), 4.5)
        self.assertIn("color: var(--on-accent);", self.css)
        self.assertNotRegex(self.css, r"background:\s*var\(--red\);[^}]*color:\s*#fff")

    def test_structural_regions_are_not_live_announcements(self) -> None:
        structural_ids = {
            "clubCatalogPanel",
            "collectionList",
            "collectionDetailPanel",
            "curationDetail",
            "importDraftList",
            "importReviewPanel",
            "scannerQueue",
            "scannerQueueDetail",
            "libraryList",
            "memberList",
        }
        for element_id in structural_ids:
            attrs, _ancestors = self.index.elements[element_id]
            self.assertNotIn("aria-live", attrs, element_id)

    def test_description_dialog_has_name_description_and_focus_management(self) -> None:
        attrs, _ancestors = self.index.elements["descriptionDialog"]
        self.assertEqual(attrs.get("aria-labelledby"), "descriptionDialogTitle")
        self.assertEqual(attrs.get("aria-describedby"), "descriptionDialogText")
        self.assertIn("function restoreDescriptionFocus()", self.javascript)
        self.assertIn("fields.closeDescriptionDialog.focus();", self.javascript)

    def test_header_separates_navigation_from_commands(self) -> None:
        _attrs, random_ancestors = self.index.elements["randomButton"]
        self.assertNotIn("nav", random_ancestors)
        for element_id in ("homeButton", "catalogButton", "inboxButton", "clubButton"):
            _attrs, ancestors = self.index.elements[element_id]
            self.assertIn("nav", ancestors)
        self.assertNotIn("mobileRandomCatalogOnly", self.html)

    def test_minimum_label_size_and_high_contrast_fallback_are_present(self) -> None:
        self.assertNotRegex(self.css, r"font-size:\s*[89]px")
        self.assertIn("--text-label: 10px", self.css)
        self.assertIn("@media (forced-colors: active)", self.css)
        self.assertRegex(self.css, r"h1\s*\{[^}]*background:\s*none;[^}]*color:\s*CanvasText;")
        self.assertRegex(self.css, r"h1\s*\{[^}]*overflow-wrap:\s*anywhere")

    def test_login_photo_is_decorative_without_an_empty_landmark(self) -> None:
        self.assertNotIn('<aside class="login-member-photo"', self.login_html)
        self.assertIn('<div class="login-member-photo" aria-hidden="true">', self.login_html)

    def test_catalog_view_model_is_precomputed(self) -> None:
        self.assertIn("function prepareCatalogViewModel()", self.javascript)
        self.assertIn("catalogSearchIndex = searchIndex", self.javascript)
        self.assertIn("fields.total.textContent = catalogMetrics.total", self.javascript)


if __name__ == "__main__":
    unittest.main()
