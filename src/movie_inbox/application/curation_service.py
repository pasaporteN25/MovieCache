"""Derived curation queues built from canonical catalog data."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from movie_inbox.domain.catalog import (
    annotate_duplicate_items,
    external_link_coverage,
    external_urls,
    has_external_link,
    title_match_keys_for_item,
)
from movie_inbox.domain.curation import curation_item_reference
from movie_inbox.domain.metadata import normalize_local_files


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
            "partial_link": sum(1 for item in items if external_link_coverage(item) in (1, 2)),
            "deferred": sum(1 for case in cases if case["status"] == "deferred"),
        },
        "cases": cases,
    }


def curation_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return dict(build_curation_payload(items)["counts"])


def _duplicate_cases(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_reference = {curation_item_reference(item): item for item in items}
    edges: dict[tuple[str, str], str] = {}
    cases: list[dict[str, Any]] = []
    for item in items:
        left_reference = curation_item_reference(item)
        candidates = [
            *[(reference, "pending") for reference in item.get("_duplicate_refs", [])],
            *[(reference, "deferred") for reference in item.get("_duplicate_deferred_refs", [])],
        ]
        for right_reference, status in candidates:
            right_key = str(right_reference)
            pair = (
                (left_reference, right_key)
                if left_reference <= right_key
                else (right_key, left_reference)
            )
            if len(set(pair)) < 2:
                continue
            if pair[0] in by_reference and pair[1] in by_reference:
                previous = edges.get(pair)
                edges[pair] = "pending" if "pending" in {previous, status} else "deferred"

    adjacency: dict[str, set[str]] = {reference: set() for reference in by_reference}
    for left_reference, right_reference in edges:
        adjacency[left_reference].add(right_reference)
        adjacency[right_reference].add(left_reference)

    unseen = {reference for reference, neighbors in adjacency.items() if neighbors}
    while unseen:
        seed = min(unseen)
        component: set[str] = set()
        pending = [seed]
        while pending:
            reference = pending.pop()
            if reference in component:
                continue
            component.add(reference)
            pending.extend(adjacency[reference] - component)
        unseen -= component
        member_references = sorted(component)
        component_edges = [
            (pair, status)
            for pair, status in edges.items()
            if pair[0] in component and pair[1] in component
        ]
        evidence: list[str] = []
        for (left_reference, right_reference), _ in component_edges:
            for row in _duplicate_evidence(
                by_reference[left_reference], by_reference[right_reference]
            ):
                if row not in evidence:
                    evidence.append(row)
        cases.append(
            {
                "id": f"duplicate:{_case_digest(*member_references)}",
                "type": "duplicate",
                "status": (
                    "pending"
                    if any(status == "pending" for _, status in component_edges)
                    else "deferred"
                ),
                "reason": "Posible obra repetida",
                "evidence": evidence,
                "members": [
                    _item_summary(by_reference[reference]) for reference in member_references
                ],
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
        "_availability": item.get("_availability"),
        "added_at": str(item.get("added_at") or ""),
        "local_files": normalize_local_files(item.get("local_files")),
    }


def _case_digest(*values: str) -> str:
    return hashlib.sha1("\0".join(values).encode("utf-8")).hexdigest()[:16]


def _case_sort_key(case: Mapping[str, Any]) -> tuple[int, int, str]:
    members = case.get("members")
    if isinstance(members, list):
        titles = [
            str(member.get("title") or "").casefold()
            for member in members
            if isinstance(member, Mapping)
        ]
        title = min(titles, default="")
    else:
        title = str(case.get("primary", {}).get("title") or "").casefold()
    return (
        1 if case.get("status") == "deferred" else 0,
        0 if case.get("type") == "duplicate" else 1,
        title,
    )
