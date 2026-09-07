"""SQLite persistence for streaming regions, platforms and member choices."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from movie_inbox.application.streaming_repository import (
    StreamingRegionNotFound,
    StreamingRepositoryError,
)
from movie_inbox.domain.streaming import (
    MemberStreamingPreferences,
    RegionPolicy,
    StreamingProvider,
    StreamingRegion,
)


class SqliteStreamingRepository:
    def __init__(self, path: Path, busy_timeout: float = 10.0) -> None:
        self.path = Path(path)
        self.busy_timeout = max(0.1, busy_timeout)
        self._thread_lock = threading.RLock()

    def list_regions(self) -> list[StreamingRegion]:
        with self._thread_lock, closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT code, name, enabled FROM streaming_regions ORDER BY code"
            ).fetchall()
        return [
            StreamingRegion(str(row["code"]), str(row["name"]), bool(row["enabled"]))
            for row in rows
        ]

    def upsert_region(self, region: StreamingRegion) -> StreamingRegion:
        with self._thread_lock, closing(self._connect()) as connection:
            self._write(
                connection,
                """INSERT INTO streaming_regions(code, name, enabled, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at""",
                (region.code, region.name, int(region.enabled), _utc_now()),
            )
        return region

    def set_region_enabled(self, code: str, enabled: bool) -> StreamingRegion:
        with self._thread_lock, closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT code, name FROM streaming_regions WHERE code = ?", (code,)
            ).fetchone()
            if row is None:
                raise StreamingRegionNotFound(f"Region is not configured: {code}")
            self._write(
                connection,
                "UPDATE streaming_regions SET enabled = ?, updated_at = ? WHERE code = ?",
                (int(enabled), _utc_now(), code),
            )
            return StreamingRegion(str(row["code"]), str(row["name"]), enabled)

    def region_policy(self) -> RegionPolicy:
        with self._thread_lock, closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT default_region, members_may_choose
                FROM streaming_region_policy WHERE id = 1"""
            ).fetchone()
        if row is None:
            return RegionPolicy()
        return RegionPolicy(
            default_region=str(row["default_region"] or ""),
            members_may_choose=bool(row["members_may_choose"]),
        )

    def set_region_policy(self, policy: RegionPolicy) -> RegionPolicy:
        with self._thread_lock, closing(self._connect()) as connection:
            self._write(
                connection,
                """UPDATE streaming_region_policy
                SET default_region = ?, members_may_choose = ?, updated_at = ?
                WHERE id = 1""",
                (policy.default_region, int(policy.members_may_choose), _utc_now()),
            )
        return policy

    def list_providers(self, region_code: str) -> list[StreamingProvider]:
        with self._thread_lock, closing(self._connect()) as connection:
            rows = connection.execute(
                """SELECT region_code, provider_id, name, display_priority, logo_path
                FROM streaming_providers WHERE region_code = ?
                ORDER BY display_priority, name""",
                (region_code,),
            ).fetchall()
        return [
            StreamingProvider(
                region_code=str(row["region_code"]),
                provider_id=str(row["provider_id"]),
                name=str(row["name"]),
                display_priority=int(row["display_priority"]),
                logo_path=str(row["logo_path"]),
            )
            for row in rows
        ]

    def replace_providers(
        self,
        region_code: str,
        providers: list[StreamingProvider],
    ) -> list[StreamingProvider]:
        # Replacing wholesale rather than merging: the upstream catalogue is the
        # authority on which platforms a market has, and a platform that left it
        # should disappear instead of lingering as a stale row.
        stamp = _utc_now()
        with self._thread_lock, closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if not connection.execute(
                    "SELECT 1 FROM streaming_regions WHERE code = ?", (region_code,)
                ).fetchone():
                    raise StreamingRegionNotFound(f"Region is not configured: {region_code}")
                connection.execute(
                    "DELETE FROM streaming_providers WHERE region_code = ?", (region_code,)
                )
                connection.executemany(
                    """INSERT INTO streaming_providers(
                        region_code, provider_id, name, display_priority, logo_path, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            provider.region_code,
                            provider.provider_id,
                            provider.name,
                            provider.display_priority,
                            provider.logo_path,
                            stamp,
                        )
                        for provider in providers
                    ],
                )
                connection.commit()
            except StreamingRegionNotFound:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise StreamingRepositoryError(
                    f"Cannot replace streaming providers in: {self.path}"
                ) from error
        return providers

    def member_preferences(self, user_id: str) -> MemberStreamingPreferences:
        with self._thread_lock, closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT region, ignored_providers_json
                FROM member_streaming_preferences WHERE user_id = ?""",
                (user_id,),
            ).fetchone()
        if row is None:
            return MemberStreamingPreferences()
        return MemberStreamingPreferences(
            region=str(row["region"] or ""),
            ignored_providers=tuple(_json_list(row["ignored_providers_json"])),
        )

    def set_member_preferences(
        self,
        user_id: str,
        preferences: MemberStreamingPreferences,
    ) -> MemberStreamingPreferences:
        with self._thread_lock, closing(self._connect()) as connection:
            self._write(
                connection,
                """INSERT INTO member_streaming_preferences(
                    user_id, region, ignored_providers_json, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    region = excluded.region,
                    ignored_providers_json = excluded.ignored_providers_json,
                    updated_at = excluded.updated_at""",
                (
                    user_id,
                    preferences.region,
                    json.dumps(list(preferences.ignored_providers), ensure_ascii=True),
                    _utc_now(),
                ),
            )
        return preferences

    def _write(
        self,
        connection: sqlite3.Connection,
        statement: str,
        parameters: tuple[object, ...],
    ) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(statement, parameters)
            connection.commit()
        except sqlite3.Error as error:
            connection.rollback()
            raise StreamingRepositoryError(
                f"Cannot write streaming configuration in: {self.path}"
            ) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout * 1000)}")
        return connection


def _json_list(value: object) -> list[str]:
    try:
        decoded = json.loads(str(value or "[]"))
    except json.JSONDecodeError as error:
        raise StreamingRepositoryError("Stored provider list is invalid JSON") from error
    if not isinstance(decoded, list):
        raise StreamingRepositoryError("Stored provider list must be an array")
    return [str(entry) for entry in decoded]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
