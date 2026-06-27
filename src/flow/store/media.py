"""Media library — generated/imported assets and the folders that organize them.

Assets are decoupled from clips: a Clip references a ``source_media_id``, so
reorganizing or renaming library assets never breaks a render, and one asset
can back multiple clips. Deletes are soft (Trash) — see UndoEntry.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field
from src.flow.store.models import new_id


class MediaType(StrEnum):
    video = "video"
    image = "image"
    audio = "audio"


class GenerationStatus(StrEnum):
    none = "none"  # imported / not generated
    generating = "generating"
    downloading = "downloading"
    ready = "ready"
    failed = "failed"


class MediaAsset(BaseModel):
    """A library asset with provenance and a reverse index of who uses it."""

    media_id: str = Field(default_factory=lambda: new_id("med"))
    type: MediaType
    url: str = ""
    filename: str = ""
    folder_id: str | None = None

    # dimensions / length (frames in project fps for video/audio)
    duration_frames: int = 0
    width: int = 0
    height: int = 0

    # provenance
    generation_status: GenerationStatus = GenerationStatus.none
    model: str = ""
    prompt: str = ""
    reference_images: list[str] = []
    character_id: str | None = None  # set when this is a character reference asset

    # reverse index: clip_ids / item_ids referencing this asset (ref-safe deletes)
    used_by: list[str] = []
    trashed: bool = False


class Folder(BaseModel):
    """A media-panel folder; nests via ``parent_folder_id``."""

    folder_id: str = Field(default_factory=lambda: new_id("fld"))
    name: str
    parent_folder_id: str | None = None
    system: bool = False  # protected (e.g. Trash, Generated)
