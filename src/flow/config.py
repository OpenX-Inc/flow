"""Configuration management for Flow."""

from __future__ import annotations

import os
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
    provider: str = "edge"  # edge, miso, elevenlabs
    voice: str = "en-US-ChristopherNeural"
    api_key: str = ""
    miso_model: str = "MisoLabs/MisoTTS"
    miso_precision: str = "int8"  # bf16, int8, int4
    miso_endpoint: str = ""  # MisoTTS HTTP endpoint; falls back to gpu_backend.url
    voice_sample: str = ""  # path to reference audio for cloning
    voice_transcript: str = ""  # transcript of the voice sample


class PublishConfig(BaseModel):
    enabled: bool = False
    platforms: list[str] = ["tiktok", "youtube", "instagram", "facebook"]
    tiktok_access_token: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    # Meta (Instagram Reels + Facebook Page) — shared Graph API auth.
    meta_page_access_token: str = ""          # long-lived Page access token
    facebook_page_id: str = ""                # FB Page id (Facebook publishing)
    instagram_business_account_id: str = ""   # IG Business account id (IG publishing)
    meta_graph_version: str = "v21.0"


class SchedulerConfig(BaseModel):
    enabled: bool = False
    cron: str = "0 2 * * *"  # daily at 2am
    topics_file: str = ""
    auto_generate_topics: bool = True


class AgentConfig(BaseModel):
    """The in-app video agent (LLM that drives the tools)."""

    provider: str = "nvidia"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    api_key: str = ""  # falls back to FLOW_NVIDIA_API_KEY env
    model: str = "kimi"  # alias -> moonshotai/kimi-k2.6
    max_iterations: int = 12


class MCPConfig(BaseModel):
    """The MCP server that exposes the tools to external agents."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8765
    token: str = ""  # bearer; falls back to FLOW_MCP_TOKEN env


class BillingConfig(BaseModel):
    """Generation gating (credits/plan)."""

    can_generate: bool = True


class DeployConfig(BaseModel):
    """Defaults for ``flow deploy`` (deploy the GPU backend as a named instance)."""

    provider: str = "modal"  # modal, aws, gcp
    name: str = "flow-gpu-backend"  # instance name (deploy several, named)
    gpu: str = "A100-80GB"
    model_t2v: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers"
    model_i2v: str = "Wan-AI/Wan2.2-I2V-A14B-Diffusers"
    region: str = ""  # AWS/GCP
    scaledown_window: int = 300  # seconds idle before Modal scales to zero


class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    gpu_backend: GPUBackendConfig = GPUBackendConfig()
    tts: TTSConfig = TTSConfig()
    publish: PublishConfig = PublishConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    agent: AgentConfig = AgentConfig()
    mcp: MCPConfig = MCPConfig()
    billing: BillingConfig = BillingConfig()
    deploy: DeployConfig = DeployConfig()
    output_dir: str = "storage/outputs"
    aspect_ratio: str = "9:16"  # 9:16, 16:9
    generation_mode: str = "sequential"  # sequential, parallel_flf2v, pipelined_flf2v


def load_config(path: str | Path = "config/config.toml") -> Config:
    """Load configuration from TOML file with environment variable overrides."""
    config_path = Path(path)
    data: dict[str, Any] = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    cfg = Config(**data)

    # Environment variable overrides for AgentConfig
    if os.environ.get("FLOW_AGENT_PROVIDER"):
        cfg.agent.provider = os.environ["FLOW_AGENT_PROVIDER"]
    if os.environ.get("FLOW_AGENT_BASE_URL"):
        cfg.agent.base_url = os.environ["FLOW_AGENT_BASE_URL"]
    if os.environ.get("FLOW_AGENT_API_KEY"):
        cfg.agent.api_key = os.environ["FLOW_AGENT_API_KEY"]
    if os.environ.get("FLOW_AGENT_MODEL"):
        cfg.agent.model = os.environ["FLOW_AGENT_MODEL"]

    return cfg
