"""One rule for whether two catalogue entries are the same work ([X12]).

Before this module the question had five answers. Curation grouped duplicates
by literal URL and title+year only, so two entries linked to the English and
the Spanish Wikipedia article of the same film -- which share a Wikidata id --
were never flagged. Auto-match knew about Wikidata, TMDb and MyAnimeList but
compared IMDb and FilmAffinity links as whole URLs, so `/es-es/title/tt…` and
`/title/tt…` were strangers. Scanner identity, catalogue membership and the
legacy `same_catalog_item` each had their own variant.

Everything now reduces an entry to a `WorkProfile` -- the ids each external
source gave it, its titles, year, kind and the few facts that can corroborate a
title -- and compares two profiles in one place.

The levels, and what may act on each:

* ``same``: a shared external id, the same article, or the same title and year
  with compatible kinds. The only level automatic matching may accept.
* ``possible``: worth a person's look, never acted on alone -- the same title
  where a year is missing but something independent agrees (direction, running
  time, the same file), or entries that share one id and disagree on another.
* ``conflict``: two ids from the same source that differ. Different works, or a
  wrong link; either way nothing joins them without a person.
* ``none``: nothing to say.

Description, review, cast, genres and tags never take part (invariant 3).
Direction and running time only ever *propose* a review: a title alone repeats
across remakes ("Frankenstein"), so a missing year needs a second, unrelated
witness before an entry is even shown as a candidate.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import unquote, urlparse

from movie_inbox.domain.catalog import (
    SOURCE_URL_FIELDS,
    canonical_url,
    external_source_name,
    external_urls,
    myanimelist_anime_id,
    normalize_path_text,
    themoviedb_media_reference,
    title_match_keys_for_item,
    title_similarity,
)
from movie_inbox.domain.curation import curation_item_reference, duplicate_decision_status
from movie_inbox.domain.metadata import (
    normalize_external_positive_id,
    normalize_local_files,
    normalize_locked_fields,
    normalize_metadata_sources,
    normalize_optional_positive_int,
)
from movie_inbox.domain.normalization import normalize_kind, normalize_search_text

IdentityLevel = Literal["same", "possible", "conflict", "none"]

# The order evidence is reported in, strongest first. TMDb leads because its id
# carries the media type, so it can also tell a film from a series.
STRONG_SOURCES = ("tmdb", "wikidata", "imdb", "mal", "filmaffinity")

SOURCE_LABELS = {
    "tmdb": "TMDb",
    "wikidata": "Wikidata",
    "imdb": "IMDb",
    "mal": "MyAnimeList",
    "filmaffinity": "FilmAffinity",
}

LANGUAGE_NAMES = {
    "en": "inglés",
    "es": "español",
    "fr": "francés",
    "it": "italiano",
    "de": "alemán",
    "pt": "portugués",
    "ja": "japonés",
    "ca": "catalán",
}

# A running time this close is the same cut measured by two sources, not two
# different films; any further apart and it stops corroborating anything.
DURATION_TOLERANCE_MINUTES = 3

_WIKIDATA_ID = re.compile(r"^Q[1-9]\d*$")
_IMDB_ID = re.compile(r"\btt\d{7,9}\b", flags=re.IGNORECASE)
_FILMAFFINITY_ID = re.compile(r"film(\d+)\.html", flags=re.IGNORECASE)
_NUMERIC_TITLE = re.compile(r"(?:19|20)\d{2}")


@dataclass(frozen=True)
class WikipediaArticle:
    language: str
    title: str

    @property
    def key(self) -> str:
        return f"{self.language}:{self.title.casefold()}"


@dataclass(frozen=True)
class WorkProfile:
    """What identity can be read from one catalogue entry, worked out once."""

    ids: Mapping[str, str]
    tmdb_media_type: str
    articles: tuple[WikipediaArticle, ...]
    urls: frozenset[str]
    titles: frozenset[str]
    year: str
    kind: str
    directors: frozenset[str]
    duration_minutes: int | None
    file_signatures: frozenset[str]

    @property
    def keys(self) -> frozenset[str]:
        """Strong keys: any two entries sharing one are candidates to compare."""

        keys = {f"{source}:{value}" for source, value in self.ids.items()}
        keys.update(f"wikipedia:{article.key}" for article in self.articles)
        keys.update(f"url:{url}" for url in self.urls)
        return frozenset(keys)


@dataclass(frozen=True)
class IdentityVerdict:
    level: IdentityLevel
    reason: str
    evidence: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_same(self) -> bool:
        return self.level == "same"

    @property
    def needs_review(self) -> bool:
        return self.level in {"same", "possible"}


def explicit_kind(item: Mapping[str, Any]) -> str:
    raw = str(item.get("kind") or "").strip()
    return normalize_kind(raw) if raw else ""


def tmdb_media_type(item: Mapping[str, Any]) -> str:
    for field_name in ("tmdb_url", "url"):
        reference = themoviedb_media_reference(str(item.get(field_name) or ""))
        if reference is not None:
            return reference[0]
    kind = explicit_kind(item)
    if kind == "serie":
        return "tv"
    if kind in {"pelicula", "documental"}:
        return "movie"
    return ""


def external_ids(item: Mapping[str, Any]) -> dict[str, str]:
    """The id each external source gave this entry, read from fields or links."""

    ids: dict[str, str] = {}
    tmdb_id = normalize_external_positive_id(item.get("tmdb_id"))
    if not tmdb_id:
        for field_name in ("tmdb_url", "url"):
            reference = themoviedb_media_reference(str(item.get(field_name) or ""))
            if reference is not None:
                tmdb_id = reference[1]
                break
    if tmdb_id:
        ids["tmdb"] = tmdb_id

    wikidata = str(item.get("wikidata_id") or "").strip().upper()
    if _WIKIDATA_ID.match(wikidata):
        ids["wikidata"] = wikidata

    imdb = _id_from_links(item, "imdb", _IMDB_ID)
    if imdb:
        ids["imdb"] = imdb.lower()

    mal_id = normalize_external_positive_id(item.get("mal_id"))
    if not mal_id:
        for field_name in ("myanimelist_url", "url"):
            mal_id = myanimelist_anime_id(str(item.get(field_name) or ""))
            if mal_id:
                break
    if mal_id:
        ids["mal"] = mal_id

    filmaffinity = _id_from_links(item, "filmaffinity", _FILMAFFINITY_ID, group=1)
    if filmaffinity:
        ids["filmaffinity"] = normalize_external_positive_id(filmaffinity)
    return {source: value for source, value in ids.items() if value}


def wikipedia_articles(item: Mapping[str, Any]) -> tuple[WikipediaArticle, ...]:
    articles: dict[str, WikipediaArticle] = {}
    for field_name in ("wikipedia_url", "url"):
        article = wikipedia_article(str(item.get(field_name) or ""))
        if article is not None:
            articles.setdefault(article.key, article)
    return tuple(articles.values())


def wikipedia_article(url: str) -> WikipediaArticle | None:
    """The language and title of a Wikipedia link, however it was written.

    Desktop and mobile hosts, percent-encoding and underscores all name the same
    article, so they all reduce to the same pair.
    """

    canonical = canonical_url(url)
    if not canonical or external_source_name(canonical) != "wikipedia":
        return None
    parsed = urlparse(canonical)
    marker = "/wiki/"
    if marker not in parsed.path:
        return None
    title = unquote(parsed.path.split(marker, 1)[1]).replace("_", " ").strip()
    host_parts = (parsed.hostname or "").split(".")
    language = host_parts[0] if len(host_parts) > 2 else ""
    if not title or not language or language == "www":
        return None
    return WikipediaArticle(language.casefold(), title)


def work_profile(item: Mapping[str, Any]) -> WorkProfile:
    return WorkProfile(
        ids=external_ids(item),
        tmdb_media_type=tmdb_media_type(item),
        articles=wikipedia_articles(item),
        urls=frozenset(external_urls(item)),
        titles=frozenset(title_match_keys_for_item(item)),
        year=str(item.get("year") or "").strip(),
        kind=explicit_kind(item),
        directors=frozenset(
            normalized
            for name in _string_list(item.get("directors"))
            if (normalized := normalize_search_text(name))
        ),
        duration_minutes=normalize_optional_positive_int(item.get("duration_minutes")),
        file_signatures=_file_signatures(item),
    )


def compare_works(left: Mapping[str, Any], right: Mapping[str, Any]) -> IdentityVerdict:
    return compare_profiles(work_profile(left), work_profile(right))


def compare_profiles(left: WorkProfile, right: WorkProfile) -> IdentityVerdict:
    conflicts = _id_conflicts(left, right)
    shared = _shared_identity(left, right)
    if conflicts:
        conflict_evidence = tuple(text for _, text, _ in conflicts)
        conflict_details = {
            key: value for _, _, details in conflicts for key, value in details.items()
        }
        if shared is not None:
            # One id says same work, another says different: a wrong link on
            # one side. A person decides; nothing acts on it automatically.
            return IdentityVerdict(
                "possible",
                "conflicting_external_ids",
                (*shared.evidence, *conflict_evidence),
                {**shared.details, **conflict_details, "conflict_reason": conflicts[0][0]},
            )
        return IdentityVerdict("conflict", conflicts[0][0], conflict_evidence, conflict_details)
    if shared is not None:
        return shared
    return _title_verdict(left, right)


def kinds_compatible(left: str, right: str) -> bool:
    return not (left and right) or left == right


def anime_release_taxonomy_mismatch(left: str, right: str) -> bool:
    return {left, right} in ({"anime", "pelicula"}, {"anime", "serie"})


def _id_conflicts(left: WorkProfile, right: WorkProfile) -> list[tuple[str, str, dict[str, Any]]]:
    conflicts: list[tuple[str, str, dict[str, Any]]] = []
    for source in STRONG_SOURCES:
        left_id = left.ids.get(source, "")
        right_id = right.ids.get(source, "")
        if not left_id or not right_id:
            continue
        label = SOURCE_LABELS[source]
        if left_id != right_id:
            conflicts.append(
                (
                    f"{source}_id_conflict",
                    f"Tienen ids distintos de {label} ({left_id} y {right_id}).",
                    {f"existing_{source}_id": left_id, f"incoming_{source}_id": right_id},
                )
            )
        elif (
            source == "tmdb"
            and left.tmdb_media_type
            and right.tmdb_media_type
            and left.tmdb_media_type != right.tmdb_media_type
        ):
            conflicts.append(
                (
                    "tmdb_media_type_conflict",
                    f"El mismo id de TMDb ({left_id}) figura como "
                    f"{_media_label(left.tmdb_media_type)} y como "
                    f"{_media_label(right.tmdb_media_type)}.",
                    {
                        "tmdb_id": left_id,
                        "existing_media_type": left.tmdb_media_type,
                        "incoming_media_type": right.tmdb_media_type,
                    },
                )
            )
    return conflicts


def _shared_identity(left: WorkProfile, right: WorkProfile) -> IdentityVerdict | None:
    for source in STRONG_SOURCES:
        value = left.ids.get(source, "")
        if not value or value != right.ids.get(source, ""):
            continue
        details: dict[str, Any] = {f"{source}_id": value}
        if source == "tmdb":
            details["media_type"] = left.tmdb_media_type or right.tmdb_media_type
        return IdentityVerdict(
            "same",
            f"shared_{source}_id",
            (_shared_id_sentence(source, value, left, right),),
            details,
        )
    shared_articles = {article.key for article in left.articles} & {
        article.key for article in right.articles
    }
    if shared_articles:
        return IdentityVerdict(
            "same",
            "shared_wikipedia_article",
            ("Apuntan al mismo artículo de Wikipedia.",),
            {"wikipedia_articles": sorted(shared_articles)},
        )
    shared_urls = sorted(left.urls & right.urls)
    if shared_urls:
        return IdentityVerdict(
            "same",
            "shared_external_url",
            ("Comparten el mismo enlace externo.",),
            {"urls": shared_urls},
        )
    return None


def _shared_id_sentence(source: str, value: str, left: WorkProfile, right: WorkProfile) -> str:
    if source == "wikidata":
        left_languages = {article.language for article in left.articles}
        right_languages = {article.language for article in right.articles}
        if left_languages and right_languages and not left_languages & right_languages:
            first = _language_name(sorted(left_languages)[0])
            second = _language_name(sorted(right_languages)[0])
            return (
                f"Los artículos de Wikipedia en {first} y en {second} son la misma "
                f"entrada de Wikidata ({value})."
            )
        return f"Comparten el id de Wikidata ({value})."
    if source == "filmaffinity":
        return f"Comparten la ficha de FilmAffinity ({value})."
    return f"Comparten el id de {SOURCE_LABELS[source]} ({value})."


def _title_verdict(left: WorkProfile, right: WorkProfile) -> IdentityVerdict:
    shared_titles = sorted(left.titles & right.titles)
    details: dict[str, Any] = {
        "shared_titles": shared_titles,
        "existing_year": left.year,
        "incoming_year": right.year,
        "existing_kind": left.kind,
        "incoming_kind": right.kind,
    }
    if not shared_titles:
        return IdentityVerdict("none", "insufficient_evidence", (), details)
    compatible = kinds_compatible(left.kind, right.kind)
    if left.year and right.year:
        if left.year != right.year:
            return IdentityVerdict("none", "exact_title_year_mismatch", (), details)
        if compatible:
            return IdentityVerdict(
                "same",
                "exact_title_year",
                (f"Mismo título y mismo año ({left.year}).",),
                details,
            )
        if anime_release_taxonomy_mismatch(left.kind, right.kind):
            details["taxonomy_note"] = "anime_vs_release_format"
            return IdentityVerdict(
                "possible",
                "exact_title_year_anime_kind_review",
                (
                    f"Mismo título y mismo año ({left.year}); una figura como anime y "
                    "la otra como película o serie.",
                ),
                details,
            )
        return IdentityVerdict("none", "exact_title_kind_mismatch", (), details)
    corroboration = _corroboration(left, right) if compatible else []
    if not corroboration:
        return IdentityVerdict("none", "exact_title_missing_year", (), details)
    missing = "a las dos les falta" if not left.year and not right.year else "a una le falta"
    details["corroboration"] = [code for code, _ in corroboration]
    return IdentityVerdict(
        "possible",
        "exact_title_missing_year_corroborated",
        (f"Mismo título; {missing} el año.", *(text for _, text in corroboration)),
        details,
    )


def _corroboration(left: WorkProfile, right: WorkProfile) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if left.file_signatures & right.file_signatures:
        found.append(("same_local_file", "Las dos apuntan al mismo archivo local."))
    shared_directors = left.directors & right.directors
    if shared_directors:
        found.append(("same_director", "Coinciden en la dirección."))
    if (
        left.duration_minutes
        and right.duration_minutes
        and abs(left.duration_minutes - right.duration_minutes) <= DURATION_TOLERANCE_MINUTES
    ):
        found.append(
            (
                "similar_duration",
                f"Duran casi lo mismo ({left.duration_minutes} y "
                f"{right.duration_minutes} minutos).",
            )
        )
    return found


def _id_from_links(
    item: Mapping[str, Any], source: str, pattern: re.Pattern[str], group: int = 0
) -> str:
    for field_name in (SOURCE_URL_FIELDS[source], "url"):
        url = canonical_url(str(item.get(field_name) or ""))
        if not url or external_source_name(url) != source:
            continue
        match = pattern.search(urlparse(url).path)
        if match:
            return match.group(group)
    return ""


def _file_signatures(item: Mapping[str, Any]) -> frozenset[str]:
    signatures: set[str] = set()
    for row in normalize_local_files(item.get("local_files")):
        fingerprint = str(row.get("fingerprint") or "").strip()
        if fingerprint:
            signatures.add(f"fingerprint:{fingerprint}")
        path = normalize_path_text(str(row.get("path") or ""))
        if path:
            signatures.add(f"path:{path}")
    return frozenset(signatures)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Iterable):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _media_label(media_type: str) -> str:
    return {"movie": "película", "tv": "serie"}.get(media_type, media_type)


def _language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def identity_resolution_target(item: Mapping[str, Any]) -> WikipediaArticle | None:
    """The Wikipedia article whose Wikidata id this entry still lacks, if any.

    [X12 B]: entries saved before every Wikipedia result carried its Wikidata id
    only have the article link. That id is what joins the English and the
    Spanish article of one film, so it is worth one batched lookup to fill in.
    """

    if str(item.get("wikidata_id") or "").strip():
        return None
    if "wikidata_id" in normalize_locked_fields(item.get("locked_fields")):
        return None
    articles = wikipedia_articles(item)
    return articles[0] if articles else None


def apply_resolved_identity(
    item: MutableMapping[str, Any], wikidata_id: str, year: str, now: str
) -> list[str]:
    """Fill the Wikidata id, and the year when missing, without overriding anyone.

    Only empty fields are written and locked fields never are (invariant 5).
    Each written field says it came from Wikidata. Returns the fields written.
    """

    entity = str(wikidata_id or "").strip().upper()
    if not _WIKIDATA_ID.match(entity):
        return []
    locked = set(normalize_locked_fields(item.get("locked_fields")))
    source = {
        "source": "wikidata",
        "url": f"https://www.wikidata.org/wiki/{entity}",
        "updated_at": now,
        "inferred": False,
    }
    written: list[str] = []
    if not str(item.get("wikidata_id") or "").strip() and "wikidata_id" not in locked:
        item["wikidata_id"] = entity
        written.append("wikidata_id")
    release_year = str(year or "").strip()
    if (
        release_year
        and _NUMERIC_TITLE.fullmatch(release_year)
        and not str(item.get("year") or "").strip()
        and "year" not in locked
    ):
        item["year"] = release_year
        written.append("year")
    if written:
        sources = dict(normalize_metadata_sources(item.get("metadata_sources")))
        for field_name in written:
            sources[field_name] = dict(source)
        item["metadata_sources"] = sources
    return written


def duplicate_verdict(left: WorkProfile, right: WorkProfile) -> IdentityVerdict:
    """`compare_profiles`, plus the one legacy pattern only curation looks for.

    Old scanner imports could mistake a numeric title ("1917") for its release
    year. Two entries sharing such a title, where one carries it as its year and
    the other a different year, are surfaced for review; ordinary remakes with
    the same title and different years stay apart.
    """

    verdict = compare_profiles(left, right)
    if verdict.level != "none" or left.year == right.year:
        return verdict
    for title in left.titles & right.titles:
        if _NUMERIC_TITLE.fullmatch(title) and title in {left.year, right.year}:
            return IdentityVerdict(
                "possible",
                "legacy_numeric_title",
                ("Una ficha parece usar el título numérico como año heredado.",),
                {"shared_titles": [title]},
            )
    return verdict


_DUPLICATE_FIELDS = (
    "_curation_ref",
    "_duplicate_count",
    "_duplicate_ids",
    "_duplicate_refs",
    "_duplicate_deferred_count",
    "_duplicate_deferred_ids",
    "_duplicate_deferred_refs",
    "_duplicate_reason",
    "_duplicate_level",
)


def annotate_duplicate_items(items: Sequence[MutableMapping[str, Any]]) -> None:
    """Mark each entry with the others that may be the same work.

    Entries are only ever compared when something makes it worth it: a shared
    strong key (an id, an article, a link), the same title and year, or the
    same title where a year is missing. Within those buckets every pair goes
    through `duplicate_verdict`, and the groups are the connected components of
    the pairs that need review -- so an English and a Spanish Wikipedia entry
    with the same Wikidata id meet through `wikidata:Q…` even though their URLs
    and titles differ.
    """

    if not items:
        return
    profiles: list[WorkProfile] = []
    buckets: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        for field_name in _DUPLICATE_FIELDS:
            item.pop(field_name, None)
        item["_curation_ref"] = curation_item_reference(item)
        profile = work_profile(item)
        profiles.append(profile)
        for key in profile.keys:
            buckets.setdefault(key, []).append(index)
        for title in profile.titles:
            buckets.setdefault(f"title:{title}", []).append(index)

    edges: dict[tuple[int, int], IdentityVerdict] = {}
    checked: set[tuple[int, int]] = set()
    for key, indexes in buckets.items():
        if len(indexes) < 2:
            continue
        by_title = key.startswith("title:")
        for position, left in enumerate(indexes):
            for right in indexes[position + 1 :]:
                pair = (left, right) if left < right else (right, left)
                if pair in checked or left == right:
                    continue
                left_profile, right_profile = profiles[pair[0]], profiles[pair[1]]
                if (
                    by_title
                    and left_profile.year
                    and right_profile.year
                    and left_profile.year != right_profile.year
                    and not _NUMERIC_TITLE.fullmatch(key.removeprefix("title:"))
                ):
                    # Remakes: same title, two different years. Nothing to see.
                    continue
                checked.add(pair)
                verdict = duplicate_verdict(left_profile, right_profile)
                if verdict.needs_review:
                    edges[pair] = verdict

    parents = list(range(len(items)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for left, right in edges:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parents[right_root] = left_root

    groups: dict[int, list[int]] = {}
    for index in range(len(items)):
        groups.setdefault(root(index), []).append(index)
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        level = (
            "same"
            if any(
                verdict.level == "same"
                for (left, right), verdict in edges.items()
                if left in indexes and right in indexes
            )
            else "possible"
        )
        for index in indexes:
            item = items[index]
            pending = [
                items[other]
                for other in indexes
                if other != index and duplicate_decision_status(item, items[other]) == "pending"
            ]
            deferred = [
                items[other]
                for other in indexes
                if other != index and duplicate_decision_status(item, items[other]) == "deferred"
            ]
            if pending:
                item["_duplicate_count"] = len(pending)
                item["_duplicate_ids"] = [str(other.get("id") or "") for other in pending]
                item["_duplicate_refs"] = [curation_item_reference(other) for other in pending]
            if deferred:
                item["_duplicate_deferred_count"] = len(deferred)
                item["_duplicate_deferred_ids"] = [str(other.get("id") or "") for other in deferred]
                item["_duplicate_deferred_refs"] = [
                    curation_item_reference(other) for other in deferred
                ]
            if pending or deferred:
                item["_duplicate_level"] = level
                item["_duplicate_reason"] = (
                    "misma obra" if level == "same" else "posible misma obra"
                )


_ComparisonRow = tuple[Mapping[str, Any], WorkProfile]


class CatalogComparisonIndex:
    """A catalogue with its identity profiles worked out once.

    `possible_duplicate_candidates` compares one item against every catalogue
    item. Profiling the catalogue once is cheap; doing it once per item in a list
    was the entire cost: measured on a 5000-item catalogue, normalising it takes
    0.124s, and opening a 200-item collection did exactly that 200 times --
    24.9s of the 28s the page spent, against 2.3s of actual comparing.

    Pass one of these wherever a list is compared against the same catalogue
    more than once. Everywhere else a plain sequence still works and is prepared
    internally, so no caller has to care. `add()` exists because copying a
    collection into the catalogue grows the catalogue as it goes.
    """

    __slots__ = ("_items", "_rows")

    def __init__(self, items: Iterable[Mapping[str, Any]] = ()) -> None:
        self._items: list[Mapping[str, Any]] = list(items)
        self._rows: list[_ComparisonRow] = []

    def add(self, item: Mapping[str, Any]) -> None:
        self._items.append(item)

    def __iter__(self) -> Iterator[_ComparisonRow]:
        # Lazily, and cached: catalog_membership returns the moment it finds a
        # work it already knows, and a caller that only ever asks once must not
        # pay to prepare the whole catalogue for a hit at position 3.
        for position, item in enumerate(self._items):
            if position >= len(self._rows):
                self._rows.append((item, work_profile(item)))
            yield self._rows[position]

    def __len__(self) -> int:
        return len(self._items)


def _prepared(
    items: Sequence[Mapping[str, Any]] | CatalogComparisonIndex,
) -> CatalogComparisonIndex:
    return items if isinstance(items, CatalogComparisonIndex) else CatalogComparisonIndex(items)


SIMILAR_TITLE_THRESHOLD = 0.75


def possible_duplicate_candidates(
    items: Sequence[Mapping[str, Any]] | CatalogComparisonIndex,
    item: Mapping[str, Any],
    *,
    profile: WorkProfile | None = None,
) -> list[dict[str, Any]]:
    """Catalogue entries a person should look at before adding `item`.

    Title-led: the same or a similar title. An entry whose external ids
    contradict `item` stays in the list -- someone adding by hand is already
    looking, so asking is free -- and its evidence says what contradicts. It is
    only curation that leaves conflicts out, because nobody asked it anything.
    """

    item_profile = profile or work_profile(item)
    item_titles = item_profile.titles
    candidates: list[dict[str, Any]] = []
    for existing, existing_profile in _prepared(items):
        existing_titles = existing_profile.titles
        if not item_titles or not existing_titles:
            continue
        exact = bool(existing_titles & item_titles)
        similarity = max(
            (title_similarity(left, right) for left in existing_titles for right in item_titles),
            default=0.0,
        )
        if not exact and similarity < SIMILAR_TITLE_THRESHOLD:
            continue
        item_year, existing_year = item_profile.year, existing_profile.year
        year_mismatch = bool(item_year and existing_year and item_year != existing_year)
        if year_mismatch and not exact:
            continue
        verdict = compare_profiles(existing_profile, item_profile)
        if exact and year_mismatch:
            reason = "exact_title_year_mismatch"
        elif exact and (not item_year or not existing_year):
            reason = "exact_title_missing_year"
        elif exact:
            reason = "exact_title_year"
        else:
            reason = "similar_title_requires_review"
        candidates.append(
            {
                **{field_name: existing.get(field_name, "") for field_name in _CANDIDATE_FIELDS},
                "alternative_titles": existing.get("alternative_titles", []),
                "en_catalogo": existing.get("en_catalogo", False),
                "reason": reason,
                "score": round(similarity, 3),
                "evidence": list(verdict.evidence),
            }
        )
    return sorted(
        candidates,
        key=lambda candidate: (
            str(candidate.get("reason") or "") == "exact_title_year",
            float(candidate.get("score") or 0),
        ),
        reverse=True,
    )


_CANDIDATE_FIELDS = (
    "id",
    "title",
    "original_title",
    "spanish_title",
    "english_title",
    "year",
    "kind",
    "source",
    "url",
    "wikipedia_url",
    "imdb_url",
    "filmaffinity_url",
    "myanimelist_url",
    "tmdb_url",
    "tmdb_id",
    "wikidata_id",
    "mal_id",
)


def catalog_membership(
    item: Mapping[str, Any], items: Sequence[Mapping[str, Any]] | CatalogComparisonIndex
) -> dict[str, Any]:
    """Whether the catalogue already holds `item`, might, or does not.

    ``present`` takes the same id, or a ``same`` verdict reached through a
    shared strong key -- an external id, the same article, the same link. The
    same title and year is still only a candidate here: adding from a list is
    where a person is looking, so it costs nothing to ask.
    """

    prepared = _prepared(items)
    item_profile = work_profile(item)
    item_id = str(item.get("id") or "")
    item_keys = item_profile.keys
    for existing, existing_profile in prepared:
        existing_id = str(existing.get("id") or "")
        same_id = bool(item_id and item_id == existing_id)
        same_work = bool(
            item_keys & existing_profile.keys
            and compare_profiles(existing_profile, item_profile).level == "same"
        )
        if same_id or same_work:
            return {
                "state": "present",
                "item_id": existing_id,
                "candidate_count": 0,
                "candidates": [],
            }
    candidates = possible_duplicate_candidates(prepared, item, profile=item_profile)
    if candidates:
        return {
            "state": "review",
            "item_id": "",
            "candidate_count": len(candidates),
            "candidates": candidates,
        }
    return {"state": "missing", "item_id": "", "candidate_count": 0, "candidates": []}
