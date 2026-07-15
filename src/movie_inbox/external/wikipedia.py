"""Wikipedia search and metadata client."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote, unquote, urlparse

from movie_inbox.domain.catalog import external_source_name
from movie_inbox.domain.titles import clean_release_title, clean_title, clean_whitespace, infer_year
from movie_inbox.external.common import fetch_json, fetch_json_safe, interleave_batches, result_index
from movie_inbox.external.wikidata import (
    fetch_wikidata_article_url,
    fetch_wikidata_metadata,
    wikidata_result_score,
)


class WikipediaAdapter:
    name = "wikipedia"
    label = "Wikipedia"

    def search(self, query: str) -> list[dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="wikipedia-search") as executor:
            batches = list(executor.map(lambda language: self._search_language(query, language), ["en", "es"]))
        return interleave_batches(batches)

    def _search_language(self, query: str, language: str) -> list[dict[str, Any]]:
        url = (
            f"https://{language}.wikipedia.org/w/api.php"
            f"?action=query&generator=search&gsrsearch={quote(query + ' film')}&gsrlimit=5"
            "&prop=extracts%7Cpageimages%7Cpageprops&exintro=1&explaintext=1&pithumbsize=480"
            "&format=json&formatversion=2"
        )
        raw = fetch_json(url)
        query_data = raw.get("query") if isinstance(raw.get("query"), dict) else {}
        rows = query_data.get("pages") if isinstance(query_data, dict) else []
        if not isinstance(rows, list):
            return []
        rows.sort(key=result_index)
        results: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "")
            if not title:
                continue
            extract = str(row.get("extract") or "")
            thumbnail = row.get("thumbnail") if isinstance(row.get("thumbnail"), dict) else {}
            pageprops = row.get("pageprops") if isinstance(row.get("pageprops"), dict) else {}
            page_url = f"https://{language}.wikipedia.org/wiki/{quote(title.replace(' ', '_'), safe='')}"
            results.append(
                {
                    "source": self.name,
                    "title": title,
                    "original_title": "",
                    "spanish_title": title if language == "es" else "",
                    "english_title": title if language == "en" else "",
                    "alternative_titles": [],
                    "year": infer_year(extract),
                    "url": page_url,
                    "description": extract[:360],
                    "wikipedia_url": page_url,
                    "wikipedia_title": title,
                    "wikidata_id": str(pageprops.get("wikibase_item") or ""),
                    "genres": [],
                    "directors": [],
                    "writers": [],
                    "cast": [],
                    "page_image": str(thumbnail.get("source") or ""),
                    "wikipedia_extract": extract,
                }
            )
        return results


def fetch_wikipedia_metadata(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if external_source_name(url) != "wikipedia":
        return {}
    page_title = wikipedia_page_title(parsed.path)
    if not page_title:
        return {}

    language = host.split(".")[0] if "." in host else "en"
    summary_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(page_title, safe='')}"
    raw = fetch_json_safe(summary_url, timeout=5)
    if not raw:
        return fetch_wikipedia_metadata_action_api(language, page_title)

    title = clean_title(str(raw.get("title") or raw.get("displaytitle") or page_title))
    description = clean_whitespace(str(raw.get("description") or ""))
    extract = clean_whitespace(str(raw.get("extract") or ""))
    thumbnail = raw.get("thumbnail") if isinstance(raw.get("thumbnail"), dict) else {}
    image_url = str(thumbnail.get("source") or "") if isinstance(thumbnail, dict) else ""
    wikidata_id = str(raw.get("wikibase_item") or "")
    metadata: dict[str, Any] = {
        "url": f"https://{language}.wikipedia.org/wiki/{quote(page_title, safe='')}",
        "wikipedia_url": f"https://{language}.wikipedia.org/wiki/{quote(page_title, safe='')}",
        "title": title,
        "spanish_title": title if language == "es" else "",
        "english_title": title if language == "en" else "",
        "description": description,
        "wikipedia_title": title,
        "wikidata_id": wikidata_id,
        "page_image": image_url,
        "wikipedia_extract": extract,
        "og_type": raw.get("type", ""),
    }
    metadata.update(fetch_wikidata_metadata(wikidata_id))
    if not (metadata["wikidata_id"] or metadata["wikipedia_extract"] or metadata["description"]):
        return fetch_wikipedia_metadata_action_api(language, page_title) or metadata
    return metadata


def fetch_wikipedia_metadata_action_api(language: str, page_title: str) -> dict[str, Any]:
    api_url = (
        f"https://{language}.wikipedia.org/w/api.php?action=query&format=json&redirects=1"
        "&prop=extracts|pageimages|pageprops|info&exintro=1&explaintext=1"
        "&piprop=thumbnail&pithumbsize=500&inprop=url"
        f"&titles={quote(page_title.replace('_', ' '))}"
    )
    raw = fetch_json_safe(api_url, timeout=5)
    query = raw.get("query") if isinstance(raw.get("query"), dict) else {}
    pages = query.get("pages") if isinstance(query, dict) else {}
    if not isinstance(pages, dict):
        return {}
    page = next((value for value in pages.values() if isinstance(value, dict) and "missing" not in value), {})
    if not page:
        return {}

    title = clean_title(str(page.get("title") or page_title))
    description = clean_whitespace(str(page.get("description") or ""))
    extract = clean_whitespace(str(page.get("extract") or ""))
    thumbnail = page.get("thumbnail") if isinstance(page.get("thumbnail"), dict) else {}
    pageprops = page.get("pageprops") if isinstance(page.get("pageprops"), dict) else {}
    wikidata_id = str(pageprops.get("wikibase_item") or "")
    canonical_url = str(page.get("canonicalurl") or f"https://{language}.wikipedia.org/wiki/{quote(page_title, safe='')}")
    metadata: dict[str, Any] = {
        "url": canonical_url,
        "wikipedia_url": canonical_url,
        "title": title,
        "spanish_title": title if language == "es" else "",
        "english_title": title if language == "en" else "",
        "description": description,
        "wikipedia_title": title,
        "wikidata_id": wikidata_id,
        "page_image": str(thumbnail.get("source") or ""),
        "wikipedia_extract": extract,
        "og_type": "",
    }
    metadata.update(fetch_wikidata_metadata(wikidata_id))
    return metadata


def fetch_wikipedia_by_title(title: str, year: str = "") -> dict[str, Any]:
    query = clean_search_title(clean_release_title(title))
    if not query or looks_like_external_id(query):
        return {}
    for language in ["en", "es"]:
        for candidate in wikipedia_direct_candidates(query, year, language):
            metadata = fetch_wikipedia_metadata(
                f"https://{language}.wikipedia.org/wiki/{quote(candidate.replace(' ', '_'), safe='')}"
            )
            if wikipedia_match_score(query, year, candidate, "", metadata) >= 3:
                return metadata
        for search_query in wikipedia_search_queries(query, year, language):
            raw = fetch_wikipedia_search(search_query, language)
            query_data = raw.get("query") if isinstance(raw.get("query"), dict) else {}
            results = query_data.get("search") if isinstance(query_data, dict) else []
            if not isinstance(results, list):
                continue
            best: tuple[int, dict[str, Any]] = (0, {})
            for result in results[:3]:
                if not isinstance(result, dict):
                    continue
                page_title = str(result.get("title") or "")
                snippet = clean_whitespace(strip_html(str(result.get("snippet") or "")))
                metadata = fetch_wikipedia_metadata(
                    f"https://{language}.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'), safe='')}"
                )
                score = wikipedia_match_score(query, year, page_title, snippet, metadata)
                if score > best[0]:
                    best = (score, metadata)
            if best[0] >= 3:
                return best[1]
    return {}


def fetch_wikipedia_by_wikidata_title(title: str, year: str = "") -> dict[str, Any]:
    for language in ["en", "es"]:
        search_url = (
            "https://www.wikidata.org/w/api.php"
            f"?action=wbsearchentities&format=json&language={language}&limit=5&search={quote(title)}"
        )
        raw = fetch_json_safe(search_url, timeout=5)
        results = raw.get("search") if isinstance(raw.get("search"), list) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            entity_id = str(result.get("id") or "")
            label = str(result.get("label") or "")
            description = str(result.get("description") or "")
            if wikidata_result_score(title, year, label, description) < 3:
                continue
            article_url = fetch_wikidata_article_url(entity_id)
            if article_url:
                metadata = fetch_wikipedia_metadata(article_url)
                if metadata and wikipedia_match_score(title, year, label, description, metadata) >= 3:
                    return metadata
    return {}


def fetch_wikipedia_search(query: str, language: str) -> dict[str, Any]:
    return fetch_json_safe(
        f"https://{language}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={quote(query)}&format=json&srlimit=5",
        timeout=5,
    )


def likely_film_result(title: str, snippet: str, year: str) -> bool:
    lowered = title.casefold()
    snippet_key = snippet.casefold()
    if year and year in title:
        return True
    return any(marker in lowered for marker in ["film", "movie", "pelicula"]) or any(
        marker in snippet_key for marker in ["film", "movie", "pelicula", "directed by", "starring"]
    )


def wikipedia_search_queries(title: str, year: str, language: str) -> list[str]:
    film_word = "pelicula" if language == "es" else "film"
    queries = [f'"{title}" {film_word}', f'"{title}"']
    if year:
        queries.insert(0, f'"{title}" {year} {film_word}')
    return queries


def wikipedia_direct_candidates(title: str, year: str, language: str) -> list[str]:
    film_suffix = "pelicula" if language == "es" else "film"
    candidates = [title]
    if year:
        candidates.append(f"{title} ({year} film)")
    candidates.append(f"{title} ({film_suffix})")
    return list(dict.fromkeys(candidates))


def wikipedia_match_score(
    query_title: str,
    year: str,
    page_title: str,
    snippet: str,
    metadata: dict[str, Any],
) -> int:
    if not metadata:
        return 0
    score = 0
    query_key = normalize_match_text(query_title)
    page_key = normalize_match_text(page_title)
    wiki_key = normalize_match_text(str(metadata.get("wikipedia_title") or ""))
    description = normalize_match_text(str(metadata.get("description") or ""))
    extract = normalize_match_text(str(metadata.get("wikipedia_extract") or ""))
    snippet_key = normalize_match_text(snippet)
    if query_key and query_key in {page_key, wiki_key}:
        score += 4
    elif query_key and (query_key in page_key or query_key in wiki_key):
        score += 2
    if year and year in f"{page_title} {metadata.get('wikipedia_extract', '')}":
        score += 2
    if any(marker in description for marker in ["film", "movie", "pelicula"]):
        score += 2
    if any(marker in f"{extract} {snippet_key}" for marker in ["directed by", "starring", "film", "movie", "pelicula"]):
        score += 1
    return score


def normalize_match_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return clean_whitespace(value)


def clean_search_title(value: str) -> str:
    value = re.sub(
        r"\s*\((film|movie|pelicula|miniserie|tv series|serie de tv|video game|cortometraje)[^)]*\)?\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"^grupo:\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+filmaffinity$", "", value, flags=re.IGNORECASE)
    return clean_whitespace(value)


def looks_like_external_id(value: str) -> bool:
    return bool(re.fullmatch(r"(tt|nm)\d+", value.strip(), flags=re.IGNORECASE)) or bool(
        re.fullmatch(r"film\d+", value.strip(), flags=re.IGNORECASE)
    )


def wikipedia_page_title(path: str) -> str:
    marker = "/wiki/"
    if marker not in path:
        return ""
    return unquote(path.split(marker, 1)[1].split("#", 1)[0]).replace(" ", "_")


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)
