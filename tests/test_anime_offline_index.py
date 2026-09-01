from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

from movie_inbox.cli.anime_dataset import ANIME_INDEX_FILENAME
from movie_inbox.cli.anime_dataset import main as anime_cli_main
from movie_inbox.external.anime_offline import AnimeOfflineAdapter
from movie_inbox.external.registry import ExternalSourceService
from movie_inbox.infrastructure.anime_offline_index import (
    ANIME_OFFLINE_ATTRIBUTION,
    AnimeOfflineIndexError,
    AnimeOfflineIndexStale,
    anime_index_stats,
    build_anime_index,
    lookup_anime_by_external_id,
    lookup_anime_by_mal_id,
    lookup_anime_by_title,
)
from movie_inbox.infrastructure.external_catalog import (
    configure_external_catalog,
    external_sources_snapshot,
)
from movie_inbox.web.catalog_api import item_from_search_result


class EmptyJikanAdapter:
    name = "jikan"
    label = "Jikan / MyAnimeList"

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def search(self, query: str) -> list[dict[str, Any]]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return []


class SuccessfulJikanAdapter:
    name = "jikan"
    label = "Jikan / MyAnimeList"

    def search(self, query: str) -> list[dict[str, Any]]:
        return [
            {
                "source": "jikan",
                "title": "Death Note",
                "alternative_titles": ["DN"],
                "kind": "anime",
                "year": "2006",
                "url": "https://myanimelist.net/anime/1535",
                "myanimelist_url": "https://myanimelist.net/anime/1535",
                "mal_id": "1535",
            }
        ]


def _metadata() -> dict[str, object]:
    return {
        "$schema": "https://example.test/anime-offline-database.jsonl.schema.json",
        "license": {
            "name": (
                "Open Data Commons Open Database License (ODbL) v1.0 + "
                "Database Contents License (DbCL) v1.0"
            ),
            "url": "https://github.com/manami-project/anime-offline-database/blob/2026-27/LICENSE",
        },
        "repository": "https://github.com/manami-project/anime-offline-database",
        "lastUpdate": "2026-07-04",
    }


def _anime_rows() -> list[dict[str, object]]:
    return [
        {
            "sources": [
                "https://anidb.net/anime/4563",
                "https://anilist.co/anime/1535",
                "https://myanimelist.net/anime/1535",
                "javascript:alert(1)",
            ],
            "title": "Death Note",
            "type": "TV",
            "animeSeason": {"season": "FALL", "year": 2006},
            "synonyms": ["El cuaderno de la muerte", "デスノート", "DEATH NOTE"],
        },
        {
            "sources": [
                "https://anilist.co/anime/1",
                "https://myanimelist.net/anime/1/Cowboy_Bebop",
            ],
            "title": "Cowboy Bebop",
            "type": "TV",
            "animeSeason": {"season": "SPRING", "year": 1998},
            "synonyms": ["カウボーイビバップ"],
        },
    ]


def _write_jsonl(path: Path) -> None:
    rows = [_metadata(), *_anime_rows(), {"title": "Broken", "sources": []}]
    payload = "".join(f"{json.dumps(row, ensure_ascii=False)}\n" for row in rows)
    path.write_text(payload, encoding="utf-8")


class AnimeOfflineIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.snapshot = self.root / "anime-offline-database.jsonl"
        self.index = self.root / ANIME_INDEX_FILENAME
        _write_jsonl(self.snapshot)

    def test_build_is_atomic_versioned_and_reports_snapshot_provenance(self) -> None:
        report = build_anime_index(self.snapshot, self.index)

        self.assertEqual(report.anime_rows, 2)
        self.assertEqual(report.alias_rows, 5)
        self.assertEqual(report.external_id_rows, 5)
        self.assertEqual(report.skipped_rows, 1)
        self.assertEqual(report.snapshot_date, "2026-07-04")
        self.assertEqual(len(report.snapshot_sha256), 64)
        self.assertGreater(report.index_size_bytes, 0)
        self.assertNotIn("javascript", self.index.read_bytes().decode("utf-8", errors="ignore"))

        original = self.index.read_bytes()
        invalid = self.root / "invalid.json"
        invalid.write_text('{"data": []}', encoding="utf-8")
        with self.assertRaises(AnimeOfflineIndexError):
            build_anime_index(invalid, self.index)
        self.assertEqual(self.index.read_bytes(), original)

    def test_lookup_uses_multilingual_aliases_and_cross_references(self) -> None:
        build_anime_index(self.snapshot, self.index)

        spanish = lookup_anime_by_title(self.index, "cuaderno de la muerte")
        japanese = lookup_anime_by_title(self.index, "デスノート")
        by_mal = lookup_anime_by_mal_id(self.index, "1535")
        by_anilist = lookup_anime_by_external_id(self.index, "anilist", "1535")

        self.assertEqual(spanish[0].title, "Death Note")
        self.assertEqual(japanese[0].title, "Death Note")
        self.assertIsNotNone(by_mal)
        self.assertIsNotNone(by_anilist)
        assert by_mal is not None and by_anilist is not None
        self.assertEqual(by_mal.entry_id, by_anilist.entry_id)
        self.assertEqual(by_mal.mal_id, "1535")
        self.assertIn("El cuaderno de la muerte", by_mal.aliases)

    def test_empty_jikan_uses_a_labeled_offline_fallback_without_changing_health(self) -> None:
        build_anime_index(self.snapshot, self.index)
        live = EmptyJikanAdapter()
        service = ExternalSourceService(
            [live],
            fallback_adapters={"jikan": AnimeOfflineAdapter(self.index)},
        )

        results, state = service.search("El cuaderno de la muerte", "jikan")

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["source"], "anime_offline_database")
        self.assertEqual(result["_search_shelf"], "jikan")
        self.assertEqual(result["fallback_reason"], "empty")
        self.assertTrue(result["offline"])
        self.assertEqual(state["sources"]["jikan"]["status"], "empty")
        self.assertEqual(state["sources"]["anime_offline_database"]["status"], "ok")

        item = item_from_search_result(result)
        self.assertEqual(item["source"], "anime_offline_database")
        self.assertEqual(item["mal_id"], "1535")
        self.assertEqual(
            item["metadata_sources"]["mal_id"]["source"],
            "anime_offline_database",
        )

    def test_live_jikan_keeps_authority_while_offline_index_adds_aliases_and_ids(self) -> None:
        build_anime_index(self.snapshot, self.index)
        service = ExternalSourceService(
            [SuccessfulJikanAdapter()],
            fallback_adapters={"jikan": AnimeOfflineAdapter(self.index)},
        )

        results, state = service.search("Death Note", "jikan")

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["source"], "jikan")
        self.assertEqual(
            result["alternative_titles"],
            ["DN", "El cuaderno de la muerte", "デスノート"],
        )
        self.assertEqual(result["external_ids"]["anilist"], "1535")
        self.assertEqual(result["offline_completion"]["source"], "anime_offline_database")
        self.assertEqual(state["sources"]["jikan"]["status"], "ok")
        self.assertEqual(state["sources"]["anime_offline_database"]["status"], "ok")

        item = item_from_search_result(result)
        self.assertEqual(item["source"], "jikan")
        self.assertEqual(
            item["metadata_sources"]["alternative_titles"]["source"],
            "jikan+anime_offline_database",
        )

    def test_jikan_timeout_uses_fallback_and_subsequent_search_honors_cooldown(self) -> None:
        build_anime_index(self.snapshot, self.index)
        live = EmptyJikanAdapter(TimeoutError("recorded timeout"))
        service = ExternalSourceService(
            [live],
            fallback_adapters={"jikan": AnimeOfflineAdapter(self.index)},
        )

        first, first_state = service.search("Death Note", "jikan")
        second, second_state = service.search("Death Note", "jikan")

        self.assertEqual(live.calls, 1)
        self.assertEqual(first[0]["fallback_reason"], "timeout")
        self.assertEqual(second[0]["fallback_reason"], "timeout")
        self.assertEqual(first_state["sources"]["jikan"]["status"], "cooldown")
        self.assertGreater(second_state["sources"]["jikan"]["retry_after_seconds"], 0)

    def test_process_gateway_exposes_offline_health_only_when_configured(self) -> None:
        build_anime_index(self.snapshot, self.index)
        try:
            configure_external_catalog("", str(self.index))
            health = external_sources_snapshot()["sources"]["anime_offline_database"]
            self.assertEqual(health["snapshot_date"], "2026-07-04")
            self.assertEqual(health["status"], "ready")

            configure_external_catalog()
            self.assertNotIn(
                "anime_offline_database",
                external_sources_snapshot()["sources"],
            )
        finally:
            configure_external_catalog()

    def test_stats_rejects_a_stale_schema(self) -> None:
        build_anime_index(self.snapshot, self.index)
        connection = sqlite3.connect(self.index)
        try:
            connection.execute("PRAGMA user_version = 0")
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(AnimeOfflineIndexStale):
            anime_index_stats(self.index)

    def test_cli_sync_stats_and_lookup_never_download_the_snapshot(self) -> None:
        output_dir = self.root / "index"
        sync_output = io.StringIO()
        with redirect_stdout(sync_output):
            result = anime_cli_main(
                [
                    "sync",
                    "--snapshot",
                    str(self.snapshot),
                    "--output-dir",
                    str(output_dir),
                ]
            )
        self.assertEqual(result, 0)
        self.assertTrue((output_dir / ANIME_INDEX_FILENAME).is_file())
        self.assertIn(ANIME_OFFLINE_ATTRIBUTION, sync_output.getvalue())

        stats_output = io.StringIO()
        with redirect_stdout(stats_output):
            self.assertEqual(
                anime_cli_main(["stats", "--output-dir", str(output_dir)]),
                0,
            )
        self.assertIn("2026-07-04", stats_output.getvalue())

        lookup_output = io.StringIO()
        with redirect_stdout(lookup_output):
            self.assertEqual(
                anime_cli_main(
                    [
                        "lookup",
                        "--output-dir",
                        str(output_dir),
                        "--external-id",
                        "anilist:1535",
                    ]
                ),
                0,
            )
        self.assertIn("Death Note", lookup_output.getvalue())
        self.assertIn("myanimelist:1535", lookup_output.getvalue())

    def test_cli_rejects_malformed_cross_reference_without_traceback(self) -> None:
        error = io.StringIO()
        with redirect_stderr(error), redirect_stdout(io.StringIO()):
            result = anime_cli_main(
                [
                    "lookup",
                    "--output-dir",
                    str(self.root),
                    "--external-id",
                    "missing-separator",
                ]
            )
        self.assertEqual(result, 2)
        self.assertIn("provider:id", error.getvalue())


if __name__ == "__main__":
    unittest.main()
