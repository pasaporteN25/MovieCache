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

from view_catalog import (
    enrich_selected_result,
    external_urls,
    has_external_link,
    merge_into_existing,
    normalize_item,
    read_json_items,
    search_sources,
    title_match_key,
    title_similarity,
    write_json_items,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Match catalog entries with Wikipedia, IMDb or FilmAffinity links.")
    parser.add_argument("catalog", type=Path, help="Input catalog JSON.")
    parser.add_argument("--json", dest="json_path", type=Path, required=True, help="Output JSON path.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum unlinked entries to search. 0 means all.")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between searches.")
    parser.add_argument("--min-score", type=float, default=0.86, help="Minimum confidence score to auto-merge.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output JSON.")
    args = parser.parse_args()

    items = [normalize_item(item) for item in read_json_items(args.catalog)]
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
        results = search_sources(query, "all")
        candidates = scored_candidates(item, results)
        if candidates and candidates[0]["score"] >= args.min_score:
            best = enrich_selected_result(candidates[0]["result"])
            merge_into_existing(items, best, str(item.get("id") or ""))
            report["matched"].append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("title") or item.get("local_name") or "",
                    "score": candidates[0]["score"],
                    "source": best.get("source", ""),
                    "url": best.get("url", ""),
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

    items, merged_labels = dedupe_external_items(items)
    report["duplicates_merged"] = merged_labels
    report["output_items"] = len(items)
    report["final_with_link"] = sum(1 for item in items if has_external_link(item))
    report["final_without_link"] = report["output_items"] - report["final_with_link"]

    if not args.dry_run:
        write_json_items(args.json_path, items)
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


def search_query(item: dict[str, Any]) -> str:
    title = str(item.get("title") or item.get("local_name") or "").strip()
    year = str(item.get("year") or "").strip()
    return " ".join(part for part in [title, year] if part)


def scored_candidates(item: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    item_title = title_match_key(str(item.get("title") or item.get("local_name") or ""))
    item_year = str(item.get("year") or "")
    scored: list[dict[str, Any]] = []
    for result in results:
        if not external_urls(result):
            continue
        result_title = title_match_key(str(result.get("title") or ""))
        if not result_title:
            continue
        score = title_similarity(item_title, result_title)
        result_year = str(result.get("year") or "")
        if item_year and result_year:
            score += 0.18 if item_year == result_year else -0.35
        if item_title == result_title:
            score += 0.08
        score = max(0.0, min(score, 1.0))
        if score <= 0:
            continue
        scored.append({"score": round(score, 3), "result": result})
    return sorted(scored, key=lambda entry: entry["score"], reverse=True)


def dedupe_external_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    unique: list[dict[str, Any]] = []
    merged: list[str] = []
    for item in items:
        target = find_duplicate(unique, item)
        if target is None:
            unique.append(item)
            continue
        merge_into_existing(unique, item, str(target.get("id") or ""))
        merged.append(str(item.get("title") or item.get("local_name") or item.get("url") or item.get("id") or ""))
    return unique, merged


def find_duplicate(items: list[dict[str, Any]], candidate: dict[str, Any]) -> dict[str, Any] | None:
    candidate_urls = external_urls(candidate)
    candidate_title = title_match_key(str(candidate.get("title") or candidate.get("local_name") or ""))
    candidate_year = str(candidate.get("year") or "")
    for item in items:
        if candidate_urls and candidate_urls & external_urls(item):
            return item
        item_title = title_match_key(str(item.get("title") or item.get("local_name") or ""))
        item_year = str(item.get("year") or "")
        if candidate_title and item_title == candidate_title and candidate_year and item_year and candidate_year == item_year:
            return item
    return None


if __name__ == "__main__":
    raise SystemExit(main())
