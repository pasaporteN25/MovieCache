"""Rebuildable SQLite index for anime-offline-database snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from movie_inbox.domain.normalization import normalize_search_text

ANIME_OFFLINE_INDEX_SCHEMA_VERSION = 1
ANIME_OFFLINE_SOURCE = "anime_offline_database"
ANIME_OFFLINE_REPOSITORY_URL = "https://github.com/manami-project/anime-offline-database"
ANIME_OFFLINE_ATTRIBUTION = (
    "Contains information from anime-offline-database, made available under "
    "the Open Database License (ODbL) and Database Contents License (DbCL)."
)

_BATCH_SIZE = 1000
_PROVIDER_PATHS = (
    ("myanimelist", "myanimelist.net", re.compile(r"^/anime/(\d+)(?:/|$)")),
    ("anidb", "anidb.net", re.compile(r"^/anime/(\d+)(?:/|$)")),
    ("anilist", "anilist.co", re.compile(r"^/anime/(\d+)(?:/|$)")),
    ("kitsu", "kitsu.app", re.compile(r"^/anime/([^/?#]+)(?:/|$)")),
    ("anime_planet", "anime-planet.com", re.compile(r"^/anime/([^/?#]+)(?:/|$)")),
    ("anisearch", "anisearch.com", re.compile(r"^/anime/(\d+)(?:/|$)")),
    ("livechart", "livechart.me", re.compile(r"^/anime/(\d+)(?:/|$)")),
    ("simkl", "simkl.com", re.compile(r"^/anime/(\d+)(?:/|$)")),
    ("animecountdown", "animecountdown.com", re.compile(r"^/(\d+)(?:/|$)")),
)

_SCHEMA = """
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE anime (
    entry_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    title_key TEXT NOT NULL,
    anime_type TEXT NOT NULL,
    release_year INTEGER,
    mal_id TEXT NOT NULL,
    primary_url TEXT NOT NULL
);
CREATE INDEX idx_anime_title_key ON anime(title_key);
CREATE INDEX idx_anime_mal_id ON anime(mal_id);

CREATE TABLE anime_alias (
    entry_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    title_key TEXT NOT NULL,
    is_primary INTEGER NOT NULL,
    PRIMARY KEY (entry_id, title_key, title),
    FOREIGN KEY (entry_id) REFERENCES anime(entry_id) ON DELETE CASCADE
);
CREATE INDEX idx_anime_alias_title_key ON anime_alias(title_key);

CREATE TABLE anime_external_id (
    entry_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    url TEXT NOT NULL,
    PRIMARY KEY (entry_id, provider, external_id),
    FOREIGN KEY (entry_id) REFERENCES anime(entry_id) ON DELETE CASCADE
);
CREATE INDEX idx_anime_external_identity
ON anime_external_id(provider, external_id);
"""


class AnimeOfflineIndexError(RuntimeError):
    """Base error for invalid snapshots and unusable indexes."""


class AnimeOfflineIndexStale(AnimeOfflineIndexError):
    """Raised when an index needs to be rebuilt for the current schema."""


@dataclass(frozen=True)
class AnimeExternalId:
    provider: str
    external_id: str
    url: str


@dataclass(frozen=True)
class AnimeLookupResult:
    entry_id: int
    title: str
    anime_type: str
    release_year: int | None
    mal_id: str
    primary_url: str
    aliases: tuple[str, ...]
    external_ids: tuple[AnimeExternalId, ...]
    snapshot_date: str


@dataclass(frozen=True)
class AnimeIndexBuildReport:
    anime_rows: int
    alias_rows: int
    external_id_rows: int
    skipped_rows: int
    elapsed_seconds: float
    index_size_bytes: int
    snapshot_date: str
    snapshot_sha256: str
    license_name: str
    license_url: str


@dataclass(frozen=True)
class AnimeIndexStats:
    anime_rows: int
    alias_rows: int
    external_id_rows: int
    index_size_bytes: int
    snapshot_date: str
    snapshot_sha256: str
    license_name: str
    license_url: str


def build_anime_index(snapshot_path: Path, destination: Path) -> AnimeIndexBuildReport:
    snapshot_path = Path(snapshot_path)
    destination = Path(destination)
    metadata, rows = _read_snapshot(snapshot_path)
    snapshot_date, license_name, license_url = _validated_metadata(metadata)
    snapshot_sha256 = _sha256(snapshot_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    started = time.monotonic()
    anime_count = 0
    alias_count = 0
    external_id_count = 0
    skipped_count = 0
    try:
        connection = sqlite3.connect(temporary_path, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = OFF")
            connection.execute("PRAGMA journal_mode = MEMORY")
            connection.executescript(_SCHEMA)
            connection.execute("BEGIN")
            _write_metadata(
                connection,
                {
                    "snapshot_date": snapshot_date,
                    "snapshot_sha256": snapshot_sha256,
                    "license_name": license_name,
                    "license_url": license_url,
                    "repository": str(metadata.get("repository") or ""),
                    "attribution": ANIME_OFFLINE_ATTRIBUTION,
                },
            )
            anime_batch: list[tuple[Any, ...]] = []
            alias_batch: list[tuple[Any, ...]] = []
            external_id_batch: list[tuple[Any, ...]] = []
            for raw_row in rows:
                parsed = _parse_anime_row(raw_row)
                if parsed is None:
                    skipped_count += 1
                    continue
                anime_count += 1
                anime_batch.append(
                    (
                        anime_count,
                        parsed["title"],
                        parsed["title_key"],
                        parsed["anime_type"],
                        parsed["release_year"],
                        parsed["mal_id"],
                        parsed["primary_url"],
                    )
                )
                for title, title_key, is_primary in parsed["aliases"]:
                    alias_batch.append((anime_count, title, title_key, is_primary))
                    alias_count += 1
                for external_id in parsed["external_ids"]:
                    external_id_batch.append(
                        (
                            anime_count,
                            external_id.provider,
                            external_id.external_id,
                            external_id.url,
                        )
                    )
                    external_id_count += 1
                if len(anime_batch) >= _BATCH_SIZE:
                    _flush_batches(connection, anime_batch, alias_batch, external_id_batch)
            _flush_batches(connection, anime_batch, alias_batch, external_id_batch)
            connection.execute(f"PRAGMA user_version = {ANIME_OFFLINE_INDEX_SCHEMA_VERSION}")
            connection.execute("COMMIT")
        finally:
            connection.close()
        os.replace(temporary_path, destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return AnimeIndexBuildReport(
        anime_rows=anime_count,
        alias_rows=alias_count,
        external_id_rows=external_id_count,
        skipped_rows=skipped_count,
        elapsed_seconds=time.monotonic() - started,
        index_size_bytes=destination.stat().st_size,
        snapshot_date=snapshot_date,
        snapshot_sha256=snapshot_sha256,
        license_name=license_name,
        license_url=license_url,
    )


def lookup_anime_by_title(
    path: Path,
    title: str,
    year: int | None = None,
    *,
    limit: int = 16,
) -> list[AnimeLookupResult]:
    title_key = normalize_search_text(title)
    if len(title_key) < 2:
        return []
    connection = _open_readonly(path)
    try:
        prefix = f"{title_key}%"
        contains = f"%{title_key}%"
        candidates = connection.execute(
            """
            SELECT entry_id,
                   MIN(CASE
                       WHEN title_key = ? THEN 0
                       WHEN title_key LIKE ? THEN 1
                       ELSE 2
                   END) AS match_rank
            FROM anime_alias
            WHERE title_key = ? OR title_key LIKE ? OR title_key LIKE ?
            GROUP BY entry_id
            ORDER BY match_rank, MIN(LENGTH(title_key)), entry_id
            LIMIT ?
            """,
            (title_key, prefix, title_key, prefix, contains, max(limit * 4, 32)),
        ).fetchall()
        results = [_fetch_anime(connection, int(row["entry_id"])) for row in candidates]
        rows = [row for row in results if row is not None]
        if year is not None:
            rows.sort(
                key=lambda row: (
                    0 if row.release_year == year else 1,
                    abs((row.release_year or year) - year),
                    row.entry_id,
                )
            )
        return rows[: max(1, limit)]
    finally:
        connection.close()


def lookup_anime_by_mal_id(path: Path, mal_id: str) -> AnimeLookupResult | None:
    normalized = _positive_id(mal_id)
    if not normalized:
        return None
    connection = _open_readonly(path)
    try:
        row = connection.execute(
            "SELECT entry_id FROM anime WHERE mal_id = ? ORDER BY entry_id LIMIT 1",
            (normalized,),
        ).fetchone()
        return _fetch_anime(connection, int(row["entry_id"])) if row else None
    finally:
        connection.close()


def lookup_anime_by_external_id(
    path: Path, provider: str, external_id: str
) -> AnimeLookupResult | None:
    normalized_provider = normalize_search_text(provider).replace(" ", "_")
    normalized_id = str(external_id or "").strip().casefold()
    if not normalized_provider or not normalized_id:
        return None
    connection = _open_readonly(path)
    try:
        row = connection.execute(
            "SELECT entry_id FROM anime_external_id "
            "WHERE provider = ? AND external_id = ? ORDER BY entry_id LIMIT 1",
            (normalized_provider, normalized_id),
        ).fetchone()
        return _fetch_anime(connection, int(row["entry_id"])) if row else None
    finally:
        connection.close()


def anime_index_stats(path: Path) -> AnimeIndexStats:
    connection = _open_readonly(path)
    try:
        metadata = _index_metadata(connection)
        anime_rows = int(connection.execute("SELECT COUNT(*) FROM anime").fetchone()[0])
        alias_rows = int(connection.execute("SELECT COUNT(*) FROM anime_alias").fetchone()[0])
        external_id_rows = int(
            connection.execute("SELECT COUNT(*) FROM anime_external_id").fetchone()[0]
        )
    finally:
        connection.close()
    return AnimeIndexStats(
        anime_rows=anime_rows,
        alias_rows=alias_rows,
        external_id_rows=external_id_rows,
        index_size_bytes=Path(path).stat().st_size,
        snapshot_date=metadata.get("snapshot_date", ""),
        snapshot_sha256=metadata.get("snapshot_sha256", ""),
        license_name=metadata.get("license_name", ""),
        license_url=metadata.get("license_url", ""),
    )


def _read_snapshot(path: Path) -> tuple[dict[str, Any], Iterable[Any]]:
    if not path.is_file():
        raise AnimeOfflineIndexError(f"Anime snapshot not found: {path}")
    if path.suffix.casefold() == ".jsonl":
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            first_line = next((line for line in handle if line.strip()), "")
        try:
            metadata = json.loads(first_line)
        except json.JSONDecodeError as error:
            raise AnimeOfflineIndexError("Invalid anime JSONL metadata line") from error
        if not isinstance(metadata, dict):
            raise AnimeOfflineIndexError("Anime JSONL metadata must be an object")
        return metadata, _iter_jsonl_rows(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AnimeOfflineIndexError("Invalid anime snapshot JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise AnimeOfflineIndexError("Anime snapshot must contain a data array")
    return payload, payload["data"]


def _iter_jsonl_rows(path: Path) -> Iterator[Any]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        metadata_seen = False
        for line in handle:
            if not line.strip():
                continue
            if not metadata_seen:
                metadata_seen = True
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield None


def _validated_metadata(metadata: Mapping[str, Any]) -> tuple[str, str, str]:
    snapshot_date = str(metadata.get("lastUpdate") or "").strip()
    license_row = metadata.get("license")
    license_data = dict(license_row) if isinstance(license_row, Mapping) else {}
    license_name = str(license_data.get("name") or "").strip()
    license_url = _safe_https_url(license_data.get("url"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", snapshot_date):
        raise AnimeOfflineIndexError("Anime snapshot has no valid lastUpdate date")
    folded_license = license_name.casefold()
    if "odbl" not in folded_license or "dbcl" not in folded_license or not license_url:
        raise AnimeOfflineIndexError("Anime snapshot has no supported ODbL/DbCL license notice")
    return snapshot_date, license_name, license_url


def _parse_anime_row(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    title = " ".join(str(value.get("title") or "").split())
    title_key = normalize_search_text(title)
    if not title or len(title_key) < 2:
        return None
    raw_sources = value.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    external_ids: list[AnimeExternalId] = []
    seen_external_ids: set[tuple[str, str]] = set()
    for raw_url in sources:
        external_id = _external_id_from_url(raw_url)
        if external_id is None:
            continue
        identity = (external_id.provider, external_id.external_id)
        if identity in seen_external_ids:
            continue
        seen_external_ids.add(identity)
        external_ids.append(external_id)
    if not external_ids:
        return None
    mal_id = next((row.external_id for row in external_ids if row.provider == "myanimelist"), "")
    primary_url = next(
        (row.url for row in external_ids if row.provider == "myanimelist"),
        external_ids[0].url,
    )
    aliases: list[tuple[str, str, int]] = [(title, title_key, 1)]
    seen_aliases = {title_key}
    raw_synonyms = value.get("synonyms")
    synonyms: list[Any] = raw_synonyms if isinstance(raw_synonyms, list) else []
    for raw_alias in synonyms:
        alias = " ".join(str(raw_alias or "").split())
        alias_key = normalize_search_text(alias)
        if not alias or len(alias_key) < 2 or alias_key in seen_aliases:
            continue
        seen_aliases.add(alias_key)
        aliases.append((alias, alias_key, 0))
    season = value.get("animeSeason")
    season_data = dict(season) if isinstance(season, Mapping) else {}
    release_year = _optional_year(season_data.get("year"))
    return {
        "title": title,
        "title_key": title_key,
        "anime_type": str(value.get("type") or "UNKNOWN").strip().upper(),
        "release_year": release_year,
        "mal_id": mal_id,
        "primary_url": primary_url,
        "aliases": aliases,
        "external_ids": tuple(external_ids),
    }


def _external_id_from_url(value: Any) -> AnimeExternalId | None:
    url = _safe_https_url(value)
    if not url:
        return None
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower().removeprefix("www.")
    for provider, expected_host, pattern in _PROVIDER_PATHS:
        if hostname != expected_host and not hostname.endswith(f".{expected_host}"):
            continue
        match = pattern.match(parsed.path)
        if match:
            return AnimeExternalId(provider, match.group(1).casefold(), url)
    if hostname == "animenewsnetwork.com" or hostname.endswith(".animenewsnetwork.com"):
        ann_id = str(parse_qs(parsed.query).get("id", [""])[0]).strip()
        if ann_id.isdigit():
            return AnimeExternalId("anime_news_network", ann_id, url)
    return None


def _safe_https_url(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = urlparse(text)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return ""
        if parsed.port not in (None, 443):
            return ""
    except (UnicodeError, ValueError):
        return ""
    return text


def _optional_year(value: Any) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1888 <= year <= 2200 else None


def _positive_id(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""
    return str(number) if number > 0 else ""


def _flush_batches(
    connection: sqlite3.Connection,
    anime_rows: list[tuple[Any, ...]],
    alias_rows: list[tuple[Any, ...]],
    external_id_rows: list[tuple[Any, ...]],
) -> None:
    connection.executemany(
        "INSERT INTO anime "
        "(entry_id, title, title_key, anime_type, release_year, mal_id, primary_url) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        anime_rows,
    )
    connection.executemany(
        "INSERT INTO anime_alias (entry_id, title, title_key, is_primary) VALUES (?, ?, ?, ?)",
        alias_rows,
    )
    connection.executemany(
        "INSERT INTO anime_external_id (entry_id, provider, external_id, url) VALUES (?, ?, ?, ?)",
        external_id_rows,
    )
    anime_rows.clear()
    alias_rows.clear()
    external_id_rows.clear()


def _write_metadata(connection: sqlite3.Connection, values: Mapping[str, str]) -> None:
    connection.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        [(key, value) for key, value in values.items()],
    )


def _open_readonly(path: Path) -> sqlite3.Connection:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"No anime index at {path}. Run `movie-inbox anime-dataset sync` first."
        )
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version != ANIME_OFFLINE_INDEX_SCHEMA_VERSION:
        connection.close()
        raise AnimeOfflineIndexStale(
            f"Anime index at {path} has schema version {version}, expected "
            f"{ANIME_OFFLINE_INDEX_SCHEMA_VERSION}. Re-run `movie-inbox anime-dataset sync`."
        )
    return connection


def _fetch_anime(connection: sqlite3.Connection, entry_id: int) -> AnimeLookupResult | None:
    row = connection.execute("SELECT * FROM anime WHERE entry_id = ?", (entry_id,)).fetchone()
    if row is None:
        return None
    aliases = tuple(
        str(alias["title"])
        for alias in connection.execute(
            "SELECT title FROM anime_alias WHERE entry_id = ? AND is_primary = 0 "
            "ORDER BY title_key, title",
            (entry_id,),
        )
    )
    external_ids = tuple(
        AnimeExternalId(
            provider=str(external_id["provider"]),
            external_id=str(external_id["external_id"]),
            url=str(external_id["url"]),
        )
        for external_id in connection.execute(
            "SELECT provider, external_id, url FROM anime_external_id "
            "WHERE entry_id = ? ORDER BY provider, external_id",
            (entry_id,),
        )
    )
    metadata = _index_metadata(connection)
    return AnimeLookupResult(
        entry_id=int(row["entry_id"]),
        title=str(row["title"]),
        anime_type=str(row["anime_type"]),
        release_year=int(row["release_year"]) if row["release_year"] is not None else None,
        mal_id=str(row["mal_id"]),
        primary_url=str(row["primary_url"]),
        aliases=aliases,
        external_ids=external_ids,
        snapshot_date=metadata.get("snapshot_date", ""),
    )


def _index_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    return {
        str(row["key"]): str(row["value"])
        for row in connection.execute("SELECT key, value FROM metadata")
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ANIME_OFFLINE_ATTRIBUTION",
    "ANIME_OFFLINE_INDEX_SCHEMA_VERSION",
    "ANIME_OFFLINE_REPOSITORY_URL",
    "ANIME_OFFLINE_SOURCE",
    "AnimeExternalId",
    "AnimeIndexBuildReport",
    "AnimeIndexStats",
    "AnimeLookupResult",
    "AnimeOfflineIndexError",
    "AnimeOfflineIndexStale",
    "anime_index_stats",
    "build_anime_index",
    "lookup_anime_by_external_id",
    "lookup_anime_by_mal_id",
    "lookup_anime_by_title",
]
