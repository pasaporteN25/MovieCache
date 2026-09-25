"""[X5] Leave a record, under the ids a phone knows, of works a person removed.

The catalogue services know which work they removed and from which file; only
the web layer has the account, the source positions and the instance secret a
phone's id is made from. So the routes that remove a work hand it here.

The record is written **after** the removal and is best effort by design: a
removal that already happened is not undone because remembering it failed.
The failure that leaves is a removal with no record, which a phone reads the
way it reads any absent work -- it asks, gets `unknown`, and lets the person
decide. It can never be a record of a removal that did not happen.
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import Request

from movie_inbox.application.identity_repository import IdentityRepositoryError
from movie_inbox.application.removal_repository import RemovalRepositoryError
from movie_inbox.domain.identity import AuthenticatedIdentity
from movie_inbox.domain.removals import DeviceRemoval, RemovedWork
from movie_inbox.web.dependencies import SessionCatalog
from movie_inbox.web.device_ids import device_id_for, sync_secret


def record_removed_works(
    request: Request,
    identity: AuthenticatedIdentity,
    catalog: SessionCatalog,
    works: Sequence[RemovedWork],
) -> None:
    if not works:
        return
    try:
        secret = sync_secret(request)
        removals = _removals(secret, identity, catalog, works)
        if removals:
            request.app.state.removal_service.record(identity.catalog.id, removals)
    except (RemovalRepositoryError, IdentityRepositoryError) as error:
        print(f"[catalog-viewer] could not record removed works error={error}", flush=True)


def forget_removed_works(
    request: Request,
    identity: AuthenticatedIdentity,
    catalog: SessionCatalog,
    works: Sequence[RemovedWork],
) -> None:
    """A removal was undone, so the works are back and there is nothing to tell."""

    if not works:
        return
    try:
        secret = sync_secret(request)
        ids = [
            device_id
            for work in works
            if (
                device_id := device_id_for(
                    secret, identity, catalog, work.source_file, work.item_id
                )
            )
        ]
        request.app.state.removal_service.forget(identity.catalog.id, ids)
    except (RemovalRepositoryError, IdentityRepositoryError) as error:
        print(f"[catalog-viewer] could not forget removed works error={error}", flush=True)


def _removals(
    secret: bytes,
    identity: AuthenticatedIdentity,
    catalog: SessionCatalog,
    works: Sequence[RemovedWork],
) -> list[DeviceRemoval]:
    removals: list[DeviceRemoval] = []
    for work in works:
        device_id = device_id_for(secret, identity, catalog, work.source_file, work.item_id)
        if device_id is None:
            continue
        survivor = (
            device_id_for(
                secret,
                identity,
                catalog,
                work.survivor_source_file or work.source_file,
                work.survivor_item_id,
            )
            if work.survivor_item_id
            else None
        )
        if survivor and survivor != device_id:
            removals.append(DeviceRemoval(device_id, "merged", merged_into=survivor))
        else:
            # A merge whose survivor a phone cannot know is told as a deletion:
            # there is nowhere to send the phone's pending changes.
            removals.append(DeviceRemoval(device_id, "deleted"))
    return removals
