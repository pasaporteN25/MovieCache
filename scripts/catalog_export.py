#!/usr/bin/env python3
"""Catalog export adapters."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from catalog_models import CatalogItem
from catalog_schema import CATALOG_FIELDS


def write_catalog_csv(path: Path, items: list[CatalogItem]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        for item in items:
            payload = item.to_dict()
            row = {key: payload.get(key, "") for key in CATALOG_FIELDS}
            for key in ("alternative_titles", "genres", "directors", "writers", "cast", "tags"):
                row[key] = ", ".join(row.get(key, []))
            row["local_files"] = json.dumps(row.get("local_files", []), ensure_ascii=False)
            row["metadata_sources"] = json.dumps(row.get("metadata_sources", {}), ensure_ascii=False)
            row["locked_fields"] = ", ".join(row.get("locked_fields", []))
            writer.writerow(row)
