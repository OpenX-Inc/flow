"""Timeline domain models — the video-track clip and its animation.

A Clip is a scene viewed as a timeline element: it references a source media
asset, trims into it, and carries playback/visual properties plus per-property
keyframe animation. Defaults are chosen so ``model_dump(exclude_defaults=True)``
yields compact payloads (token hygiene for the agent context).
"""

from __future__ import annotations

import uuid
from enum import Enum

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    """Short, prefixed, sortable-enough id (e.g. ``clip_a1b2c3d4``)."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Easing(str, Enum):
    linear = "linear"
    ease_in = "ease_in"
    ease_out = "ease_out"
    ease_in_out = "ease_in_out"
    bezier = "bezier"


class Keyframe(BaseModel):
    """Animates one property of one clip at a clip-relative frame.

    Keyframes are stored clip-relative so they survive reorder/move untouched.
    """

    property: str  # opacity | volume | scale | x | y | rotation
    frame: int = Field(ge=0)  # clip-relative
    value: float
    easing: Easing = Easing.linear
    bezier: list[float] | None = None  # 4 control points when easing == bezier


class Transform(BaseModel):
    """2D transform applied to the clip's video (identity by default)."""

    scale: float = 1.0
    x: int = 0  # pixel offset from center
    y: int = 0
    rotation: float = 0.0  # degrees


class ClipStatus(str, Enum):
    pending = "pending"
    generating = "generating"
    done = "done"
    failed = "failed"


class Clip(BaseModel):
    """A scene as a video-track timeline element.

    ``in_frame``/``out_frame`` are a half-open trim into the source media
    (``[in, out)``); effective on-timeline length scales by ``speed``.
    """

    clip_id: str = Field(default_factory=lambda: new_id("clip"))
    order_index: int = 0

    # Source + generation provenance (so a clip can be regenerated in place)
    source_media_id: str | None = None
    visual_prompt: str = ""
    model: str = ""
    first_frame_ref: str | None = None
    last_frame_ref: str | None = None
    reference_images: list[str] = []
    characters: list[str] = []

    # Timeline / trim
    source_duration_frames: int = 0
    in_frame: int = 0
    out_frame: int = 0

    # Playback / visual props (defaults = no-op, omitted from compact dumps)
    speed: float = 1.0
    volume: float = 1.0
    opacity: float = 1.0
    transform: Transform = Field(default_factory=Transform)
    fade_in_frames: int = 0
    fade_out_frames: int = 0
    transition: str = ""  # transition INTO this clip (e.g. "crossfade")

    keyframes: list[Keyframe] = []

    # Render artifacts
    video_url: str | None = None
    narration_segment: str = ""
    status: ClipStatus = ClipStatus.pending

    @property
    def effective_frames(self) -> int:
        """On-timeline length after trim + speed (ceil to whole frames)."""
        import math

        trimmed = max(0, self.out_frame - self.in_frame)
        return math.ceil(trimmed / self.speed) if self.speed > 0 else trimmed
