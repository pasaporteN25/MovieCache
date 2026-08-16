from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from movie_inbox.application.search_evaluation import (
    SearchCorpusError,
    evaluate_search_corpus,
    inspect_catalog_search,
    validate_search_corpus,
)
from movie_inbox.cli.search_lab import main, render_html_report
from movie_inbox.search_lab import load_builtin_corpus


class SearchLabTests(unittest.TestCase):
    def test_builtin_corpus_meets_the_v030_quality_gate(self) -> None:
        # The four docs/search-quality.md problems (short tokens, secondary
        # metadata, weak year-mismatch penalty, no external relevance floor)
        # plus a numeric-title parsing bug in parse_search_query are all fixed.
        # This corpus run is the "prueba manual con un snapshot de catalogo que
        # no permita escrituras" the v0.3.0 exit gate (docs/roadmap.md) calls for.
        corpus = load_builtin_corpus()

        report = evaluate_search_corpus(corpus)

        self.assertEqual(report["algorithm"], "production-baseline")
        self.assertEqual(report["corpus"]["case_count"], 22)
        self.assertEqual(
            set(report["metrics"]["by_context"]), {"catalog", "external", "identity", "scanner"}
        )
        self.assertEqual(report["metrics"]["forbidden_hits"], 0)
        self.assertEqual(report["metrics"]["auto_match_precision"], 1.0)
        self.assertEqual(report["metrics"]["auto_match_false_positives"], 0)
        self.assertGreaterEqual(report["metrics"]["precision_at_5"], 0.9)
        self.assertGreaterEqual(report["metrics"]["mrr"], 0.9)
        self.assertGreaterEqual(report["metrics"]["recall_at_5"], 0.9)
        self.assertTrue(report["gate"]["passed"])

    def test_enforced_baseline_now_passes(self) -> None:
        with redirect_stdout(io.StringIO()):
            baseline_status = main(["run"])
            enforced_status = main(["run", "--enforce"])

        self.assertEqual(baseline_status, 0)
        self.assertEqual(enforced_status, 0)

    def test_reports_do_not_modify_the_input_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus_path = root / "corpus.json"
            json_report = root / "report.json"
            html_report = root / "report.html"
            original = json.dumps(load_builtin_corpus(), ensure_ascii=False, indent=2) + "\n"
            corpus_path.write_text(original, encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                status = main(
                    [
                        "run",
                        "--corpus",
                        str(corpus_path),
                        "--json",
                        str(json_report),
                        "--html",
                        str(html_report),
                    ]
                )

            self.assertEqual(status, 0)
            self.assertEqual(corpus_path.read_text(encoding="utf-8"), original)
            self.assertEqual(
                json.loads(json_report.read_text(encoding="utf-8"))["report_type"], "search_corpus"
            )
            self.assertIn(
                "Movie Inbox / lectura solamente", html_report.read_text(encoding="utf-8")
            )
            self.assertFalse((root / ".corpus.json.lock").exists())

    def test_report_target_cannot_overwrite_the_read_only_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            corpus_path = Path(temporary) / "corpus.json"
            original = json.dumps(load_builtin_corpus(), ensure_ascii=False)
            corpus_path.write_text(original, encoding="utf-8")

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                status = main(["run", "--corpus", str(corpus_path), "--json", str(corpus_path)])

            self.assertEqual(status, 2)
            self.assertEqual(corpus_path.read_text(encoding="utf-8"), original)

    def test_inspection_reads_a_legacy_json_export_without_lock_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog_path = root / "catalog.json"
            report_path = root / "inspection.json"
            catalog_path.write_text(
                json.dumps([{"id": "heat", "title": "Heat", "year": "1995", "kind": "pelicula"}]),
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                status = main(
                    [
                        "inspect",
                        str(catalog_path),
                        "Heat",
                        "--json",
                        str(report_path),
                    ]
                )

            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(report_path.read_text(encoding="utf-8"))["results"][0]["id"], "heat"
            )
            self.assertFalse((root / ".catalog.json.lock").exists())

    def test_identity_and_scanner_inspection_expose_current_evidence(self) -> None:
        items = [
            {"id": "fly-1958", "title": "The Fly", "year": "1958", "kind": "pelicula"},
            {"id": "fly-1986", "title": "The Fly", "year": "1986", "kind": "pelicula"},
        ]

        identity = inspect_catalog_search(items, "The Fly", mode="identity", year="1986")
        scanner = inspect_catalog_search(items, "The Fly", mode="scanner", year="1986")

        self.assertEqual(identity["results"][0]["id"], "fly-1986")
        self.assertTrue(identity["results"][0]["accepted"])
        self.assertEqual(scanner["classification"], "matched")
        self.assertEqual(scanner["results"][0]["id"], "fly-1986")

    def test_invalid_corpus_and_html_values_are_handled_safely(self) -> None:
        with self.assertRaises(SearchCorpusError):
            validate_search_corpus({"schema_version": 99, "catalog_items": [], "cases": []})

        report = inspect_catalog_search(
            [{"id": "x", "title": "<script>alert(1)</script>"}], "script"
        )
        markup = render_html_report(report)
        self.assertNotIn("<script>alert(1)</script>", markup)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", markup)


if __name__ == "__main__":
    unittest.main()
