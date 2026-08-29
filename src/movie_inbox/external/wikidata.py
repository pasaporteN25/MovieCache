"""Wikidata metadata and article resolution client."""

from __future__ import annotations

import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from movie_inbox.domain.catalog import merge_lists
from movie_inbox.domain.releases import normalize_release_dates
from movie_inbox.external.common import fetch_json_safe, object_dict, string_list

WIKIDATA_LIST_FIELDS = {
    "countries": ("P495", 8),
    "original_languages": ("P364", 8),
    "producers": ("P162", 12),
    "composers": ("P86", 12),
    "genres": ("P136", 8),
    "directors": ("P57", 8),
    "writers": ("P58", 10),
    "cast": ("P161", 20),
}


def fetch_wikidata_title_matches(query: str) -> dict[str, dict[str, object]]:
    """Return multilingual title evidence keyed by the entity's IMDb title id.

    ``wbsearchentities`` can find a work through an alias even when its label is
    translated (for example, ``Addio zio Tom`` resolves to ``Goodbye Uncle
    Tom``).  The second, batched request verifies that the matching Wikidata
    entity carries the same IMDb id before any title is used as search evidence.
    """
    query = " ".join(query.strip().split())
    if len(query) < 2:
        return {}
    languages = ("es", "en", "ja")
    batches: dict[str, list[object]] = {language: [] for language in languages}
    with ThreadPoolExecutor(
        max_workers=len(languages), thread_name_prefix="wikidata-title"
    ) as executor:
        futures = {
            executor.submit(
                fetch_json_safe,
                "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json"
                f"&language={language}&uselang={language}&type=item&limit=5&search=" + quote(query),
                timeout=5,
            ): language
            for language in languages
        }
        for future in as_completed(futures):
            language = futures[future]
            try:
                raw = future.result()
            except (OSError, TimeoutError, ValueError):
                raw = {}
            search_rows = raw.get("search")
            batches[language] = list(search_rows) if isinstance(search_rows, list) else []

    matched_rows: dict[str, dict[str, object]] = {}
    for language in languages:
        for row in batches[language]:
            if not isinstance(row, dict):
                continue
            entity_id = str(row.get("id") or "")
            if entity_id.startswith("Q"):
                matched_rows.setdefault(entity_id, row)
    entity_ids = list(matched_rows)[:12]
    if not entity_ids:
        return {}
    entity_raw = fetch_json_safe(
        "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
        "&props=claims%7Clabels%7Caliases&languages=es%7Cen%7Cja&ids="
        + quote("|".join(entity_ids), safe="|"),
        timeout=5,
    )
    entities = object_dict(entity_raw.get("entities"))
    matches: dict[str, dict[str, object]] = {}
    for entity_id, search_row in matched_rows.items():
        entity = object_dict(entities.get(entity_id))
        if not entity:
            continue
        claims = object_dict(entity.get("claims"))
        imdb_id = wikidata_claim_string(claims, "P345")
        if not re.fullmatch(r"tt\d{7,9}", imdb_id, flags=re.IGNORECASE):
            continue
        metadata = wikidata_title_metadata(entity)
        kind = wikidata_kind(claims)
        if kind:
            metadata["kind"] = kind
        year = wikidata_claim_year(claims, "P577")
        if year:
            metadata["year"] = year
        match = object_dict(search_row.get("match"))
        search_aliases = search_row.get("aliases")
        candidate_aliases = [
            str(search_row.get("label") or ""),
            str(match.get("text") or ""),
            *(
                [str(value or "") for value in search_aliases]
                if isinstance(search_aliases, list)
                else []
            ),
        ]
        primary_keys = {
            str(metadata.get(field) or "").casefold()
            for field in ("original_title", "spanish_title", "english_title")
            if metadata.get(field)
        }
        aliases = [
            value
            for value in merge_lists(
                string_list(metadata.get("alternative_titles")),
                candidate_aliases,
            )
            if value.casefold() not in primary_keys
        ][:40]
        if aliases:
            metadata["alternative_titles"] = aliases
        matches[imdb_id.lower()] = metadata
    return matches


def fetch_wikidata_metadata(entity_id: str) -> dict[str, object]:
    if not entity_id:
        return {}
    raw = fetch_json_safe(
        f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json", timeout=5
    )
    entities = object_dict(raw.get("entities"))
    entity = object_dict(entities.get(entity_id))
    if not entity:
        return {}
    claims = object_dict(entity.get("claims"))
    ids_by_field: dict[str, list[str]] = {}
    all_ids: list[str] = []
    for field, (prop, limit) in WIKIDATA_LIST_FIELDS.items():
        ids = wikidata_claim_entity_ids(claims, prop, limit)
        ids_by_field[field] = ids
        all_ids.extend(ids)

    labels = fetch_wikidata_labels(all_ids)
    metadata = wikidata_title_metadata(entity)
    kind = wikidata_kind(claims)
    if kind:
        metadata["kind"] = kind
    year = wikidata_claim_year(claims, "P577")
    if year:
        metadata["year"] = year
    release_dates = wikidata_claim_release_dates(claims, entity_id)
    if release_dates:
        metadata["release_dates"] = release_dates
    duration_minutes = wikidata_claim_duration_minutes(claims)
    if duration_minutes is not None:
        metadata["duration_minutes"] = duration_minutes
    for field, ids in ids_by_field.items():
        values = [labels.get(item_id, item_id) for item_id in ids if labels.get(item_id, item_id)]
        if values:
            metadata[field] = values
    return metadata


def wikidata_kind(claims: dict[str, object]) -> str:
    instance_ids = set(wikidata_claim_entity_ids(claims, "P31", 12))
    if instance_ids & {"Q1107", "Q63952888"}:
        return "anime"
    if "Q93204" in instance_ids:
        return "documental"
    if instance_ids & {"Q5398426", "Q1259759", "Q15416"}:
        return "serie"
    if instance_ids & {"Q11424", "Q24862", "Q506240"}:
        return "pelicula"
    return ""


def wikidata_title_metadata(entity: dict[str, object]) -> dict[str, object]:
    labels = object_dict(entity.get("labels"))
    aliases = object_dict(entity.get("aliases"))
    claims = object_dict(entity.get("claims"))
    original_title = wikidata_claim_monolingual_text(claims, "P1476")
    spanish_title = wikidata_label_value(labels, "es")
    english_title = wikidata_label_value(labels, "en")
    alternative_titles = merge_lists(
        wikidata_all_label_values(labels), wikidata_all_alias_values(aliases)
    )
    primary_keys = {
        value.casefold() for value in [original_title, spanish_title, english_title] if value
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


def wikidata_claim_string(claims: dict[str, object], prop: str) -> str:
    for statement in _ordered_statements(claims, prop):
        value = _claim_value(statement)
        text = str(value or "").strip() if not isinstance(value, dict) else ""
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


def wikidata_claim_duration_minutes(claims: dict[str, object]) -> int | None:
    unit_factors = {
        "Q7727": 1.0,
        "Q11574": 1.0 / 60.0,
        "Q25235": 60.0,
    }
    for statement in _ordered_statements(claims, "P2047"):
        value = _claim_value(statement)
        if not isinstance(value, dict):
            continue
        unit_id = str(value.get("unit") or "").rstrip("/").rsplit("/", 1)[-1]
        factor = unit_factors.get(unit_id)
        if factor is None:
            continue
        try:
            minutes = float(str(value.get("amount") or "")) * factor
        except ValueError:
            continue
        if math.isfinite(minutes) and minutes > 0:
            return max(1, int(round(minutes)))
    return None


def wikidata_claim_release_dates(
    claims: dict[str, object], entity_id: str = ""
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for position, statement in enumerate(_ordered_statements(claims, "P577")):
        value = _claim_value(statement)
        if not isinstance(value, dict):
            continue
        raw_time = str(value.get("time") or "").lstrip("+")
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw_time)
        if not match:
            continue
        year, month, day = match.groups()
        try:
            precision_value = int(value.get("precision") or 9)
        except (TypeError, ValueError):
            precision_value = 9
        if precision_value >= 11:
            release_date, precision = f"{year}-{month}-{day}", "day"
        elif precision_value == 10:
            release_date, precision = f"{year}-{month}", "month"
        else:
            release_date, precision = year, "year"
        rows.append(
            {
                "date": release_date,
                "precision": precision,
                "country": "",
                "release_type": "publication",
                "source": "wikidata",
                "source_url": f"https://www.wikidata.org/wiki/{entity_id}" if entity_id else "",
                "is_primary": position == 0,
            }
        )
    return normalize_release_dates(rows)


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
        entities = object_dict(raw.get("entities"))
        for item_id, entity in entities.items():
            if not isinstance(entity, dict):
                continue
            label = wikidata_label(object_dict(entity.get("labels")))
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
    raw = fetch_json_safe(
        f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json", timeout=5
    )
    entities = object_dict(raw.get("entities"))
    entity = object_dict(entities.get(entity_id))
    if not entity:
        return ""
    claims = object_dict(entity.get("claims"))
    if not wikidata_claims_include(claims, "P31", {"Q11424", "Q5398426", "Q24862", "Q506240"}):
        description_rows = object_dict(entity.get("descriptions"))
        descriptions = " ".join(
            str(object_dict(value).get("value") or "")
            for value in description_rows.values()
            if isinstance(value, dict)
        ).casefold()
        if not any(marker in descriptions for marker in ["film", "movie", "pelicula"]):
            return ""
    sitelinks = object_dict(entity.get("sitelinks"))
    for key in ["enwiki", "eswiki"]:
        link = object_dict(sitelinks.get(key))
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
    score = (
        4
        if title_key and title_key == label_key
        else 2
        if title_key and (title_key in label_key or label_key in title_key)
        else 0
    )
    if year and year in description:
        score += 1
    if any(marker in description_key for marker in ["film", "movie", "pelicula"]):
        score += 2
    return score


def _match_text(value: str) -> str:
    value = re.sub(r"\([^)]*\)", " ", value.casefold())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()
