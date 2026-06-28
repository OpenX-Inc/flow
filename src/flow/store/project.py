"""Project aggregate — the full timeline the agent operates on.

Holds the video track (ordered clips), audio/text tracks, media library,
folders, cast, and the undo stack. This is the single object ``get_project``
serializes for agent context and that every tool mutates.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from flow.schemas import Character
from flow.store.frames import DEFAULT_FPS
from flow.store.media import Folder, MediaAsset
from flow.store.models import Clip, new_id
from flow.store.tracks import Track
from flow.store.undo import UndoEntry


class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: new_id("proj"))
    title: str = "Untitled"
    fps: int = DEFAULT_FPS
    width: int = 832
    height: int = 480
    revision: int = 0  # optimistic concurrency; bumps on every mutation

    clips: list[Clip] = []  # the video track, ordered by order_index
    tracks: list[Track] = []  # audio + text lanes
    media: list[MediaAsset] = []
    folders: list[Folder] = []
    characters: dict[str, Character] = {}  # cast, name -> Character

    undo_stack: list[UndoEntry] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # --- lookups ---
    def get_clip(self, clip_id: str) -> Clip | None:
        return next((c for c in self.clips if c.clip_id == clip_id), None)

    def get_track(self, track_id: str) -> Track | None:
        return next((t for t in self.tracks if t.track_id == track_id), None)

    def get_media(self, media_id: str) -> MediaAsset | None:
        return next((m for m in self.media if m.media_id == media_id), None)

    def ordered_clips(self) -> list[Clip]:
        return sorted(self.clips, key=lambda c: c.order_index)

    def total_frames(self) -> int:
        """Length of the assembled video track (clips are sequential)."""
        return sum(c.effective_frames for c in self.clips)

    def next_order_index(self) -> int:
        return (max((c.order_index for c in self.clips), default=-1)) + 1

    def touch(self) -> None:
        """Mark mutated: bump revision + updated_at."""
        self.revision += 1
        self.updated_at = datetime.now(UTC)
