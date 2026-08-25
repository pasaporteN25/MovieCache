from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "movie_inbox" / "web" / "static"

_IMPORT_RE = re.compile(r'@import\s+"([^"]+)";')


def _effective_stylesheet() -> str:
    """style.css is just `@import` lines into static/css/*.css (one file per
    frontend surface). Resolve those imports the way a browser would, so
    token/rule checks below see the same effective stylesheet the app ships."""
    entry = (STATIC / "style.css").read_text(encoding="utf-8")
    imports = _IMPORT_RE.findall(entry)
    assert imports, "expected style.css to @import its per-surface css/*.css files"
    return "\n".join((STATIC / path).read_text(encoding="utf-8") for path in imports)


def relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


class DesignTokenTests(unittest.TestCase):
    """Static checks over CSS custom properties and rules. These read design
    tokens, not copy or markup structure, so they don't need a browser --
    behavioral guarantees live in tests/browser/test_ui_browser.py instead."""

    css: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.css = _effective_stylesheet()

    def test_primary_actions_have_aa_contrast_at_both_gradient_stops(self) -> None:
        tokens = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", self.css))
        foreground = tokens["on-accent"]
        self.assertGreaterEqual(contrast_ratio(foreground, tokens["red"]), 4.5)
        self.assertGreaterEqual(contrast_ratio(foreground, tokens["action-primary-end"]), 4.5)
        self.assertIn("color: var(--on-accent);", self.css)
        self.assertNotRegex(self.css, r"background:\s*var\(--red\);[^}]*color:\s*#fff")

    def test_minimum_label_size_and_high_contrast_fallback_are_present(self) -> None:
        self.assertNotRegex(self.css, r"font-size:\s*[89]px")
        self.assertIn("--text-label: 10px", self.css)
        self.assertIn("@media (forced-colors: active)", self.css)
        self.assertRegex(self.css, r"h1\s*\{[^}]*background:\s*none;[^}]*color:\s*CanvasText;")
        self.assertRegex(self.css, r"h1\s*\{[^}]*overflow-wrap:\s*anywhere")


if __name__ == "__main__":
    unittest.main()
