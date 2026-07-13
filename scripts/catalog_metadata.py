#!/usr/bin/env python3
"""External metadata clients for Wikipedia, Wikidata, IMDb and HTML pages."""

from __future__ import annotations

import html
import json
import re
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from catalog_domain import external_source_name, merge_lists, source_url_field
from catalog_titles import clean_title, clean_whitespace


class MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            name = (attr.get("property") or attr.get("name") or "").lower()
            content = attr.get("content", "").strip()
            if name and content:
                self.meta[name] = html.unescape(content)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def page_title(self) -> str:
        return clean_title(" ".join(self.title_parts))

def fetch_metadata(url: str) -> dict[str, str]:
    wikipedia_metadata = fetch_wikipedia_metadata(url)
    if wikipedia_metadata:
        return wikipedia_metadata

    imdb_id = imdb_id_from_text(url)
    if imdb_id:
        wikidata_metadata = fetch_wikipedia_by_imdb_id(imdb_id)
        if wikidata_metadata:
            wikidata_metadata["imdb_url"] = f"https://www.imdb.com/title/{imdb_id}/"
            return wikidata_metadata

    request = Request(
        url,
        headers={
            "User-Agent": "MovieInboxImporter/0.1 (+local personal catalog)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            if "html" not in content_type:
                return {}
            raw = response.read(800_000).decode(charset, errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return {}

    parser = MetadataParser()
    parser.feed(raw)
    title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.page_title
        or guess_title_from_url(url)
    )
    description = parser.meta.get("og:description") or parser.meta.get("description") or ""

    link_field = source_url_field(source_name(urlparse(url).netloc), url)
    metadata = {
        "title": clean_title(title),
        "description": clean_whitespace(description),
        "og_type": parser.meta.get("og:type", ""),
    }
    if external_source_name(url) == "imdb":
        metadata["english_title"] = metadata["title"]
    if external_source_name(url) == "filmaffinity":
        metadata["spanish_title"] = metadata["title"]
    if link_field:
        metadata[link_field] = url
    return metadata


def fetch_wikipedia_metadata(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if external_source_name(url) != "wikipedia":
        return {}

    page_title = wikipedia_page_title(parsed.path)
    if not page_title:
        return {}

    language = host.split(".")[0] if "." in host else "en"
    summary_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{quote(page_title, safe='')}"
    raw = fetch_json(summary_url)
    if not raw:
        return fetch_wikipedia_metadata_action_api(language, page_title)

    title = clean_title(str(raw.get("title") or raw.get("displaytitle") or page_title))
    description = clean_whitespace(str(raw.get("description") or ""))
    extract = clean_whitespace(str(raw.get("extract") or ""))
    thumbnail = raw.get("thumbnail") if isinstance(raw.get("thumbnail"), dict) else {}
    image_url = str(thumbnail.get("source") or "") if isinstance(thumbnail, dict) else ""
    wikidata_id = str(raw.get("wikibase_item") or "")

    metadata = {
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
        fallback = fetch_wikipedia_metadata_action_api(language, page_title)
        return fallback or metadata
    return metadata


def fetch_wikipedia_metadata_action_api(language: str, page_title: str) -> dict[str, str]:
    api_url = (
        f"https://{language}.wikipedia.org/w/api.php"
        "?action=query"
        "&format=json"
        "&redirects=1"
        "&prop=extracts|pageimages|pageprops|info"
        "&exintro=1"
        "&explaintext=1"
        "&piprop=thumbnail"
        "&pithumbsize=500"
        "&inprop=url"
        f"&titles={quote(page_title.replace('_', ' '))}"
    )
    raw = fetch_json(api_url)
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
    image_url = str(thumbnail.get("source") or "") if isinstance(thumbnail, dict) else ""
    pageprops = page.get("pageprops") if isinstance(page.get("pageprops"), dict) else {}
    wikidata_id = str(pageprops.get("wikibase_item") or "")
    canonical_url = str(page.get("canonicalurl") or f"https://{language}.wikipedia.org/wiki/{quote(page_title, safe='')}")

    metadata = {
        "url": canonical_url,
        "wikipedia_url": canonical_url,
        "title": title,
        "spanish_title": title if language == "es" else "",
        "english_title": title if language == "en" else "",
        "description": description,
        "wikipedia_title": title,
        "wikidata_id": wikidata_id,
        "page_image": image_url,
        "wikipedia_extract": extract,
        "og_type": "",
    }
    metadata.update(fetch_wikidata_metadata(wikidata_id))
    return metadata


WIKIDATA_LIST_FIELDS = {
    "genres": ("P136", 8),
    "directors": ("P57", 8),
    "writers": ("P58", 10),
    "cast": ("P161", 20),
}


def fetch_wikidata_metadata(entity_id: str) -> dict[str, object]:
    if not entity_id:
        return {}
    raw = fetch_json(f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json")
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    entity = entities.get(entity_id) if isinstance(entities, dict) else {}
    if not isinstance(entity, dict):
        return {}

    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    ids_by_field: dict[str, list[str]] = {}
    all_ids: list[str] = []
    for field, (prop, limit) in WIKIDATA_LIST_FIELDS.items():
        ids = wikidata_claim_entity_ids(claims, prop, limit)
        ids_by_field[field] = ids
        all_ids.extend(ids)

    labels = fetch_wikidata_labels(all_ids)
    metadata: dict[str, object] = {}
    title_metadata = wikidata_title_metadata(entity)
    metadata.update(title_metadata)
    year = wikidata_claim_year(claims, "P577")
    if year:
        metadata["year"] = year
    for field, ids in ids_by_field.items():
        values = [labels.get(item_id, item_id) for item_id in ids if labels.get(item_id, item_id)]
        if values:
            metadata[field] = values
    return metadata


def wikidata_title_metadata(entity: dict[str, object]) -> dict[str, object]:
    labels = entity.get("labels") if isinstance(entity.get("labels"), dict) else {}
    aliases = entity.get("aliases") if isinstance(entity.get("aliases"), dict) else {}
    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    original_title = wikidata_claim_monolingual_text(claims, "P1476")
    spanish_title = wikidata_label_value(labels, "es")
    english_title = wikidata_label_value(labels, "en")
    alternative_titles = merge_lists(
        wikidata_all_label_values(labels),
        wikidata_all_alias_values(aliases),
    )
    primary_keys = {
        value.casefold()
        for value in [original_title, spanish_title, english_title]
        if value
    }
    alternative_titles = [
        value for value in alternative_titles if value.casefold() not in primary_keys
    ][:40]
    metadata: dict[str, object] = {}
    if original_title:
        metadata["original_title"] = original_title
    if spanish_title:
        metadata["spanish_title"] = spanish_title
    if english_title:
        metadata["english_title"] = english_title
    if alternative_titles:
        metadata["alternative_titles"] = alternative_titles
    return metadata


def wikidata_label_value(labels: dict[str, object], language: str) -> str:
    value = labels.get(language) if isinstance(labels, dict) else {}
    return str(value.get("value") or "") if isinstance(value, dict) else ""


def wikidata_alias_values(aliases: dict[str, object], language: str) -> list[str]:
    rows = aliases.get(language) if isinstance(aliases, dict) else []
    if not isinstance(rows, list):
        return []
    return [str(row.get("value") or "").strip() for row in rows if isinstance(row, dict) and str(row.get("value") or "").strip()]


def wikidata_all_label_values(labels: dict[str, object]) -> list[str]:
    return [
        str(row.get("value") or "").strip()
        for row in labels.values()
        if isinstance(row, dict) and str(row.get("value") or "").strip()
    ]


def wikidata_all_alias_values(aliases: dict[str, object]) -> list[str]:
    values: list[str] = []
    for rows in aliases.values():
        if not isinstance(rows, list):
            continue
        values.extend(
            str(row.get("value") or "").strip()
            for row in rows
            if isinstance(row, dict) and str(row.get("value") or "").strip()
        )
    return values


def wikidata_claim_monolingual_text(claims: dict[str, object], prop: str) -> str:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return ""
    ordered = sorted(
        [statement for statement in statements if isinstance(statement, dict) and statement.get("rank") != "deprecated"],
        key=lambda statement: 0 if statement.get("rank") == "preferred" else 1,
    )
    for statement in ordered:
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        text = str(value.get("text") or "").strip() if isinstance(value, dict) else ""
        if text:
            return text
    return ""


def wikidata_claim_entity_ids(claims: dict[str, object], prop: str, limit: int) -> list[str]:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return []
    ordered = sorted(
        [statement for statement in statements if isinstance(statement, dict) and statement.get("rank") != "deprecated"],
        key=lambda statement: 0 if statement.get("rank") == "preferred" else 1,
    )
    ids: list[str] = []
    for statement in ordered:
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        item_id = value.get("id") if isinstance(value, dict) else ""
        if item_id and item_id not in ids:
            ids.append(str(item_id))
        if len(ids) >= limit:
            break
    return ids


def wikidata_claim_year(claims: dict[str, object], prop: str) -> str:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return ""
    for statement in statements:
        if not isinstance(statement, dict) or statement.get("rank") == "deprecated":
            continue
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        raw_time = str(value.get("time") or "") if isinstance(value, dict) else ""
        match = re.search(r"([+-]?\d{4})", raw_time)
        if match:
            return match.group(1).lstrip("+")
    return ""


def fetch_wikidata_labels(entity_ids: list[str]) -> dict[str, str]:
    unique_ids = list(dict.fromkeys(entity_ids))
    labels: dict[str, str] = {}
    for index in range(0, len(unique_ids), 50):
        chunk = unique_ids[index : index + 50]
        if not chunk:
            continue
        url = (
            "https://www.wikidata.org/w/api.php"
            "?action=wbgetentities&format=json&props=labels&languages=es|en"
            f"&ids={quote('|'.join(chunk), safe='|')}"
        )
        raw = fetch_json(url)
        entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
        if not isinstance(entities, dict):
            continue
        for item_id, entity in entities.items():
            if not isinstance(entity, dict):
                continue
            label_values = entity.get("labels") if isinstance(entity.get("labels"), dict) else {}
            label = wikidata_label(label_values)
            if label:
                labels[str(item_id)] = label
    return labels


def wikidata_label(labels: dict[str, object]) -> str:
    for language in ["es", "en"]:
        value = labels.get(language) if isinstance(labels, dict) else {}
        if isinstance(value, dict) and value.get("value"):
            return str(value["value"])
    return ""


def fetch_wikipedia_by_title(title: str, year: str = "") -> dict[str, str]:
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

            best: tuple[int, dict[str, str]] = (0, {})
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


def fetch_wikipedia_by_imdb_id(imdb_id: str) -> dict[str, str]:
    query = f"""
SELECT ?item ?article WHERE {{
  ?item wdt:P345 "{imdb_id}".
  ?article schema:about ?item ;
           schema:isPartOf ?site.
  VALUES ?site {{ <https://en.wikipedia.org/> <https://es.wikipedia.org/> }}
}}
LIMIT 1
"""
    url = "https://query.wikidata.org/sparql?format=json&query=" + quote(query)
    raw = fetch_json(url)
    results = raw.get("results") if isinstance(raw.get("results"), dict) else {}
    bindings = results.get("bindings") if isinstance(results, dict) else []
    if not isinstance(bindings, list) or not bindings:
        return {}
    binding = bindings[0]
    article = binding.get("article") if isinstance(binding, dict) else {}
    article_url = article.get("value") if isinstance(article, dict) else ""
    if article_url:
        return fetch_wikipedia_metadata(str(article_url))
    return {}


def fetch_wikipedia_by_wikidata_title(title: str, year: str = "") -> dict[str, str]:
    for language in ["en", "es"]:
        search_url = (
            "https://www.wikidata.org/w/api.php"
            f"?action=wbsearchentities&format=json&language={language}&limit=5"
            f"&search={quote(title)}"
        )
        raw = fetch_json(search_url)
        results = raw.get("search") if isinstance(raw.get("search"), list) else []
        for result in results:
            if not isinstance(result, dict):
                continue
            entity_id = str(result.get("id") or "")
            label = str(result.get("label") or "")
            description = str(result.get("description") or "")
            score = wikidata_result_score(title, year, label, description)
            if score < 3:
                continue
            article_url = fetch_wikidata_article_url(entity_id)
            if article_url:
                metadata = fetch_wikipedia_metadata(article_url)
                if metadata and wikipedia_match_score(title, year, label, description, metadata) >= 3:
                    return metadata
    return {}


def fetch_wikidata_article_url(entity_id: str) -> str:
    if not entity_id:
        return ""
    raw = fetch_json(f"https://www.wikidata.org/wiki/Special:EntityData/{quote(entity_id)}.json")
    entities = raw.get("entities") if isinstance(raw.get("entities"), dict) else {}
    entity = entities.get(entity_id) if isinstance(entities, dict) else {}
    if not isinstance(entity, dict):
        return ""

    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    if not wikidata_claims_include(claims, "P31", {"Q11424", "Q5398426", "Q24862", "Q506240"}):
        description_values = entity.get("descriptions") if isinstance(entity.get("descriptions"), dict) else {}
        descriptions = " ".join(
            str(value.get("value") or "")
            for value in description_values.values()
            if isinstance(value, dict)
        ).lower()
        if not any(marker in descriptions for marker in ["film", "movie", "película", "pelicula"]):
            return ""

    sitelinks = entity.get("sitelinks") if isinstance(entity.get("sitelinks"), dict) else {}
    for key in ["enwiki", "eswiki"]:
        link = sitelinks.get(key) if isinstance(sitelinks, dict) else {}
        if isinstance(link, dict) and link.get("url"):
            return str(link["url"])
    return ""


def wikidata_claims_include(claims: dict[str, object], prop: str, ids: set[str]) -> bool:
    statements = claims.get(prop) if isinstance(claims, dict) else []
    if not isinstance(statements, list):
        return False
    for statement in statements:
        mainsnak = statement.get("mainsnak") if isinstance(statement, dict) else {}
        datavalue = mainsnak.get("datavalue") if isinstance(mainsnak, dict) else {}
        value = datavalue.get("value") if isinstance(datavalue, dict) else {}
        entity_id = value.get("id") if isinstance(value, dict) else ""
        if entity_id in ids:
            return True
    return False


def wikidata_result_score(title: str, year: str, label: str, description: str) -> int:
    score = 0
    title_key = normalize_match_text(title)
    label_key = normalize_match_text(label)
    description_key = normalize_match_text(description)
    if title_key and title_key == label_key:
        score += 4
    elif title_key and (title_key in label_key or label_key in title_key):
        score += 2
    if year and year in description:
        score += 1
    if any(marker in description_key for marker in ["film", "movie", "pelicula", "película"]):
        score += 2
    return score


def likely_film_result(title: str, snippet: str, year: str) -> bool:
    lowered = title.lower()
    if year and year in title:
        return True
    return any(marker in lowered for marker in ["film", "movie"]) or any(
        marker in snippet for marker in ["film", "movie", "directed by", "starring"]
    )


def fetch_wikipedia_search(query: str, language: str) -> dict[str, object]:
    search_url = (
        f"https://{language}.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={quote(query)}&format=json&srlimit=5"
    )
    return fetch_json(search_url)


def wikipedia_search_queries(title: str, year: str, language: str) -> list[str]:
    film_word = "película" if language == "es" else "film"
    movie_word = "cine" if language == "es" else "movie"
    queries = []
    if year:
        queries.append(f'"{title}" {year} {film_word}')
    queries.append(f'"{title}" {film_word}')
    queries.append(f'"{title}"')
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
    metadata: dict[str, str],
) -> int:
    if not metadata:
        return 0
    score = 0
    query_key = normalize_match_text(query_title)
    page_key = normalize_match_text(page_title)
    wiki_key = normalize_match_text(metadata.get("wikipedia_title", ""))
    description = normalize_match_text(metadata.get("description", ""))
    extract = normalize_match_text(metadata.get("wikipedia_extract", ""))
    snippet_key = normalize_match_text(snippet)

    if query_key and query_key in {page_key, wiki_key}:
        score += 4
    elif query_key and (query_key in page_key or query_key in wiki_key):
        score += 2
    if year and year in f"{page_title} {metadata.get('wikipedia_extract', '')}":
        score += 2
    if any(marker in description for marker in ["film", "movie", "pelicula", "película"]):
        score += 2
    if any(marker in f"{extract} {snippet_key}" for marker in ["directed by", "starring", "film", "movie", "pelicula", "película"]):
        score += 1
    return score


def normalize_match_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9áéíóúñü]+", " ", value)
    return clean_whitespace(value)


def clean_search_title(value: str) -> str:
    value = re.sub(
        r"\s*\((film|movie|pelicula|película|miniserie|tv series|serie de tv|video game|cortometraje)[^)]*\)?\s*$",
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


def imdb_id_from_text(value: str) -> str:
    match = re.search(r"\btt\d{7,9}\b", value)
    return match.group(0) if match else ""


def wikipedia_page_title(path: str) -> str:
    marker = "/wiki/"
    if marker not in path:
        return ""
    title = path.split(marker, 1)[1].split("#", 1)[0]
    return unquote(title).replace(" ", "_")


def fetch_json(url: str) -> dict[str, object]:
    request = Request(
        url,
        headers={
            "User-Agent": "MovieInboxImporter/0.1 (+local personal catalog)",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            raw = json.loads(response.read(800_000).decode("utf-8", errors="replace"))
            return raw if isinstance(raw, dict) else {}
    except (HTTPError, URLError, TimeoutError, socket.timeout, OSError, ValueError, json.JSONDecodeError):
        return {}


def source_name(netloc: str) -> str:
    try:
        host = (urlparse(f"//{netloc}").hostname or "").encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return ""
    host = host.lower().rstrip(".").removeprefix("www.")
    source = external_source_name(f"https://{host}/")
    if source:
        return source
    if host == "letterboxd.com" or host.endswith(".letterboxd.com"):
        return "letterboxd"
    return host


def guess_title_from_url(url: str) -> str:
    parsed = urlparse(url)
    slug = parsed.path.strip("/").split("/")[-1]
    if not slug and parsed.netloc:
        return parsed.netloc
    slug = re.sub(r"\.[a-zA-Z0-9]+$", "", slug)
    return clean_title(unquote(slug).replace("_", " ").replace("-", " "))


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)
