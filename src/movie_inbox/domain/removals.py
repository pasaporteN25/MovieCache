"""[X5] What a paired device is told about a work that left the catalogue."""

from __future__ import annotations

from dataclasses import dataclass

# A person deleted it, or a person merged it into another work.
REMOVAL_REASONS = frozenset({"deleted", "merged"})


@dataclass(frozen=True)
class DeviceRemoval:
    """One work that left the catalogue, by the opaque id a device knew it by.

    Both ids are the ones a phone already holds, never the catalogue's own:
    turning one into the other needs the instance secret and the source
    position, and that belongs to the web layer, which is where they exist.

    `merged_into` is the work that took its place, and only a merge has one.
    """

    device_id: str
    reason: str
    merged_into: str = ""
    removed_at: int = 0

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("A removal requires the id a device knew the work by")
        if self.reason not in REMOVAL_REASONS:
            raise ValueError(f"Invalid removal reason: {self.reason}")
        if self.reason == "merged" and not self.merged_into:
            raise ValueError("A merged work has to say what it was merged into")
        if self.reason == "deleted" and self.merged_into:
            raise ValueError("A deleted work is not merged into anything")
        if self.merged_into == self.device_id:
            raise ValueError("A work cannot be merged into itself")
