"""Schema definitions for Flow pipeline data."""

from __future__ import annotations

from pydantic import BaseModel


class Scene(BaseModel):
    id: int
    duration: int = 5
    visual_prompt: str
    camera: str = ""
    narration_segment: str = ""
    characters: list[str] = []


class Character(BaseModel):
    description: str
    reference_image: str | None = None


class ShotList(BaseModel):
    title: str
    narration: str
    scenes: list[Scene]
    characters: dict[str, Character] = {}


class GeneratedClip(BaseModel):
    scene_id: int
    path: str
    duration: float
    last_frame_path: str | None = None
