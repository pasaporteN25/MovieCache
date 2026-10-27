"""[X12 B] Fill in the Wikidata id of entries that only have a Wikipedia link.

The Wikidata id is what tells curation that the English and the Spanish
Wikipedia article of one film are one film. Entries saved before Wikipedia
results carried it only have the article link, so this looks the ids up --
fifty articles per request, per language -- and writes them back, with the year
when the entry has none. Nothing already filled or locked is touched.

It runs three ways and all three share this service: a slow background loop, a
"do it now" button in curation, and `movie-inbox identity resolve`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from movie_inbox.application.repository import CatalogRepository, CatalogRepositoryError
from movie_inbox.domain.models import CatalogItem
from movie_inbox.domain.work_identity import (
    WikipediaArticle,
    apply_resolved_identity,
    identity_resolution_target,
)

# language, article titles -> {title as asked: Wikidata id}. Raises on a
# network failure, so a source that did not answer is never mistaken for an
# article that has no Wikidata id.
ArticleIdLookup = Callable[[str, Sequence[str]], Mapping[str, str]]
# Wikidata ids -> {id: release year}. Best effort: an empty answer only means no
# year gets filled.
ReleaseYearLookup = Callable[[Sequence[str]], Mapping[str, str]]
CatalogRepositories = Callable[[], Sequence[CatalogRepository]]

BATCH_SIZE = 50
# An article Wikipedia answered without an id (deleted, a redirect to a list) is
# asked again after a month, not on every pass.
RETRY_AFTER_SECONDS = 30 * 24 * 60 * 60
LOOKUP_ERRORS = (OSError, TimeoutError, ValueError)


class IdentityAttemptStore(Protocol):
    def recent_misses(self, keys: Sequence[str], since: int) -> set[str]: ...

    def record_misses(self, keys: Sequence[str], at: int) -> None: ...


class IdentityAttemptStoreError(RuntimeError):
    """The attempt record could not be read or written."""


@dataclass
class ResolutionReport:
    resolved: int = 0
    years: int = 0
    missing: int = 0
    failed: int = 0
    pending: int = 0
    errors: list[str] = field(default_factory=list)

    def add(self, other: ResolutionReport) -> None:
        self.resolved += other.resolved
        self.years += other.years
        self.missing += other.missing
        self.failed += other.failed
        self.pending = other.pending
        self.errors.extend(error for error in other.errors if error not in self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved": self.resolved,
            "years": self.years,
            "missing": self.missing,
            "failed": self.failed,
            "pending": self.pending,
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class _Target:
    repository: CatalogRepository
    item_id: str
    article: WikipediaArticle


class IdentityResolutionService:
    def __init__(
        self,
        repositories: CatalogRepositories,
        article_ids: ArticleIdLookup,
        release_years: ReleaseYearLookup | None = None,
        attempts: IdentityAttemptStore | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.repositories = repositories
        self.article_ids = article_ids
        self.release_years = release_years
        self.attempts = attempts
        self.clock = clock
        # The background loop and the button must not resolve the same batch
        # twice at the same time.
        self._lock = threading.Lock()

    def pending_count(self) -> int:
        return len(self._targets())

    def resolve_batch(self, limit: int = BATCH_SIZE) -> ResolutionReport:
        with self._lock:
            return self._resolve_batch(max(1, int(limit)))

    def resolve_all(self, max_batches: int = 200) -> ResolutionReport:
        """Work through everything pending, a batch at a time, until done or stuck."""

        total = ResolutionReport()
        for _ in range(max(1, int(max_batches))):
            report = self.resolve_batch()
            total.add(report)
            if not report.pending or not (report.resolved or report.missing):
                break
        return total

    def _resolve_batch(self, limit: int) -> ResolutionReport:
        report = ResolutionReport()
        targets = self._targets()
        batch = targets[:limit]
        report.pending = len(targets)
        if not batch:
            return report

        found: dict[str, str] = {}
        asked: set[str] = set()
        by_language: dict[str, list[_Target]] = {}
        for target in batch:
            by_language.setdefault(target.article.language, []).append(target)
        for language, language_targets in by_language.items():
            titles = list(dict.fromkeys(target.article.title for target in language_targets))
            try:
                answer = self.article_ids(language, titles)
            except LOOKUP_ERRORS as error:
                report.failed += len(language_targets)
                report.errors.append(f"wikipedia:{language}: {type(error).__name__}")
                continue
            asked.update(target.article.key for target in language_targets)
            for title in titles:
                entity = str(answer.get(title) or "").strip().upper()
                if entity:
                    found[WikipediaArticle(language, title).key] = entity

        years: Mapping[str, str] = {}
        if found and self.release_years is not None:
            try:
                years = self.release_years(sorted(set(found.values())))
            except LOOKUP_ERRORS as error:
                report.errors.append(f"wikidata: {type(error).__name__}")

        now = datetime.now(UTC).isoformat()
        by_repository: dict[int, list[_Target]] = {}
        repositories: dict[int, CatalogRepository] = {}
        for target in batch:
            if target.article.key in found:
                by_repository.setdefault(id(target.repository), []).append(target)
                repositories[id(target.repository)] = target.repository
        for key, repository_targets in by_repository.items():
            try:
                written = repositories[key].mutate(
                    _apply_mutation(repository_targets, found, years, now)
                )
            except CatalogRepositoryError as error:
                report.failed += len(repository_targets)
                report.errors.append(f"catalog: {type(error).__name__}")
                continue
            report.resolved += written[0]
            report.years += written[1]

        misses = sorted(asked - set(found))
        report.missing = len(misses)
        if misses and self.attempts is not None:
            try:
                self.attempts.record_misses(misses, int(self.clock()))
            except IdentityAttemptStoreError as error:
                report.errors.append(f"attempts: {error}")
        report.pending = max(0, len(targets) - report.resolved - report.missing)
        return report

    def _targets(self) -> list[_Target]:
        targets: list[_Target] = []
        for repository in self.repositories():
            try:
                items = repository.read()
            except CatalogRepositoryError:
                continue
            for item in items:
                article = identity_resolution_target(item)
                if article is not None and item.id:
                    targets.append(_Target(repository, item.id, article))
        if not targets or self.attempts is None:
            return targets
        try:
            recent = self.attempts.recent_misses(
                [target.article.key for target in targets],
                int(self.clock()) - RETRY_AFTER_SECONDS,
            )
        except IdentityAttemptStoreError:
            recent = set()
        return [target for target in targets if target.article.key not in recent]


def _apply_mutation(
    targets: Sequence[_Target],
    found: Mapping[str, str],
    years: Mapping[str, str],
    now: str,
) -> Callable[[list[CatalogItem]], tuple[bool, tuple[int, int]]]:
    wanted = {target.item_id: found[target.article.key] for target in targets}

    def mutation(items: list[CatalogItem]) -> tuple[bool, tuple[int, int]]:
        resolved = filled_years = 0
        for item in items:
            entity = wanted.get(item.id)
            # Re-checked inside the write: someone may have edited the entry
            # between the read that queued it and now.
            if not entity or identity_resolution_target(item) is None:
                continue
            written = apply_resolved_identity(item, entity, str(years.get(entity) or ""), now)
            resolved += "wikidata_id" in written
            filled_years += "year" in written
        return bool(resolved or filled_years), (resolved, filled_years)

    return mutation


class IdentityResolutionScheduler:
    """Resolves one small batch every `poll_seconds`, in the background.

    Slow on purpose: Wikipedia is a shared, free service, and nothing here is
    urgent -- the button in curation exists for when it is.
    """

    def __init__(self, service: IdentityResolutionService, poll_seconds: float = 300.0) -> None:
        self.service = service
        self.poll_seconds = max(30.0, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="movie-inbox-identity", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5.0)
        self._thread = None

    def _loop(self) -> None:
        # The first pass waits too, so starting the server does not add a burst
        # of requests to everything else it does on startup.
        while not self._stop.wait(self.poll_seconds):
            try:
                self.service.resolve_batch()
            except Exception as error:  # noqa: BLE001 - a background loop must survive
                print(f"[identity] background resolution failed error={error}", flush=True)
