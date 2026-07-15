"""Transactional SQLite repository for the canonical catalog model."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from movie_inbox.application.repository import (
    CatalogBusyError,
    CatalogFormatError,
    CatalogMutation,
    CatalogNormalizer,
    CatalogRepositoryError,
    T,
)
from movie_inbox.domain.models import CatalogItem
from movie_inbox.infrastructure.schema import CATALOG_FIELDS, CatalogSchemaError, catalog_document


DATABASE_SCHEMA_VERSION = 1
LIST_METADATA_FIELDS = ("genres", "directors", "writers", "cast")

SCHEMA_V1 = """
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE catalog_items (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    primary_url TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    original_title TEXT NOT NULL DEFAULT '',
    spanish_title TEXT NOT NULL DEFAULT '',
    english_title TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    watched_at TEXT NOT NULL DEFAULT '',
    rating INTEGER NOT NULL DEFAULT 0 CHECK (rating BETWEEN 0 AND 10),
    year TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    page_image TEXT NOT NULL DEFAULT '',
    wikipedia_extract TEXT NOT NULL DEFAULT '',
    en_catalogo INTEGER NOT NULL DEFAULT 0 CHECK (en_catalogo IN (0, 1)),
    local_name TEXT NOT NULL DEFAULT '',
    local_path TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    review TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX ix_catalog_items_title_year ON catalog_items(title COLLATE NOCASE, year);
CREATE INDEX ix_catalog_items_kind_status ON catalog_items(kind, status);

CREATE TABLE alternative_titles (
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    PRIMARY KEY (item_id, position)
);
CREATE INDEX ix_alternative_titles_title ON alternative_titles(title COLLATE NOCASE);

CREATE TABLE external_ids (
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (item_id, source)
);
CREATE INDEX ix_external_ids_lookup ON external_ids(source, external_id);
CREATE INDEX ix_external_urls_lookup ON external_ids(url);

CREATE TABLE metadata_values (
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    position INTEGER NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (item_id, field, position)
);
CREATE INDEX ix_metadata_values_lookup ON metadata_values(field, value COLLATE NOCASE);

CREATE TABLE tags (
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (item_id, position)
);
CREATE INDEX ix_tags_value ON tags(value COLLATE NOCASE);

CREATE TABLE locked_fields (
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    PRIMARY KEY (item_id, field)
);

CREATE TABLE local_files (
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    path TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    modified_at TEXT NOT NULL DEFAULT '',
    part TEXT NOT NULL DEFAULT '',
    library_id TEXT NOT NULL DEFAULT '',
    relative_path TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL DEFAULT '',
    last_seen_at TEXT NOT NULL DEFAULT '',
    available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    PRIMARY KEY (item_id, position)
);
CREATE INDEX ix_local_files_library_path ON local_files(library_id, relative_path);
CREATE INDEX ix_local_files_fingerprint ON local_files(fingerprint);

CREATE TABLE metadata_provenance (
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    inferred INTEGER NOT NULL DEFAULT 0 CHECK (inferred IN (0, 1)),
    PRIMARY KEY (item_id, field)
);

CREATE TABLE seasons (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
    season_number INTEGER NOT NULL CHECK (season_number >= 0),
    title TEXT NOT NULL DEFAULT '',
    overview TEXT NOT NULL DEFAULT '',
    air_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'to_watch',
    UNIQUE (item_id, season_number)
);

CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    episode_number INTEGER NOT NULL CHECK (episode_number >= 0),
    title TEXT NOT NULL DEFAULT '',
    overview TEXT NOT NULL DEFAULT '',
    air_date TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'to_watch',
    watched_at TEXT NOT NULL DEFAULT '',
    rating INTEGER NOT NULL DEFAULT 0 CHECK (rating BETWEEN 0 AND 10),
    review TEXT NOT NULL DEFAULT '',
    UNIQUE (season_id, episode_number)
);
"""


class SqliteCatalogRepository:
    def __init__(
        self,
        path: Path,
        normalizer: CatalogNormalizer,
        busy_timeout: float = 10.0,
    ) -> None:
        self.path = Path(path)
        self.normalizer = normalizer
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def read(self) -> list[CatalogItem]:
        if not self.path.is_file():
            raise CatalogRepositoryError(f"Catalog does not exist: {self.path}")
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN")
                    items = self._read_items(connection)
                    connection.commit()
                    return items
            except sqlite3.Error as error:
                raise self._repository_error("read", error) from error

    def write(self, items: list[CatalogItem]) -> None:
        rows = self._validated_rows(items)
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    self._replace_items(connection, rows)
                    connection.commit()
            except sqlite3.Error as error:
                raise self._repository_error("write", error) from error

    def mutate(self, mutation: CatalogMutation[T]) -> T:
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    items = self._read_items(connection)
                    changed, result = mutation(items)
                    if changed:
                        rows = self._validated_rows(items)
                        self._replace_items(connection, rows)
                    connection.commit()
                    return result
            except sqlite3.Error as error:
                raise self._repository_error("mutate", error) from error

    def database_version(self) -> int:
        if not self.path.is_file():
            raise CatalogRepositoryError(f"Catalog does not exist: {self.path}")
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    return self._current_version(connection)
            except sqlite3.Error as error:
                raise self._repository_error("inspect", error) from error

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection

    def _initialize(self, connection: sqlite3.Connection) -> None:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        if not exists:
            has_tables = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()
            if has_tables:
                raise CatalogFormatError(f"SQLite catalog has tables but no migration history: {self.path}")
            try:
                connection.executescript("BEGIN IMMEDIATE;\n" + SCHEMA_V1)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (1, "initial relational catalog", _utc_now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            return
        version = self._current_version(connection)
        if version > DATABASE_SCHEMA_VERSION:
            raise CatalogFormatError(
                f"SQLite schema v{version} is newer than supported v{DATABASE_SCHEMA_VERSION}: {self.path}"
            )
        if version < DATABASE_SCHEMA_VERSION:
            raise CatalogFormatError(f"Missing SQLite migration from v{version}: {self.path}")

    @staticmethod
    def _current_version(connection: sqlite3.Connection) -> int:
        row = connection.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
        return int(row["version"] if row else 0)

    def _validated_rows(self, items: list[CatalogItem]) -> list[dict[str, Any]]:
        try:
            rows = [dict(row) for row in catalog_document(items)["items"]]
        except CatalogSchemaError as error:
            raise CatalogFormatError(f"Cannot write invalid catalog: {self.path} ({error})") from error
        ids = [str(row.get("id") or "") for row in rows]
        if len(ids) != len(set(ids)):
            raise CatalogFormatError(f"Cannot write catalog with duplicate item ids: {self.path}")
        return rows

    def _read_items(self, connection: sqlite3.Connection) -> list[CatalogItem]:
        rows = connection.execute("SELECT * FROM catalog_items ORDER BY position, id").fetchall()
        items: list[CatalogItem] = []
        for row in rows:
            item_id = str(row["id"])
            item: dict[str, Any] = {
                "id": item_id,
                "url": row["primary_url"],
                "source": row["source"],
                "title": row["title"],
                "original_title": row["original_title"],
                "spanish_title": row["spanish_title"],
                "english_title": row["english_title"],
                "alternative_titles": self._values(connection, "alternative_titles", item_id, "title"),
                "kind": row["kind"],
                "status": row["status"],
                "watched_at": row["watched_at"],
                "rating": int(row["rating"]),
                "year": row["year"],
                "description": row["description"],
                "wikipedia_url": "",
                "imdb_url": "",
                "filmaffinity_url": "",
                "wikipedia_title": "",
                "wikidata_id": "",
                "genres": [],
                "directors": [],
                "writers": [],
                "cast": [],
                "page_image": row["page_image"],
                "wikipedia_extract": row["wikipedia_extract"],
                "en_catalogo": bool(row["en_catalogo"]),
                "local_files": self._local_files(connection, item_id),
                "local_name": row["local_name"],
                "local_path": row["local_path"],
                "tags": self._values(connection, "tags", item_id, "value"),
                "notes": row["notes"],
                "review": row["review"],
                "metadata_sources": self._metadata_sources(connection, item_id),
                "locked_fields": self._values(connection, "locked_fields", item_id, "field", order="field"),
                "added_at": row["added_at"],
            }
            for field in LIST_METADATA_FIELDS:
                item[field] = self._metadata_values(connection, item_id, field)
            self._apply_external_ids(connection, item)
            extra = _json_object(row["extra_json"])
            for key, value in extra.items():
                if key not in item:
                    item[key] = value
            normalized = self.normalizer(item)
            items.append(normalized)
        return items

    @staticmethod
    def _values(
        connection: sqlite3.Connection,
        table: str,
        item_id: str,
        column: str,
        order: str = "position",
    ) -> list[str]:
        allowed = {
            ("alternative_titles", "title", "position"),
            ("tags", "value", "position"),
            ("locked_fields", "field", "field"),
        }
        if (table, column, order) not in allowed:
            raise ValueError("Unsupported relational list")
        rows = connection.execute(
            f"SELECT {column} FROM {table} WHERE item_id = ? ORDER BY {order}",
            (item_id,),
        ).fetchall()
        return [str(row[column]) for row in rows]

    @staticmethod
    def _metadata_values(connection: sqlite3.Connection, item_id: str, field: str) -> list[str]:
        rows = connection.execute(
            "SELECT value FROM metadata_values WHERE item_id = ? AND field = ? ORDER BY position",
            (item_id, field),
        ).fetchall()
        return [str(row["value"]) for row in rows]

    @staticmethod
    def _local_files(connection: sqlite3.Connection, item_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM local_files WHERE item_id = ? ORDER BY position",
            (item_id,),
        ).fetchall()
        return [
            {
                "path": row["path"],
                "name": row["name"],
                "size_bytes": int(row["size_bytes"]),
                "modified_at": row["modified_at"],
                "part": row["part"],
                "library_id": row["library_id"],
                "relative_path": row["relative_path"],
                "fingerprint": row["fingerprint"],
                "last_seen_at": row["last_seen_at"],
                "available": bool(row["available"]),
            }
            for row in rows
        ]

    @staticmethod
    def _metadata_sources(connection: sqlite3.Connection, item_id: str) -> dict[str, dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM metadata_provenance WHERE item_id = ? ORDER BY field",
            (item_id,),
        ).fetchall()
        return {
            str(row["field"]): {
                "source": row["source"],
                "url": row["url"],
                "updated_at": row["updated_at"],
                "inferred": bool(row["inferred"]),
            }
            for row in rows
        }

    @staticmethod
    def _apply_external_ids(connection: sqlite3.Connection, item: dict[str, Any]) -> None:
        rows = connection.execute(
            "SELECT source, external_id, url, title FROM external_ids WHERE item_id = ?",
            (item["id"],),
        ).fetchall()
        for row in rows:
            source = str(row["source"])
            if source == "wikipedia":
                item["wikipedia_url"] = row["url"]
                item["wikipedia_title"] = row["title"]
            elif source == "imdb":
                item["imdb_url"] = row["url"]
            elif source == "filmaffinity":
                item["filmaffinity_url"] = row["url"]
            elif source == "wikidata":
                item["wikidata_id"] = row["external_id"]

    def _replace_items(self, connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
        incoming_ids = {str(item["id"]) for item in rows}
        existing_ids = {str(row["id"]) for row in connection.execute("SELECT id FROM catalog_items")}
        for removed_id in existing_ids - incoming_ids:
            connection.execute("DELETE FROM catalog_items WHERE id = ?", (removed_id,))
        for position, item in enumerate(rows):
            item_id = str(item["id"])
            for table in (
                "alternative_titles",
                "external_ids",
                "metadata_values",
                "tags",
                "locked_fields",
                "local_files",
                "metadata_provenance",
            ):
                connection.execute(f"DELETE FROM {table} WHERE item_id = ?", (item_id,))
            extra = {
                key: value
                for key, value in item.items()
                if key not in CATALOG_FIELDS and not str(key).startswith("_")
            }
            connection.execute(
                """INSERT INTO catalog_items(
                    id, position, primary_url, source, title, original_title, spanish_title, english_title,
                    kind, status, watched_at, rating, year, description, page_image, wikipedia_extract,
                    en_catalogo, local_name, local_path, notes, review, added_at, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    position = excluded.position,
                    primary_url = excluded.primary_url,
                    source = excluded.source,
                    title = excluded.title,
                    original_title = excluded.original_title,
                    spanish_title = excluded.spanish_title,
                    english_title = excluded.english_title,
                    kind = excluded.kind,
                    status = excluded.status,
                    watched_at = excluded.watched_at,
                    rating = excluded.rating,
                    year = excluded.year,
                    description = excluded.description,
                    page_image = excluded.page_image,
                    wikipedia_extract = excluded.wikipedia_extract,
                    en_catalogo = excluded.en_catalogo,
                    local_name = excluded.local_name,
                    local_path = excluded.local_path,
                    notes = excluded.notes,
                    review = excluded.review,
                    added_at = excluded.added_at,
                    extra_json = excluded.extra_json""",
                (
                    item_id, position, item.get("url", ""), item.get("source", ""), item.get("title", ""),
                    item.get("original_title", ""), item.get("spanish_title", ""), item.get("english_title", ""),
                    item.get("kind", "pelicula"), item.get("status", "to_watch"), item.get("watched_at", ""),
                    int(item.get("rating") or 0), item.get("year", ""), item.get("description", ""),
                    item.get("page_image", ""), item.get("wikipedia_extract", ""),
                    int(bool(item.get("en_catalogo"))), item.get("local_name", ""), item.get("local_path", ""),
                    item.get("notes", ""), item.get("review", ""), item.get("added_at", ""), _json_dump(extra),
                ),
            )
            self._insert_positioned(connection, "alternative_titles", "title", item_id, item.get("alternative_titles", []))
            for field in LIST_METADATA_FIELDS:
                for value_position, value in enumerate(item.get(field, [])):
                    connection.execute(
                        "INSERT INTO metadata_values(item_id, field, position, value) VALUES (?, ?, ?, ?)",
                        (item_id, field, value_position, str(value)),
                    )
            self._insert_positioned(connection, "tags", "value", item_id, item.get("tags", []))
            for field in item.get("locked_fields", []):
                connection.execute(
                    "INSERT INTO locked_fields(item_id, field) VALUES (?, ?)",
                    (item_id, str(field)),
                )
            self._insert_external_ids(connection, item)
            self._insert_local_files(connection, item_id, item.get("local_files", []))
            self._insert_metadata_sources(connection, item_id, item.get("metadata_sources", {}))

    @staticmethod
    def _insert_positioned(
        connection: sqlite3.Connection,
        table: str,
        column: str,
        item_id: str,
        values: Any,
    ) -> None:
        if (table, column) not in {("alternative_titles", "title"), ("tags", "value")}:
            raise ValueError("Unsupported relational list")
        for position, value in enumerate(values if isinstance(values, list) else []):
            connection.execute(
                f"INSERT INTO {table}(item_id, position, {column}) VALUES (?, ?, ?)",
                (item_id, position, str(value)),
            )

    @staticmethod
    def _insert_external_ids(connection: sqlite3.Connection, item: dict[str, Any]) -> None:
        records = [
            ("wikipedia", "", item.get("wikipedia_url", ""), item.get("wikipedia_title", "")),
            ("imdb", _external_id(item.get("imdb_url", ""), r"\btt\d{7,9}\b"), item.get("imdb_url", ""), ""),
            ("filmaffinity", _external_id(item.get("filmaffinity_url", ""), r"film(\d+)"), item.get("filmaffinity_url", ""), ""),
            ("wikidata", item.get("wikidata_id", ""), "", ""),
        ]
        for source, external_id, url, title in records:
            if not any([external_id, url, title]):
                continue
            connection.execute(
                "INSERT INTO external_ids(item_id, source, external_id, url, title) VALUES (?, ?, ?, ?, ?)",
                (item["id"], source, str(external_id), str(url), str(title)),
            )

    @staticmethod
    def _insert_local_files(connection: sqlite3.Connection, item_id: str, files: Any) -> None:
        for position, row in enumerate(files if isinstance(files, list) else []):
            connection.execute(
                """INSERT INTO local_files(
                    item_id, position, path, name, size_bytes, modified_at, part, library_id,
                    relative_path, fingerprint, last_seen_at, available
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item_id, position, row.get("path", ""), row.get("name", ""), int(row.get("size_bytes") or 0),
                    row.get("modified_at", ""), row.get("part", ""), row.get("library_id", ""),
                    row.get("relative_path", ""), row.get("fingerprint", ""), row.get("last_seen_at", ""),
                    int(bool(row.get("available", True))),
                ),
            )

    @staticmethod
    def _insert_metadata_sources(connection: sqlite3.Connection, item_id: str, sources: Any) -> None:
        if not isinstance(sources, dict):
            return
        for field, row in sources.items():
            connection.execute(
                """INSERT INTO metadata_provenance(
                    item_id, field, source, url, updated_at, inferred
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    item_id, str(field), row.get("source", ""), row.get("url", ""),
                    row.get("updated_at", ""), int(bool(row.get("inferred"))),
                ),
            )

    def _repository_error(self, operation: str, error: sqlite3.Error) -> CatalogRepositoryError:
        message = str(error).casefold()
        if "locked" in message or "busy" in message:
            return CatalogBusyError(f"Catalog is busy: {self.path}")
        if isinstance(error, (sqlite3.DatabaseError, sqlite3.IntegrityError)):
            return CatalogFormatError(f"Cannot {operation} SQLite catalog: {self.path} ({error})")
        return CatalogRepositoryError(f"Cannot {operation} SQLite catalog: {self.path} ({error})")


def _external_id(value: Any, pattern: str) -> str:
    match = re.search(pattern, str(value or ""), flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1) if match.lastindex else match.group(0)


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
