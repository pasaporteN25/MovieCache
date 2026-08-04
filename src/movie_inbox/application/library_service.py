"""Application services for managed scans and shared physical availability."""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping

from movie_inbox.application.library_repository import (
    LibraryNotFound,
    LibraryRepository,
    LibraryRepositoryError,
    LibraryRunBusy,
)
from movie_inbox.domain.catalog import external_urls, title_match_keys_for_item
from movie_inbox.domain.libraries import (
    LibraryFile,
    LibraryScanRun,
    LibraryValidationError,
    ManagedLibrary,
    detected_work_identity,
    identity_matches_item,
    normalize_library_name,
    normalize_missing_ratio,
    normalize_schedule,
    work_identity,
    work_identity_key,
)
from movie_inbox.domain.matching import decide_match, explicit_kind


CatalogUniverseProvider = Callable[[], list[dict[str, Any]]]
FilesystemScanner = Callable[..., tuple[list[dict[str, Any]], list[str]]]
PREVIEW_LIMIT = 100
SCHEDULE_SECONDS = {"manual": 0, "hourly": 60 * 60, "daily": 24 * 60 * 60}


class LibraryPathError(ValueError):
    """Raised when a requested root is outside the server allowlist."""


@dataclass(frozen=True)
class _CatalogMatchIndex:
    items: tuple[dict[str, Any], ...]
    by_title: Mapping[str, frozenset[int]]
    by_term: Mapping[str, frozenset[int]]

    @classmethod
    def build(cls, items: list[dict[str, Any]]) -> "_CatalogMatchIndex":
        by_title: dict[str, set[int]] = defaultdict(set)
        by_term: dict[str, set[int]] = defaultdict(set)
        for position, item in enumerate(items):
            for title in title_match_keys_for_item(item):
                by_title[title].add(position)
                for term in title.split():
                    by_term[term].add(position)
        return cls(
            tuple(items),
            {key: frozenset(value) for key, value in by_title.items()},
            {key: frozenset(value) for key, value in by_term.items()},
        )

    def candidates(self, detected: Mapping[str, Any]) -> list[dict[str, Any]]:
        titles = title_match_keys_for_item(detected)
        exact: set[int] = set()
        for title in titles:
            exact.update(self.by_title.get(title, ()))
        if exact:
            positions = exact
        else:
            positions: set[int] = set()
            for term in {term for title in titles for term in title.split()}:
                positions.update(self.by_term.get(term, ()))
        return [self.items[position] for position in sorted(positions)]


class ManagedLibraryService:
    def __init__(
        self,
        repository: LibraryRepository,
        *,
        allowed_roots: tuple[str, ...],
        catalog_universe: CatalogUniverseProvider,
        scanner: FilesystemScanner,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.repository = repository
        self.allowed_roots = tuple(_resolved_root(value) for value in allowed_roots if str(value or "").strip())
        self.catalog_universe = catalog_universe
        self.scanner = scanner
        self.clock = clock

    @property
    def configured(self) -> bool:
        return bool(self.allowed_roots)

    def create_library(self, owner_user_id: str, payload: Mapping[str, Any]) -> ManagedLibrary:
        now = self._now()
        root = self.validate_root(str(payload.get("root_path") or ""))
        library = ManagedLibrary(
            id=uuid.uuid4().hex,
            name=normalize_library_name(payload.get("name")),
            root_path=str(root),
            created_by_user_id=str(owner_user_id or ""),
            schedule=normalize_schedule(payload.get("schedule")),
            active=False,
            status="unverified",
            max_missing_ratio=normalize_missing_ratio(payload.get("max_missing_ratio", 0.5)),
            created_at=now,
            updated_at=now,
        )
        return self.repository.create_library(library)

    def update_library(self, library_id: str, payload: Mapping[str, Any]) -> ManagedLibrary:
        library = self._library(library_id)
        schedule = normalize_schedule(payload.get("schedule", library.schedule))
        active = library.active and schedule != "manual"
        status = library.status
        if library.active and not active:
            status = "ready" if library.verified_at else "unverified"
        updated = replace(
            library,
            name=normalize_library_name(payload.get("name", library.name)),
            schedule=schedule,
            active=active,
            status=status,
            max_missing_ratio=normalize_missing_ratio(
                payload.get("max_missing_ratio", library.max_missing_ratio)
            ),
            next_scan_at=(
                _next_scan(self._now(), schedule)
                if active and schedule != library.schedule
                else library.next_scan_at if active else 0
            ),
            updated_at=self._now(),
        )
        return self.repository.update_library(updated)

    def set_active(self, library_id: str, active: bool) -> ManagedLibrary:
        library = self._library(library_id)
        if library.status == "scanning":
            raise LibraryRunBusy("The library is currently being scanned")
        if active and library.schedule == "manual":
            raise LibraryValidationError("Manual libraries do not use scheduled activation")
        if active and not library.verified_at:
            raise LibraryValidationError("Run a successful test scan before activating this library")
        if active and not library.last_scan_at:
            raise LibraryValidationError("Apply inventory before activating scheduled scans")
        now = self._now()
        updated = replace(
            library,
            active=bool(active),
            status="ready" if active else "paused",
            next_scan_at=_next_scan(now, library.schedule) if active else 0,
            updated_at=now,
        )
        return self.repository.update_library(updated)

    def delete_library(self, library_id: str) -> bool:
        return self.repository.delete_library(library_id)

    def list_libraries(self) -> list[dict[str, Any]]:
        return [self.library_payload(library) for library in self.repository.list_libraries()]

    def library_detail(self, library_id: str) -> dict[str, Any]:
        library = self._library(library_id)
        return {
            **self.library_payload(library),
            "runs": [self.run_payload(run) for run in self.repository.list_runs(library.id)],
        }

    def queue_scan(
        self,
        library_id: str,
        mode: str,
        *,
        trigger: str = "manual",
    ) -> LibraryScanRun:
        library = self._library(library_id)
        normalized_mode = str(mode or "").strip().casefold()
        normalized_trigger = str(trigger or "manual").strip().casefold()
        if normalized_mode not in {"dry_run", "apply"}:
            raise ValueError("Scanner mode must be dry_run or apply")
        if normalized_trigger not in {"manual", "scheduled"}:
            raise ValueError("Scanner trigger must be manual or scheduled")
        if normalized_mode == "apply" and not library.verified_at:
            raise LibraryValidationError("Run a successful test scan before applying changes")
        now = self._now()
        return self.repository.create_run(
            LibraryScanRun(
                id=uuid.uuid4().hex,
                library_id=library.id,
                mode=normalized_mode,
                trigger=normalized_trigger,
                created_at=now,
            )
        )

    def execute_run(self, run_id: str) -> None:
        started_at = self._now()
        run = self.repository.claim_run(run_id, started_at)
        if run is None:
            return
        library = self._library(run.library_id)
        previous = self.repository.previous_files(library.id)
        previous_by_path = {item.relative_path: _scanner_cache_row(item) for item in previous}
        try:
            root = self.validate_root(library.root_path)
            scanned, errors = self.scanner(root, previous_by_path, scanned_at=started_at)
            classified, summary, preview = self._classify_scan(library, run, scanned, previous)
            guard_error = _removal_guard(previous, scanned, library.max_missing_ratio)
            if guard_error:
                errors.append(guard_error)
            finished_at = self._now()
            status = "blocked" if guard_error else "partial" if errors else "completed"
            commit_inventory = run.mode == "apply" and not guard_error
            mark_missing = commit_inventory and not errors
            summary = {
                **summary,
                "errors": len(errors),
                "removals_skipped": bool(errors),
            }
            verified_at = library.verified_at
            if run.mode == "dry_run" and not errors:
                verified_at = finished_at
            library_status = "warning" if errors else "ready"
            completed_library = replace(
                library,
                status=library_status,
                verified_at=verified_at,
                last_scan_at=finished_at if run.mode == "apply" else library.last_scan_at,
                next_scan_at=(
                    _next_scan(finished_at, library.schedule)
                    if library.active
                    else library.next_scan_at
                ),
                updated_at=finished_at,
            )
            completed_run = replace(
                run,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                summary=summary,
                errors=tuple(errors),
                preview=tuple(preview),
            )
            self.repository.complete_run(
                completed_run,
                completed_library,
                classified,
                commit_inventory=commit_inventory,
                mark_missing=mark_missing,
            )
        except Exception as error:
            self._fail_run(run, library, started_at, error)

    def queue_due_scans(self) -> list[LibraryScanRun]:
        if not self.configured:
            return []
        queued: list[LibraryScanRun] = []
        for library in self.repository.due_libraries(self._now()):
            try:
                queued.append(self.queue_scan(library.id, "apply", trigger="scheduled"))
            except (LibraryRunBusy, LibraryPathError, LibraryValidationError):
                continue
        return queued

    def review_queue(self) -> list[dict[str, Any]]:
        libraries = {library.id: library for library in self.repository.list_libraries()}
        return [
            self.file_payload(item, libraries.get(item.library_id))
            for item in self.repository.review_queue()
        ]

    def review_file(self, file_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action") or "").strip().casefold()
        selected_identity: dict[str, Any] | None = None
        queue = {item.id: item for item in self.repository.review_queue()}
        item = queue.get(file_id)
        if item is None:
            raise LibraryNotFound("Scanner queue item was not found")
        if action == "confirm":
            candidate_key = str(payload.get("candidate_key") or "").strip()
            if candidate_key:
                candidate = next(
                    (dict(value) for value in item.candidates if str(value.get("key") or "") == candidate_key),
                    None,
                )
                if candidate is None:
                    raise ValueError("Scanner candidate was not found")
                candidate.pop("key", None)
                candidate.pop("score", None)
                selected_identity = candidate
            else:
                selected_identity = detected_work_identity(
                    str(payload.get("title") or item.detected_title),
                    str(payload.get("year") or item.detected_year),
                    str(payload.get("kind") or item.detected_kind),
                )
                if not str(selected_identity.get("year") or "").strip():
                    raise ValueError("Confirm the year or choose an existing candidate")
        updated = self.repository.review_file(file_id, action, selected_identity, self._now())
        library = self.repository.get_library(updated.library_id)
        return self.file_payload(updated, library)

    def validate_root(self, value: str) -> Path:
        if not self.allowed_roots:
            raise LibraryPathError("Managed scanner has no allowed roots configured")
        raw = Path(os.path.expandvars(os.path.expanduser(str(value or "").strip())))
        if not raw.is_absolute():
            raise LibraryPathError("Managed library path must be absolute")
        candidate = raw.resolve()
        if not any(_is_within(candidate, allowed) for allowed in self.allowed_roots):
            raise LibraryPathError("Managed library path is outside the server allowlist")
        if not candidate.exists() or not candidate.is_dir():
            raise LibraryPathError("Managed library path is offline or is not a directory")
        if candidate.is_symlink() or bool(getattr(candidate, "is_junction", lambda: False)()):
            raise LibraryPathError("Managed library root cannot be a symbolic link or junction")
        return candidate

    def library_payload(self, library: ManagedLibrary) -> dict[str, Any]:
        counts_method = getattr(self.repository, "counts", None)
        counts = counts_method(library.id) if callable(counts_method) else {}
        return {
            "id": library.id,
            "name": library.name,
            "root_path": library.root_path,
            "schedule": library.schedule,
            "active": library.active,
            "status": library.status,
            "max_missing_ratio": library.max_missing_ratio,
            "verified_at": library.verified_at,
            "last_scan_at": library.last_scan_at,
            "next_scan_at": library.next_scan_at,
            "created_at": library.created_at,
            "updated_at": library.updated_at,
            "counts": counts,
        }

    @staticmethod
    def run_payload(run: LibraryScanRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "library_id": run.library_id,
            "mode": run.mode,
            "trigger": run.trigger,
            "status": run.status,
            "created_at": run.created_at,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "summary": dict(run.summary),
            "errors": list(run.errors),
            "preview": [dict(value) for value in run.preview],
        }

    @staticmethod
    def file_payload(item: LibraryFile, library: ManagedLibrary | None) -> dict[str, Any]:
        return {
            "id": item.id,
            "library_id": item.library_id,
            "library_name": library.name if library else "Biblioteca",
            "relative_path": item.relative_path,
            "name": item.name,
            "size_bytes": item.size_bytes,
            "detected_title": item.detected_title,
            "detected_year": item.detected_year,
            "detected_kind": item.detected_kind,
            "state": item.state,
            "candidates": [dict(value) for value in item.candidates],
            "last_seen_at": item.last_seen_at,
        }

    def _classify_scan(
        self,
        library: ManagedLibrary,
        run: LibraryScanRun,
        scanned: list[dict[str, Any]],
        previous: list[LibraryFile],
    ) -> tuple[list[LibraryFile], dict[str, int], list[dict[str, Any]]]:
        match_index = _CatalogMatchIndex.build(self.catalog_universe())
        previous_by_path = {_relative_path_key(item.relative_path): item for item in previous}
        current_path_keys = {
            _relative_path_key(str(row.get("relative_path") or ""))
            for row in scanned
        }
        fingerprint_index: dict[str, list[LibraryFile]] = defaultdict(list)
        for item in previous:
            if item.fingerprint:
                fingerprint_index[item.fingerprint].append(item)
        claimed_ids: set[str] = set()
        counts = {
            "discovered": len(scanned),
            "unchanged": 0,
            "updated": 0,
            "moved": 0,
            "matched": 0,
            "new": 0,
            "review": 0,
            "ignored": 0,
            "missing": 0,
        }
        classified: list[LibraryFile] = []
        preview: list[dict[str, Any]] = []
        for row in scanned:
            relative_path = str(row.get("relative_path") or "")
            existing = previous_by_path.get(_relative_path_key(relative_path))
            moved = False
            if existing is None and row.get("fingerprint"):
                possible = [
                    item
                    for item in fingerprint_index.get(str(row["fingerprint"]), [])
                    if item.id not in claimed_ids
                    and _relative_path_key(item.relative_path) not in current_path_keys
                ]
                if len(possible) == 1:
                    existing = possible[0]
                    moved = existing.relative_path.casefold() != relative_path.casefold()
            if existing:
                claimed_ids.add(existing.id)
            state, identity, candidates = self._classification(existing, row, match_index)
            first_seen = existing.first_seen_at if existing else run.started_at
            item = LibraryFile(
                id=existing.id if existing else uuid.uuid4().hex,
                library_id=library.id,
                relative_path=relative_path,
                name=str(row.get("name") or ""),
                size_bytes=int(row.get("size_bytes") or 0),
                modified_ns=int(row.get("modified_ns") or 0),
                modified_at=str(row.get("modified_at") or ""),
                fingerprint=str(row.get("fingerprint") or ""),
                detected_title=str(row.get("title") or ""),
                detected_year=str(row.get("year") or ""),
                detected_kind=str(row.get("kind") or "pelicula"),
                state=state,
                work_key=work_identity_key(identity) if state == "matched" else "",
                identity=identity,
                candidates=tuple(candidates),
                available=True,
                first_seen_at=first_seen,
                last_seen_at=run.started_at,
                updated_at=run.started_at,
                last_run_id=run.id,
            )
            classified.append(item)
            counts[state] += 1
            if existing is None:
                counts["updated"] += 1
            elif moved:
                counts["moved"] += 1
            elif _same_file(existing, row):
                counts["unchanged"] += 1
            else:
                counts["updated"] += 1
            if len(preview) < PREVIEW_LIMIT:
                preview.append(
                    {
                        "relative_path": relative_path,
                        "title": item.detected_title,
                        "year": item.detected_year,
                        "kind": item.detected_kind,
                        "state": state,
                        "candidate_count": len(candidates),
                    }
                )
        counts["missing"] = len([item for item in previous if item.available and item.id not in claimed_ids])
        return classified, counts, preview

    @staticmethod
    def _classification(
        existing: LibraryFile | None,
        row: Mapping[str, Any],
        match_index: _CatalogMatchIndex,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        if (
            existing
            and existing.state in {"matched", "ignored"}
            and existing.fingerprint == str(row.get("fingerprint") or "")
        ):
            return existing.state, dict(existing.identity), [dict(value) for value in existing.candidates]
        detected = detected_work_identity(
            str(row.get("title") or ""),
            str(row.get("year") or ""),
            str(row.get("kind") or "pelicula"),
        )
        groups: dict[str, dict[str, Any]] = {}
        for catalog_item in match_index.candidates(detected):
            decision = decide_match(catalog_item, detected)
            if not decision.accepted and decision.score < 0.72:
                continue
            identity = work_identity(catalog_item)
            key = work_identity_key(identity)
            if not key:
                continue
            candidate = {**identity, "key": key, "score": decision.score, "reason": decision.reason}
            prior = groups.get(key)
            if prior is None or float(candidate["score"]) > float(prior.get("score") or 0):
                groups[key] = candidate
        accepted = [value for value in groups.values() if str(value.get("reason") or "") in {"shared_external_url", "shared_wikidata_id", "exact_title_year"}]
        if len(accepted) == 1:
            identity = dict(accepted[0])
            for key in ("key", "score", "reason"):
                identity.pop(key, None)
            return "matched", identity, []
        candidates = sorted(groups.values(), key=lambda value: float(value.get("score") or 0), reverse=True)[:8]
        if candidates:
            return "review", {}, candidates
        return "new", {}, []

    def _fail_run(
        self,
        run: LibraryScanRun,
        library: ManagedLibrary,
        started_at: int,
        error: Exception,
    ) -> None:
        finished_at = self._now()
        offline = isinstance(error, (LibraryPathError, OSError)) or "offline" in str(error).casefold()
        failed_library = replace(
            library,
            status="offline" if offline else "error",
            next_scan_at=_next_scan(finished_at, library.schedule) if library.active else 0,
            updated_at=finished_at,
        )
        failed_run = replace(
            run,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            summary={"discovered": 0, "errors": 1},
            errors=(str(error),),
        )
        self.repository.complete_run(
            failed_run,
            failed_library,
            [],
            commit_inventory=False,
            mark_missing=False,
        )

    def _library(self, library_id: str) -> ManagedLibrary:
        library = self.repository.get_library(str(library_id or ""))
        if library is None:
            raise LibraryNotFound("Managed library was not found")
        return library

    def _now(self) -> int:
        return int(self.clock())


class AvailabilityService:
    """Decorate personal catalog rows without persisting scanner state into them."""

    def __init__(self, repository: LibraryRepository) -> None:
        self.repository = repository

    def decorate_items(
        self,
        items: list[dict[str, Any]],
        *,
        include_sources: bool = False,
    ) -> list[dict[str, Any]]:
        records = self.repository.availability_records()
        indexes = _availability_indexes(records)
        decorated: list[dict[str, Any]] = []
        for original in items:
            item = dict(original)
            matches = _availability_matches(item, records, indexes)
            manual = bool(item.get("en_catalogo"))
            sources: dict[str, dict[str, Any]] = {}
            for record in matches:
                source = sources.setdefault(
                    str(record.get("library_id") or ""),
                    {
                        "library_id": str(record.get("library_id") or ""),
                        "library_name": str(record.get("library_name") or "Biblioteca"),
                        "file_count": 0,
                    },
                )
                source["file_count"] += int(record.get("file_count") or 0)
            server = bool(sources)
            availability = {
                "effective": bool(manual or server),
                "manual": manual,
                "server": server,
                "verified": server,
                "file_count": sum(int(value["file_count"]) for value in sources.values()),
                "library_count": len(sources),
            }
            if include_sources:
                availability["sources"] = list(sources.values())
            item["_availability"] = availability
            item["_manual_en_catalogo"] = manual
            item["en_catalogo"] = availability["effective"]
            decorated.append(item)
        return decorated


class ManagedLibraryScheduler:
    def __init__(self, service: ManagedLibraryService, poll_seconds: float = 15.0) -> None:
        self.service = service
        self.poll_seconds = max(1.0, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.service.repository.recover_interrupted_runs(int(self.service.clock()))
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="movie-inbox-scanner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=min(5.0, self.poll_seconds + 1.0))
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                for run in self.service.queue_due_scans():
                    if self._stop.is_set():
                        break
                    self.service.execute_run(run.id)
            except LibraryRepositoryError:
                pass
            self._stop.wait(self.poll_seconds)


def _availability_indexes(records: list[dict[str, Any]]) -> dict[str, dict[Any, set[int]]]:
    indexes: dict[str, dict[Any, set[int]]] = {
        "url": defaultdict(set),
        "wikidata": defaultdict(set),
        "signature": defaultdict(set),
    }
    for position, record in enumerate(records):
        identity = record.get("identity") or {}
        for url in external_urls(identity):
            indexes["url"][url].add(position)
        wikidata = str(identity.get("wikidata_id") or "").strip().upper()
        if wikidata:
            indexes["wikidata"][wikidata].add(position)
        year = str(identity.get("year") or "").strip()
        kind = explicit_kind(identity) or "pelicula"
        if year:
            for title in title_match_keys_for_item(identity):
                indexes["signature"][(title, year, kind)].add(position)
    return indexes


def _availability_matches(
    item: Mapping[str, Any],
    records: list[dict[str, Any]],
    indexes: dict[str, dict[Any, set[int]]],
) -> list[dict[str, Any]]:
    positions: set[int] = set()
    for url in external_urls(item):
        positions.update(indexes["url"].get(url, set()))
    wikidata = str(item.get("wikidata_id") or "").strip().upper()
    if wikidata:
        positions.update(indexes["wikidata"].get(wikidata, set()))
    year = str(item.get("year") or "").strip()
    kind = explicit_kind(item) or "pelicula"
    if year:
        for title in title_match_keys_for_item(item):
            positions.update(indexes["signature"].get((title, year, kind), set()))
    return [
        records[position]
        for position in sorted(positions)
        if identity_matches_item(records[position]["identity"], item)
    ]


def _scanner_cache_row(item: LibraryFile) -> dict[str, Any]:
    return {
        "size_bytes": item.size_bytes,
        "modified_ns": item.modified_ns,
        "fingerprint": item.fingerprint,
    }


def _same_file(item: LibraryFile, row: Mapping[str, Any]) -> bool:
    return bool(
        item.available
        and item.size_bytes == int(row.get("size_bytes") or 0)
        and item.modified_ns == int(row.get("modified_ns") or 0)
        and item.fingerprint == str(row.get("fingerprint") or "")
    )


def _removal_guard(
    previous: list[LibraryFile],
    scanned: list[Mapping[str, Any]],
    maximum: float,
) -> str:
    previous_paths = {_relative_path_key(item.relative_path) for item in previous if item.available}
    if not previous_paths:
        return ""
    current_paths = {
        _relative_path_key(str(item.get("relative_path") or ""))
        for item in scanned
    }
    missing = len(previous_paths - current_paths)
    ratio = missing / len(previous_paths)
    if ratio <= maximum:
        return ""
    return (
        f"Removal guard: {missing}/{len(previous_paths)} prior files are missing "
        f"({ratio:.1%}, configured maximum {maximum:.1%})"
    )


def _next_scan(now: int, schedule: str) -> int:
    interval = SCHEDULE_SECONDS.get(schedule, 0)
    return now + interval if interval else 0


def _resolved_root(value: str) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve()
    return path


def _relative_path_key(value: str) -> str:
    return os.path.normcase(str(value or "").replace("\\", "/"))


def _is_within(candidate: Path, allowed: Path) -> bool:
    try:
        candidate.relative_to(allowed)
        return True
    except ValueError:
        return False
