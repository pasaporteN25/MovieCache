"""Public scores for the viewer's own catalogue, read at display time.

Read-only by construction. These are other people's aggregate opinions and are
served beside the viewer's own `rating`, never merged into it ([F3.2]).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE
from movie_inbox.domain.public_ratings import sorted_ratings
from movie_inbox.external.imdb import imdb_id_from_text
from movie_inbox.web.catalog_api import load_items
from movie_inbox.web.dependencies import SessionCatalog, require_ready_identity, require_token
from movie_inbox.web.responses import error_response

router = APIRouter()


@router.get("/api/ratings", dependencies=[Depends(require_token)])
def public_ratings(request: Request) -> JSONResponse:
    identity = require_ready_identity(request)
    source = request.app.state.imdb_dataset_source
    if source is None:
        # No index configured: an empty map, not an error. Public scores are
        # supplementary, and a viewer without the index simply sees their own.
        return JSONResponse({"ratings": {}, "attribution": {}})
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        items = load_items(catalog.config.patterns)
    except CatalogRepositoryError:
        return error_response("catalog_unavailable", 503)

    ratings: dict[str, list[dict[str, object]]] = {}
    for item in items:
        imdb_id = imdb_id_from_text(str(item.get("imdb_url") or ""))
        if not imdb_id:
            continue
        found = source.rating_for(imdb_id)
        if found is not None:
            ratings[str(item.get("id") or "")] = [row.to_dict() for row in sorted_ratings([found])]
    return JSONResponse(
        {
            "ratings": ratings,
            # Required whenever this data is shown, per the terms verified in [F1].
            "attribution": {"imdb": IMDB_ATTRIBUTION_NOTICE},
        }
    )
