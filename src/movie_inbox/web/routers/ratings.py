"""Public scores for the viewer's own catalogue, read at display time.

Read-only by construction. These are other people's aggregate opinions and are
served beside the viewer's own `rating`, never merged into it ([F3.2]).

Two sources answer here at once, by owner decision: IMDb from the local index
and TMDb from a dated snapshot. Which ones actually appear depends on what the
instance has configured, and a work with no score at all is simply absent from
the map.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.domain.imdb_dataset import IMDB_ATTRIBUTION_NOTICE
from movie_inbox.external.tmdb import TMDB_ATTRIBUTION_NOTICE
from movie_inbox.web.catalog_api import load_items
from movie_inbox.web.dependencies import SessionCatalog, require_ready_identity, require_token
from movie_inbox.web.responses import error_response

router = APIRouter()


@router.get("/api/ratings", dependencies=[Depends(require_token)])
def public_ratings(request: Request, item_id: str | None = None) -> JSONResponse:
    identity = require_ready_identity(request)
    service = request.app.state.public_ratings_service
    if not service.sources_configured:
        # Nothing configured: an empty map, not an error. Public scores are
        # supplementary, and a viewer without either source simply sees theirs.
        return JSONResponse({"ratings": {}, "attribution": {}})
    try:
        catalog = SessionCatalog.from_identity(request.app.state.viewer_config, identity)
        items = load_items(catalog.config.patterns)
    except CatalogRepositoryError:
        return error_response("catalog_unavailable", 503)

    # A dossier must spend its refresh budget on the selected work, including
    # one beyond the first batch. Filter only inside the authenticated catalogue.
    if item_id is not None:
        items = [item for item in items if item.get("id") == item_id]
    found = service.ratings_for(items)
    ratings = {item_id: [rating.to_dict() for rating in rows] for item_id, rows in found.items()}
    # Both notices are required by their sources' terms wherever the data is
    # shown, so only the ones that could have contributed a score are sent: an
    # attribution for a source that answered nothing would be noise.
    attribution: dict[str, str] = {}
    if service.imdb_lookup is not None:
        attribution["imdb"] = IMDB_ATTRIBUTION_NOTICE
    if service.tmdb_loader is not None:
        attribution["tmdb"] = TMDB_ATTRIBUTION_NOTICE
    return JSONResponse({"ratings": ratings, "attribution": attribution})
