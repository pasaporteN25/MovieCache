#!/usr/bin/env python3
"""Upgrade a legacy catalog to the current versioned JSON schema."""

from __future__ import annotations

import argparse
from pathlib import Path

from catalog_domain import annotate_duplicate_items, normalize_item
from catalog_repository import JsonCatalogRepository
from catalog_schema import SCHEMA_VERSION


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate a movie catalog to the current JSON schema.")
    parser.add_argument("catalog", type=Path, help="Legacy or current catalog JSON.")
    parser.add_argument("--json", dest="output", type=Path, required=True, help="Output JSON path.")
    args = parser.parse_args()

    source = JsonCatalogRepository(args.catalog, normalize_item)
    destination = JsonCatalogRepository(args.output, normalize_item)
    items = source.read()
    annotate_duplicate_items(items)
    duplicate_items = sum(1 for item in items if int(item.get("_duplicate_count") or 0) > 0)
    local_files = sum(len(item.get("local_files") or []) for item in items)
    provenance_fields = sum(len(item.get("metadata_sources") or {}) for item in items)
    locked_fields = sum(len(item.get("locked_fields") or []) for item in items)
    destination.write(items)

    print("Catalog migration summary")
    print(f"- Schema version: {SCHEMA_VERSION}")
    print(f"- Items: {len(items)}")
    print(f"- Local files: {local_files}")
    print(f"- Metadata provenance records: {provenance_fields}")
    print(f"- Locked metadata fields: {locked_fields}")
    print(f"- Items marked as possible duplicates: {duplicate_items}")
    print(f"- Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
