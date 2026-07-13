#!/usr/bin/env python3
"""Canonical domain models and boundary payload types."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from dataclasses import dataclass, field, fields
from typing import Any, TypedDict

from catalog_primitives import normalize_bool


class ModelMapping(MutableMapping[str, Any]):
    extra: dict[str, Any]

    @classmethod
    def model_fields(cls) -> tuple[str, ...]:
        return tuple(row.name for row in fields(cls) if row.name != "extra")

    def __getitem__(self, key: str) -> Any:
        if key in self.model_fields():
            return getattr(self, key)
        return self.extra[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.model_fields():
            setattr(self, key, self.coerce_field(key, value))
            return
        self.extra[key] = value

    def __delitem__(self, key: str) -> None:
        if key in self.extra:
            del self.extra[key]
            return
        if key in self.model_fields():
            raise KeyError(f"Canonical field cannot be deleted: {key}")
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        yield from self.model_fields()
        yield from (key for key in self.extra if key not in self.model_fields())

    def __len__(self) -> int:
        return len(self.model_fields()) + len([key for key in self.extra if key not in self.model_fields()])

    def coerce_field(self, key: str, value: Any) -> Any:
        return value

    def to_dict(self) -> dict[str, Any]:
        payload = {key: model_value(getattr(self, key)) for key in self.model_fields()}
        payload.update({key: model_value(value) for key, value in self.extra.items()})
        return payload

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        names = set(cls.model_fields())
        kwargs = {key: value[key] for key in names if key in value}
        instance = cls(**kwargs)
        instance.extra.update({str(key): row for key, row in value.items() if key not in names})
        return instance


@dataclass
class MetadataSource(ModelMapping):
    source: str = ""
    url: str = ""
    updated_at: str = ""
    inferred: bool = False
    extra: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.source = str(self.source or "")
        self.url = str(self.url or "")
        self.updated_at = str(self.updated_at or "")
        self.inferred = normalize_bool(self.inferred)


@dataclass
class LocalFile(ModelMapping):
    path: str = ""
    name: str = ""
    size_bytes: int = 0
    modified_at: str = ""
    part: str = ""
    library_id: str = ""
    relative_path: str = ""
    fingerprint: str = ""
    last_seen_at: str = ""
    available: bool = True
    extra: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        for key in ("path", "name", "modified_at", "part", "library_id", "relative_path", "fingerprint", "last_seen_at"):
            setattr(self, key, str(getattr(self, key) or ""))
        try:
            self.size_bytes = max(0, int(self.size_bytes or 0))
        except (TypeError, ValueError):
            self.size_bytes = 0
        self.available = normalize_bool(self.available, default=True)


@dataclass
class CatalogItem(ModelMapping):
    id: str = ""
    url: str = ""
    source: str = ""
    title: str = ""
    original_title: str = ""
    spanish_title: str = ""
    english_title: str = ""
    alternative_titles: list[str] = field(default_factory=list)
    kind: str = "pelicula"
    status: str = "to_watch"
    watched_at: str = ""
    rating: int = 0
    year: str = ""
    description: str = ""
    wikipedia_url: str = ""
    imdb_url: str = ""
    filmaffinity_url: str = ""
    wikipedia_title: str = ""
    wikidata_id: str = ""
    genres: list[str] = field(default_factory=list)
    directors: list[str] = field(default_factory=list)
    writers: list[str] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)
    page_image: str = ""
    wikipedia_extract: str = ""
    en_catalogo: bool = False
    local_files: list[LocalFile] = field(default_factory=list)
    local_name: str = ""
    local_path: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    review: str = ""
    metadata_sources: dict[str, MetadataSource] = field(default_factory=dict)
    locked_fields: list[str] = field(default_factory=list)
    added_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.local_files = self.coerce_field("local_files", self.local_files)
        self.metadata_sources = self.coerce_field("metadata_sources", self.metadata_sources)

    def coerce_field(self, key: str, value: Any) -> Any:
        if key == "local_files":
            rows = value if isinstance(value, list) else []
            return [row if isinstance(row, LocalFile) else LocalFile.from_mapping(row) for row in rows if isinstance(row, Mapping)]
        if key == "metadata_sources":
            if not isinstance(value, Mapping):
                return {}
            return {
                str(field_name): row if isinstance(row, MetadataSource) else MetadataSource.from_mapping(row)
                for field_name, row in value.items()
                if isinstance(row, Mapping)
            }
        return value


class ExternalSearchResult(TypedDict, total=False):
    url: str
    source: str
    title: str
    original_title: str
    spanish_title: str
    english_title: str
    alternative_titles: list[str]
    kind: str
    year: str
    description: str
    wikipedia_url: str
    imdb_url: str
    filmaffinity_url: str
    wikipedia_title: str
    wikidata_id: str
    genres: list[str]
    directors: list[str]
    writers: list[str]
    cast: list[str]
    page_image: str
    wikipedia_extract: str


def model_value(value: Any) -> Any:
    if isinstance(value, ModelMapping):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): model_value(row) for key, row in value.items()}
    if isinstance(value, list):
        return [model_value(row) for row in value]
    return value
