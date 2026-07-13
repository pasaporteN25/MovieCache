from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LayeringTests(unittest.TestCase):
    def test_batch_commands_do_not_import_web_or_importer_entrypoints(self) -> None:
        forbidden = {"view_catalog", "txt_to_catalog"}
        for name in ("match_external_links.py", "enrich_catalog.py"):
            path = ROOT / "scripts" / name
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".", 1)[0])
            self.assertFalse(forbidden & imported, f"{name} imports a presentation entrypoint")


if __name__ == "__main__":
    unittest.main()
