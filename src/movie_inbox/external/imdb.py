"""IMDb search client and Wikidata bridge."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from movie_inbox.external.common import fetch_json, fetch_json_safe


class ImdbAdapter:
    name = "imdb"
    label = "IMDb"

    def search(self, query: str) -> list[dict[str, Any]]:
        key = re.sub(r"[^a-z0-9_ -]+", "", query.lower()).strip().replace(" ", "_")
        if not key:
            return []
        raw = fetch_json(f"https://v3.sg.media-imdb.com/suggestion/x/{quote(key)}.json")
        rows = raw.get("d") if isinstance(raw.get("d"), list) else []
        results: list[dict[str, Any]] = []
        for row in rows[:8]:
            if not isinstance(row, dict) or row.get("qid") not in {"movie", "tvSeries", "tvMiniSeries", "tvMovie"}:
                continue
            imdb_id = str(row.get("id") or "")
            title = str(row.get("l") or "")
            if not imdb_id or not title:
                continue
            image = row.get("i") if isinstance(row.get("i"), dict) else {}
            results.append(
                {
                    "source": self.name,
                    "title": title,
                    "original_title": "",
                    "spanish_title": "",
                    "english_title": title,
                    "alternative_titles": [],
                    "year": str(row.get("y") or ""),
                    "url": f"https://www.imdb.com/title/{imdb_id}/",
                    "description": str(row.get("s") or ""),
                    "page_image": str(image.get("imageUrl") or ""),
                }
            )
        return results


def imdb_id_from_text(value: str) -> str:
    match = re.search(r"\btt\d{7,9}\b", value)
    return match.group(0) if match else ""


def fetch_wikipedia_by_imdb_id(imdb_id: str) -> dict[str, Any]:
    from movie_inbox.external.wikipedia import fetch_wikipedia_metadata

    query = f'''SELECT ?item ?article WHERE {{
  ?item wdt:P345 "{imdb_id}".
  ?article schema:about ?item ; schema:isPartOf ?site.
  VALUES ?site {{ <https://en.wikipedia.org/> <https://es.wikipedia.org/> }}
}} LIMIT 1'''
    raw = fetch_json_safe("https://query.wikidata.org/sparql?format=json&query=" + quote(query), timeout=5)
    results = raw.get("results") if isinstance(raw.get("results"), dict) else {}
    bindings = results.get("bindings") if isinstance(results, dict) else []
    if not isinstance(bindings, list) or not bindings:
        return {}
    binding = bindings[0]
    article = binding.get("article") if isinstance(binding, dict) else {}
    article_url = article.get("value") if isinstance(article, dict) else ""
    return fetch_wikipedia_metadata(str(article_url)) if article_url else {}
