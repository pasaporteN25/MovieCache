#!/usr/bin/env python3
"""
Try to attach external movie links to catalog entries.

Searches Wikipedia, IMDb and FilmAffinity for entries that do not yet have a
trusted external link, merges high-confidence matches, and deduplicates entries
that point to the same external URL or the same exact title/year.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from movie_inbox.domain.deduplication import deduplicate_items
from movie_inbox.domain.catalog import (
    has_external_link,
    merge_into_existing,
    normalize_item,
)
from movie_inbox.infrastructure.external_catalog import enrich_external_result, search_external_sources
from movie_inbox.domain.models import CatalogItem
from movie_inbox.domain.matching import rank_candidates
from movie_inbox.infrastructure.repositories import open_catalog_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Match catalog entries with Wikipedia, IMDb or FilmAffinity links.")
    parser.add_argument("catalog", type=Path, help="Input JSON or SQLite catalog.")
    parser.add_argument("--json", "--output", dest="json_path", type=Path, required=True, help="Output JSON or SQLite catalog.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum unlinked entries to search. 0 means all.")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between searches.")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum ranking score included in review reports.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output JSON.")
    args = parser.parse_args(argv)

    items = open_catalog_repository(args.catalog, normalize_item).read()
    report: dict[str, Any] = {
        "input_items": len(items),
        "initial_with_link": sum(1 for item in items if has_external_link(item)),
        "matched": [],
        "needs_review": [],
        "unmatched": [],
        "duplicates_merged": [],
    }

    searched = 0
    for item in items:
        if has_external_link(item):
            continue
        if args.limit and searched >= args.limit:
            break
        query = search_query(item)
        if not query:
            continue

        searched += 1
        results, _ = search_external_sources(query, "all")
        candidates = [candidate for candidate in rank_candidates(item, results) if candidate["score"] >= args.min_score]
        if candidates and candidates[0]["decision"]["accepted"]:
            best = enrich_external_result(candidates[0]["result"])
            merge_into_existing(items, best, str(item.get("id") or ""))
            report["matched"].append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("title") or item.get("local_name") or "",
                    "score": candidates[0]["score"],
                    "source": best.get("source", ""),
                    "url": best.get("url", ""),
                    "reason": candidates[0]["decision"]["reason"],
                    "evidence": candidates[0]["decision"]["evidence"],
                }
            )
        elif candidates:
            report["needs_review"].append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("title") or item.get("local_name") or "",
                    "query": query,
                    "candidates": candidates[:5],
                }
            )
        else:
            report["unmatched"].append({"id": item.get("id", ""), "title": item.get("title") or item.get("local_name") or ""})

        if args.delay:
            time.sleep(args.delay)

    items, merged_labels = deduplicate_items(items)
    report["duplicates_merged"] = merged_labels
    report["output_items"] = len(items)
    report["final_with_link"] = sum(1 for item in items if has_external_link(item))
    report["final_without_link"] = report["output_items"] - report["final_with_link"]

    if not args.dry_run:
        open_catalog_repository(args.json_path, normalize_item).write(items)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("External link match summary")
    print(f"- Input items: {report['input_items']}")
    print(f"- Initial with link: {report['initial_with_link']}")
    print(f"- Auto matched: {len(report['matched'])}")
    print(f"- Needs review: {len(report['needs_review'])}")
    print(f"- Unmatched: {len(report['unmatched'])}")
    print(f"- Duplicates merged: {len(report['duplicates_merged'])}")
    print(f"- Output items: {report['output_items']}")
    print(f"- Final with link: {report['final_with_link']}")
    print(f"- Final without link: {report['final_without_link']}")
    return 0


def search_query(item: CatalogItem) -> str:
    title = str(item.get("title") or item.get("local_name") or "").strip()
    year = str(item.get("year") or "").strip()
    return " ".join(part for part in [title, year] if part)
if __name__ == "__main__":
    raise SystemExit(main())
