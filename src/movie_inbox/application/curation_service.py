"""Derived curation queues built from canonical catalog data."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from movie_inbox.domain.catalog import (
    annotate_duplicate_items,
    external_urls,
    has_external_link,
    title_match_keys_for_item,
)
from movie_inbox.domain.curation import curation_item_reference


def build_curation_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    annotate_duplicate_items(items)
    cases = [*_duplicate_cases(items), *_missing_link_cases(items)]
    cases.sort(key=_case_sort_key)
    pending = [case for case in cases if case["status"] == "pending"]
    return {
        "counts": {
            "pending": len(pending),
            "duplicates": sum(1 for case in pending if case["type"] == "duplicate"),
            "missing_link": sum(1 for case in pending if case["type"] == "missing_link"),
            "deferred": sum(1 for case in cases if case["status"] == "deferred"),
        },
        "cases": cases,
    }


def curation_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(build_curation_payload(items)["counts"])


def _duplicate_cases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_reference = {curation_item_reference(item): item for item in items}
    seen: set[tuple[str, str]] = set()
    cases: list[dict[str, Any]] = []
    for item in items:
        left_reference = curation_item_reference(item)
        candidates = [
            *[(reference, "pending") for reference in item.get("_duplicate_refs", [])],
            *[(reference, "deferred") for reference in item.get("_duplicate_deferred_refs", [])],
        ]
        for right_reference, status in candidates:
            pair = tuple(sorted((left_reference, str(right_reference))))
            if len(set(pair)) < 2 or pair in seen:
                continue
            seen.add(pair)
            left = by_reference.get(pair[0])
            right = by_reference.get(pair[1])
            if left is None or right is None:
                continue
            cases.append(
                {
                    "id": f"duplicate:{_case_digest(*pair)}",
                    "type": "duplicate",
                    "status": status,
                    "reason": "Posible obra repetida",
                    "evidence": _duplicate_evidence(left, right),
                    "primary": _item_summary(left),
                    "secondary": _item_summary(right),
                }
            )
    return cases


def _missing_link_cases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for item in items:
        if has_external_link(item):
            continue
        status = str(item.get("link_curation_status") or "pending")
        if status in {"not_required", "resolved"}:
            continue
        cases.append(
            {
                "id": f"link:{_case_digest(curation_item_reference(item))}",
                "type": "missing_link",
                "status": "deferred" if status == "deferred" else "pending",
                "reason": "Sin referencia externa",
                "evidence": ["No tiene enlaces de Wikipedia, IMDb ni FilmAffinity"],
                "primary": _item_summary(item),
                "secondary": None,
            }
        )
    return cases


def _duplicate_evidence(left: Mapping[str, Any], right: Mapping[str, Any]) -> list[str]:
    evidence: list[str] = []
    if external_urls(left) & external_urls(right):
        evidence.append("Comparten el mismo enlace externo")
    left_titles = set(title_match_keys_for_item(left))
    right_titles = set(title_match_keys_for_item(right))
    shared_titles = left_titles & right_titles
    if shared_titles:
        left_year = str(left.get("year") or "")
        right_year = str(right.get("year") or "")
        if left_year and left_year == right_year:
            evidence.append(f"Comparten título normalizado y año {left_year}")
        elif any(
            len(title) == 4
            and title.isdigit()
            and title in {left_year, right_year}
            and left_year != right_year
            for title in shared_titles
        ):
            evidence.append("Una ficha parece usar el título numérico como año heredado")
        else:
            evidence.append("Comparten un título normalizado")
    return evidence or ["La similitud del catálogo requiere revisión manual"]


def _item_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ref": curation_item_reference(item),
        "id": str(item.get("id") or ""),
        "source_file": str(item.get("_source_file") or ""),
        "title": str(item.get("title") or item.get("local_name") or "Sin título"),
        "original_title": str(item.get("original_title") or ""),
        "spanish_title": str(item.get("spanish_title") or ""),
        "english_title": str(item.get("english_title") or ""),
        "year": str(item.get("year") or ""),
        "kind": str(item.get("kind") or "pelicula"),
        "source": str(item.get("source") or ""),
        "url": str(item.get("url") or ""),
        "page_image": str(item.get("page_image") or ""),
        "description": str(item.get("wikipedia_extract") or item.get("description") or ""),
        "en_catalogo": bool(item.get("en_catalogo")),
        "status": str(item.get("status") or "to_watch"),
    }


def _case_digest(*values: str) -> str:
    return hashlib.sha1("\0".join(values).encode("utf-8")).hexdigest()[:16]


def _case_sort_key(case: Mapping[str, Any]) -> tuple[int, int, str]:
    return (
        1 if case.get("status") == "deferred" else 0,
        0 if case.get("type") == "duplicate" else 1,
        str(case.get("primary", {}).get("title") or "").casefold(),
    )
