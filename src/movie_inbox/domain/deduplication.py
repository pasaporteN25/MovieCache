#!/usr/bin/env python3
"""Strong-signal catalog deduplication."""

from __future__ import annotations

from movie_inbox.domain.catalog import merge_into_existing
from movie_inbox.domain.matching import find_strong_duplicate
from movie_inbox.domain.models import CatalogItem


def deduplicate_items(items: list[CatalogItem]) -> tuple[list[CatalogItem], list[str]]:
    unique: list[CatalogItem] = []
    merged: list[str] = []
    for item in items:
        target = find_strong_duplicate(unique, item)
        if target is None:
            unique.append(item)
            continue
        merge_into_existing(unique, item, str(target.get("id") or ""))
        merged.append(str(item.get("title") or item.get("local_name") or item.get("url") or item.get("id") or ""))
    return unique, merged


def merge_catalogs(existing: list[CatalogItem], incoming: list[CatalogItem]) -> tuple[list[CatalogItem], list[str]]:
    output = list(existing)
    merged: list[str] = []
    for item in incoming:
        target = find_strong_duplicate(output, item)
        if target is None:
            output.append(item)
            continue
        merge_into_existing(output, item, str(target.get("id") or ""))
        merged.append(str(item.get("title") or item.get("local_name") or item.get("url") or item.get("id") or ""))
    return output, merged

