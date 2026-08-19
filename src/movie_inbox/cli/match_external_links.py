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

from movie_inbox.domain.catalog import (
    external_link_coverage,
    has_external_link,
    linked_sources,
    merge_into_existing,
    normalize_item,
)
from movie_inbox.domain.deduplication import deduplicate_items
from movie_inbox.domain.matching import RankedCandidate, rank_candidates
from movie_inbox.domain.models import CatalogItem
from movie_inbox.infrastructure.external_catalog import (
    enrich_external_result,
    search_external_sources,
)
from movie_inbox.infrastructure.repositories import open_catalog_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Match catalog entries with Wikipedia, IMDb or FilmAffinity links."
    )
    parser.add_argument("catalog", type=Path, help="Input JSON or SQLite catalog.")
    parser.add_argument(
        "--json",
        "--output",
        dest="json_path",
        type=Path,
        required=True,
        help="Output JSON or SQLite catalog.",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Maximum unlinked entries to search. 0 means all."
    )
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between searches.")
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.0,
        help="Minimum ranking score included in review reports.",
    )
    parser.add_argument(
        "--target-coverage",
        type=int,
        default=3,
        choices=(1, 2, 3),
        help=(
            "Skip an item once it has links from this many of the 3 sources "
            "(1-3). Lower this for a faster pass that settles for IMDb+Wikipedia."
        ),
    )
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
        if external_link_coverage(item) >= args.target_coverage:
            continue
        if args.limit and searched >= args.limit:
            break
        query = search_query(item)
        if not query:
            continue

        searched += 1
        results, _ = search_external_sources(query, "all")
        candidates = [
            candidate
            for candidate in rank_candidates(item, results)
            if candidate["score"] >= args.min_score
        ]
        matched_sources = merge_best_candidate_per_missing_source(items, item, candidates)
        if matched_sources:
            report["matched"].append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("title") or item.get("local_name") or "",
                    "sources": matched_sources,
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
            report["unmatched"].append(
                {
                    "id": item.get("id", ""),
                    "title": item.get("title") or item.get("local_name") or "",
                }
            )

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


def merge_best_candidate_per_missing_source(
    items: list[CatalogItem],
    item: CatalogItem,
    candidates: list[RankedCandidate],
) -> list[dict[str, Any]]:
    """Merge the best accepted candidate from each source the item still lacks.

    rank_candidates() ranks all 3 sources together and used to let only the
    single overall-best candidate through -- if Wikipedia and IMDb both found
    a good match in the same run, the runner-up source's candidate was
    silently discarded, and it would never be retried once the item showed
    *a* link at all.
    """
    already_linked = linked_sources(item)
    best_per_source: dict[str, RankedCandidate] = {}
    for candidate in candidates:
        if not candidate["decision"]["accepted"]:
            continue
        source = str(candidate["result"].get("source") or "")
        if not source or source in already_linked or source in best_per_source:
            continue
        best_per_source[source] = candidate

    item_id = str(item.get("id") or "")
    merged: list[dict[str, Any]] = []
    for source, candidate in best_per_source.items():
        best = enrich_external_result(candidate["result"])
        merge_into_existing(items, best, item_id)
        merged.append(
            {
                "source": source,
                "score": candidate["score"],
                "url": best.get("url", ""),
                "reason": candidate["decision"]["reason"],
                "evidence": candidate["decision"]["evidence"],
            }
        )
    return merged


def search_query(item: CatalogItem) -> str:
    title = str(item.get("title") or item.get("local_name") or "").strip()
    year = str(item.get("year") or "").strip()
    return " ".join(part for part in [title, year] if part)


if __name__ == "__main__":
    raise SystemExit(main())
