"""Persistence contract for managed media libraries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from movie_inbox.domain.libraries import LibraryFile, LibraryScanRun, ManagedLibrary


class LibraryRepositoryError(RuntimeError):
    """Raised when the shared library inventory cannot be persisted."""


class LibraryNotFound(LookupError):
    """Raised when a managed library or scanner record does not exist."""


class LibraryRunBusy(RuntimeError):
    """Raised when a scan is already queued or running."""


class LibraryConflict(RuntimeError):
    """Raised when a scanner review row changed since the operation being restored."""


@dataclass(frozen=True)
class ReviewedFileState:
    """The reviewable slice of a `LibraryFile` a review decision reads and writes."""

    state: str
    work_key: str
    identity: Mapping[str, Any] = field(default_factory=dict)
    candidates: tuple[Mapping[str, Any], ...] = ()

    @classmethod
    def from_file(cls, file: LibraryFile) -> ReviewedFileState:
        return cls(
            state=file.state,
            work_key=file.work_key,
            identity=dict(file.identity),
            candidates=tuple(dict(candidate) for candidate in file.candidates),
        )


class LibraryRepository(Protocol):
    def create_library(self, library: ManagedLibrary) -> ManagedLibrary: ...

    def list_libraries(self) -> list[ManagedLibrary]: ...

    def get_library(self, library_id: str) -> ManagedLibrary | None: ...

    def update_library(self, library: ManagedLibrary) -> ManagedLibrary: ...

    def delete_library(self, library_id: str) -> bool: ...

    def create_run(self, run: LibraryScanRun) -> LibraryScanRun: ...

    def claim_run(self, run_id: str, started_at: int) -> LibraryScanRun | None: ...

    def get_run(self, run_id: str) -> LibraryScanRun | None: ...

    def list_runs(self, library_id: str, limit: int = 20) -> list[LibraryScanRun]: ...

    def previous_files(self, library_id: str) -> list[LibraryFile]: ...

    def complete_run(
        self,
        run: LibraryScanRun,
        library: ManagedLibrary,
        files: list[LibraryFile],
        *,
        commit_inventory: bool,
        mark_missing: bool,
    ) -> None: ...

    def recover_interrupted_runs(self, finished_at: int) -> int: ...

    def due_libraries(self, now: int) -> list[ManagedLibrary]: ...

    def review_queue(self) -> list[LibraryFile]: ...

    def review_file(
        self,
        file_id: str,
        action: str,
        identity: dict[str, Any] | None,
        updated_at: int,
    ) -> LibraryFile: ...

    def review_files(
        self,
        file_ids: list[str],
        action: str,
        identity: dict[str, Any] | None,
        updated_at: int,
    ) -> list[LibraryFile]: ...

    def restore_reviewed_files(
        self,
        expected: dict[str, ReviewedFileState],
        target: dict[str, ReviewedFileState],
        updated_at: int,
    ) -> list[LibraryFile]: ...

    def availability_records(self) -> list[dict[str, Any]]: ...

    def counts(self, library_id: str) -> dict[str, int]: ...
