"""Opt-in TMDb search and selected-result metadata client."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode, urlparse

from movie_inbox.domain.catalog import canonical_url, merge_lists, normalize_tags
from movie_inbox.domain.releases import normalize_release_dates
from movie_inbox.domain.search import parse_search_query
from movie_inbox.external.common import clean_text, fetch_json, object_dict, object_list

TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_WEB_BASE_URL = "https://www.themoviedb.org"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
TMDB_DEFAULT_LANGUAGE = "es-AR"
_TMDB_REFERENCE_PATH = re.compile(r"^/(movie|tv)/(\d+)(?:[-/]|$)", flags=re.IGNORECASE)
_MOVIE_APPEND = "alternative_titles,translations,credits,external_ids,release_dates,images"
_TV_APPEND = "alternative_titles,translations,credits,external_ids,images"
_RELEASE_TYPES = {
    1: "premiere",
    2: "theatrical_limited",
    3: "theatrical",
    4: "digital",
    5: "physical",
    6: "tv",
}


class TmdbAdapter:
    name = "tmdb"
    label = "TMDb"

    def __init__(self, read_access_token: str, *, language: str = TMDB_DEFAULT_LANGUAGE) -> None:
        token = str(read_access_token or "").strip()
        if not token:
            raise ValueError("TMDb requires an API Read Access Token")
        self._read_access_token = token
        self.language = language

    def search(self, query: str) -> list[dict[str, Any]]:
        intent = parse_search_query(query)
        if intent.director_query:
            return []
        if intent.source and intent.source != self.name:
            return []
        if intent.source == self.name and intent.canonical_url:
            metadata = self.metadata(intent.canonical_url)
            return [metadata] if metadata else []
        if intent.external_id.startswith("tt"):
            raw = self._request(
                f"/find/{intent.external_id}",
                {"external_source": "imdb_id", "language": self.language},
            )
            rows = [
                *(("movie", row) for row in object_list(raw.get("movie_results"))),
                *(("tv", row) for row in object_list(raw.get("tv_results"))),
            ]
        else:
            # An ambiguous year-shaped token can be part of the title ("Verano 1993").
            # Keep that reading for TMDb and let the shared scorer use the separate
            # release year, instead of sending a destructively shortened title.
            lookup = intent.alternate_title or intent.title or query.strip()
            if not lookup:
                return []
            raw = self._request(
                "/search/multi",
                {
                    "query": lookup,
                    "include_adult": "false",
                    "language": self.language,
                    "page": 1,
                },
            )
            rows = [
                (str(row.get("media_type") or ""), row)
                for row in object_list(raw.get("results"))
                if isinstance(row, Mapping)
            ]
        results: list[dict[str, Any]] = []
        for media_type, row in rows:
            parsed = tmdb_search_result(row, media_type, language=self.language)
            if parsed is not None:
                if intent.external_id.startswith("tt"):
                    parsed["imdb_url"] = f"https://www.imdb.com/title/{intent.external_id.lower()}/"
                results.append(parsed)
        return results

    def metadata(self, url: str) -> dict[str, Any]:
        reference = tmdb_reference(url)
        if reference is None:
            return {}
        media_type, tmdb_id = reference
        append = _MOVIE_APPEND if media_type == "movie" else _TV_APPEND
        raw = self._request(
            f"/{media_type}/{tmdb_id}",
            {
                "language": self.language,
                "append_to_response": append,
                "include_image_language": "es,en,null",
            },
        )
        return tmdb_detail_result(raw, media_type, language=self.language) or {}

    def _request(self, path: str, parameters: Mapping[str, object]) -> dict[str, Any]:
        url = f"{TMDB_API_BASE_URL}{path}?{urlencode(parameters)}"
        return fetch_json(
            url,
            headers={
                "Authorization": f"Bearer {self._read_access_token}",
                "Accept": "application/json",
            },
        )


def fetch_tmdb_metadata(
    url: str,
    read_access_token: str,
    *,
    language: str = TMDB_DEFAULT_LANGUAGE,
) -> dict[str, Any]:
    if not read_access_token or tmdb_reference(url) is None:
        return {}
    return TmdbAdapter(read_access_token, language=language).metadata(url)


def tmdb_reference(value: str) -> tuple[str, str] | None:
    canonical = canonical_url(value)
    if not canonical:
        return None
    parsed = urlparse(canonical)
    hostname = (parsed.hostname or "").lower().rstrip(".").removeprefix("www.")
    if hostname != "themoviedb.org":
        return None
    match = _TMDB_REFERENCE_PATH.match(parsed.path)
    if not match:
        return None
    return match.group(1).lower(), str(int(match.group(2)))


def tmdb_search_result(
    value: Any,
    media_type: str,
    *,
    language: str = TMDB_DEFAULT_LANGUAGE,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or media_type not in {"movie", "tv"}:
        return None
    row = dict(value)
    tmdb_id = _positive_id(row.get("id"))
    title_field = "title" if media_type == "movie" else "name"
    original_field = "original_title" if media_type == "movie" else "original_name"
    date_field = "release_date" if media_type == "movie" else "first_air_date"
    title = clean_text(str(row.get(title_field) or ""))
    if not tmdb_id or not title:
        return None
    original_title = clean_text(str(row.get(original_field) or ""))
    original_language = clean_text(str(row.get("original_language") or ""))
    release_date = str(row.get(date_field) or "").split("T", 1)[0]
    public_url = f"{TMDB_WEB_BASE_URL}/{media_type}/{tmdb_id}"
    result: dict[str, Any] = {
        "source": "tmdb",
        "title": title,
        "original_title": original_title,
        "spanish_title": title if language.casefold().startswith("es") else "",
        "english_title": original_title if original_language.casefold() == "en" else "",
        "alternative_titles": [],
        "kind": "pelicula" if media_type == "movie" else "serie",
        "year": release_date[:4] if re.match(r"^\d{4}", release_date) else "",
        "url": public_url,
        "tmdb_id": tmdb_id,
        "description": clean_text(str(row.get("overview") or "")),
        "page_image": _image_url(row.get("poster_path"), "w500"),
        "backdrop_image": _image_url(row.get("backdrop_path"), "w780"),
    }
    if release_date:
        result["release_dates"] = normalize_release_dates(
            [
                {
                    "date": release_date,
                    "source": "tmdb",
                    "source_url": public_url,
                    "is_primary": True,
                }
            ]
        )
    return result


def tmdb_detail_result(
    value: Any,
    media_type: str,
    *,
    language: str = TMDB_DEFAULT_LANGUAGE,
) -> dict[str, Any] | None:
    result = tmdb_search_result(value, media_type, language=language)
    if result is None or not isinstance(value, Mapping):
        return None
    row = dict(value)
    translations = _translations(row.get("translations"), media_type)
    spanish_title, spanish_overview = _translation(translations, "es")
    english_title, english_overview = _translation(translations, "en")
    if spanish_title:
        result["spanish_title"] = spanish_title
    if english_title:
        result["english_title"] = english_title
    if not result["description"]:
        result["description"] = spanish_overview or english_overview
    aliases = _alternative_titles(row.get("alternative_titles"))
    result["alternative_titles"] = _aliases(
        result,
        [*aliases, *(title for title, _overview in translations.values())],
    )

    result["genres"] = _names(row.get("genres"))
    result["countries"] = _names(row.get("production_countries"))
    result["original_languages"] = _original_languages(row)
    credits = object_dict(row.get("credits"))
    crew = [entry for entry in object_list(credits.get("crew")) if isinstance(entry, Mapping)]
    result["directors"] = _crew_names(crew, jobs={"Director"})
    result["writers"] = _crew_names(crew, departments={"Writing"})
    result["producers"] = _crew_names(crew, jobs={"Producer"})
    result["composers"] = _crew_names(crew, jobs={"Original Music Composer"})
    result["cast"] = _names(object_list(credits.get("cast"))[:20])
    if media_type == "movie":
        duration = _positive_id(row.get("runtime"))
        if duration:
            result["duration_minutes"] = int(duration)
    external_ids = object_dict(row.get("external_ids"))
    imdb_id = clean_text(str(external_ids.get("imdb_id") or ""))
    if re.fullmatch(r"tt\d{7,9}", imdb_id, flags=re.IGNORECASE):
        result["imdb_url"] = f"https://www.imdb.com/title/{imdb_id.lower()}/"
    wikidata_id = clean_text(str(external_ids.get("wikidata_id") or ""))
    if re.fullmatch(r"Q\d+", wikidata_id, flags=re.IGNORECASE):
        result["wikidata_id"] = wikidata_id.upper()
    result["release_dates"] = _release_dates(row, media_type, result)
    return result


def _translations(value: Any, media_type: str) -> dict[str, tuple[str, str]]:
    translations: dict[str, tuple[str, str]] = {}
    title_field = "title" if media_type == "movie" else "name"
    for entry in object_list(object_dict(value).get("translations")):
        if not isinstance(entry, Mapping):
            continue
        language = clean_text(str(entry.get("iso_639_1") or "")).casefold()
        data = object_dict(entry.get("data"))
        title = clean_text(str(data.get(title_field) or ""))
        overview = clean_text(str(data.get("overview") or ""))
        if language and (title or overview) and language not in translations:
            translations[language] = (title, overview)
    return translations


def _translation(translations: Mapping[str, tuple[str, str]], language: str) -> tuple[str, str]:
    return translations.get(language, ("", ""))


def _alternative_titles(value: Any) -> list[str]:
    container = object_dict(value)
    rows = object_list(container.get("titles") or container.get("results"))
    return [clean_text(str(row.get("title") or "")) for row in rows if isinstance(row, Mapping)]


def _aliases(result: Mapping[str, Any], candidates: list[str]) -> list[str]:
    primary = {
        clean_text(str(result.get(field) or "")).casefold()
        for field in ("title", "original_title", "spanish_title", "english_title")
        if clean_text(str(result.get(field) or ""))
    }
    return [
        alias
        for alias in merge_lists([], [clean_text(value) for value in candidates])
        if alias and alias.casefold() not in primary
    ][:40]


def _names(value: Any) -> list[str]:
    rows = value if isinstance(value, list) else object_list(value)
    return normalize_tags(
        [clean_text(str(row.get("name") or "")) for row in rows if isinstance(row, Mapping)]
    )


def _crew_names(
    crew: list[Mapping[str, Any]],
    *,
    jobs: set[str] | None = None,
    departments: set[str] | None = None,
) -> list[str]:
    return normalize_tags(
        [
            clean_text(str(row.get("name") or ""))
            for row in crew
            if (not jobs or str(row.get("job") or "") in jobs)
            and (not departments or str(row.get("department") or "") in departments)
        ]
    )


def _original_languages(row: Mapping[str, Any]) -> list[str]:
    original = clean_text(str(row.get("original_language") or "")).casefold()
    for language in object_list(row.get("spoken_languages")):
        if not isinstance(language, Mapping):
            continue
        code = clean_text(str(language.get("iso_639_1") or "")).casefold()
        if code == original:
            name = clean_text(str(language.get("name") or language.get("english_name") or code))
            return [name] if name else []
    return [original] if original else []


def _release_dates(
    row: Mapping[str, Any], media_type: str, result: Mapping[str, Any]
) -> list[dict[str, Any]]:
    public_url = str(result.get("url") or "")
    rows = list(result.get("release_dates") or [])
    if media_type != "movie":
        return normalize_release_dates(rows)
    for country in object_list(object_dict(row.get("release_dates")).get("results")):
        if not isinstance(country, Mapping):
            continue
        country_code = clean_text(str(country.get("iso_3166_1") or ""))
        for release in object_list(country.get("release_dates")):
            if not isinstance(release, Mapping):
                continue
            try:
                release_type = _RELEASE_TYPES.get(int(release.get("type") or 0), "")
            except (TypeError, ValueError):
                release_type = ""
            rows.append(
                {
                    "date": str(release.get("release_date") or "").split("T", 1)[0],
                    "country": country_code,
                    "release_type": release_type,
                    "source": "tmdb",
                    "source_url": public_url,
                    "is_primary": False,
                }
            )
    return normalize_release_dates(rows)


def _image_url(value: Any, size: str) -> str:
    path = str(value or "").strip()
    if not re.fullmatch(r"/[A-Za-z0-9._/-]+", path):
        return ""
    return f"{TMDB_IMAGE_BASE_URL}/{size}{path}"


def _positive_id(value: Any) -> str:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return ""
    return str(normalized) if normalized > 0 else ""


__all__ = [
    "TMDB_API_BASE_URL",
    "TMDB_DEFAULT_LANGUAGE",
    "TMDB_IMAGE_BASE_URL",
    "TMDB_WEB_BASE_URL",
    "TmdbAdapter",
    "fetch_tmdb_metadata",
    "tmdb_detail_result",
    "tmdb_reference",
    "tmdb_search_result",
]
