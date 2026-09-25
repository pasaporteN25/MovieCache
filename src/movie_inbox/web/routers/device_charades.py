"""Charades for a device: what a phone needs to deal the same decks offline ([A2.4]).

[G2] made the generator portable so a phone could deal without a connection, as
ADR-0005 has it playing. What a phone could not do was get the deck's input: the
eligible works, each with the key the deck is ordered and fingerprinted by and
the difficulty the server resolved. This serves exactly that, and only reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from movie_inbox.application.charades_repository import CharadesRepositoryError
from movie_inbox.application.collection_repository import CollectionRepositoryError
from movie_inbox.application.repository import CatalogRepositoryError
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.web.dependencies import require_device_identity
from movie_inbox.web.responses import DeviceApiRequestError

router = APIRouter()


@router.get("/api/v1/charades")
def device_charades(
    request: Request,
    identity: AuthenticatedIdentity = Depends(require_device_identity),
) -> JSONResponse:
    """The deck's whole input, unpaged on purpose.

    The fingerprint covers every eligible work, so half a list would deal a
    different deck. Keys travel as the server computes them instead of as opaque
    ids: the deck is sorted and fingerprinted by them, and any stand-in would
    deal a different order. They are built from public identifiers -- TMDb, IMDb,
    Wikidata -- or a normalised title and year, never from a path, a file or an
    internal id, which is what ADR-0003 keeps off the wire.
    """

    service = request.app.state.charades_service
    try:
        return JSONResponse(service.snapshot(identity))
    except CatalogRepositoryError as error:
        raise DeviceApiRequestError("catalog_unavailable", 503) from error
    except CollectionRepositoryError as error:
        raise DeviceApiRequestError("collections_unavailable", 503) from error
    except CharadesRepositoryError as error:
        raise DeviceApiRequestError("charades_unavailable", 503) from error
