"""Search across the personal catalog and external sources.

Shared by Colección (manual add), Curaduría (comparators) and Club (duplicate checks).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.search_service import (
    group_external_results,
    rank_catalog_candidates,
    search_catalog_items,
)
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.domain.search import parse_search_query
from movie_inbox.infrastructure.external_catalog import external_sources_snapshot
from movie_inbox.web.catalog_api import enrich_selected_result, search_sources
from movie_inbox.web.dependencies import (
    authorized_json,
    require_ready_identity,
    require_token,
    session_catalog_rows,
)

router = APIRouter()


@router.get("/api/search", dependencies=[Depends(require_token)])
def search(
    request: Request,
    q: str = "",
    source: str = "all",
    external: bool = True,
    catalog: bool = True,
    identity: AuthenticatedIdentity = Depends(require_ready_identity),
) -> JSONResponse:
    catalog_results: list[dict[str, Any]] = []
    if catalog:
        _, _, rows = session_catalog_rows(request, identity)
        catalog_results = search_catalog_items(rows, q)
    results = search_sources(q, source) if external else []
    if parse_search_query(q).director_query_key:
        # [Q4] tareas.md: external results carry no `directors` field of
        # their own to check per-row (only single-item metadata fetches
        # populate it, never a source's plain search-result list), so the
        # discovery label is applied once, from the query itself.
        for result in results:
            result["_search"] = {"reason": "director_match", "matched_field": "director"}
    source_groups = group_external_results(results)
    print(
        f"[catalog-viewer] search query={q!r} source={source} "
        f"catalog={catalog} "
        f"catalog_count={len(catalog_results)} external_count={len(results)} "
        f"result_sources={sorted(set(str(result.get('source') or '') for result in results))}",
        flush=True,
    )
    return JSONResponse(
        {
            "query": q,
            "catalog": {"results": catalog_results, "count": len(catalog_results)},
            "sources": {
                name: {"results": grouped, "count": len(grouped)}
                for name, grouped in source_groups.items()
            },
            "results": results,
            "external": external_sources_snapshot(),
        }
    )


@router.post("/api/search/catalog-candidates")
def search_catalog_candidates(
    request: Request,
    body: dict[str, Any] = Depends(authorized_json),
) -> JSONResponse:
    identity = require_ready_identity(request)
    selected_result = body.get("result")
    raw_result = selected_result if isinstance(selected_result, dict) else body
    enriched = enrich_selected_result(raw_result)
    _, _, rows = session_catalog_rows(request, identity)
    candidates = rank_catalog_candidates(rows, enriched)
    return JSONResponse(
        {
            "candidate": enriched,
            "results": candidates,
            "count": len(candidates),
        }
    )


@router.get("/api/source-health", dependencies=[Depends(require_token)])
def source_health() -> JSONResponse:
    return JSONResponse({"external": external_sources_snapshot()})
