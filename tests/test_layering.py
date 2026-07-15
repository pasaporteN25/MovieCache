from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LayeringTests(unittest.TestCase):
    def test_domain_and_application_do_not_import_infrastructure_or_web(self) -> None:
        forbidden = (
            "movie_inbox.infrastructure",
            "movie_inbox.external",
            "movie_inbox.web",
            "movie_inbox.cli",
        )
        for layer in ("domain", "application"):
            for path in (ROOT / "src" / "movie_inbox" / layer).glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                modules = {
                    node.module
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                }
                self.assertFalse(
                    any(module.startswith(forbidden) for module in modules),
                    f"{path.name} imports an outer layer",
                )

    def test_batch_commands_do_not_import_web_or_importer_entrypoints(self) -> None:
        forbidden_prefixes = ("movie_inbox.web",)
        for name in ("match_external_links.py", "enrich_catalog.py", "scan_library.py"):
            path = ROOT / "src" / "movie_inbox" / "cli" / name
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            self.assertFalse(
                any(module.startswith(forbidden_prefixes) for module in imported),
                f"{name} imports the presentation layer",
            )

    def test_legacy_entrypoints_are_thin_wrappers(self) -> None:
        for name in ("view_catalog.py", "txt_to_catalog.py", "scan_library.py"):
            lines = (ROOT / "scripts" / name).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), 25, f"{name} contains application logic")


if __name__ == "__main__":
    unittest.main()
