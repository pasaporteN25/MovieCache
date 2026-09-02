from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "scripts" / "homeserver_package_prototype.py"
INSTANCE_ID = "11111111-1111-4111-8111-111111111111"
PACKAGE_ID = "22222222-2222-4222-8222-222222222222"
CREATED_AT = "2026-09-02T12:00:00Z"


class HomeserverPackagePrototypeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.payload_path = self.root / "collection.json"
        self.package_path = self.root / "collection.mipkg"
        self.payload_path.write_text(json.dumps(self._payload()), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "collection",
            "collection": {"title": "Bergman", "description": "Dos peliculas"},
            "items": [
                {
                    "position": 1,
                    "title": "Fanny and Alexander",
                    "original_title": "Fanny och Alexander",
                    "year": 1982,
                    "kind": "movie",
                    "directors": ["Ingmar Bergman"],
                    "identity": {"imdb_id": "tt0083922", "wikidata_id": "Q1392170"},
                }
            ],
        }

    def run_prototype(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(PROTOTYPE), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def build(self) -> subprocess.CompletedProcess[str]:
        return self.run_prototype(
            "build",
            "--input",
            str(self.payload_path),
            "--output",
            str(self.package_path),
            "--instance-id",
            INSTANCE_ID,
            "--package-id",
            PACKAGE_ID,
            "--created-at",
            CREATED_AT,
        )

    def test_manual_package_builds_and_inspects_without_network(self) -> None:
        built = self.build()

        self.assertEqual(built.returncode, 0, built.stderr)
        self.assertTrue(self.package_path.is_file())
        build_summary = json.loads(built.stdout)
        self.assertEqual(build_summary["network"], "none")
        self.assertIn("not a signature", build_summary["trust"])
        with zipfile.ZipFile(self.package_path) as archive:
            self.assertEqual(set(archive.namelist()), {"manifest.json", "payload.json"})
            self.assertEqual(json.loads(archive.read("manifest.json"))["proof"], {"mode": "manual"})

        inspected = self.run_prototype("inspect", "--package", str(self.package_path))

        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        summary = json.loads(inspected.stdout)
        self.assertEqual(summary["package_id"], PACKAGE_ID)
        self.assertEqual(summary["source_instance_id"], INSTANCE_ID)
        self.assertEqual(summary["items"], 1)

    def test_inspect_rejects_payload_changed_after_its_digest(self) -> None:
        self.assertEqual(self.build().returncode, 0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.package_path, "a") as archive:
                archive.writestr("payload.json", b'{"not":"the original payload"}')

        result = self.run_prototype("inspect", "--package", str(self.package_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("duplicate ZIP entries", result.stderr)

    def test_build_rejects_private_or_unknown_item_fields(self) -> None:
        payload = self._payload()
        item = payload["items"]
        assert isinstance(item, list)
        item[0]["local_path"] = "D:/Movies/private.mkv"
        self.payload_path.write_text(json.dumps(payload), encoding="utf-8")

        result = self.build()

        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported fields: local_path", result.stderr)

    def test_inspect_rejects_extra_zip_entries_instead_of_extracting_them(self) -> None:
        self.assertEqual(self.build().returncode, 0)
        with zipfile.ZipFile(self.package_path, "a") as archive:
            archive.writestr("../../owner.json", b"not read")

        result = self.run_prototype("inspect", "--package", str(self.package_path))

        self.assertEqual(result.returncode, 2)
        self.assertIn("must contain exactly", result.stderr)
