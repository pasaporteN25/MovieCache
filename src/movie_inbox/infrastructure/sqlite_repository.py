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
    CatalogItemMutation,
    CatalogMutation,
    CatalogNormalizer,
    CatalogRepositoryError,
    T,
)
from movie_inbox.domain.metadata import normalize_local_files
from movie_inbox.domain.models import CatalogItem
from movie_inbox.domain.catalog import possible_duplicate_candidates
from movie_inbox.domain.releases import normalize_release_dates
from movie_inbox.infrastructure.schema import CATALOG_FIELDS, CatalogSchemaError, catalog_document


DATABASE_SCHEMA_VERSION = 4
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

MIGRATIONS = {
    2: (
        "landscape artwork and TMDB identity",
        (
            "ALTER TABLE catalog_items ADD COLUMN backdrop_image TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE catalog_items ADD COLUMN tmdb_id TEXT NOT NULL DEFAULT ''",
        ),
    ),
    3: (
        "persistent curation decisions",
        (
            "ALTER TABLE catalog_items ADD COLUMN link_curation_status TEXT NOT NULL DEFAULT 'pending'",
            "ALTER TABLE catalog_items ADD COLUMN curation_updated_at TEXT NOT NULL DEFAULT ''",
            """CREATE TABLE duplicate_decisions (
                item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
                other_reference TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('deferred', 'not_duplicate')),
                updated_at TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (item_id, other_reference)
            )""",
            "CREATE INDEX ix_catalog_items_link_curation ON catalog_items(link_curation_status)",
            "CREATE INDEX ix_duplicate_decisions_status ON duplicate_decisions(status)",
        ),
    ),
    4: (
        "release dates with precision and provenance",
        (
            """CREATE TABLE release_dates (
                item_id TEXT NOT NULL REFERENCES catalog_items(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                release_date TEXT NOT NULL,
                precision TEXT NOT NULL CHECK (precision IN ('year', 'month', 'day')),
                country TEXT NOT NULL DEFAULT '',
                release_type TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0, 1)),
                PRIMARY KEY (item_id, position)
            )""",
            "CREATE INDEX ix_release_dates_date ON release_dates(release_date)",
        ),
    ),
}


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

    def get(self, item_id: str) -> CatalogItem | None:
        if not self.path.is_file():
            raise CatalogRepositoryError(f"Catalog does not exist: {self.path}")
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN")
                    item = self._read_item(connection, item_id)
                    connection.commit()
                    return item
            except sqlite3.Error as error:
                raise self._repository_error("get", error) from error

    def write(self, items: list[CatalogItem]) -> None:
        rows = self._validated_rows(items)
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    existing = self._validated_rows(self._read_items(connection))
                    self._sync_items(connection, existing, rows)
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
                    before = self._validated_rows(items)
                    changed, result = mutation(items)
                    if changed:
                        rows = self._validated_rows(items)
                        self._sync_items(connection, before, rows)
                    connection.commit()
                    return result
            except sqlite3.Error as error:
                raise self._repository_error("mutate", error) from error

    def update_item(self, item_id: str, mutation: CatalogItemMutation) -> bool:
        if not self.path.is_file():
            return False
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute(
                        "SELECT position FROM catalog_items WHERE id = ?",
                        (item_id,),
                    ).fetchone()
                    if row is None:
                        connection.commit()
                        return False
                    item = self._read_item(connection, item_id)
                    if item is None:
                        connection.commit()
                        return False
                    before = self._validated_rows([item])[0]
                    mutation(item)
                    after = self._validated_rows([item])[0]
                    if str(after["id"]) != item_id:
                        raise CatalogFormatError("Catalog item updates cannot change the item id")
                    if before != after:
                        self._sync_item(connection, before, after, int(row["position"]))
                    connection.commit()
                    return True
            except sqlite3.Error as error:
                raise self._repository_error("update", error) from error

    def update_status(self, item_id: str, status: str, watched_at: str | None = None) -> bool:
        if status not in {"to_watch", "watched"}:
            raise ValueError("Invalid status")
        if not self.path.is_file():
            return False
        assignments = "status = ?"
        values: list[Any] = [status]
        if watched_at is not None:
            assignments += ", watched_at = ?"
            values.append(watched_at)
        values.append(item_id)
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    cursor = connection.execute(
                        f"UPDATE catalog_items SET {assignments} WHERE id = ?",
                        values,
                    )
                    connection.commit()
                    return cursor.rowcount == 1
            except sqlite3.Error as error:
                raise self._repository_error("update status in", error) from error

    def update_metadata(self, item_id: str, mutation: CatalogItemMutation) -> bool:
        return self.update_item(item_id, mutation)

    def delete_by_id(self, item_id: str) -> bool:
        if not self.path.is_file():
            return False
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    row = connection.execute("SELECT position FROM catalog_items WHERE id = ?", (item_id,)).fetchone()
                    if row is None:
                        connection.commit()
                        return False
                    cursor = connection.execute("DELETE FROM catalog_items WHERE id = ?", (item_id,))
                    connection.execute(
                        "UPDATE catalog_items SET position = position - 1 WHERE position > ?",
                        (int(row["position"]),),
                    )
                    connection.commit()
                    return cursor.rowcount == 1
            except sqlite3.Error as error:
                raise self._repository_error("delete from", error) from error

    def attach_local_file(self, item_id: str, local_file: dict[str, Any]) -> bool:
        normalized = normalize_local_files([local_file])
        if not normalized:
            raise ValueError("Invalid local file")
        if not self.path.is_file():
            return False
        row = normalized[0]
        with self._thread_lock:
            try:
                with closing(self._connect()) as connection:
                    self._initialize(connection)
                    connection.execute("BEGIN IMMEDIATE")
                    item = connection.execute(
                        "SELECT local_name, local_path FROM catalog_items WHERE id = ?",
                        (item_id,),
                    ).fetchone()
                    if item is None:
                        connection.commit()
                        return False
                    existing_file = connection.execute(
                        """SELECT 1 FROM local_files
                        WHERE item_id = ? AND (
                            (? != '' AND path = ?) OR (
                                library_id = ? AND relative_path != '' AND relative_path = ?
                            )
                        )""",
                        (item_id, row["path"], row["path"], row["library_id"], row["relative_path"]),
                    ).fetchone()
                    if existing_file is not None:
                        connection.commit()
                        return True
                    position_row = connection.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 AS position FROM local_files WHERE item_id = ?",
                        (item_id,),
                    ).fetchone()
                    position = int(position_row["position"] if position_row else 0)
                    self._insert_local_files(connection, item_id, [row], start_position=position)
                    connection.execute(
                        """UPDATE catalog_items
                        SET en_catalogo = 1,
                            local_name = CASE WHEN local_name = '' THEN ? ELSE local_name END,
                            local_path = CASE WHEN local_path = '' THEN ? ELSE local_path END
                        WHERE id = ?""",
                        (row["name"], row["path"], item_id),
                    )
                    connection.commit()
                    return True
            except sqlite3.Error as error:
                raise self._repository_error("attach local file to", error) from error

    def find_candidates(self, candidate: CatalogItem) -> list[dict[str, Any]]:
        return possible_duplicate_candidates(self.read(), candidate)

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
        version = self._current_version(connection)
        if version > DATABASE_SCHEMA_VERSION:
            raise CatalogFormatError(
                f"SQLite schema v{version} is newer than supported v{DATABASE_SCHEMA_VERSION}: {self.path}"
            )
        for target_version in range(version + 1, DATABASE_SCHEMA_VERSION + 1):
            migration = MIGRATIONS.get(target_version)
            if migration is None:
                raise CatalogFormatError(f"Missing SQLite migration from v{version}: {self.path}")
            name, statements = migration
            try:
                connection.execute("BEGIN IMMEDIATE")
                for statement in statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (target_version, name, _utc_now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

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
        return [self._item_from_row(connection, row) for row in rows]

    def _read_item(self, connection: sqlite3.Connection, item_id: str) -> CatalogItem | None:
        row = connection.execute("SELECT * FROM catalog_items WHERE id = ?", (item_id,)).fetchone()
        return self._item_from_row(connection, row) if row is not None else None

    def _item_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> CatalogItem:
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
            "release_dates": self._release_dates(connection, item_id),
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
            "backdrop_image": row["backdrop_image"],
            "tmdb_id": row["tmdb_id"],
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
            "link_curation_status": row["link_curation_status"],
            "duplicate_decisions": self._duplicate_decisions(connection, item_id),
            "curation_updated_at": row["curation_updated_at"],
            "added_at": row["added_at"],
        }
        for field in LIST_METADATA_FIELDS:
            item[field] = self._metadata_values(connection, item_id, field)
        self._apply_external_ids(connection, item)
        extra = _json_object(row["extra_json"])
        for key, value in extra.items():
            if key not in item:
                item[key] = value
        return self.normalizer(item)

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
    def _release_dates(connection: sqlite3.Connection, item_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT * FROM release_dates WHERE item_id = ? ORDER BY position",
            (item_id,),
        ).fetchall()
        return normalize_release_dates(
            [
                {
                    "date": row["release_date"],
                    "precision": row["precision"],
                    "country": row["country"],
                    "release_type": row["release_type"],
                    "source": row["source"],
                    "source_url": row["source_url"],
                    "is_primary": bool(row["is_primary"]),
                }
                for row in rows
            ]
        )

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
    def _duplicate_decisions(connection: sqlite3.Connection, item_id: str) -> dict[str, dict[str, str]]:
        rows = connection.execute(
            "SELECT other_reference, status, updated_at FROM duplicate_decisions WHERE item_id = ?",
            (item_id,),
        ).fetchall()
        return {
            str(row["other_reference"]): {
                "status": str(row["status"]),
                "updated_at": str(row["updated_at"]),
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

    def _sync_items(
        self,
        connection: sqlite3.Connection,
        existing: list[dict[str, Any]],
        incoming: list[dict[str, Any]],
    ) -> None:
        existing_by_id = {str(item["id"]): (position, item) for position, item in enumerate(existing)}
        incoming_ids = {str(item["id"]) for item in incoming}
        for removed_id in set(existing_by_id) - incoming_ids:
            connection.execute("DELETE FROM catalog_items WHERE id = ?", (removed_id,))
        for position, item in enumerate(incoming):
            previous = existing_by_id.get(str(item["id"]))
            if previous is None:
                self._sync_item(connection, None, item, position)
            elif previous[1] != item:
                self._sync_item(connection, previous[1], item, position)
            elif previous[0] != position:
                connection.execute("UPDATE catalog_items SET position = ? WHERE id = ?", (position, item["id"]))

    def _sync_item(
        self,
        connection: sqlite3.Connection,
        previous: dict[str, Any] | None,
        item: dict[str, Any],
        position: int,
    ) -> None:
        item_id = str(item["id"])
        extra = {
            key: value
            for key, value in item.items()
            if key not in CATALOG_FIELDS and not str(key).startswith("_")
        }
        connection.execute(
                """INSERT INTO catalog_items(
                    id, position, primary_url, source, title, original_title, spanish_title, english_title,
                    kind, status, watched_at, rating, year, description, page_image, backdrop_image, tmdb_id,
                    wikipedia_extract,
                    en_catalogo, local_name, local_path, notes, review, link_curation_status,
                    curation_updated_at, added_at, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    backdrop_image = excluded.backdrop_image,
                    tmdb_id = excluded.tmdb_id,
                    wikipedia_extract = excluded.wikipedia_extract,
                    en_catalogo = excluded.en_catalogo,
                    local_name = excluded.local_name,
                    local_path = excluded.local_path,
                    notes = excluded.notes,
                    review = excluded.review,
                    link_curation_status = excluded.link_curation_status,
                    curation_updated_at = excluded.curation_updated_at,
                    added_at = excluded.added_at,
                    extra_json = excluded.extra_json""",
                (
                    item_id, position, item.get("url", ""), item.get("source", ""), item.get("title", ""),
                    item.get("original_title", ""), item.get("spanish_title", ""), item.get("english_title", ""),
                    item.get("kind", "pelicula"), item.get("status", "to_watch"), item.get("watched_at", ""),
                    int(item.get("rating") or 0), item.get("year", ""), item.get("description", ""),
                    item.get("page_image", ""), item.get("backdrop_image", ""), item.get("tmdb_id", ""),
                    item.get("wikipedia_extract", ""),
                    int(bool(item.get("en_catalogo"))), item.get("local_name", ""), item.get("local_path", ""),
                    item.get("notes", ""), item.get("review", ""), item.get("link_curation_status", "pending"),
                    item.get("curation_updated_at", ""), item.get("added_at", ""), _json_dump(extra),
                ),
            )

        if previous is None or previous.get("alternative_titles") != item.get("alternative_titles"):
            connection.execute("DELETE FROM alternative_titles WHERE item_id = ?", (item_id,))
            self._insert_positioned(connection, "alternative_titles", "title", item_id, item.get("alternative_titles", []))
        for field in LIST_METADATA_FIELDS:
            if previous is None or previous.get(field) != item.get(field):
                connection.execute("DELETE FROM metadata_values WHERE item_id = ? AND field = ?", (item_id, field))
                for value_position, value in enumerate(item.get(field, [])):
                    connection.execute(
                        "INSERT INTO metadata_values(item_id, field, position, value) VALUES (?, ?, ?, ?)",
                        (item_id, field, value_position, str(value)),
                    )
        if previous is None or previous.get("tags") != item.get("tags"):
            connection.execute("DELETE FROM tags WHERE item_id = ?", (item_id,))
            self._insert_positioned(connection, "tags", "value", item_id, item.get("tags", []))
        if previous is None or previous.get("locked_fields") != item.get("locked_fields"):
            connection.execute("DELETE FROM locked_fields WHERE item_id = ?", (item_id,))
            for field in item.get("locked_fields", []):
                connection.execute(
                    "INSERT INTO locked_fields(item_id, field) VALUES (?, ?)",
                    (item_id, str(field)),
                )
        if previous is None or previous.get("duplicate_decisions") != item.get("duplicate_decisions"):
            connection.execute("DELETE FROM duplicate_decisions WHERE item_id = ?", (item_id,))
            for other_reference, decision in item.get("duplicate_decisions", {}).items():
                connection.execute(
                    """INSERT INTO duplicate_decisions(item_id, other_reference, status, updated_at)
                    VALUES (?, ?, ?, ?)""",
                    (
                        item_id,
                        str(other_reference),
                        str(decision.get("status") or ""),
                        str(decision.get("updated_at") or ""),
                    ),
                )
        external_fields = ("wikipedia_url", "wikipedia_title", "imdb_url", "filmaffinity_url", "wikidata_id")
        if previous is None or any(previous.get(field) != item.get(field) for field in external_fields):
            connection.execute("DELETE FROM external_ids WHERE item_id = ?", (item_id,))
            self._insert_external_ids(connection, item)
        if previous is None or previous.get("local_files") != item.get("local_files"):
            connection.execute("DELETE FROM local_files WHERE item_id = ?", (item_id,))
            self._insert_local_files(connection, item_id, item.get("local_files", []))
        if previous is None or previous.get("release_dates") != item.get("release_dates"):
            connection.execute("DELETE FROM release_dates WHERE item_id = ?", (item_id,))
            for release_position, release in enumerate(normalize_release_dates(item.get("release_dates"))):
                connection.execute(
                    """INSERT INTO release_dates(
                        item_id, position, release_date, precision, country,
                        release_type, source, source_url, is_primary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item_id,
                        release_position,
                        release["date"],
                        release["precision"],
                        release["country"],
                        release["release_type"],
                        release["source"],
                        release["source_url"],
                        int(bool(release["is_primary"])),
                    ),
                )
        if previous is None or previous.get("metadata_sources") != item.get("metadata_sources"):
            connection.execute("DELETE FROM metadata_provenance WHERE item_id = ?", (item_id,))
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
    def _insert_local_files(
        connection: sqlite3.Connection,
        item_id: str,
        files: Any,
        start_position: int = 0,
    ) -> None:
        for offset, row in enumerate(files if isinstance(files, list) else []):
            position = start_position + offset
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
