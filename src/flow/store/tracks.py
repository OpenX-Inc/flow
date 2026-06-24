"""Non-video tracks — audio (narration/music) and text (captions/titles).

The video track is the ordered list of ``Clip`` on the project. These Track
objects hold the parallel lanes that ffmpeg mixes/overlays at assembly time.
Items are frame-positioned on the timeline (absolute project frames).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.flow.store.models import new_id


class TrackKind(str, Enum):
    audio = "audio"  # narration, music, sfx
    text = "text"  # captions, titles, lower-thirds


class TextPosition(str, Enum):
    top = "top"
    center = "center"
    bottom = "bottom"


class TextStyle(BaseModel):
    """Style for a text/caption item (defaults = a clean centered caption)."""

    font_family: str = "Inter"
    size_pct: float = 5.0  # % of frame height — resolution-independent
    color: str = "#ffffff"
    background: str = ""  # e.g. "rgba(0,0,0,0.5)"; empty = none
    bold: bool = False
    position: TextPosition = TextPosition.bottom
    align: str = "center"  # left | center | right


class TrackItem(BaseModel):
    """One item on an audio or text track, placed at absolute project frames.

    Audio items reference ``source_media_id`` (a generated/imported asset);
    text items carry ``text`` + ``style``. Fields irrelevant to the parent
    track kind stay at defaults and are omitted from compact dumps.
    """

    item_id: str = Field(default_factory=lambda: new_id("item"))
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(ge=0)

    # audio
    source_media_id: str | None = None
    volume: float = 1.0
    gain_db: float = 0.0
    fade_in_frames: int = 0
    fade_out_frames: int = 0

    # text
    text: str = ""
    style: TextStyle | None = None


class Track(BaseModel):
    """An audio or text lane of frame-positioned items."""

    track_id: str = Field(default_factory=lambda: new_id("track"))
    kind: TrackKind
    name: str = ""  # e.g. "narration", "music", "captions"
    order: int = 0
    muted: bool = False
    hidden: bool = False
    items: list[TrackItem] = []
