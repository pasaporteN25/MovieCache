"""Opt-in local IMDb index as a metadata source ([F6.1], implementing [Q5]).

[F1] built the index but left it deliberately disconnected from the catalogue.
Meanwhile [Q5] fixed an authority matrix that names it the *first* source tried
for identity fragments, classification and structured data. This module is the
cable between the two.

Lookup is by IMDb id only. A title+year search can return several works, and
picking one would be exactly the kind of guess invariant 3 forbids; an id is
identity, so it is the only key used here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE, dataset_metadata
from movie_inbox.domain.public_ratings import IMDB_SOURCE, PublicRating, public_rating
from movie_inbox.infrastructure.imdb_dataset_index import (
    ImdbDatasetIndexStale,
    lookup_by_tconst,
    lookup_ratings_by_tconst,
)

# Field families the matrix gives the index. Anything outside this set is left to
# the sources that actually carry it, even when the index could technically fill it.
DATASET_FIELDS = frozenset(
    {"title", "original_title", "alternative_titles", "kind", "year", "duration_minutes", "genres"}
)


class DatasetLookup(Protocol):
    """What the authority helper needs, so a caller can substitute a fake."""

    def metadata_for(self, imdb_id: str) -> dict[str, Any]: ...


class ImdbDatasetSource:
    name = "imdb_dataset"
    label = "IMDb (índice local)"
    attribution = IMDB_ATTRIBUTION_NOTICE

    def __init__(self, index_path: Path) -> None:
        self.index_path = Path(index_path)

    def metadata_for(self, imdb_id: str) -> dict[str, Any]:
        """Fields the local index can contribute for one IMDb id.

        A missing, stale or unreadable index yields nothing rather than raising:
        the index is an optional accelerator, so an instance that never ran
        `imdb-dataset sync` must keep enriching exactly as it did before.
        """

        tconst = _tconst(imdb_id)
        if not tconst:
            return {}
        try:
            found = lookup_by_tconst(self.index_path, tconst)
        except (FileNotFoundError, ImdbDatasetIndexStale, OSError):
            return {}
        return dataset_metadata(found)

    def rating_for(self, imdb_id: str) -> PublicRating | None:
        """The public score for one work, read from the index at display time.

        Deliberately not part of `metadata_for`: ratings move, and merging one
        into the catalogue would store a number that quietly goes stale. The
        index is the storage, and the owner controls when it is re-synced.
        """

        tconst = _tconst(imdb_id)
        if not tconst:
            return None
        try:
            found = lookup_ratings_by_tconst(self.index_path, tconst)
        except (FileNotFoundError, ImdbDatasetIndexStale, OSError):
            return None
        if found is None:
            return None
        return public_rating(IMDB_SOURCE, found.average_rating, found.num_votes)


def _tconst(imdb_id: str) -> str:
    value = str(imdb_id or "").strip().lower()
    return value if value.startswith("tt") and value[2:].isdigit() else ""


def apply_dataset_authority(
    metadata: dict[str, Any],
    source: DatasetLookup | None,
    imdb_id: str,
) -> dict[str, Any]:
    """Let the local index win over a live source, for its fields only.

    [Q5] puts the index first for these families. Downstream merges only fill
    empty fields, so "first" has to mean the index's value is already in the dict
    the live fetch returns -- hence an override here rather than a later pass.

    `alternative_titles` is a union field and is merged instead of replaced, so a
    live source's aliases are never lost.
    """

    if source is None or not imdb_id:
        return metadata
    contributed = source.metadata_for(imdb_id)
    if not contributed:
        return metadata
    merged = dict(metadata)
    for field, value in contributed.items():
        if field == "alternative_titles":
            existing = [str(row) for row in merged.get(field) or []]
            merged[field] = existing + [row for row in value if row not in existing]
            continue
        merged[field] = value
    return merged


__all__ = ["DATASET_FIELDS", "DatasetLookup", "ImdbDatasetSource", "apply_dataset_authority"]
