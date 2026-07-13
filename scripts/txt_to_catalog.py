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
import hashlib
import html
import json
import re
import socket
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from catalog_schema import (
    CATALOG_FIELDS,
    METADATA_FIELDS,
    atomic_write_json,
    backup_json_file as create_json_backup,
    catalog_document,
    merge_local_files,
    normalize_locked_fields,
    normalize_local_files,
    normalize_metadata_sources,
)

URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


@dataclass
class CatalogItem:
    id: str
    url: str
    source: str
    title: str
    original_title: str
    spanish_title: str
    english_title: str
    alternative_titles: list[str]
    kind: str
    status: str
    watched_at: str
    rating: int
    year: str
    description: str
    wikipedia_url: str
    imdb_url: str
    filmaffinity_url: str
    wikipedia_title: str
    wikidata_id: str
    genres: list[str]
    directors: list[str]
    writers: list[str]
    cast: list[str]
    page_image: str
    wikipedia_extract: str
    en_catalogo: bool
    local_files: list[dict[str, object]]
    local_name: str
    local_path: str
    tags: list[str]
    notes: str
    review: str
    added_at: str
    metadata_sources: dict[str, dict[str, object]] = field(default_factory=dict)
    locked_fields: list[str] = field(default_factory=list)


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


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            name = (attr.get("property") or attr.get("name") or "").lower()
            content = attr.get("content", "").strip()
            if name and content:
                self.meta[name] = html.unescape(content)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def page_title(self) -> str:
        return clean_title(" ".join(self.title_parts))


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert and merge movie/show URL/title catalogs.")
    parser.add_argument("input", type=Path, help="TXT, JSON or CSV file containing movie/show URLs or titles.")
    parser.add_argument("--json", dest="json_path", type=Path, help="Output JSON path.")
    parser.add_argument("--csv", dest="csv_path", type=Path, help="Output CSV path.")
    parser.add_argument("--merge", type=Path, help="Existing JSON/CSV catalog to merge into.")
    parser.add_argument("--log-json", type=Path, help="Write import stats to a JSON log file.")
    parser.add_argument("--fetch", action="store_true", help="Fetch page metadata when possible.")
    parser.add_argument("--delay", type=float, default=0.4, help="Delay between fetches in seconds.")
    parser.add_argument("--status", default="to_watch", help="Default status for imported items.")
    args = parser.parse_args()

    if not args.json_path and not args.csv_path:
        args.json_path = Path("catalog.json")

    imported_rows = read_items_or_urls(args.input, status=args.status)
    imported_items = materialize_items(imported_rows.urls, imported_rows.items, args.fetch, args.delay, args.status)
    input_items, input_duplicate_urls = dedupe_items(imported_items)

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
        existing_items, existing_duplicate_urls = dedupe_items(existing_materialized)

    items, skipped_existing = merge_items(existing_items, input_items)
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
    rows = raw if isinstance(raw, list) else raw.get("items", []) if isinstance(raw, dict) else []
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


def normalize_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def merge_lists(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in primary + secondary:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(value)
    return merged


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
    return CatalogItem(
        id=str(row.get("id") or stable_id(url or local_path or local_name or title)),
        url=url,
        source=str(row.get("source") or source_name(urlparse(url).netloc)),
        title=title,
        original_title=str(row.get("original_title") or row.get("originalTitle") or ""),
        spanish_title=str(row.get("spanish_title") or row.get("spanishTitle") or ""),
        english_title=str(row.get("english_title") or row.get("englishTitle") or ""),
        alternative_titles=normalize_list(row.get("alternative_titles") or row.get("alternativeTitles")),
        kind=normalize_kind(row.get("kind")),
        status=normalize_status_value(row.get("status"), default_status),
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
    )


def item_from_text_title(raw_title: str, default_status: str) -> CatalogItem | None:
    raw_title = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", raw_title)
    title = clean_release_title(raw_title)
    year = infer_year(title, raw_title)
    if year:
        title = re.sub(rf"\b{re.escape(year)}\b", "", title, count=1).strip(" -_.()[]")
        title = clean_whitespace(title)
    if not title or looks_like_external_id(title):
        return None

    return CatalogItem(
        id=stable_id(f"txt:{normalize_title_key(title)}:{year}"),
        url="",
        source="txt",
        title=title,
        original_title="",
        spanish_title="",
        english_title="",
        alternative_titles=[],
        kind="pelicula",
        status=normalize_status_value(default_status, "to_watch"),
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
    )


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


def dedupe_items(items: list[CatalogItem]) -> tuple[list[CatalogItem], list[str]]:
    seen: dict[str, int] = {}
    unique: list[CatalogItem] = []
    duplicates: list[str] = []
    for item in items:
        keys = catalog_keys(item)
        existing_index = next((seen[key] for key in keys if key in seen), None)
        if existing_index is not None:
            duplicates.append(item.url or item.local_name or item.title)
            unique[existing_index] = merge_catalog_item(unique[existing_index], item)
            continue
        index = len(unique)
        for key in keys:
            seen[key] = index
        unique.append(item)
    return unique, duplicates


def merge_items(existing: list[CatalogItem], incoming: list[CatalogItem]) -> tuple[list[CatalogItem], int]:
    seen: dict[str, int] = {}
    output = list(existing)
    for index, item in enumerate(output):
        for key in catalog_keys(item):
            seen[key] = index

    skipped = 0
    for item in incoming:
        keys = catalog_keys(item)
        existing_index = next((seen[key] for key in keys if key in seen), None)
        if existing_index is not None:
            skipped += 1
            output[existing_index] = merge_catalog_item(output[existing_index], item)
            continue
        index = len(output)
        for key in keys:
            seen[key] = index
        output.append(item)
    return output, skipped


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


def canonical_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    if not parsed.scheme or not parsed.netloc:
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{scheme}://{host}{path}"


def catalog_keys(item: CatalogItem) -> list[str]:
    keys: list[str] = []
    for raw_url in [item.url, item.wikipedia_url, item.imdb_url, item.filmaffinity_url]:
        url = canonical_url(raw_url)
        if url:
            keys.append(f"url:{url}")

    for title_value in catalog_title_values(item):
        title = normalize_title_key(title_value)
        if title:
            keys.append(f"title:{title}")

    if not keys and item.id:
        keys.append(f"id:{item.id}")
    return keys


def catalog_title_values(item: CatalogItem) -> list[str]:
    local_file_values = [
        str(value)
        for local_file in normalize_local_files(item.local_files)
        for value in (local_file.get("name", ""), local_file.get("path", ""))
        if value
    ]
    return [
        item.title,
        item.original_title,
        item.spanish_title,
        item.english_title,
        *item.alternative_titles,
        item.local_name,
        *local_file_values,
    ]


def normalize_title_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = re.sub(r"\.[a-z0-9]{2,5}$", "", value)
    value = re.sub(r"[\._-]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


LIST_METADATA_FIELDS = {"alternative_titles", "genres", "directors", "writers", "cast"}


def merge_catalog_metadata_field(primary: CatalogItem, secondary: CatalogItem, field_name: str) -> None:
    if field_name in set(primary.locked_fields):
        return
    before = getattr(primary, field_name)
    incoming = getattr(secondary, field_name)
    if field_name in LIST_METADATA_FIELDS:
        after = merge_lists(before, incoming)
    elif field_name == "kind":
        after = normalize_kind(before or incoming)
    else:
        after = before or incoming
    if after == before:
        return
    setattr(primary, field_name, after)
    record = secondary.metadata_sources.get(field_name)
    if record:
        primary.metadata_sources[field_name] = dict(record)
    else:
        primary.metadata_sources[field_name] = {
            "source": secondary.source or "legacy",
            "url": secondary.url,
            "updated_at": secondary.added_at,
            "inferred": True,
        }


def merge_catalog_item(primary: CatalogItem, secondary: CatalogItem) -> CatalogItem:
    primary.en_catalogo = bool(primary.en_catalogo or secondary.en_catalogo)
    primary.local_files = merge_local_files(
        normalize_local_files(primary.local_files, primary.local_name, primary.local_path),
        normalize_local_files(secondary.local_files, secondary.local_name, secondary.local_path),
    )
    primary.local_name = primary.local_name or secondary.local_name
    primary.local_path = primary.local_path or secondary.local_path
    primary.url = primary.url or secondary.url
    primary.source = primary.source if primary.source and primary.source != "local_files" else secondary.source or primary.source
    for field_name in METADATA_FIELDS:
        merge_catalog_metadata_field(primary, secondary, field_name)
    primary.status = normalize_status_value(primary.status, "to_watch")
    secondary_status = normalize_status_value(secondary.status, "to_watch")
    primary.status = "watched" if "watched" in {primary.status, secondary_status} else primary.status or secondary_status
    primary.watched_at = primary.watched_at or secondary.watched_at
    primary.rating = primary.rating or secondary.rating
    primary.wikipedia_url = primary.wikipedia_url or secondary.wikipedia_url
    primary.imdb_url = primary.imdb_url or secondary.imdb_url
    primary.filmaffinity_url = primary.filmaffinity_url or secondary.filmaffinity_url
    primary.notes = primary.notes or secondary.notes
    primary.review = primary.review or secondary.review
    primary.tags = sorted(set(primary.tags + secondary.tags))
    primary.locked_fields = normalize_locked_fields(primary.locked_fields)
    primary.added_at = min(primary.added_at, secondary.added_at) if primary.added_at and secondary.added_at else primary.added_at or secondary.added_at
    return primary


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

        item = CatalogItem(
                id=stable_id(url),
                url=url,
                source=source,
                title=title,
                original_title=metadata.get("original_title", ""),
                spanish_title=metadata.get("spanish_title", ""),
                english_title=metadata.get("english_title", ""),
                alternative_titles=normalize_list(metadata.get("alternative_titles")),
                kind=kind,
                status=status,
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
            )
        origin_url = str(metadata.get("url") or url)
        origin_source = source_name(urlparse(origin_url).netloc) or source
        item.metadata_sources = {
            field_name: {
                "source": origin_source,
                "url": origin_url,
                "updated_at": now,
                "inferred": not fetch,
            }
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
    item.metadata_sources[field_name] = {
        "source": source_name(urlparse(origin_url).netloc) or item.source or "external",
        "url": origin_url,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "inferred": False,
    }


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


def fetch_metadata(url: str) -> dict[str, str]:
    wikipedia_metadata = fetch_wikipedia_metadata(url)
    if wikipedia_metadata:
        return wikipedia_metadata

    imdb_id = imdb_id_from_text(url)
    if imdb_id:
        wikidata_metadata = fetch_wikipedia_by_imdb_id(imdb_id)
        if wikidata_metadata:
            wikidata_metadata["imdb_url"] = f"https://www.imdb.com/title/{imdb_id}/"
            return wikidata_metadata

    request = Request(
        url,
        headers={
            "User-Agent": "MovieInboxImporter/0.1 (+local personal catalog)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            if "html" not in content_type:
                return {}
            raw = response.read(800_000).decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return {}

    parser = MetadataParser()
    parser.feed(raw)
    title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.page_title
        or guess_title_from_url(url)
    )
    description = parser.meta.get("og:description") or parser.meta.get("description") or ""

    link_field = source_url_field(source_name(urlparse(url).netloc), url)
    metadata = {
        "title": clean_title(title),
        "description": clean_whitespace(description),
        "og_type": parser.meta.get("og:type", ""),
    }
    if "imdb.com" in urlparse(url).netloc.lower():
        metadata["english_title"] = metadata["title"]
    if "filmaffinity.com" in urlparse(url).netloc.lower():
        metadata["spanish_title"] = metadata["title"]
    if link_field:
        metadata[link_field] = url
    return metadata


def fetch_wikipedia_metadata(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "wikipedia.org" not in host:
        return {}

    page_title = wikipedia_page_title(parsed.path)
    if not page_title:
        return {}

    language = host.split(".")[0] if "." in host else "en"
    summary_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(page_title, safe='')}"
    raw = fetch_json(summary_url)
    if not raw:
        return fetch_wikipedia_metadata_action_api(language, page_title)

    title = clean_title(str(raw.get("title") or raw.get("displaytitle") or page_title))
    description = clean_whitespace(str(raw.get("description") or ""))
    extract = clean_whitespace(str(raw.get("extract") or ""))
    thumbnail = raw.get("thumbnail") if isinstance(raw.get("thumbnail"), dict) else {}
    image_url = str(thumbnail.get("source") or "") if isinstance(thumbnail, dict) else ""
    wikidata_id = str(raw.get("wikibase_item") or "")

    metadata = {
        "url": f"https://{language}.wikipedia.org/wiki/{quote(page_title, safe='')}",
        "wikipedia_url": f"https://{language}.wikipedia.org/wiki/{quote(page_title, safe='')}",
        "title": title,
        "spanish_title": title if language == "es" else "",
        "english_title": title if language == "en" else "",
        "description": description,
        "wikipedia_title": title,
        "wikidata_id": wikidata_id,
        "page_image": image_url,
        "wikipedia_extract": extract,
        "og_type": raw.get("type", ""),
    }
    metadata.update(fetch_wikidata_metadata(wikidata_id))
    if not (metadata["wikidata_id"] or metadata["wikipedia_extract"] or metadata["description"]):
        fallback = fetch_wikipedia_metadata_action_api(language, page_title)
        return fallback or metadata
    return metadata


def fetch_wikipedia_metadata_action_api(language: str, page_title: str) -> dict[str, str]:
    api_url = (
        f"https://{language}.wikipedia.org/w/api.php"
        "?action=query"
        "&format=json"
        "&redirects=1"
        "&prop=extracts|pageimages|pageprops|info"
        "&exintro=1"
        "&explaintext=1"
        "&piprop=thumbnail"
        "&pithumbsize=500"
        "&inprop=url"
        f"&titles={quote(page_title.replace('_', ' '))}"
    )
    raw = fetch_json(api_url)
    query = raw.get("query") if isinstance(raw.get("query"), dict) else {}
    pages = query.get("pages") if isinstance(query, dict) else {}
    if not isinstance(pages, dict):
        return {}

    page = next((value for value in pages.values() if isinstance(value, dict) and "missing" not in value), {})
    if not page:
        return {}

    title = clean_title(str(page.get("title") or page_title))
    description = clean_whitespace(str(page.get("description") or ""))
    extract = clean_whitespace(str(page.get("extract") or ""))
    thumbnail = page.get("thumbnail") if isinstance(page.get("thumbnail"), dict) else {}
    image_url = str(thumbnail.get("source") or "") if isinstance(thumbnail, dict) else ""
    pageprops = page.get("pageprops") if isinstance(page.get("pageprops"), dict) else {}
    wikidata_id = str(pageprops.get("wikibase_item") or "")
    canonical_url = str(page.get("canonicalurl") or f"https://{language}.wikipedia.org/wiki/{quote(page_title, safe='')}")

    metadata = {
        "url": canonical_url,
        "wikipedia_url": canonical_url,
        "title": title,
        "spanish_title": title if language == "es" else "",
        "english_title": title if language == "en" else "",
        "description": description,
        "wikipedia_title": title,
        "wikidata_id": wikidata_id,
        "page_image": image_url,
        "wikipedia_extract": extract,
        "og_type": "",
    }
    metadata.update(fetch_wikidata_metadata(wikidata_id))
    return metadata


WIKIDATA_LIST_FIELDS = {
    "genres": ("P136", 8),
    "directors": ("P57", 8),
    "writers": ("P58", 10),
    "cast": ("P161", 20),
}


def fetch_wikidata_metadata(entity_id: str) -> dict[str, object]:
    if not entity_id:
        return {}
    raw = fetch_json(f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json")
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    entity = entities.get(entity_id) if isinstance(entities, dict) else {}
    if not isinstance(entity, dict):
        return {}

    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    ids_by_field: dict[str, list[str]] = {}
    all_ids: list[str] = []
    for field, (prop, limit) in WIKIDATA_LIST_FIELDS.items():
        ids = wikidata_claim_entity_ids(claims, prop, limit)
        ids_by_field[field] = ids
        all_ids.extend(ids)

    labels = fetch_wikidata_labels(all_ids)
    metadata: dict[str, object] = {}
    title_metadata = wikidata_title_metadata(entity)
    metadata.update(title_metadata)
    year = wikidata_claim_year(claims, "P577")
    if year:
        metadata["year"] = year
    for field, ids in ids_by_field.items():
        values = [labels.get(item_id, item_id) for item_id in ids if labels.get(item_id, item_id)]
        if values:
            metadata[field] = values
    return metadata


def wikidata_title_metadata(entity: dict[str, object]) -> dict[str, object]:
    labels = entity.get("labels") if isinstance(entity.get("labels"), dict) else {}
    aliases = entity.get("aliases") if isinstance(entity.get("aliases"), dict) else {}
    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    original_title = wikidata_claim_monolingual_text(claims, "P1476")
    spanish_title = wikidata_label_value(labels, "es")
    english_title = wikidata_label_value(labels, "en")
    alternative_titles = merge_lists(
        wikidata_all_label_values(labels),
        wikidata_all_alias_values(aliases),
    )
    primary_keys = {
        value.casefold()
        for value in [original_title, spanish_title, english_title]
        if value
    }
    alternative_titles = [
        value for value in alternative_titles if value.casefold() not in primary_keys
    ][:40]
    metadata: dict[str, object] = {}
    if original_title:
        metadata["original_title"] = original_title
    if spanish_title:
        metadata["spanish_title"] = spanish_title
    if english_title:
        metadata["english_title"] = english_title
    if alternative_titles:
        metadata["alternative_titles"] = alternative_titles
    return metadata


def wikidata_label_value(labels: dict[str, object], language: str) -> str:
    value = labels.get(language) if isinstance(labels, dict) else {}
    return str(value.get("value") or "") if isinstance(value, dict) else ""


def wikidata_alias_values(aliases: dict[str, object], language: str) -> list[str]:
    rows = aliases.get(language) if isinstance(aliases, dict) else []
    if not isinstance(rows, list):
        return []
    return [str(row.get("value") or "").strip() for row in rows if isinstance(row, dict) and str(row.get("value") or "").strip()]


def wikidata_all_label_values(labels: dict[str, object]) -> list[str]:
    return [
        str(row.get("value") or "").strip()
        for row in labels.values()
        if isinstance(row, dict) and str(row.get("value") or "").strip()
    ]


def wikidata_all_alias_values(aliases: dict[str, object]) -> list[str]:
    values: list[str] = []
    for rows in aliases.values():
        if not isinstance(rows, list):
            continue
        values.extend(
            str(row.get("value") or "").strip()
            for row in rows
            if isinstance(row, dict) and str(row.get("value") or "").strip()
        )
    return values


def wikidata_claim_monolingual_text(claims: dict[str, object], prop: str) -> str:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return ""
    ordered = sorted(
        [statement for statement in statements if isinstance(statement, dict) and statement.get("rank") != "deprecated"],
        key=lambda statement: 0 if statement.get("rank") == "preferred" else 1,
    )
    for statement in ordered:
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        text = str(value.get("text") or "").strip() if isinstance(value, dict) else ""
        if text:
            return text
    return ""


def wikidata_claim_entity_ids(claims: dict[str, object], prop: str, limit: int) -> list[str]:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return []
    ordered = sorted(
        [statement for statement in statements if isinstance(statement, dict) and statement.get("rank") != "deprecated"],
        key=lambda statement: 0 if statement.get("rank") == "preferred" else 1,
    )
    ids: list[str] = []
    for statement in ordered:
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        item_id = value.get("id") if isinstance(value, dict) else ""
        if item_id and item_id not in ids:
            ids.append(str(item_id))
        if len(ids) >= limit:
            break
    return ids


def wikidata_claim_year(claims: dict[str, object], prop: str) -> str:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return ""
    for statement in statements:
        if not isinstance(statement, dict) or statement.get("rank") == "deprecated":
            continue
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        raw_time = str(value.get("time") or "") if isinstance(value, dict) else ""
        match = re.search(r"([+-]?\d{4})", raw_time)
        if match:
            return match.group(1).lstrip("+")
    return ""


def fetch_wikidata_labels(entity_ids: list[str]) -> dict[str, str]:
    unique_ids = list(dict.fromkeys(entity_ids))
    labels: dict[str, str] = {}
    for index in range(0, len(unique_ids), 50):
        chunk = unique_ids[index : index + 50]
        if not chunk:
            continue
        url = (
            "https://www.wikidata.org/w/api.php"
            "?action=wbgetentities&format=json&props=labels&languages=es|en"
            f"&ids={quote('|'.join(chunk), safe='|')}"
        )
        raw = fetch_json(url)
        entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
        if not isinstance(entities, dict):
            continue
        for item_id, entity in entities.items():
            if not isinstance(entity, dict):
                continue
            label_values = entity.get("labels") if isinstance(entity.get("labels"), dict) else {}
            label = wikidata_label(label_values)
            if label:
                labels[str(item_id)] = label
    return labels


def wikidata_label(labels: dict[str, object]) -> str:
    for language in ["es", "en"]:
        value = labels.get(language) if isinstance(labels, dict) else {}
        if isinstance(value, dict) and value.get("value"):
            return str(value["value"])
    return ""


def fetch_wikipedia_by_title(title: str, year: str = "") -> dict[str, str]:
    query = clean_search_title(clean_release_title(title))
    if not query or looks_like_external_id(query):
        return {}

    for language in ["en", "es"]:
        for candidate in wikipedia_direct_candidates(query, year, language):
            metadata = fetch_wikipedia_metadata(
                f"https://{language}.wikipedia.org/wiki/{quote(candidate.replace(' ', '_'), safe='')}"
            )
            if wikipedia_match_score(query, year, candidate, "", metadata) >= 3:
                return metadata

        for search_query in wikipedia_search_queries(query, year, language):
            raw = fetch_wikipedia_search(search_query, language)
            query_data = raw.get("query") if isinstance(raw.get("query"), dict) else {}
            results = query_data.get("search") if isinstance(query_data, dict) else []
            if not isinstance(results, list):
                continue

            best: tuple[int, dict[str, str]] = (0, {})
            for result in results[:3]:
                if not isinstance(result, dict):
                    continue
                page_title = str(result.get("title") or "")
                snippet = clean_whitespace(strip_html(str(result.get("snippet") or "")))
                metadata = fetch_wikipedia_metadata(
                    f"https://{language}.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'), safe='')}"
                )
                score = wikipedia_match_score(query, year, page_title, snippet, metadata)
                if score > best[0]:
                    best = (score, metadata)
            if best[0] >= 3:
                return best[1]
    return {}


def fetch_wikipedia_by_imdb_id(imdb_id: str) -> dict[str, str]:
    query = f"""
SELECT ?item ?article WHERE {{
  ?item wdt:P345 "{imdb_id}".
  ?article schema:about ?item ;
           schema:isPartOf ?site.
  VALUES ?site {{ <https://en.wikipedia.org/> <https://es.wikipedia.org/> }}
}}
LIMIT 1
"""
    url = "https://query.wikidata.org/sparql?format=json&query=" + quote(query)
    raw = fetch_json(url)
    results = raw.get("results") if isinstance(raw.get("results"), dict) else {}
    bindings = results.get("bindings") if isinstance(results, dict) else []
    if not isinstance(bindings, list) or not bindings:
        return {}
    binding = bindings[0]
    article = binding.get("article") if isinstance(binding, dict) else {}
    article_url = article.get("value") if isinstance(article, dict) else ""
    if article_url:
        return fetch_wikipedia_metadata(str(article_url))
    return {}


def fetch_wikipedia_by_wikidata_title(title: str, year: str = "") -> dict[str, str]:
    for language in ["en", "es"]:
        search_url = (
            "https://www.wikidata.org/w/api.php"
            f"?action=wbsearchentities&format=json&language={language}&limit=5"
            f"&search={quote(title)}"
        )
        raw = fetch_json(search_url)
        results = raw.get("search") if isinstance(raw.get("search"), list) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            entity_id = str(result.get("id") or "")
            label = str(result.get("label") or "")
            description = str(result.get("description") or "")
            score = wikidata_result_score(title, year, label, description)
            if score < 3:
                continue
            article_url = fetch_wikidata_article_url(entity_id)
            if article_url:
                metadata = fetch_wikipedia_metadata(article_url)
                if metadata and wikipedia_match_score(title, year, label, description, metadata) >= 3:
                    return metadata
    return {}


def fetch_wikidata_article_url(entity_id: str) -> str:
    if not entity_id:
        return ""
    raw = fetch_json(f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json")
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    entity = entities.get(entity_id) if isinstance(entities, dict) else {}
    if not isinstance(entity, dict):
        return ""

    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    if not wikidata_claims_include(claims, "P31", {"Q11424", "Q5398426", "Q24862", "Q506240"}):
        description_values = entity.get("descriptions") if isinstance(entity.get("descriptions"), dict) else {}
        descriptions = " ".join(
            str(value.get("value") or "")
            for value in description_values.values()
            if isinstance(value, dict)
        ).lower()
        if not any(marker in descriptions for marker in ["film", "movie", "película", "pelicula"]):
            return ""

    sitelinks = entity.get("sitelinks") if isinstance(entity.get("sitelinks"), dict) else {}
    for key in ["enwiki", "eswiki"]:
        link = sitelinks.get(key) if isinstance(sitelinks, dict) else {}
        if isinstance(link, dict) and link.get("url"):
            return str(link["url"])
    return ""


def wikidata_claims_include(claims: dict[str, object], prop: str, ids: set[str]) -> bool:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return False
    for statement in statements:
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        entity_id = value.get("id") if isinstance(value, dict) else ""
        if entity_id in ids:
            return True
    return False


def wikidata_result_score(title: str, year: str, label: str, description: str) -> int:
    score = 0
    title_key = normalize_match_text(title)
    label_key = normalize_match_text(label)
    description_key = normalize_match_text(description)
    if title_key and title_key == label_key:
        score += 4
    elif title_key and (title_key in label_key or label_key in title_key):
        score += 2
    if year and year in description:
        score += 1
    if any(marker in description_key for marker in ["film", "movie", "pelicula", "película"]):
        score += 2
    return score


def likely_film_result(title: str, snippet: str, year: str) -> bool:
    lowered = title.lower()
    if year and year in title:
        return True
    return any(marker in lowered for marker in ["film", "movie"]) or any(
        marker in snippet for marker in ["film", "movie", "directed by", "starring"]
    )


def fetch_wikipedia_search(query: str, language: str) -> dict[str, object]:
    search_url = (
        f"https://{language}.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={quote(query)}&format=json&srlimit=5"
    )
    return fetch_json(search_url)


def wikipedia_search_queries(title: str, year: str, language: str) -> list[str]:
    film_word = "película" if language == "es" else "film"
    movie_word = "cine" if language == "es" else "movie"
    queries = []
    if year:
        queries.append(f'"{title}" {year} {film_word}')
    queries.append(f'"{title}" {film_word}')
    queries.append(f'"{title}"')
    return queries


def wikipedia_direct_candidates(title: str, year: str, language: str) -> list[str]:
    film_suffix = "pelicula" if language == "es" else "film"
    candidates = [title]
    if year:
        candidates.append(f"{title} ({year} film)")
    candidates.append(f"{title} ({film_suffix})")
    return list(dict.fromkeys(candidates))


def wikipedia_match_score(
    query_title: str,
    year: str,
    page_title: str,
    snippet: str,
    metadata: dict[str, str],
) -> int:
    if not metadata:
        return 0
    score = 0
    query_key = normalize_match_text(query_title)
    page_key = normalize_match_text(page_title)
    wiki_key = normalize_match_text(metadata.get("wikipedia_title", ""))
    description = normalize_match_text(metadata.get("description", ""))
    extract = normalize_match_text(metadata.get("wikipedia_extract", ""))
    snippet_key = normalize_match_text(snippet)

    if query_key and query_key in {page_key, wiki_key}:
        score += 4
    elif query_key and (query_key in page_key or query_key in wiki_key):
        score += 2
    if year and year in f"{page_title} {metadata.get('wikipedia_extract', '')}":
        score += 2
    if any(marker in description for marker in ["film", "movie", "pelicula", "película"]):
        score += 2
    if any(marker in f"{extract} {snippet_key}" for marker in ["directed by", "starring", "film", "movie", "pelicula", "película"]):
        score += 1
    return score


def normalize_match_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9áéíóúñü]+", " ", value)
    return clean_whitespace(value)


def clean_search_title(value: str) -> str:
    value = re.sub(
        r"\s*\((film|movie|pelicula|película|miniserie|tv series|serie de tv|video game|cortometraje)[^)]*\)?\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"^grupo:\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+filmaffinity$", "", value, flags=re.IGNORECASE)
    return clean_whitespace(value)


def looks_like_external_id(value: str) -> bool:
    return bool(re.fullmatch(r"(tt|nm)\d+", value.strip(), flags=re.IGNORECASE)) or bool(
        re.fullmatch(r"film\d+", value.strip(), flags=re.IGNORECASE)
    )


def imdb_id_from_text(value: str) -> str:
    match = re.search(r"\btt\d{7,9}\b", value)
    return match.group(0) if match else ""


def wikipedia_page_title(path: str) -> str:
    marker = "/wiki/"
    if marker not in path:
        return ""
    title = path.split(marker, 1)[1].split("#", 1)[0]
    return unquote(title).replace(" ", "_")


def fetch_json(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={
            "User-Agent": "MovieInboxImporter/0.1 (+local personal catalog)",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            raw = json.loads(response.read(800_000).decode("utf-8", errors="replace"))
            return raw if isinstance(raw, dict) else {}
    except (HTTPError, URLError, TimeoutError, socket.timeout, OSError, ValueError, json.JSONDecodeError):
        return {}


def source_name(netloc: str) -> str:
    host = netloc.lower().removeprefix("www.")
    if "wikipedia.org" in host:
        return "wikipedia"
    if "imdb.com" in host:
        return "imdb"
    if "filmaffinity.com" in host:
        return "filmaffinity"
    if "letterboxd.com" in host:
        return "letterboxd"
    return host


def source_url_field(source: str, url: str = "") -> str:
    text = f"{source} {url}".lower()
    if "wikipedia" in text:
        return "wikipedia_url"
    if "imdb" in text:
        return "imdb_url"
    if "filmaffinity" in text:
        return "filmaffinity_url"
    return ""


def guess_title_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    if not slug and parsed.netloc:
        return parsed.netloc
    slug = re.sub(r"\.[a-zA-Z0-9]+$", "", slug)
    return clean_title(unquote(slug).replace("_", " ").replace("-", " "))


def clean_title(value: str) -> str:
    value = clean_whitespace(value)
    value = re.sub(r"\s+-\s+Wikipedia$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+-\s+IMDb$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+\(\d{4}\)\s+-\s+IMDb$", "", value, flags=re.IGNORECASE)
    return value


def clean_release_title(value: str) -> str:
    value = clean_title(value)
    value = re.sub(r"\.[a-z0-9]{2,5}$", "", value, flags=re.IGNORECASE)
    value = value.replace(".", " ").replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s+(480p|576p|720p|1080p|2160p|4k|8k)\b.*$", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"\s+(bluray|blu ray|brrip|bdrip|webrip|web dl|webdl|hdrip|dvdrip|hdtv)\b.*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"\s+(x264|x265|h264|h265|hevc|avc|aac|dts|ac3|yify|rarbg)\b.*$", "", value, flags=re.IGNORECASE)
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
    if year_match:
        value = value[: year_match.end()]
    return clean_whitespace(value)


def clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


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


def normalize_kind(value: object) -> str:
    text = str(value or "pelicula").strip().lower()
    mapping = {
        "movie": "pelicula",
        "film": "pelicula",
        "pelicula": "pelicula",
        "película": "pelicula",
        "series": "serie",
        "tv series": "serie",
        "tvseries": "serie",
        "episode": "serie",
        "tv episode": "serie",
        "serie": "serie",
        "anime": "anime",
        "documentary": "documental",
        "documental": "documental",
    }
    return mapping.get(text, "pelicula")


def infer_year(*values: str) -> str:
    for value in values:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", value)
        if match:
            return match.group(1)
    return ""


def normalize_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else ""


def normalize_rating(value: object) -> int:
    try:
        rating = int(float(str(value or 0).strip()))
    except ValueError:
        return 0
    return max(0, min(10, rating))


def stable_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def normalize_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"si", "sí", "yes", "true", "1"}:
        return True
    if text in {"no", "false", "0", ""}:
        return False
    return default


def normalize_status_value(value: object, default: str) -> str:
    text = str(value or default or "to_watch").strip().lower()
    if text == "watched":
        return "watched"
    return "to_watch"


def write_json(path: Path, items: list[CatalogItem]) -> None:
    atomic_write_json(path, catalog_document([asdict(item) for item in items]))


def write_csv(path: Path, items: list[CatalogItem]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        for item in items:
            row = asdict(item)
            for key in ["alternative_titles", "genres", "directors", "writers", "cast", "tags"]:
                row[key] = ", ".join(row.get(key, []))
            row["local_files"] = json.dumps(row.get("local_files", []), ensure_ascii=False)
            row["metadata_sources"] = json.dumps(row.get("metadata_sources", {}), ensure_ascii=False)
            row["locked_fields"] = ", ".join(row.get("locked_fields", []))
            writer.writerow(row)


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
