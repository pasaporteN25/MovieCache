#!/usr/bin/env python3
"""
Clean release-style movie titles and optionally link catalog items to Wikipedia.

Examples:
    py scripts/enrich_catalog.py catalogv2.json --json catalog_clean.json --csv catalog_clean.csv
    py scripts/enrich_catalog.py catalogv2.json --json catalog_wiki.json --fetch-wikipedia --limit 100
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from movie_inbox.domain.deduplication import deduplicate_items
from movie_inbox.domain.catalog import external_source_name, normalize_item, normalize_tags as normalize_list
from movie_inbox.infrastructure.export import write_catalog_csv
from movie_inbox.external.metadata import fetch_metadata, fetch_wikipedia_by_title
from movie_inbox.domain.models import CatalogItem
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.domain.titles import clean_release_title, infer_year


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean and enrich a merged movie catalog.")
    parser.add_argument("catalog", type=Path, help="Input JSON or SQLite catalog.")
    parser.add_argument("--json", "--output", dest="json_path", type=Path, required=True, help="Output JSON or SQLite catalog.")
    parser.add_argument("--csv", dest="csv_path", type=Path, help="Optional output CSV path.")
    parser.add_argument("--fetch-wikipedia", action="store_true", help="Search Wikipedia for missing links/metadata.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum items to fetch from Wikipedia. 0 means all.")
    parser.add_argument("--delay", type=float, default=0.35, help="Delay between Wikipedia requests.")
    parser.add_argument("--progress-every", type=int, default=25, help="Print and save progress every N fetched items.")
    parser.add_argument("--report", type=Path, help="Write a JSON report with changed and unmatched items.")
    args = parser.parse_args(argv)

    items = open_catalog_repository(args.catalog, normalize_item).read()

    report = {
        "input_items": len(items),
        "titles_cleaned": 0,
        "status_normalized": 0,
        "wikipedia_linked": 0,
        "wikipedia_unmatched": [],
    }

    fetch_count = 0
    interrupted = False
    try:
        for item in items:
            if normalize_item_status(item):
                report["status_normalized"] += 1
            if clean_item_title(item):
                report["titles_cleaned"] += 1

            if args.fetch_wikipedia and should_fetch_wikipedia(item):
                if args.limit and fetch_count >= args.limit:
                    continue
                fetch_count += 1
                if link_wikipedia(item):
                    report["wikipedia_linked"] += 1
                else:
                    report["wikipedia_unmatched"].append(item.title or item.local_name)
                if args.progress_every and fetch_count % args.progress_every == 0:
                    save_outputs(items, args, report)
                    print(
                        f"Progress: fetched {fetch_count}, linked {report['wikipedia_linked']}, "
                        f"unmatched {len(report['wikipedia_unmatched'])}",
                        flush=True,
                    )
                time.sleep(args.delay)
    except KeyboardInterrupt:
        interrupted = True
        report["interrupted"] = True
        print("\nInterrupted. Saving partial output...", flush=True)

    items, duplicate_labels = deduplicate_items(items)
    report["output_items"] = len(items)
    report["duplicates_merged"] = len(duplicate_labels)
    save_outputs(items, args, report)

    print("Enrich summary")
    print(f"- Input items: {report['input_items']}")
    print(f"- Titles cleaned: {report['titles_cleaned']}")
    print(f"- Status normalized: {report['status_normalized']}")
    print(f"- Wikipedia linked: {report['wikipedia_linked']}")
    print(f"- Duplicates merged: {report['duplicates_merged']}")
    print(f"- Output items: {report['output_items']}")
    if report["wikipedia_unmatched"]:
        print(f"- Wikipedia unmatched: {len(report['wikipedia_unmatched'])}")
    return 130 if interrupted else 0


def normalize_item_status(item: CatalogItem) -> bool:
    if item.status == "cataloged":
        item.status = "to_watch"
        return True
    if not item.status:
        item.status = "to_watch"
        return True
    return False


def clean_item_title(item: CatalogItem) -> bool:
    original = item.title
    source = item.local_name or item.local_path or item.title
    cleaned = clean_release_title(source)
    if not cleaned:
        return False

    year = infer_year(cleaned, item.year)
    title_without_year = cleaned
    if year:
        title_without_year = title_without_year.replace(year, "").strip(" -_.()[]")
        item.year = item.year or year

    if title_without_year and title_without_year != item.title:
        item.title = title_without_year
        return item.title != original
    return False


def should_fetch_wikipedia(item: CatalogItem) -> bool:
    if item.wikidata_id or item.wikipedia_title:
        if not (item.genres and item.directors and item.writers and item.cast):
            return bool(item.url or item.wikipedia_url or item.title)
        return False
    return bool(item.url or item.wikipedia_url or item.title)


def link_wikipedia(item: CatalogItem) -> bool:
    source_url = item.url or item.wikipedia_url
    metadata = fetch_metadata(source_url) if source_url else fetch_wikipedia_by_title(item.title, item.year)
    if not metadata:
        return False
    metadata_url = str(metadata.get("url") or "")
    if not (metadata.get("wikipedia_title") or metadata.get("wikidata_id") or external_source_name(metadata_url) == "wikipedia"):
        return False

    item.url = item.url or metadata_url
    if not item.source:
        item.source = external_source_name(item.url)
    item.wikipedia_url = item.wikipedia_url or metadata.get("wikipedia_url", "") or (
        metadata_url if external_source_name(metadata_url) == "wikipedia" else ""
    )
    item.original_title = item.original_title or metadata.get("original_title", "")
    item.spanish_title = item.spanish_title or metadata.get("spanish_title", "")
    item.english_title = item.english_title or metadata.get("english_title", "")
    item.alternative_titles = normalize_list(item.alternative_titles) + [
        title for title in normalize_list(metadata.get("alternative_titles")) if title not in normalize_list(item.alternative_titles)
    ]
    item.wikipedia_title = item.wikipedia_title or metadata.get("wikipedia_title", "")
    item.wikidata_id = item.wikidata_id or metadata.get("wikidata_id", "")
    item.genres = item.genres or normalize_list(metadata.get("genres"))
    item.directors = item.directors or normalize_list(metadata.get("directors"))
    item.writers = item.writers or normalize_list(metadata.get("writers"))
    item.cast = item.cast or normalize_list(metadata.get("cast"))
    item.page_image = item.page_image or metadata.get("page_image", "")
    item.wikipedia_extract = item.wikipedia_extract or metadata.get("wikipedia_extract", "")
    item.description = item.description or metadata.get("description", "")
    item.year = item.year or metadata.get("year", "") or infer_year(item.wikipedia_title, item.wikipedia_extract)
    return True


def save_outputs(items: list[CatalogItem], args: argparse.Namespace, report: dict[str, object]) -> None:
    open_catalog_repository(args.json_path, normalize_item).write(items)
    if args.csv_path:
        write_catalog_csv(args.csv_path, items)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
