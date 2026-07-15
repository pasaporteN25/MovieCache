"""Wikidata metadata and article resolution client."""

from __future__ import annotations

import re
from urllib.parse import quote

from movie_inbox.domain.catalog import merge_lists
from movie_inbox.external.common import fetch_json_safe


WIKIDATA_LIST_FIELDS = {
    "genres": ("P136", 8),
    "directors": ("P57", 8),
    "writers": ("P58", 10),
    "cast": ("P161", 20),
}


def fetch_wikidata_metadata(entity_id: str) -> dict[str, object]:
    if not entity_id:
        return {}
    raw = fetch_json_safe(f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json", timeout=5)
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
    metadata = wikidata_title_metadata(entity)
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
    alternative_titles = merge_lists(wikidata_all_label_values(labels), wikidata_all_alias_values(aliases))
    primary_keys = {value.casefold() for value in [original_title, spanish_title, english_title] if value}
    alternative_titles = [value for value in alternative_titles if value.casefold() not in primary_keys][:40]
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
    return [
        str(row.get("value") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("value") or "").strip()
    ]


def wikidata_all_label_values(labels: dict[str, object]) -> list[str]:
    return [
        str(row.get("value") or "").strip()
        for row in labels.values()
        if isinstance(row, dict) and str(row.get("value") or "").strip()
    ]


def wikidata_all_alias_values(aliases: dict[str, object]) -> list[str]:
    values: list[str] = []
    for rows in aliases.values():
        if isinstance(rows, list):
            values.extend(
                str(row.get("value") or "").strip()
                for row in rows
                if isinstance(row, dict) and str(row.get("value") or "").strip()
            )
    return values


def _ordered_statements(claims: dict[str, object], prop: str) -> list[dict[str, object]]:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return []
    return sorted(
        [row for row in statements if isinstance(row, dict) and row.get("rank") != "deprecated"],
        key=lambda row: 0 if row.get("rank") == "preferred" else 1,
    )


def _claim_value(statement: dict[str, object]) -> object:
    mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
    datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
    return datavalue.get("value") if isinstance(datavalue, dict) else {}


def wikidata_claim_monolingual_text(claims: dict[str, object], prop: str) -> str:
    for statement in _ordered_statements(claims, prop):
        value = _claim_value(statement)
        text = str(value.get("text") or "").strip() if isinstance(value, dict) else ""
        if text:
            return text
    return ""


def wikidata_claim_entity_ids(claims: dict[str, object], prop: str, limit: int) -> list[str]:
    ids: list[str] = []
    for statement in _ordered_statements(claims, prop):
        value = _claim_value(statement)
        item_id = str(value.get("id") or "") if isinstance(value, dict) else ""
        if item_id and item_id not in ids:
            ids.append(item_id)
        if len(ids) >= limit:
            break
    return ids


def wikidata_claim_year(claims: dict[str, object], prop: str) -> str:
    for statement in _ordered_statements(claims, prop):
        value = _claim_value(statement)
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
        raw = fetch_json_safe(
            "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
            f"&props=labels&languages=es|en&ids={quote('|'.join(chunk), safe='|')}",
            timeout=5,
        )
        entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
        for item_id, entity in entities.items():
            if not isinstance(entity, dict):
                continue
            label = wikidata_label(entity.get("labels") if isinstance(entity.get("labels"), dict) else {})
            if label:
                labels[str(item_id)] = label
    return labels


def wikidata_label(labels: dict[str, object]) -> str:
    for language in ["es", "en"]:
        value = labels.get(language) if isinstance(labels, dict) else {}
        if isinstance(value, dict) and value.get("value"):
            return str(value["value"])
    return ""


def fetch_wikidata_article_url(entity_id: str) -> str:
    if not entity_id:
        return ""
    raw = fetch_json_safe(f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json", timeout=5)
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    entity = entities.get(entity_id) if isinstance(entities, dict) else {}
    if not isinstance(entity, dict):
        return ""
    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    if not wikidata_claims_include(claims, "P31", {"Q11424", "Q5398426", "Q24862", "Q506240"}):
        description_rows = entity.get("descriptions") if isinstance(entity.get("descriptions"), dict) else {}
        descriptions = " ".join(
            str(value.get("value") or "")
            for value in description_rows.values()
            if isinstance(value, dict)
        ).casefold()
        if not any(marker in descriptions for marker in ["film", "movie", "pelicula"]):
            return ""
    sitelinks = entity.get("sitelinks") if isinstance(entity.get("sitelinks"), dict) else {}
    for key in ["enwiki", "eswiki"]:
        link = sitelinks.get(key) if isinstance(sitelinks, dict) else {}
        if isinstance(link, dict) and link.get("url"):
            return str(link["url"])
    return ""


def wikidata_claims_include(claims: dict[str, object], prop: str, ids: set[str]) -> bool:
    for statement in _ordered_statements(claims, prop):
        value = _claim_value(statement)
        if isinstance(value, dict) and value.get("id") in ids:
            return True
    return False


def wikidata_result_score(title: str, year: str, label: str, description: str) -> int:
    title_key = _match_text(title)
    label_key = _match_text(label)
    description_key = _match_text(description)
    score = 4 if title_key and title_key == label_key else 2 if title_key and (title_key in label_key or label_key in title_key) else 0
    if year and year in description:
        score += 1
    if any(marker in description_key for marker in ["film", "movie", "pelicula"]):
        score += 2
    return score


def _match_text(value: str) -> str:
    value = re.sub(r"\([^)]*\)", " ", value.casefold())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()
