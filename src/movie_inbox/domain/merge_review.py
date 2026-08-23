"""Field-by-field catalog merge review rules."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from movie_inbox.domain.catalog import (
    ensure_metadata_sources,
    has_external_link,
    merge_lists,
    metadata_source_record,
    normalize_item,
)
from movie_inbox.domain.curation import curation_timestamp, normalize_duplicate_decisions
from movie_inbox.domain.metadata import (
    merge_local_files,
    normalize_local_files,
    normalize_locked_fields,
)
from movie_inbox.domain.releases import merge_release_dates, normalize_release_dates


@dataclass(frozen=True)
class MergeField:
    key: str
    label: str
    group: str
    strategy: str = "scalar"
    protected: bool = False


MERGE_FIELDS = (
    MergeField("title", "Titulo principal", "identity"),
    MergeField("original_title", "Titulo original", "identity"),
    MergeField("spanish_title", "Titulo en espanol", "identity"),
    MergeField("english_title", "Titulo en ingles", "identity"),
    MergeField("alternative_titles", "Titulos alternativos", "identity", "list"),
    MergeField("kind", "Tipo de obra", "identity"),
    MergeField("year", "Ano", "identity"),
    MergeField("release_dates", "Fechas de estreno", "metadata", "release_dates"),
    MergeField("description", "Descripcion", "metadata"),
    MergeField("wikipedia_extract", "Extracto de Wikipedia", "metadata"),
    MergeField("genres", "Generos", "metadata", "list"),
    MergeField("directors", "Direccion", "metadata", "list"),
    MergeField("writers", "Guion", "metadata", "list"),
    MergeField("cast", "Reparto", "metadata", "list"),
    MergeField("page_image", "Portada", "metadata"),
    MergeField("backdrop_image", "Imagen panoramica", "metadata"),
    MergeField("source", "Fuente principal", "sources"),
    MergeField("url", "URL principal", "sources"),
    MergeField("wikipedia_url", "Wikipedia", "sources"),
    MergeField("imdb_url", "IMDb", "sources"),
    MergeField("filmaffinity_url", "FilmAffinity", "sources"),
    MergeField("wikipedia_title", "Titulo de Wikipedia", "sources"),
    MergeField("wikidata_id", "Wikidata", "sources"),
    MergeField("tmdb_id", "TMDB", "sources"),
    MergeField("status", "Estado personal", "personal", protected=True),
    MergeField("watched_at", "Fecha de vista", "personal", protected=True),
    MergeField("rating", "Puntaje", "personal", protected=True),
    MergeField("review", "Review", "personal", protected=True),
    MergeField("notes", "Notas", "personal", protected=True),
    MergeField("tags", "Etiquetas", "personal", "list"),
    MergeField("en_catalogo", "En catalogo", "availability", "boolean_or", protected=True),
    MergeField("local_files", "Archivos locales", "availability", "local_files", protected=True),
)

MERGE_GROUPS = (
    ("identity", "Identidad"),
    ("metadata", "Ficha tecnica"),
    ("sources", "Fuentes externas"),
    ("personal", "Registro personal"),
    ("availability", "Disponibilidad"),
)

FORCED_COMBINE_STRATEGIES = {"boolean_or", "local_files"}


class MergeReviewError(ValueError):
    """Raised when a reviewed merge contains incomplete or invalid decisions."""


def build_merge_review(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    survivor_side: str = "left",
    *,
    external_side: str = "",
) -> dict[str, Any]:
    if survivor_side not in {"left", "right"}:
        raise MergeReviewError("Invalid survivor side")
    if external_side not in {"", "left", "right"}:
        raise MergeReviewError("Invalid external side")
    left_item = normalize_item(left).to_dict()
    right_item = normalize_item(right).to_dict()
    locked = set(normalize_locked_fields(left_item.get("locked_fields"))) | set(
        normalize_locked_fields(right_item.get("locked_fields"))
    )
    fields: list[dict[str, Any]] = []
    unresolved = 0
    for definition in MERGE_FIELDS:
        left_value = _plain_value(left_item.get(definition.key))
        right_value = _plain_value(right_item.get(definition.key))
        different = not _equivalent(definition, left_value, right_value)
        protected = definition.protected or definition.key in locked
        allowed = _allowed_choices(definition)
        default_choice = _default_choice(
            definition,
            left_value,
            right_value,
            survivor_side,
            protected=protected,
            external_side=external_side,
        )
        required = different and protected and not default_choice
        if required:
            unresolved += 1
        fields.append(
            {
                "key": definition.key,
                "label": definition.label,
                "group": definition.group,
                "strategy": definition.strategy,
                "protected": protected,
                "locked": definition.key in locked,
                "different": different,
                "allowed": allowed,
                "default_choice": default_choice,
                "required": required,
                "left": left_value,
                "right": right_value,
            }
        )
    return {
        "review_id": merge_review_id(left_item, right_item),
        "survivor_side": survivor_side,
        "left": _item_summary(left_item),
        "right": _item_summary(right_item),
        "groups": [{"key": key, "label": label} for key, label in MERGE_GROUPS],
        "fields": fields,
        "different_count": sum(1 for field in fields if field["different"]),
        "unresolved_count": unresolved,
    }


def merge_review_id(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    payload = json.dumps(
        [_snapshot_payload(left), _snapshot_payload(right)],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_reviewed_merge(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    survivor_side: str,
    choices: Mapping[str, Any],
    *,
    removed_references: tuple[str, ...] = (),
    external_side: str = "",
) -> dict[str, Any]:
    review = build_merge_review(
        left,
        right,
        survivor_side,
        external_side=external_side,
    )
    left_item = normalize_item(left).to_dict()
    right_item = normalize_item(right).to_dict()
    survivor = left_item if survivor_side == "left" else right_item
    result = dict(survivor)
    left_sources = ensure_metadata_sources(left_item)
    right_sources = ensure_metadata_sources(right_item)
    result_sources = ensure_metadata_sources(survivor)

    for row in review["fields"]:
        key = str(row["key"])
        choice = str(choices.get(key) or row["default_choice"] or "")
        if not row["different"]:
            continue
        if choice not in row["allowed"]:
            if row["required"]:
                raise MergeReviewError(f"Missing decision for protected field: {key}")
            raise MergeReviewError(f"Invalid decision for field: {key}")
        value = _selected_value(
            row["strategy"],
            choice,
            left_item.get(key),
            right_item.get(key),
        )
        result[key] = value
        if key in left_sources or key in right_sources:
            if choice == "left" and key in left_sources:
                result_sources[key] = left_sources[key]
            elif choice == "right" and key in right_sources:
                result_sources[key] = right_sources[key]
            elif choice == "combine":
                result_sources[key] = metadata_source_record("manual_merge", "", False)

    result["id"] = str(survivor.get("id") or "")
    result["metadata_sources"] = result_sources
    result["locked_fields"] = normalize_locked_fields(
        [
            *normalize_locked_fields(left_item.get("locked_fields")),
            *normalize_locked_fields(right_item.get("locked_fields")),
        ]
    )
    result["duplicate_decisions"] = _merged_duplicate_decisions(
        left_item,
        right_item,
        removed_references,
    )
    result["curation_updated_at"] = curation_timestamp()
    result["added_at"] = str(survivor.get("added_at") or _oldest_date(left_item, right_item))

    local_files = normalize_local_files(result.get("local_files"))
    if local_files:
        result["local_name"] = str(result.get("local_name") or local_files[0].get("name") or "")
        result["local_path"] = str(result.get("local_path") or local_files[0].get("path") or "")
    if has_external_link(result):
        result["link_curation_status"] = "resolved"

    return normalize_item(result).to_dict()


def _allowed_choices(definition: MergeField) -> list[str]:
    if definition.strategy in FORCED_COMBINE_STRATEGIES:
        return ["combine"]
    if definition.strategy in {"list", "release_dates"}:
        return ["left", "combine", "right"]
    return ["left", "right"]


def _default_choice(
    definition: MergeField,
    left: Any,
    right: Any,
    survivor_side: str,
    *,
    protected: bool,
    external_side: str,
) -> str:
    if _equivalent(definition, left, right):
        return ""
    if definition.strategy in FORCED_COMBINE_STRATEGIES:
        return "combine"
    if definition.group == "personal" and external_side:
        return "right" if external_side == "left" else "left"
    left_has_value = _meaningful(definition.key, left)
    right_has_value = _meaningful(definition.key, right)
    if left_has_value and not right_has_value:
        return "left"
    if right_has_value and not left_has_value:
        return "right"
    if (
        definition.key == "kind"
        and str(left or "") == "pelicula"
        and str(right or "") in {"serie", "anime", "documental"}
    ):
        return "right"
    if protected:
        return ""
    if definition.strategy in {"list", "release_dates"}:
        return "combine"
    return survivor_side


def _selected_value(strategy: str, choice: str, left: Any, right: Any) -> Any:
    if choice == "left":
        return _plain_value(left)
    if choice == "right":
        return _plain_value(right)
    if choice != "combine":
        raise MergeReviewError("Invalid merge choice")
    if strategy == "list":
        return merge_lists(_string_list(left), _string_list(right))
    if strategy == "local_files":
        return merge_local_files(normalize_local_files(left), normalize_local_files(right))
    if strategy == "release_dates":
        return merge_release_dates(left, right)
    if strategy == "boolean_or":
        return bool(left or right)
    raise MergeReviewError("Field cannot be combined")


def _equivalent(definition: MergeField, left: Any, right: Any) -> bool:
    if definition.strategy == "list":
        return {value.casefold() for value in _string_list(left)} == {
            value.casefold() for value in _string_list(right)
        }
    if definition.strategy == "local_files":
        return _local_file_keys(left) == _local_file_keys(right)
    if definition.strategy == "release_dates":
        return normalize_release_dates(left) == normalize_release_dates(right)
    return bool(left == right)


def _meaningful(key: str, value: Any) -> bool:
    if key == "status":
        return bool(str(value or ""))
    if key == "rating":
        try:
            return int(value or 0) > 0
        except (TypeError, ValueError):
            return False
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    if isinstance(value, bool):
        return value
    return bool(str(value or "").strip())


def _string_list(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else []
    return [str(row).strip() for row in rows if str(row).strip()]


def _local_file_keys(value: Any) -> set[tuple[str, str, str]]:
    return {
        (
            str(row.get("library_id") or "").casefold(),
            str(row.get("relative_path") or "").replace("\\", "/").casefold(),
            str(row.get("path") or "").replace("\\", "/").casefold(),
        )
        for row in normalize_local_files(value)
    }


def _merged_duplicate_decisions(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    removed_references: tuple[str, ...],
) -> dict[str, dict[str, str]]:
    decisions = {
        **normalize_duplicate_decisions(left.get("duplicate_decisions")),
        **normalize_duplicate_decisions(right.get("duplicate_decisions")),
    }
    for reference in removed_references:
        decisions.pop(reference, None)
        decisions.pop(reference.split("::", 1)[0], None)
    return decisions


def _oldest_date(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    dates = sorted(
        value
        for value in (str(left.get("added_at") or ""), str(right.get("added_at") or ""))
        if value
    )
    return dates[0] if dates else ""


def _snapshot_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_item(item).to_dict()
    keys = {"id", "locked_fields", *(field.key for field in MERGE_FIELDS)}
    return {key: _plain_value(normalized.get(key)) for key in sorted(keys)}


def _plain_value(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _plain_value(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_value(row) for row in value]
    return value


def _item_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "title": str(item.get("title") or item.get("local_name") or "Sin titulo"),
        "year": str(item.get("year") or ""),
        "kind": str(item.get("kind") or "pelicula"),
        "source": str(item.get("source") or ""),
        "page_image": str(item.get("page_image") or ""),
        "en_catalogo": bool(item.get("en_catalogo")),
        "status": str(item.get("status") or "to_watch"),
        "local_files_count": len(normalize_local_files(item.get("local_files"))),
        "has_external_link": has_external_link(item),
        "added_at": str(item.get("added_at") or ""),
    }
