#!/usr/bin/env python3
"""Catalog application service shared by the viewer and filesystem scanner."""

from __future__ import annotations

from typing import Any

from movie_inbox.application.repository import CatalogRepository
from movie_inbox.domain.models import CatalogItem
from movie_inbox.domain.metadata import normalize_local_files, normalize_locked_fields, normalize_metadata_sources
from movie_inbox.domain.catalog import (
    external_urls,
    merge_into_existing,
    metadata_source_record,
    normalize_bool,
    normalize_date,
    normalize_item,
    normalize_kind,
    normalize_rating,
    possible_duplicate_candidates,
    same_catalog_item,
    stable_id,
    title_match_keys_for_item,
    today_date,
)
from movie_inbox.domain.matching import decide_match


EDITABLE_METADATA_FIELDS = {
    "title",
    "original_title",
    "spanish_title",
    "english_title",
    "alternative_titles",
    "kind",
    "year",
    "description",
    "genres",
    "directors",
    "writers",
    "cast",
}
LIST_METADATA_FIELDS = {"alternative_titles", "genres", "directors", "writers", "cast"}


class CatalogService:
    def __init__(self, repository: CatalogRepository) -> None:
        self.repository = repository

    def list_items(self) -> list[CatalogItem]:
        return self.repository.read()

    def append_item(
        self,
        item: dict[str, Any],
        action: str = "check",
        target_id: str = "",
    ) -> tuple[bool, str, dict[str, Any]]:
        normalized = normalize_item(item)

        def mutation(items: list[CatalogItem]) -> tuple[bool, tuple[bool, str, dict[str, Any]]]:
            if action == "merge":
                merged = merge_into_existing(items, normalized, target_id)
                return merged, (merged, "merged" if merged else "merge_target_not_found", {})
            item_urls = external_urls(normalized)
            if item_urls and any(item_urls & external_urls(existing) for existing in items):
                return False, (False, "duplicate", {})
            candidates = possible_duplicate_candidates(items, normalized)
            if action == "check" and candidates:
                return False, (False, "possible_duplicate", {"candidates": candidates[:5]})
            items.insert(0, normalized)
            return True, (True, "added", {})

        return self.repository.mutate(mutation)

    def delete_item(
        self,
        item_id: str,
        item_url: str,
        title: str,
        year: str,
        local_name: str,
        confirmed: bool,
    ) -> tuple[bool, str]:
        if not confirmed:
            raise ValueError("Deletion requires confirmation")
        if not any([item_id, item_url, title, local_name]):
            raise ValueError("Missing item reference")

        def mutation(items: list[CatalogItem]) -> tuple[bool, tuple[bool, str]]:
            for index, item in enumerate(items):
                if same_catalog_item(item, item_id, item_url, title, year, local_name):
                    del items[index]
                    return True, (True, "deleted")
            return False, (False, "not_found")

        return self.repository.mutate(mutation)

    def update_status(self, item_id: str, status: str, watched_at: str = "") -> tuple[bool, str]:
        if not item_id:
            raise ValueError("Missing item id")
        if status not in {"to_watch", "watched"}:
            raise ValueError("Invalid status")

        def update(item: dict[str, Any]) -> None:
            item["status"] = status
            if status == "watched":
                item["watched_at"] = normalize_date(watched_at) or today_date()

        return self._update_item(item_id, update)

    def update_kind(self, item_id: str, kind: str) -> tuple[bool, str]:
        if not item_id:
            raise ValueError("Missing item id")
        kind = normalize_kind(kind)

        def update(item: dict[str, Any]) -> None:
            item["kind"] = kind
            item["locked_fields"] = normalize_locked_fields([*normalize_locked_fields(item.get("locked_fields")), "kind"])
            sources = normalize_metadata_sources(item.get("metadata_sources"))
            sources["kind"] = metadata_source_record("manual", "", False)
            item["metadata_sources"] = sources

        return self._update_item(item_id, update)

    def update_catalog_status(self, item_id: str, en_catalogo: Any) -> tuple[bool, str]:
        if not item_id:
            raise ValueError("Missing item id")
        return self._update_item(item_id, lambda item: item.__setitem__("en_catalogo", normalize_bool(en_catalogo)))

    def update_personal(self, item_id: str, watched_at: str, rating: Any, review: str) -> tuple[bool, str]:
        if not item_id:
            raise ValueError("Missing item id")

        def update(item: dict[str, Any]) -> None:
            item["watched_at"] = normalize_date(watched_at)
            item["rating"] = normalize_rating(rating)
            item["review"] = review.strip()

        return self._update_item(item_id, update)

    def update_metadata(
        self,
        item_id: str,
        values: dict[str, Any],
        locked_fields: Any,
    ) -> tuple[bool, str]:
        if not item_id:
            raise ValueError("Missing item id")
        requested_fields = set(values) & EDITABLE_METADATA_FIELDS
        if not requested_fields and locked_fields is None:
            raise ValueError("Missing metadata values")

        def update(item: dict[str, Any]) -> None:
            sources = normalize_metadata_sources(item.get("metadata_sources"))
            for field in requested_fields:
                value = values.get(field)
                if field in LIST_METADATA_FIELDS:
                    normalized: Any = _normalize_list(value)
                elif field == "kind":
                    normalized = normalize_kind(value)
                else:
                    normalized = str(value or "").strip()
                if field == "title" and not normalized:
                    raise ValueError("Title cannot be empty")
                if item.get(field) == normalized:
                    continue
                item[field] = normalized
                sources[field] = metadata_source_record("manual", "", False)
            if locked_fields is not None:
                item["locked_fields"] = normalize_locked_fields(locked_fields)
            item["metadata_sources"] = sources

        return self._update_item(item_id, update)

    def reconcile_library(
        self,
        library_id: str,
        scanned_files: list[dict[str, Any]],
        scanned_at: str,
        allow_removals: bool,
        commit: bool,
    ) -> dict[str, Any]:
        if not library_id.strip():
            raise ValueError("Missing library id")

        def mutation(items: list[CatalogItem]) -> tuple[bool, dict[str, Any]]:
            report: dict[str, Any] = {
                "discovered": len(scanned_files),
                "unchanged": 0,
                "updated": 0,
                "moved": 0,
                "matched": 0,
                "match_details": [],
                "created": 0,
                "unavailable": 0,
                "needs_review": [],
                "removals_skipped": not allow_removals,
            }
            changed = False
            path_index: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
            fingerprint_index: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
            consumed_fingerprints: set[str] = set()

            for item in items:
                local_files = normalize_local_files(item.get("local_files"), item.get("local_name", ""), item.get("local_path", ""))
                item["local_files"] = local_files
                local_files = item["local_files"]
                for local_file in local_files:
                    relative = _relative_key(local_file.get("relative_path") or local_file.get("path"))
                    owner_library = str(local_file.get("library_id") or "").casefold()
                    if relative:
                        path_index[(owner_library, relative)] = (item, local_file)
                    fingerprint = str(local_file.get("fingerprint") or "")
                    if fingerprint and owner_library == library_id.casefold():
                        fingerprint_index.setdefault(fingerprint, []).append((item, local_file))

            seen_keys: set[tuple[str, str]] = set()
            for raw_file in scanned_files:
                scanned_file = normalize_local_files([raw_file])[0]
                relative = _relative_key(scanned_file.get("relative_path"))
                current_key = (library_id.casefold(), relative)
                seen_keys.add(current_key)
                existing_pair = path_index.get(current_key) or path_index.get(("", relative))

                if existing_pair:
                    owner, local_file = existing_pair
                    file_changed = _file_content_changed(local_file, scanned_file)
                    if file_changed:
                        report["updated"] += 1
                    else:
                        report["unchanged"] += 1
                    if file_changed or str(local_file.get("library_id") or "") != library_id:
                        local_file.update(scanned_file)
                        changed = True
                    elif str(local_file.get("last_seen_at") or "")[:10] != scanned_at[:10]:
                        local_file["last_seen_at"] = scanned_at
                        changed = True
                    if not owner.get("en_catalogo"):
                        owner["en_catalogo"] = True
                        changed = True
                    path_index[current_key] = (owner, local_file)
                    continue

                fingerprint = str(scanned_file.get("fingerprint") or "")
                fingerprint_matches = (
                    fingerprint_index.get(fingerprint, [])
                    if fingerprint and fingerprint not in consumed_fingerprints
                    else []
                )
                if len(fingerprint_matches) == 1:
                    owner, local_file = fingerprint_matches[0]
                    local_file.update(scanned_file)
                    owner["en_catalogo"] = True
                    path_index[current_key] = (owner, local_file)
                    consumed_fingerprints.add(fingerprint)
                    report["moved"] += 1
                    changed = True
                    continue

                candidate = {
                    "title": str(raw_file.get("title") or ""),
                    "year": str(raw_file.get("year") or ""),
                    "local_name": str(scanned_file.get("name") or ""),
                    "local_path": str(scanned_file.get("path") or ""),
                    "kind": str(raw_file.get("kind") or ""),
                }
                title_keys = set(title_match_keys_for_item(candidate))
                exact_matches = [
                    item
                    for item in items
                    if title_keys.intersection(title_match_keys_for_item(item))
                    and _years_compatible(candidate, item)
                ]
                accepted_matches = [
                    (item, decision)
                    for item in exact_matches
                    if (decision := decide_match(item, candidate)).accepted
                ]
                if len(accepted_matches) == 1:
                    owner, decision = accepted_matches[0]
                    owner["local_files"] = normalize_local_files([*owner.get("local_files", []), scanned_file])
                    owner["local_name"] = owner.get("local_name") or scanned_file.get("name", "")
                    owner["local_path"] = owner.get("local_path") or scanned_file.get("path", "")
                    owner["en_catalogo"] = True
                    path_index[current_key] = (owner, owner["local_files"][-1])
                    report["matched"] += 1
                    report["match_details"].append(
                        {
                            "relative_path": scanned_file.get("relative_path", ""),
                            "item_id": owner.get("id", ""),
                            "reason": decision.reason,
                            "evidence": decision.evidence,
                        }
                    )
                    changed = True
                    continue

                candidates = exact_matches or possible_duplicate_candidates(items, candidate)
                if candidates:
                    report["needs_review"].append(
                        {
                            "relative_path": scanned_file.get("relative_path", ""),
                            "title": candidate["title"],
                            "year": candidate["year"],
                            "candidates": [
                                {
                                    "id": item.get("id", ""),
                                    "title": item.get("title", ""),
                                    "year": item.get("year", ""),
                                }
                                for item in candidates[:5]
                            ],
                        }
                    )
                    continue

                new_item = _new_local_item(library_id, scanned_file, candidate, scanned_at, str(raw_file.get("kind") or "pelicula"))
                items.insert(0, new_item)
                path_index[current_key] = (new_item, new_item["local_files"][0])
                report["created"] += 1
                changed = True

            if allow_removals:
                for item in items:
                    item_changed = False
                    for local_file in item.get("local_files", []):
                        if str(local_file.get("library_id") or "").casefold() != library_id.casefold():
                            continue
                        key = (library_id.casefold(), _relative_key(local_file.get("relative_path")))
                        if key not in seen_keys and local_file.get("available", True):
                            local_file["available"] = False
                            report["unavailable"] += 1
                            item_changed = True
                    if item_changed:
                        available = any(bool(local_file.get("available", True)) for local_file in item.get("local_files", []))
                        item["en_catalogo"] = available
                        changed = True

            report["changed"] = changed
            report["items_after"] = len(items)
            return changed, report

        if commit:
            return self.repository.mutate(mutation)
        items = self.repository.read()
        _, report = mutation(items)
        return report

    def _update_item(self, item_id: str, update: Any) -> tuple[bool, str]:
        def mutation(items: list[CatalogItem]) -> tuple[bool, tuple[bool, str]]:
            for item in items:
                if str(item.get("id") or "") == item_id:
                    update(item)
                    return True, (True, "updated")
            return False, (False, "not_found")

        return self.repository.mutate(mutation)


def _normalize_list(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else str(value or "").split(",")
    return list(dict.fromkeys(str(row).strip() for row in rows if str(row).strip()))


def _relative_key(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/").casefold()


def _file_content_changed(existing: dict[str, Any], scanned: dict[str, Any]) -> bool:
    fields = ("path", "name", "size_bytes", "modified_at", "fingerprint", "available")
    return any(existing.get(field) != scanned.get(field) for field in fields)


def _years_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_year = str(left.get("year") or "")
    right_year = str(right.get("year") or "")
    return not left_year or not right_year or left_year == right_year


def _new_local_item(
    library_id: str,
    local_file: dict[str, Any],
    candidate: dict[str, Any],
    scanned_at: str,
    kind: str,
) -> CatalogItem:
    title = str(candidate.get("title") or local_file.get("name") or "Sin titulo")
    seed = f"{library_id}:{local_file.get('relative_path') or local_file.get('path')}"
    return normalize_item(
        {
            "id": stable_id(seed),
            "url": "",
            "source": "local_files",
            "title": title,
            "original_title": "",
            "spanish_title": "",
            "english_title": "",
            "alternative_titles": [],
            "kind": kind,
            "status": "to_watch",
            "watched_at": "",
            "rating": 0,
            "year": str(candidate.get("year") or ""),
            "description": "",
            "wikipedia_url": "",
            "imdb_url": "",
            "filmaffinity_url": "",
            "wikipedia_title": "",
            "wikidata_id": "",
            "genres": [],
            "directors": [],
            "writers": [],
            "cast": [],
            "page_image": "",
            "wikipedia_extract": "",
            "en_catalogo": True,
            "local_files": [local_file],
            "local_name": local_file.get("name", ""),
            "local_path": local_file.get("path", ""),
            "tags": [],
            "notes": "",
            "review": "",
            "metadata_sources": {
                "title": metadata_source_record("local_files", "", False, scanned_at),
                "kind": metadata_source_record("local_files", "", False, scanned_at),
            },
            "locked_fields": [],
            "added_at": scanned_at,
        }
    )
