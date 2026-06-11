"""Configuration management for Flow."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class LLMConfig(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-4o-mini"


class GPUBackendConfig(BaseModel):
    provider: str = "modal"  # modal, runpod, self-hosted
    url: str = ""
    api_key: str = ""
    resolution: str = "480p"  # 480p, 720p
    clip_duration: int = 5


class TTSConfig(BaseModel):
    provider: str = "edge"  # edge, elevenlabs
    voice: str = "en-US-ChristopherNeural"
    api_key: str = ""


class PublishConfig(BaseModel):
    enabled: bool = False
    platforms: list[str] = ["tiktok", "youtube", "instagram"]
    tiktok_access_token: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""


class SchedulerConfig(BaseModel):
    enabled: bool = False
    cron: str = "0 2 * * *"  # daily at 2am
    topics_file: str = ""
    auto_generate_topics: bool = True


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    gpu_backend: GPUBackendConfig = GPUBackendConfig()
    tts: TTSConfig = TTSConfig()
    publish: PublishConfig = PublishConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    output_dir: str = "storage/outputs"
    aspect_ratio: str = "9:16"  # 9:16, 16:9


def load_config(path: str | Path = "config/config.toml") -> Config:
    """Load configuration from TOML file."""
    config_path = Path(path)
    if not config_path.exists():
        return Config()
    data: dict[str, Any] = tomllib.loads(config_path.read_text())
    return Config(**data)
