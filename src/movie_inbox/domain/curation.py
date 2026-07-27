"""Persistent curation decisions shared by catalog workflows."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LINK_CURATION_STATUSES = {"pending", "deferred", "not_required", "resolved"}
DUPLICATE_DECISION_STATUSES = {"deferred", "not_duplicate"}


def curation_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_link_curation_status(value: Any, *, linked: bool = False) -> str:
    if linked:
        return "resolved"
    status = str(value or "").strip().casefold()
    if status in {"deferred", "not_required"}:
        return status
    return "pending"


def normalize_duplicate_decisions(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, Mapping):
        return {}
    decisions: dict[str, dict[str, str]] = {}
    for raw_reference, raw_decision in value.items():
        reference = str(raw_reference or "").strip()
        if not reference:
            continue
        if isinstance(raw_decision, Mapping):
            status = str(raw_decision.get("status") or "").strip().casefold()
            updated_at = str(raw_decision.get("updated_at") or "").strip()
        else:
            status = str(raw_decision or "").strip().casefold()
            updated_at = ""
        if status not in DUPLICATE_DECISION_STATUSES:
            continue
        decisions[reference] = {"status": status, "updated_at": updated_at}
    return decisions


def apply_link_curation_decision(
    item: MutableMapping[str, Any],
    status: str,
    *,
    linked: bool = False,
) -> None:
    requested = str(status or "").strip().casefold()
    if requested not in {"pending", "deferred", "not_required"}:
        raise ValueError("Invalid link curation status")
    item["link_curation_status"] = normalize_link_curation_status(requested, linked=linked)
    item["curation_updated_at"] = curation_timestamp()


def apply_duplicate_curation_decision(
    item: MutableMapping[str, Any],
    other_reference: str,
    status: str,
) -> None:
    reference = str(other_reference or "").strip()
    if not reference:
        raise ValueError("Missing duplicate reference")
    requested = str(status or "").strip().casefold()
    if requested not in {*DUPLICATE_DECISION_STATUSES, "pending"}:
        raise ValueError("Invalid duplicate curation status")
    decisions = normalize_duplicate_decisions(item.get("duplicate_decisions"))
    if requested == "pending":
        decisions.pop(reference, None)
        decisions.pop(reference.split("::", 1)[0], None)
    else:
        decisions[reference] = {
            "status": requested,
            "updated_at": curation_timestamp(),
        }
    item["duplicate_decisions"] = decisions
    item["curation_updated_at"] = curation_timestamp()


def curation_item_reference(item: Mapping[str, Any]) -> str:
    item_id = str(item.get("id") or "").strip()
    source_file = str(item.get("_source_file") or "").strip()
    if not source_file:
        return item_id
    return f"{item_id}::{Path(source_file).name.casefold()}"


def duplicate_decision_status(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    left_decisions = normalize_duplicate_decisions(left.get("duplicate_decisions"))
    right_decisions = normalize_duplicate_decisions(right.get("duplicate_decisions"))
    statuses = {
        _decision_status(left_decisions, right),
        _decision_status(right_decisions, left),
    }
    if "not_duplicate" in statuses:
        return "not_duplicate"
    if "deferred" in statuses:
        return "deferred"
    return "pending"


def _decision_status(decisions: Mapping[str, Mapping[str, str]], other: Mapping[str, Any]) -> str:
    reference = curation_item_reference(other)
    item_id = str(other.get("id") or "").strip()
    row = decisions.get(reference) or decisions.get(item_id) or {}
    return str(row.get("status") or "")
