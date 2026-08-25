"""IMDb search client and Wikidata bridge."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from movie_inbox.domain.catalog import merge_lists
from movie_inbox.domain.search import (
    EXTERNAL_RELEVANCE_THRESHOLD,
    external_result_score,
    parse_search_query,
    search_key,
)
from movie_inbox.external.common import (
    fetch_json,
    fetch_json_safe,
    object_dict,
    object_list,
    string_list,
)
from movie_inbox.external.wikidata import fetch_wikidata_title_matches


class ImdbAdapter:
    name = "imdb"
    label = "IMDb"

    def search(self, query: str) -> list[dict[str, Any]]:
        intent = parse_search_query(query)
        if intent.source and intent.source != self.name:
            return []
        lookup = intent.external_id or intent.title or query
        key = search_key(lookup).replace(" ", "_")
        if not key:
            return []
        raw = fetch_json(f"https://v3.sg.media-imdb.com/suggestion/x/{quote(key)}.json")
        rows = object_list(raw.get("d"))
        results: list[dict[str, Any]] = []
        for row in rows[:8]:
            if not isinstance(row, dict) or row.get("qid") not in {
                "movie",
                "tvSeries",
                "tvMiniSeries",
                "tvMovie",
            }:
                continue
            imdb_id = str(row.get("id") or "")
            title = str(row.get("l") or "")
            if not imdb_id or not title:
                continue
            image = object_dict(row.get("i"))
            results.append(
                {
                    "source": self.name,
                    "title": title,
                    "original_title": "",
                    "spanish_title": "",
                    "english_title": title,
                    "alternative_titles": [],
                    "kind": "serie"
                    if row.get("qid") in {"tvSeries", "tvMiniSeries"}
                    else "pelicula",
                    "year": str(row.get("y") or ""),
                    "url": f"https://www.imdb.com/title/{imdb_id}/",
                    "description": str(row.get("s") or ""),
                    "page_image": str(image.get("imageUrl") or ""),
                }
            )
        if (
            results
            and not intent.external_id
            and all(
                external_result_score(intent, result) < EXTERNAL_RELEVANCE_THRESHOLD
                for result in results
            )
        ):
            title_matches = fetch_wikidata_title_matches(intent.title or query)
            for result in results:
                imdb_id = imdb_id_from_text(str(result.get("url") or ""))
                metadata = title_matches.get(imdb_id)
                if not metadata:
                    continue
                for field in ("original_title", "spanish_title", "english_title"):
                    if metadata.get(field):
                        result[field] = str(metadata[field])
                result["alternative_titles"] = merge_lists(
                    string_list(result.get("alternative_titles")),
                    string_list(metadata.get("alternative_titles")),
                )
        return results


def imdb_id_from_text(value: str) -> str:
    match = re.search(r"\btt\d{7,9}\b", value, flags=re.IGNORECASE)
    return match.group(0).lower() if match else ""


def fetch_wikipedia_by_imdb_id(imdb_id: str) -> dict[str, Any]:
    from movie_inbox.external.wikipedia import fetch_wikipedia_metadata

    query = f'''SELECT ?item ?article WHERE {{
  ?item wdt:P345 "{imdb_id}".
  ?article schema:about ?item ; schema:isPartOf ?site.
  VALUES ?site {{ <https://en.wikipedia.org/> <https://es.wikipedia.org/> }}
}} LIMIT 1'''
    raw = fetch_json_safe(
        "https://query.wikidata.org/sparql?format=json&query=" + quote(query), timeout=5
    )
    results = object_dict(raw.get("results"))
    bindings = object_list(results.get("bindings"))
    if not bindings:
        return {}
    binding = object_dict(bindings[0])
    article = object_dict(binding.get("article"))
    article_url = article.get("value")
    return fetch_wikipedia_metadata(str(article_url)) if article_url else {}
