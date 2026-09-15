"""SQLite-backed local index for IMDb's non-commercial bulk datasets.

Scope: [F1] in tareas.md. This is a disposable, fully-rebuildable local
cache built from the official title.basics/title.akas dumps, entirely
separate from catalog.db and instance.db. It exists to measure disk usage
and load time, and to offer a read-only lookup; it never merges into the
real catalog (that authority/merge decision is [Q5]'s).

Every `build_index` call rebuilds the index from scratch into a temporary
file and atomically swaps it into place, so there is no row-level migration
to preserve across schema changes — a schema bump only needs a new
`IMDB_DATASET_INDEX_SCHEMA_VERSION` and updated `_SCHEMA`, tracked via
`PRAGMA user_version` rather than a migrations history table.
"""

from __future__ import annotations

import gzip
import os
import sqlite3
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from movie_inbox.domain.imdb_dataset import (
    AKA_REGIONS,
    kind_from_title_type,
    parse_title_akas_row,
    parse_title_basics_row,
    parse_title_ratings_row,
)

IMDB_DATASET_INDEX_SCHEMA_VERSION = 2

_BATCH_SIZE = 5000

_BASICS_COLUMNS = (
    "tconst",
    "title_type",
    "primary_title",
    "original_title",
    "is_adult",
    "start_year",
    "end_year",
    "runtime_minutes",
    "genres",
)
_AKAS_COLUMNS = (
    "tconst",
    "ordering",
    "title",
    "region",
    "language",
    "is_original_title",
)
_RATINGS_COLUMNS = ("tconst", "average_rating", "num_votes")

_SCHEMA = """
CREATE TABLE imdb_title_basics (
    tconst TEXT PRIMARY KEY,
    title_type TEXT NOT NULL,
    primary_title TEXT NOT NULL,
    original_title TEXT NOT NULL,
    is_adult INTEGER NOT NULL,
    start_year INTEGER,
    end_year INTEGER,
    runtime_minutes INTEGER,
    genres TEXT
);

CREATE TABLE imdb_title_akas (
    tconst TEXT NOT NULL,
    ordering INTEGER NOT NULL,
    title TEXT NOT NULL,
    region TEXT,
    language TEXT,
    is_original_title INTEGER,
    PRIMARY KEY (tconst, ordering)
);

CREATE TABLE imdb_title_ratings (
    tconst TEXT PRIMARY KEY,
    average_rating REAL NOT NULL,
    num_votes INTEGER NOT NULL
);
"""


class ImdbDatasetIndexStale(RuntimeError):
    """Raised when an existing index file predates the current schema version."""


@dataclass(frozen=True)
class IndexBuildReport:
    basics_rows: int
    basics_skipped_lines: int
    akas_rows: int
    akas_skipped_lines: int
    elapsed_seconds: float
    index_size_bytes: int
    basics_filtered_rows: int = 0
    akas_filtered_rows: int = 0
    ratings_rows: int = 0


@dataclass(frozen=True)
class IndexStats:
    basics_rows: int
    akas_rows: int
    index_size_bytes: int
    ratings_rows: int = 0


@dataclass(frozen=True)
class AkaEntry:
    title: str
    region: str | None
    language: str | None
    is_original_title: bool


@dataclass(frozen=True)
class RatingLookupResult:
    tconst: str
    average_rating: float
    num_votes: int


@dataclass(frozen=True)
class TitleLookupResult:
    tconst: str
    title_type: str
    primary_title: str
    original_title: str
    start_year: int | None
    end_year: int | None
    runtime_minutes: int | None
    genres: str | None
    akas: tuple[AkaEntry, ...]


class _RowCounter:
    def __init__(self) -> None:
        self.parsed = 0
        self.skipped = 0
        self.filtered = 0


def _iter_rows(
    path: Path,
    parse: Callable[[str], dict[str, Any] | None],
    counter: _RowCounter,
    keep: Callable[[dict[str, Any]], bool] | None = None,
) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            row = parse(line)
            if row is None:
                counter.skipped += 1
                continue
            if keep is not None and not keep(row):
                counter.filtered += 1
                continue
            counter.parsed += 1
            yield row


def _insert_batches(
    connection: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
    rows: Iterator[dict[str, Any]],
) -> None:
    statement = (
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})"
    )
    batch: list[tuple[Any, ...]] = []
    for row in rows:
        batch.append(tuple(row[column] for column in columns))
        if len(batch) >= _BATCH_SIZE:
            connection.executemany(statement, batch)
            batch.clear()
    if batch:
        connection.executemany(statement, batch)


def build_index(
    basics_path: Path,
    akas_path: Path,
    destination: Path,
    ratings_path: Path | None = None,
) -> IndexBuildReport:
    """Build a lean index: only what [Q5] gives the local source, nothing else.

    Measured on the real datasets 2026-09-07: 58% of `title.basics` rows are
    `tvEpisode`, which contributes no `kind` at all, and only 37% of aka rows
    are in a region this catalogue reads. Storing the rest, plus text indexes
    for a lookup path that only ever keys on `tconst`, is what made the v1 index
    8.1 GB. Everything dropped here is unreachable by design, not a trade-off
    against future features.
    """

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    descriptor, temp_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    temporary_path: Path | None = temp_path
    basics_counter = _RowCounter()
    akas_counter = _RowCounter()
    ratings_counter = _RowCounter()
    stored_akas = 0
    stored_ratings = 0
    try:
        connection = sqlite3.connect(temp_path, isolation_level=None)
        try:
            connection.execute("PRAGMA synchronous = OFF")
            connection.execute("PRAGMA journal_mode = MEMORY")
            connection.executescript(_SCHEMA)
            connection.execute("BEGIN")
            _insert_batches(
                connection,
                "imdb_title_basics",
                _BASICS_COLUMNS,
                _iter_rows(
                    basics_path,
                    parse_title_basics_row,
                    basics_counter,
                    lambda row: bool(kind_from_title_type(row.get("title_type"))),
                ),
            )
            _insert_batches(
                connection,
                "imdb_title_akas",
                _AKAS_COLUMNS,
                _iter_rows(
                    akas_path,
                    parse_title_akas_row,
                    akas_counter,
                    lambda row: str(row.get("region") or "").upper() in AKA_REGIONS,
                ),
            )
            if ratings_path is not None and Path(ratings_path).exists():
                _insert_batches(
                    connection,
                    "imdb_title_ratings",
                    _RATINGS_COLUMNS,
                    _iter_rows(ratings_path, parse_title_ratings_row, ratings_counter),
                )
            # Rows whose work was filtered out of basics can never be reached by a
            # lookup, so they are pure weight. Removing them set-based is far
            # cheaper than holding several million ids in memory while streaming.
            for table in ("imdb_title_akas", "imdb_title_ratings"):
                connection.execute(
                    f"DELETE FROM {table} WHERE tconst NOT IN "
                    "(SELECT tconst FROM imdb_title_basics)"
                )
            # Counted after the delete, so the report states what is actually on
            # disk rather than what was read from the dumps.
            stored_akas = connection.execute("SELECT COUNT(*) FROM imdb_title_akas").fetchone()[0]
            stored_ratings = connection.execute(
                "SELECT COUNT(*) FROM imdb_title_ratings"
            ).fetchone()[0]
            connection.execute(f"PRAGMA user_version = {IMDB_DATASET_INDEX_SCHEMA_VERSION}")
            connection.execute("COMMIT")
            connection.execute("VACUUM")
        finally:
            connection.close()
        os.replace(temp_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return IndexBuildReport(
        basics_rows=basics_counter.parsed,
        basics_skipped_lines=basics_counter.skipped,
        akas_rows=stored_akas,
        akas_skipped_lines=akas_counter.skipped,
        elapsed_seconds=time.monotonic() - started,
        index_size_bytes=destination.stat().st_size,
        basics_filtered_rows=basics_counter.filtered,
        akas_filtered_rows=akas_counter.filtered + (akas_counter.parsed - stored_akas),
        ratings_rows=stored_ratings,
    )


def _open_readonly(path: Path) -> sqlite3.Connection:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No IMDb dataset index at {path}. Run `movie-inbox imdb-dataset sync` first."
        )
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != IMDB_DATASET_INDEX_SCHEMA_VERSION:
        connection.close()
        raise ImdbDatasetIndexStale(
            f"Index at {path} has schema version {version}, expected "
            f"{IMDB_DATASET_INDEX_SCHEMA_VERSION}. Re-run `movie-inbox imdb-dataset sync`."
        )
    return connection


def _fetch_title(connection: sqlite3.Connection, tconst: str) -> TitleLookupResult | None:
    row = connection.execute(
        "SELECT * FROM imdb_title_basics WHERE tconst = ?", (tconst,)
    ).fetchone()
    if row is None:
        return None
    akas = tuple(
        AkaEntry(
            title=aka["title"],
            region=aka["region"],
            language=aka["language"],
            is_original_title=bool(aka["is_original_title"]),
        )
        for aka in connection.execute(
            "SELECT title, region, language, is_original_title FROM imdb_title_akas "
            "WHERE tconst = ? ORDER BY ordering",
            (tconst,),
        )
    )
    return TitleLookupResult(
        tconst=row["tconst"],
        title_type=row["title_type"],
        primary_title=row["primary_title"],
        original_title=row["original_title"],
        start_year=row["start_year"],
        end_year=row["end_year"],
        runtime_minutes=row["runtime_minutes"],
        genres=row["genres"],
        akas=akas,
    )


def lookup_ratings_by_tconst(path: Path, tconst: str) -> RatingLookupResult | None:
    """Public score for one work, read on demand.

    Kept out of `TitleLookupResult` on purpose: ratings move, so they are read
    when they are shown rather than merged into a catalogue that would then hold
    a number that quietly goes stale.
    """

    connection = _open_readonly(path)
    try:
        row = connection.execute(
            "SELECT average_rating, num_votes FROM imdb_title_ratings WHERE tconst = ?",
            (tconst,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return RatingLookupResult(
        tconst=tconst,
        average_rating=float(row["average_rating"]),
        num_votes=int(row["num_votes"]),
    )


def lookup_by_tconst(path: Path, tconst: str) -> TitleLookupResult | None:
    connection = _open_readonly(path)
    try:
        return _fetch_title(connection, tconst)
    finally:
        connection.close()


def lookup_by_title(path: Path, title: str, year: int | None = None) -> list[TitleLookupResult]:
    connection = _open_readonly(path)
    try:
        if year is None:
            candidates = connection.execute(
                "SELECT tconst FROM imdb_title_basics "
                "WHERE primary_title = ? OR original_title = ?",
                (title, title),
            ).fetchall()
        else:
            candidates = connection.execute(
                "SELECT tconst FROM imdb_title_basics "
                "WHERE (primary_title = ? OR original_title = ?) AND start_year = ?",
                (title, title, year),
            ).fetchall()
        results = []
        for candidate in candidates:
            result = _fetch_title(connection, candidate["tconst"])
            if result is not None:
                results.append(result)
        return results
    finally:
        connection.close()


def index_stats(path: Path) -> IndexStats:
    connection = _open_readonly(path)
    try:
        basics_rows = connection.execute("SELECT COUNT(*) FROM imdb_title_basics").fetchone()[0]
        akas_rows = connection.execute("SELECT COUNT(*) FROM imdb_title_akas").fetchone()[0]
        ratings_rows = connection.execute("SELECT COUNT(*) FROM imdb_title_ratings").fetchone()[0]
    finally:
        connection.close()
    return IndexStats(
        basics_rows=basics_rows,
        akas_rows=akas_rows,
        index_size_bytes=Path(path).stat().st_size,
        ratings_rows=ratings_rows,
    )
