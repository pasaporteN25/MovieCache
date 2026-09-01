"""Persistence boundary for public presentation snapshots."""

from __future__ import annotations

from typing import Protocol

from movie_inbox.domain.public_presentations import PublicPresentation


class PublicPresentationRepositoryError(RuntimeError):
    """Raised when public presentation persistence is unavailable."""


class PublicPresentationRepository(Protocol):
    def create(self, presentation: PublicPresentation) -> None: ...

    def list_for_owner(self, owner_user_id: str) -> list[PublicPresentation]: ...

    def get_for_owner(
        self, owner_user_id: str, presentation_id: str
    ) -> PublicPresentation | None: ...

    def get_active_by_capability_hash(self, capability_hash: str) -> PublicPresentation | None: ...

    def replace_snapshot(
        self,
        owner_user_id: str,
        presentation_id: str,
        *,
        title: str,
        description: str,
        snapshot: dict[str, object],
        updated_at: str,
    ) -> PublicPresentation | None: ...

    def revoke(
        self, owner_user_id: str, presentation_id: str, *, revoked_at: str
    ) -> PublicPresentation | None: ...
