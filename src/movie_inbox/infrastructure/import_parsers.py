"""Bounded, offline parsers for untrusted TXT, CSV and JSON imports."""

from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import uuid
from collections.abc import Mapping
from pathlib import PurePath
from typing import Any
from urllib.parse import unquote, urlparse

from movie_inbox.domain.catalog import (
    canonical_url,
    external_source_name,
    normalize_item,
    source_url_field,
    stable_id,
    title_match_key,
    trusted_external_url,
)
from movie_inbox.domain.imports import ParsedImport, ParsedImportItem
from movie_inbox.domain.titles import (
    clean_release_title,
    clean_title,
    clean_whitespace,
    infer_year,
    looks_like_external_id,
)
from movie_inbox.infrastructure.schema import (
    SCHEMA_VERSION,
    CatalogSchemaError,
    extract_catalog_items,
)

MAX_IMPORT_CONTENT_BYTES = 8 * 1024 * 1024
MAX_IMPORT_ROWS = 10_000
MAX_IMPORT_FIELD_CHARS = 32_768
MAX_IMPORT_JSON_DEPTH = 16
MAX_IMPORT_COLUMNS = 100
SUPPORTED_FORMATS = {"auto", "txt", "csv", "json"}
URL_RE = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
WEB_IMPORT_LOCAL_FIELDS = {
    "_source_file",
    "absolute_path",
    "file_path",
    "filepath",
    "library_path",
    "local_files",
    "local_name",
    "local_path",
    "path",
    "relative_path",
    "source_file",
}

CSV_ALIASES = {
    "id": {"id", "item_id"},
    "url": {"url", "link", "href"},
    "title": {"title", "titulo", "name", "nombre"},
    "original_title": {"original_title", "originaltitle", "titulo_original"},
    "spanish_title": {"spanish_title", "spanishtitle", "titulo_espanol", "titulo_en_espanol"},
    "english_title": {"english_title", "englishtitle", "titulo_ingles", "titulo_en_ingles"},
    "alternative_titles": {
        "alternative_titles",
        "alternativetitles",
        "aliases",
        "titulos_alternativos",
    },
    "kind": {"kind", "type", "tipo"},
    "status": {"status", "estado"},
    "watched_at": {"watched_at", "watchedat", "fecha_vista"},
    "rating": {"rating", "score", "puntaje", "puntuacion"},
    "year": {"year", "ano", "anio"},
    "duration_minutes": {"duration_minutes", "duration", "duracion", "duracion_minutos"},
    "description": {"description", "descripcion", "summary", "sinopsis"},
    "wikipedia_url": {"wikipedia_url", "wikipedia"},
    "imdb_url": {"imdb_url", "imdb"},
    "filmaffinity_url": {"filmaffinity_url", "filmaffinity"},
    "myanimelist_url": {"myanimelist_url", "myanimelist", "mal_url"},
    "mal_id": {"mal_id", "myanimelist_id"},
    "countries": {"countries", "country", "paises", "pais"},
    "original_languages": {
        "original_languages",
        "original_language",
        "idiomas_originales",
        "idioma_original",
    },
    "producers": {"producers", "producer", "productores", "productor"},
    "composers": {"composers", "composer", "compositores", "compositor"},
    "genres": {"genres", "genre", "generos", "genero"},
    "directors": {"directors", "director", "direccion"},
    "writers": {"writers", "writer", "guionistas", "guionista"},
    "cast": {"cast", "actors", "actor", "reparto"},
    "en_catalogo": {"en_catalogo", "in_catalog", "available"},
    "review": {"review", "resena", "comentario"},
    "notes": {"notes", "notas"},
}
CSV_FIELDS = frozenset(CSV_ALIASES)


class ImportParseError(ValueError):
    """Raised when an import source cannot be safely interpreted."""


def parse_import_content(
    source_name: str,
    requested_format: str,
    content: str,
    column_map: Mapping[str, str] | None = None,
) -> ParsedImport:
    if not isinstance(content, str):
        raise ImportParseError("Import content must be text")
    size = len(content.encode("utf-8"))
    if size <= 0:
        raise ImportParseError("Import content is empty")
    if size > MAX_IMPORT_CONTENT_BYTES:
        raise ImportParseError("Import content exceeds the 8 MiB limit")
    if "\x00" in content:
        raise ImportParseError("Binary import content is not allowed")

    clean_name = sanitize_source_name(source_name)
    source_format = detect_import_format(clean_name, requested_format, content)
    if source_format == "json":
        items = _parse_json(content)
    elif source_format == "csv":
        items = _parse_csv(content, column_map or {})
    else:
        items = _parse_txt(content)
    if not items:
        raise ImportParseError("Import source does not contain entries")
    if len(items) > MAX_IMPORT_ROWS:
        raise ImportParseError(f"Import source exceeds the {MAX_IMPORT_ROWS} row limit")
    return ParsedImport(clean_name, source_format, tuple(items))


def sanitize_source_name(value: str) -> str:
    normalized = str(value or "importacion").replace("\\", "/").split("/")[-1]
    normalized = "".join(
        character for character in normalized if character >= " " and character != "\x7f"
    )
    return clean_whitespace(normalized)[:160] or "importacion"


def detect_import_format(source_name: str, requested_format: str, content: str) -> str:
    requested = str(requested_format or "auto").strip().casefold()
    if requested not in SUPPORTED_FORMATS:
        raise ImportParseError("Import format must be auto, txt, csv or json")
    if requested != "auto":
        return requested
    suffix = PurePath(source_name).suffix.casefold()
    if suffix in {".json", ".csv", ".txt"}:
        return suffix[1:]
    stripped = content.lstrip("\ufeff \t\r\n")
    if stripped.startswith(("{", "[")):
        return "json"
    first_line = next((line for line in content.splitlines() if line.strip()), "")
    normalized_headers = {_header_key(value) for value in re.split(r"[,;\t|]", first_line)}
    known_headers = set().union(*CSV_ALIASES.values())
    if len(normalized_headers & known_headers) >= 2:
        return "csv"
    return "txt"


def _parse_txt(content: str) -> list[ParsedImportItem]:
    items: list[ParsedImportItem] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = clean_whitespace(raw_line)
        if not line:
            continue
        if len(line) > MAX_IMPORT_FIELD_CHARS:
            items.append(_invalid_item(len(items), line, "field_too_long"))
            continue
        urls = [_normalize_text_url(match.group(0)) for match in URL_RE.finditer(line)]
        urls = [url for url in urls if url]
        if urls:
            for url in urls:
                items.append(
                    _parsed_mapping(len(items), {"url": url}, f"Linea {line_number}: {url}")
                )
        else:
            items.append(_parsed_title(len(items), line, line_number))
        if len(items) > MAX_IMPORT_ROWS:
            raise ImportParseError(f"Import source exceeds the {MAX_IMPORT_ROWS} row limit")
    return items


def _parse_csv(content: str, column_map: Mapping[str, str]) -> list[ParsedImportItem]:
    sample = content[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    previous_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_IMPORT_FIELD_CHARS)
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff"), newline=""), dialect=dialect)
        headers = [str(value or "").strip() for value in (reader.fieldnames or [])]
        if not headers:
            raise ImportParseError("CSV import requires a header row")
        if len(headers) > MAX_IMPORT_COLUMNS:
            raise ImportParseError(f"CSV import exceeds the {MAX_IMPORT_COLUMNS} column limit")
        mapping = _csv_mapping(headers, column_map)
        items: list[ParsedImportItem] = []
        for row_number, row in enumerate(reader, start=2):
            if len(items) >= MAX_IMPORT_ROWS:
                raise ImportParseError(f"Import source exceeds the {MAX_IMPORT_ROWS} row limit")
            if None in row:
                items.append(_invalid_item(len(items), f"Fila {row_number}", "csv_column_mismatch"))
                continue
            values = {
                field: str(row.get(header) or "").strip()
                for field, header in mapping.items()
                if str(row.get(header) or "").strip()
            }
            label = values.get("title") or values.get("url") or f"Fila {row_number}"
            items.append(_parsed_mapping(len(items), values, label))
        return items
    except csv.Error as error:
        raise ImportParseError(f"CSV import is invalid: {error}") from error
    finally:
        csv.field_size_limit(previous_limit)


def _parse_json(content: str) -> list[ParsedImportItem]:
    _validate_json_text_depth(content)
    try:
        raw = json.loads(
            content.lstrip("\ufeff"),
            object_pairs_hook=_strict_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ImportParseError("JSON import is invalid") from error
    if _json_depth(raw) > MAX_IMPORT_JSON_DEPTH:
        raise ImportParseError(f"JSON import exceeds the depth limit of {MAX_IMPORT_JSON_DEPTH}")

    version: int | None = None
    rows: list[Any]
    if isinstance(raw, list):
        rows = list(raw)
    elif isinstance(raw, Mapping):
        extra = set(raw) - {"schema_version", "items"}
        if extra:
            raise ImportParseError("JSON catalog contains unsupported root fields")
        raw_rows = raw.get("items")
        if not isinstance(raw_rows, list):
            raise ImportParseError("JSON catalog must contain an items array")
        rows = list(raw_rows)
        if "schema_version" in raw:
            version = raw.get("schema_version")
            if (
                not isinstance(version, int)
                or isinstance(version, bool)
                or not 1 <= version <= SCHEMA_VERSION
            ):
                raise ImportParseError("JSON catalog schema version is not supported")
    else:
        raise ImportParseError("JSON catalog root must be an object or array")
    if len(rows) > MAX_IMPORT_ROWS:
        raise ImportParseError(f"Import source exceeds the {MAX_IMPORT_ROWS} row limit")

    items: list[ParsedImportItem] = []
    for position, row in enumerate(rows):
        label = _mapping_label(row) if isinstance(row, Mapping) else f"Entrada {position + 1}"
        if not isinstance(row, Mapping):
            items.append(_invalid_item(position, label, "json_item_not_object"))
            continue
        try:
            envelope: Any = (
                [dict(row)]
                if version is None
                else {"schema_version": version, "items": [dict(row)]}
            )
            migrated = extract_catalog_items(envelope)[0]
        except (CatalogSchemaError, IndexError):
            items.append(_invalid_item(position, label, "invalid_catalog_item"))
            continue
        items.append(_parsed_mapping(position, migrated, label))
    return items


def _csv_mapping(headers: list[str], requested: Mapping[str, str]) -> dict[str, str]:
    by_key = {_header_key(header): header for header in headers if header}
    mapping: dict[str, str] = {}
    for field, aliases in CSV_ALIASES.items():
        match = next((by_key[alias] for alias in aliases if alias in by_key), "")
        if match:
            mapping[field] = match
    for raw_field, raw_header in requested.items():
        field = str(raw_field or "").strip()
        header = str(raw_header or "").strip()
        if field not in CSV_FIELDS or header not in headers:
            raise ImportParseError("CSV column mapping is invalid")
        mapping[field] = header
    if "title" not in mapping and not (
        {"url", "wikipedia_url", "imdb_url", "filmaffinity_url", "myanimelist_url"} & set(mapping)
    ):
        raise ImportParseError("CSV import needs a title or URL column")
    return mapping


def _parsed_title(position: int, raw_title: str, line_number: int) -> ParsedImportItem:
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", raw_title)
    title = clean_release_title(text)
    year = infer_year(title, text)
    if year:
        title = re.sub(rf"\b{re.escape(year)}\b", "", title, count=1).strip(" -_.()[]")
        title = clean_whitespace(title)
    if not title or looks_like_external_id(title):
        return _invalid_item(position, raw_title, "title_not_recognized")
    return _parsed_mapping(
        position,
        {
            "id": stable_id(f"txt:{title_match_key(title)}:{year}"),
            "source": "txt",
            "title": title,
            "year": year,
        },
        f"Linea {line_number}: {title}",
    )


def _parsed_mapping(position: int, raw: Mapping[str, Any], label: str) -> ParsedImportItem:
    try:
        _validate_mapping_bounds(raw)
        item = _normalize_import_item(raw)
    except (TypeError, ValueError):
        return _invalid_item(position, label, "invalid_item")
    if not item.get("id") or not str(item.get("title") or "").strip():
        return _invalid_item(position, label, "title_not_recognized")
    return ParsedImportItem(
        uuid.uuid4().hex, position, _safe_label(item.get("title") or label), item
    )


def _normalize_import_item(raw: Mapping[str, Any]) -> dict[str, Any]:
    item = dict(raw)
    candidate_urls = [
        str(item.get("url") or ""),
        str(item.get("wikipedia_url") or item.get("wikipedia") or ""),
        str(item.get("imdb_url") or item.get("imdb") or ""),
        str(item.get("filmaffinity_url") or item.get("filmaffinity") or ""),
        str(item.get("myanimelist_url") or item.get("myanimelist") or ""),
    ]
    primary_url = next(
        (canonical_url(value) for value in candidate_urls if canonical_url(value)), ""
    )
    if any(value for value in candidate_urls) and not primary_url:
        raise ValueError("Invalid URL")
    source = str(item.get("source") or external_source_name(primary_url) or "").strip().casefold()
    if primary_url:
        item["url"] = primary_url
        item["source"] = source or "web"
        link_field = source_url_field(source, primary_url)
        if link_field:
            item[link_field] = trusted_external_url(primary_url)
    for field in ("wikipedia_url", "imdb_url", "filmaffinity_url", "myanimelist_url"):
        value = str(item.get(field) or "")
        if value:
            trusted = trusted_external_url(value)
            if not trusted or source_url_field("", trusted) != field:
                raise ValueError("Invalid external URL")
            item[field] = trusted
    title = str(item.get("title") or item.get("name") or "").strip()
    if not title and primary_url:
        title = _title_from_url(primary_url)
    if not title:
        title = str(item.get("local_name") or "").strip()
    item["title"] = clean_release_title(title)
    item["year"] = str(item.get("year") or infer_year(title))
    for field in WEB_IMPORT_LOCAL_FIELDS:
        item.pop(field, None)
    item["local_files"] = []
    item["local_name"] = ""
    item["local_path"] = ""
    normalized = normalize_item(item).to_dict()
    normalized["local_files"] = []
    normalized["local_name"] = ""
    normalized["local_path"] = ""
    return normalized


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    slug = re.sub(r"\.[A-Za-z0-9]+$", "", slug)
    return clean_title(unquote(slug).replace("_", " ").replace("-", " "))


def _normalize_text_url(value: str) -> str:
    url = str(value or "").strip()
    while url and url[-1] in ".,;\"'":
        url = url[:-1]
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1]
    while url.endswith("]") and url.count("[") < url.count("]"):
        url = url[:-1]
    return canonical_url(url)


def _validate_mapping_bounds(value: Mapping[str, Any]) -> None:
    for field, row in value.items():
        if len(str(field)) > 128:
            raise ValueError("Field name is too long")
        if isinstance(row, str) and len(row) > MAX_IMPORT_FIELD_CHARS:
            raise ValueError("Field value is too long")
        if isinstance(row, list) and len(row) > 500:
            raise ValueError("Field list is too long")


def _invalid_item(position: int, label: str, reason: str) -> ParsedImportItem:
    return ParsedImportItem(uuid.uuid4().hex, position, _safe_label(label), None, reason)


def _safe_label(value: Any) -> str:
    return clean_whitespace(str(value or "Entrada sin titulo"))[:180] or "Entrada sin titulo"


def _mapping_label(value: Mapping[str, Any]) -> str:
    return _safe_label(
        value.get("title") or value.get("name") or value.get("url") or "Entrada sin titulo"
    )


def _header_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _validate_json_text_depth(value: str) -> None:
    depth = 0
    quoted = False
    escaped = False
    for character in value:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_IMPORT_JSON_DEPTH:
                raise ImportParseError(
                    f"JSON import exceeds the depth limit of {MAX_IMPORT_JSON_DEPTH}"
                )
        elif character in "]}":
            depth = max(0, depth - 1)


def _json_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, Mapping):
        return max((_json_depth(row, depth + 1) for row in value.values()), default=depth + 1)
    if isinstance(value, list):
        return max((_json_depth(row, depth + 1) for row in value), default=depth + 1)
    return depth
