"""Deployers — push the GPU backend to a provider as a NAMED instance.

A token/API key alone can't generate video: the open-source GPU backend
(``gpu_backend/modal_server.py``) must be *deployed* into the target account,
which produces the thing jobs actually route to — an **endpoint URL**. These
deployers do that deployment, parameterized by a :class:`DeploySpec` (from CLI
args and/or the config file), so you can stand up several named instances
(e.g. an A100 pool and an H100 pool) and register their URLs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DeploySpec:
    """What to deploy, and how. Defaults mirror the config example."""

    name: str = "flow-gpu-backend"
    gpu: str = "A100-80GB"
    model_t2v: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers"
    model_i2v: str = "Wan-AI/Wan2.2-I2V-A14B-Diffusers"
    region: str = ""
    scaledown_window: int = 300
    # Provider credentials passed *per invocation* (e.g. Modal token_id/secret).
    # Deployers inject these into the deploy subprocess's env only — never the
    # ambient process env — so a shared host can deploy for many accounts
    # concurrently without leaking tokens between deploys.
    credentials: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)


@dataclass
class DeployResult:
    """Outcome of a deploy. ``status`` is honest about what happened."""

    name: str
    provider: str
    status: str  # "deployed" | "manual_required" | "failed"
    endpoint_url: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "deployed"


class Deployer(ABC):
    """Interface for provider deployers."""

    provider: str = "base"

    @abstractmethod
    def deploy(self, spec: DeploySpec) -> DeployResult:
        """Deploy the GPU backend; return where it landed (or honest guidance)."""
        ...


_REGISTRY: dict[str, type[Deployer]] = {}


def register(cls: type[Deployer]) -> type[Deployer]:
    _REGISTRY[cls.provider] = cls
    return cls


def get_deployer(provider: str) -> Deployer:
    cls = _REGISTRY.get(provider)
    if cls is None:
        raise ValueError(
            f"unknown provider {provider!r}; available: {sorted(_REGISTRY)}"
        )
    return cls()


def available_providers() -> list[str]:
    return sorted(_REGISTRY)
