"""External source search protocol."""

from __future__ import annotations

from typing import Protocol


class SourceAdapter(Protocol):
    name: str
    label: str

    def search(self, query: str) -> list[dict[str, object]]:
        """Return lightweight search results for a query."""
        ...
