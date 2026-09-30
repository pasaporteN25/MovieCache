"""[U7 B] TMDb and Wikidata behind the image service's source protocol.

The service in `application/image_service.py` never learns which clients answer
it; this adapter turns their raw answers into domain values and every network
failure into `ImageSourceUnavailable`, so "the source is down" can never be
mistaken for "the source has nothing for this work".
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.error import HTTPError, URLError

from movie_inbox.domain.images import (
    ImageCandidate,
    ImageSourceUnavailable,
    TmdbMatch,
    tmdb_image_candidates,
)
from movie_inbox.external.tmdb import TmdbAdapter
from movie_inbox.external.wikidata import fetch_wikidata_tmdb_references

T = TypeVar("T")
_NETWORK_ERRORS = (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError)


class TmdbImageSource:
    def __init__(self, adapter: TmdbAdapter) -> None:
        self.adapter = adapter

    def candidates(self, media_type: str, tmdb_id: str) -> list[ImageCandidate]:
        return tmdb_image_candidates(_call({}, self.adapter.images, media_type, tmdb_id))

    def matches_for_imdb(self, imdb_id: str) -> list[TmdbMatch]:
        empty_rows: list[dict[str, str]] = []
        rows = _call(empty_rows, self.adapter.find_by_imdb, imdb_id)
        return [TmdbMatch(row["media_type"], row["tmdb_id"], row["year"]) for row in rows]

    def matches_for_wikidata(self, entity_id: str) -> list[TmdbMatch]:
        no_references: list[tuple[str, str]] = []
        references = _call(no_references, fetch_wikidata_tmdb_references, entity_id)
        # Wikidata states the id but not TMDb's year; the rule needs both, so
        # each stated work is confirmed against TMDb itself.
        return [
            TmdbMatch(
                media_type, tmdb_id, _call("", self.adapter.release_year, media_type, tmdb_id)
            )
            for media_type, tmdb_id in references
        ]


def _call(empty: T, function: Callable[..., T], *arguments: Any) -> T:
    try:
        return function(*arguments)
    except HTTPError as error:
        if error.code == 404:
            # An id the upstream does not know is an empty answer, not an outage.
            return empty
        raise ImageSourceUnavailable(str(error), rate_limited=error.code == 429) from error
    except _NETWORK_ERRORS as error:
        raise ImageSourceUnavailable(str(error)) from error
