#!/usr/bin/env python3
"""
Convert a plain text list of movie/show URLs or titles into JSON and/or CSV.

The script works without third-party dependencies. Metadata fetching is optional
and intentionally conservative so the file can become a stable seed for a
future webapp or Kotlin app.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from movie_inbox.domain.catalog import (
    merge_lists,
    normalize_date,
    normalize_item,
    normalize_kind,
    normalize_rating,
    normalize_status,
    normalize_tags as normalize_list,
    source_url_field,
    stable_id,
    title_match_key,
)
from movie_inbox.domain.deduplication import deduplicate_items, merge_catalogs
from movie_inbox.infrastructure.export import write_catalog_csv as write_csv
from movie_inbox.external.metadata import (
    fetch_metadata,
    fetch_wikipedia_by_title,
    guess_title_from_url,
    source_name,
)
from movie_inbox.domain.models import CatalogItem, MetadataSource
from movie_inbox.infrastructure.schema import (
    METADATA_FIELDS,
    atomic_write_json,
    backup_json_file as create_json_backup,
    catalog_document,
    extract_catalog_items,
    normalize_bool,
    normalize_locked_fields,
    normalize_local_files,
    normalize_metadata_sources,
)
from movie_inbox.infrastructure.repositories import open_catalog_repository
from movie_inbox.domain.titles import clean_release_title, clean_whitespace, infer_year

URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


@dataclass
class ImportStats:
    input_path: str
    input_format: str
    input_rows: int
    input_urls: int
    input_duplicates: int
    existing_items: int
    existing_duplicates: int
    added_items: int
    skipped_existing: int
    output_items: int
    duplicate_urls: list[str]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert and merge movie/show URL/title catalogs.")
    parser.add_argument("input", type=Path, help="TXT, JSON or CSV file containing movie/show URLs or titles.")
    parser.add_argument("--json", dest="json_path", type=Path, help="Output JSON path.")
    parser.add_argument("--db", dest="db_path", type=Path, help="Output SQLite path.")
    parser.add_argument("--csv", dest="csv_path", type=Path, help="Output CSV path.")
    parser.add_argument("--merge", type=Path, help="Existing JSON/CSV/SQLite catalog to merge into.")
    parser.add_argument("--log-json", type=Path, help="Write import stats to a JSON log file.")
    parser.add_argument("--fetch", action="store_true", help="Fetch page metadata when possible.")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between fetches in seconds.")
    parser.add_argument("--status", default="to_watch", help="Default status for imported items.")
    args = parser.parse_args(argv)

    if not args.json_path and not args.db_path and not args.csv_path:
        args.json_path = Path("catalog.json")

    imported_rows = read_items_or_urls(args.input, status=args.status)
    imported_items = materialize_items(imported_rows.urls, imported_rows.items, args.fetch, args.delay, args.status)
    input_items, input_duplicate_urls = deduplicate_items(imported_items)

    existing_items: list[CatalogItem] = []
    existing_duplicate_urls: list[str] = []
    if args.merge:
        existing_rows = read_items_or_urls(args.merge, status=args.status)
        existing_materialized = materialize_items(
            existing_rows.urls,
            existing_rows.items,
            fetch=False,
            delay=args.delay,
            status=args.status,
        )
        existing_items, existing_duplicate_urls = deduplicate_items(existing_materialized)

    items, merged_existing = merge_catalogs(existing_items, input_items)
    skipped_existing = len(merged_existing)
    stats = ImportStats(
        input_path=str(args.input),
        input_format=args.input.suffix.lower().lstrip(".") or "txt",
        input_rows=imported_rows.row_count,
        input_urls=len(imported_items),
        input_duplicates=len(input_duplicate_urls),
        existing_items=len(existing_items),
        existing_duplicates=len(existing_duplicate_urls),
        added_items=len(input_items) - skipped_existing,
        skipped_existing=skipped_existing,
        output_items=len(items),
        duplicate_urls=input_duplicate_urls + existing_duplicate_urls,
    )

    if args.json_path:
        write_json(args.json_path, items)
    if args.db_path:
        open_catalog_repository(args.db_path, normalize_item).write(items)
    if args.csv_path:
        write_csv(args.csv_path, items)
    if args.log_json:
        write_import_log(args.log_json, stats)

    print_report(stats)
    return 0


@dataclass
class InputRows:
    items: list[CatalogItem]
    urls: list[str]
    row_count: int


def read_items_or_urls(path: Path, status: str) -> InputRows:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return read_json_catalog(path, status)
    if suffix == ".csv":
        return read_csv_catalog(path, status)
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        items = open_catalog_repository(path, normalize_item).read()
        return InputRows(items=items, urls=[], row_count=len(items))
    return read_text_catalog(path, status)


def read_text_catalog(path: Path, status: str) -> InputRows:
    items: list[CatalogItem] = []
    urls: list[str] = []
    row_count = 0

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = clean_whitespace(raw_line)
        if not line:
            continue
        row_count += 1

        line_urls = list(extract_urls(line))
        if line_urls:
            urls.extend(line_urls)
            continue

        item = item_from_text_title(line, status)
        if item:
            items.append(item)

    return InputRows(items=items, urls=urls, row_count=row_count)


def read_json_catalog(path: Path, status: str) -> InputRows:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = extract_catalog_items(raw)
    items: list[CatalogItem] = []
    urls: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = item_from_mapping(row, status)
        if item:
            items.append(item)
        elif row.get("url"):
            urls.append(normalize_url(str(row["url"])))
    return InputRows(items=items, urls=urls, row_count=len(rows))


def read_csv_catalog(path: Path, status: str) -> InputRows:
    items: list[CatalogItem] = []
    urls: list[str] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    for row in rows:
        item = item_from_mapping(row, status)
        if item:
            items.append(item)
        elif row.get("url"):
            urls.append(normalize_url(str(row["url"])))
    return InputRows(items=items, urls=urls, row_count=len(rows))


def item_from_mapping(row: dict[str, object], default_status: str) -> CatalogItem | None:
    url = normalize_url(str(row.get("url") or ""))
    local_name = str(row.get("local_name") or "")
    local_path = str(row.get("local_path") or "")
    local_files = normalize_local_files(row.get("local_files"), local_name, local_path)
    raw_title = str(row.get("title") or (guess_title_from_url(url) if url else local_name))
    title = clean_release_title(raw_title)
    if not url and not title and not local_name:
        return None
    tags = normalize_list(row.get("tags"))
    added_at = str(row.get("added_at") or row.get("addedAt") or datetime.now(timezone.utc).isoformat())
    link_field = source_url_field(str(row.get("source") or source_name(urlparse(url).netloc)), url)
    wikipedia_url = str(row.get("wikipedia_url") or "")
    imdb_url = str(row.get("imdb_url") or "")
    filmaffinity_url = str(row.get("filmaffinity_url") or "")
    if link_field == "wikipedia_url":
        wikipedia_url = wikipedia_url or url
    elif link_field == "imdb_url":
        imdb_url = imdb_url or url
    elif link_field == "filmaffinity_url":
        filmaffinity_url = filmaffinity_url or url
    return normalize_item(CatalogItem(
        id=str(row.get("id") or stable_id(url or local_path or local_name or title)),
        url=url,
        source=str(row.get("source") or source_name(urlparse(url).netloc)),
        title=title,
        original_title=str(row.get("original_title") or row.get("originalTitle") or ""),
        spanish_title=str(row.get("spanish_title") or row.get("spanishTitle") or ""),
        english_title=str(row.get("english_title") or row.get("englishTitle") or ""),
        alternative_titles=normalize_list(row.get("alternative_titles") or row.get("alternativeTitles")),
        kind=normalize_kind(row.get("kind")),
        status=normalize_status(row.get("status") or default_status),
        watched_at=normalize_date(row.get("watched_at") or row.get("watchedAt")),
        rating=normalize_rating(row.get("rating")),
        year=str(row.get("year") or infer_year(title, local_name, local_path)),
        description=str(row.get("description") or ""),
        wikipedia_url=wikipedia_url,
        imdb_url=imdb_url,
        filmaffinity_url=filmaffinity_url,
        wikipedia_title=str(row.get("wikipedia_title") or ""),
        wikidata_id=str(row.get("wikidata_id") or ""),
        genres=normalize_list(row.get("genres") or row.get("genre")),
        directors=normalize_list(row.get("directors") or row.get("director")),
        writers=normalize_list(row.get("writers") or row.get("writer") or row.get("screenwriters")),
        cast=normalize_list(row.get("cast") or row.get("actors") or row.get("actor")),
        page_image=str(row.get("page_image") or ""),
        wikipedia_extract=str(row.get("wikipedia_extract") or ""),
        en_catalogo=normalize_bool(row.get("en_catalogo"), default=False),
        local_files=local_files,
        local_name=local_name,
        local_path=local_path,
        tags=tags,
        notes=str(row.get("notes") or ""),
        review=str(row.get("review") or ""),
        added_at=added_at,
        metadata_sources=normalize_metadata_sources(row.get("metadata_sources")),
        locked_fields=normalize_locked_fields(row.get("locked_fields")),
    ))


def item_from_text_title(raw_title: str, default_status: str) -> CatalogItem | None:
    raw_title = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", raw_title)
    title = clean_release_title(raw_title)
    year = infer_year(title, raw_title)
    if year:
        title = re.sub(rf"\b{re.escape(year)}\b", "", title, count=1).strip(" -_.()[]")
        title = clean_whitespace(title)
    if not title or looks_like_external_id(title):
        return None

    return normalize_item(CatalogItem(
        id=stable_id(f"txt:{title_match_key(title)}:{year}"),
        url="",
        source="txt",
        title=title,
        original_title="",
        spanish_title="",
        english_title="",
        alternative_titles=[],
        kind="pelicula",
        status=normalize_status(default_status),
        watched_at="",
        rating=0,
        year=year,
        description="",
        wikipedia_url="",
        imdb_url="",
        filmaffinity_url="",
        wikipedia_title="",
        wikidata_id="",
        genres=[],
        directors=[],
        writers=[],
        cast=[],
        page_image="",
        wikipedia_extract="",
        en_catalogo=False,
        local_files=[],
        local_name="",
        local_path="",
        tags=[],
        notes="",
        review="",
        added_at=datetime.now(timezone.utc).isoformat(),
    ))


def materialize_items(
    urls: list[str],
    items: list[CatalogItem],
    fetch: bool,
    delay: float,
    status: str,
) -> list[CatalogItem]:
    if items and not urls and not fetch:
        return items
    materialized = items + build_catalog(urls, fetch=False, delay=delay, status=status)
    if not fetch:
        return materialized

    enriched: list[CatalogItem] = []
    for index, item in enumerate(materialized):
        enriched.append(enrich_item(item))
        if index < len(materialized) - 1:
            time.sleep(delay)
    return enriched


def extract_urls(text: str) -> Iterable[str]:
    for match in URL_RE.finditer(text):
        url = normalize_url(match.group(0))
        if url:
            yield url


def normalize_url(url: str) -> str:
    url = url.strip()
    while url and url[-1] in ".,;\"'":
        url = url[:-1]
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1]
    while url.endswith("]") and url.count("[") < url.count("]"):
        url = url[:-1]
    return url


def build_catalog(urls: list[str], fetch: bool, delay: float, status: str) -> list[CatalogItem]:
    now = datetime.now(timezone.utc).isoformat()
    items: list[CatalogItem] = []

    for index, url in enumerate(urls):
        metadata = fetch_metadata(url) if fetch else {}
        parsed = urlparse(url)
        source = source_name(parsed.netloc)
        title = metadata.get("title") or guess_title_from_url(url)
        description = metadata.get("description", "")
        kind = infer_kind(url, metadata)
        year = infer_year(title, description)

        item = normalize_item(CatalogItem(
                id=stable_id(url),
                url=url,
                source=source,
                title=title,
                original_title=metadata.get("original_title", ""),
                spanish_title=metadata.get("spanish_title", ""),
                english_title=metadata.get("english_title", ""),
                alternative_titles=normalize_list(metadata.get("alternative_titles")),
                kind=kind,
                status=normalize_status(status),
                watched_at="",
                rating=0,
                year=year,
                description=description,
                wikipedia_url=url if source == "wikipedia" else metadata.get("wikipedia_url", ""),
                imdb_url=url if source == "imdb" else metadata.get("imdb_url", ""),
                filmaffinity_url=url if source == "filmaffinity" else metadata.get("filmaffinity_url", ""),
                wikipedia_title=metadata.get("wikipedia_title", ""),
                wikidata_id=metadata.get("wikidata_id", ""),
                genres=normalize_list(metadata.get("genres")),
                directors=normalize_list(metadata.get("directors")),
                writers=normalize_list(metadata.get("writers")),
                cast=normalize_list(metadata.get("cast")),
                page_image=metadata.get("page_image", ""),
                wikipedia_extract=metadata.get("wikipedia_extract", ""),
                en_catalogo=False,
                local_files=[],
                local_name="",
                local_path="",
                tags=[],
                notes="",
                review="",
                added_at=now,
            ))
        origin_url = str(metadata.get("url") or url)
        origin_source = source_name(urlparse(origin_url).netloc) or source
        item["metadata_sources"] = {
            field_name: MetadataSource(
                source=origin_source,
                url=origin_url,
                updated_at=now,
                inferred=not fetch,
            )
            for field_name in METADATA_FIELDS
            if getattr(item, field_name) not in (None, "", [], {})
        }
        items.append(item)

        if fetch and index < len(urls) - 1:
            time.sleep(delay)

    return items


def apply_fetched_metadata(
    item: CatalogItem,
    metadata: dict[str, object],
    field_name: str,
    incoming: object,
    prefer_incoming: bool = False,
    merge_values: bool = False,
) -> None:
    if field_name in set(item.locked_fields):
        return
    before = getattr(item, field_name)
    if merge_values:
        after = merge_lists(before, normalize_list(incoming))
    else:
        after = (incoming or before) if prefer_incoming else (before or incoming)
    if field_name == "kind":
        after = normalize_kind(after)
    if after == before:
        return
    setattr(item, field_name, after)
    origin_url = str(metadata.get("url") or metadata.get("wikipedia_url") or item.url)
    item.metadata_sources[field_name] = MetadataSource(
        source=source_name(urlparse(origin_url).netloc) or item.source or "external",
        url=origin_url,
        updated_at=datetime.now(timezone.utc).isoformat(),
        inferred=False,
    )


def enrich_item(item: CatalogItem) -> CatalogItem:
    metadata = fetch_metadata(item.url) if item.url else fetch_wikipedia_by_title(item.title, item.year)
    if not metadata:
        return item

    item.url = item.url or metadata.get("url", "")
    link_field = source_url_field(item.source, item.url or metadata.get("url", ""))
    if link_field == "wikipedia_url":
        item.wikipedia_url = item.wikipedia_url or item.url or metadata.get("url", "")
    elif link_field == "imdb_url":
        item.imdb_url = item.imdb_url or item.url or metadata.get("url", "")
    elif link_field == "filmaffinity_url":
        item.filmaffinity_url = item.filmaffinity_url or item.url or metadata.get("url", "")
    item.wikipedia_url = item.wikipedia_url or metadata.get("wikipedia_url", "")
    item.imdb_url = item.imdb_url or metadata.get("imdb_url", "")
    item.filmaffinity_url = item.filmaffinity_url or metadata.get("filmaffinity_url", "")
    apply_fetched_metadata(item, metadata, "title", metadata.get("title", ""), prefer_incoming=True)
    apply_fetched_metadata(item, metadata, "original_title", metadata.get("original_title", ""))
    apply_fetched_metadata(item, metadata, "spanish_title", metadata.get("spanish_title", ""))
    apply_fetched_metadata(item, metadata, "english_title", metadata.get("english_title", ""))
    apply_fetched_metadata(item, metadata, "alternative_titles", metadata.get("alternative_titles", []), merge_values=True)
    apply_fetched_metadata(item, metadata, "description", metadata.get("description", ""))
    apply_fetched_metadata(item, metadata, "kind", infer_kind(item.url, metadata))
    fetched_year = metadata.get("year", "") or infer_year(item.title, item.description, str(metadata.get("wikipedia_extract", "")))
    apply_fetched_metadata(item, metadata, "year", fetched_year)
    apply_fetched_metadata(item, metadata, "wikipedia_title", metadata.get("wikipedia_title", ""))
    apply_fetched_metadata(item, metadata, "wikidata_id", metadata.get("wikidata_id", ""))
    for field_name in ("genres", "directors", "writers", "cast"):
        apply_fetched_metadata(item, metadata, field_name, metadata.get(field_name, []), merge_values=True)
    apply_fetched_metadata(item, metadata, "page_image", metadata.get("page_image", ""))
    apply_fetched_metadata(item, metadata, "wikipedia_extract", metadata.get("wikipedia_extract", ""))
    return item


def infer_kind(url: str, metadata: dict[str, str]) -> str:
    lowered = (
        f"{url} {metadata.get('og_type', '')} {metadata.get('description', '')} "
        f"{metadata.get('wikipedia_extract', '')}"
    ).lower()
    if "tv series" in lowered or "/title/tt" in lowered and "series" in lowered:
        return "serie"
    if "episode" in lowered:
        return "serie"
    if "documentary" in lowered or "documental" in lowered:
        return "documental"
    return "pelicula"


def write_json(path: Path, items: list[CatalogItem]) -> None:
    atomic_write_json(path, catalog_document(items))


def write_import_log(path: Path, stats: ImportStats) -> None:
    path.write_text(json.dumps(asdict(stats), ensure_ascii=False, indent=2), encoding="utf-8")


def backup_json_file(path: Path) -> None:
    create_json_backup(path)


def print_report(stats: ImportStats) -> None:
    print("Import summary")
    print(f"- Input rows: {stats.input_rows}")
    print(f"- Input URLs/items: {stats.input_urls}")
    print(f"- Duplicates inside input: {stats.input_duplicates}")
    if stats.existing_items or stats.existing_duplicates:
        print(f"- Existing catalog items: {stats.existing_items}")
        print(f"- Duplicates inside existing catalog: {stats.existing_duplicates}")
        print(f"- Already present in existing catalog: {stats.skipped_existing}")
    print(f"- Added items: {stats.added_items}")
    print(f"- Output items: {stats.output_items}")
    if stats.duplicate_urls:
        print("- Duplicate URLs/items:")
        for url in stats.duplicate_urls[:20]:
            print(f"  {url}")
        if len(stats.duplicate_urls) > 20:
            print(f"  ...and {len(stats.duplicate_urls) - 20} more")


if __name__ == "__main__":
    raise SystemExit(main())
