"""NVIDIA build API client (OpenAI-compatible chat completions + model listing).

Default model alias ``kimi`` resolves to ``moonshotai/kimi-k2.6``. Reads the key
from ``FLOW_NVIDIA_API_KEY``.
"""

from __future__ import annotations

import os

import httpx

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
MODEL_ALIASES = {"kimi": "moonshotai/kimi-k2.6"}


class NvidiaClient:
    def __init__(self, api_key: str | None = None, base_url: str = NVIDIA_BASE,
                 model: str = "kimi", timeout: float = 120.0) -> None:
        self.api_key = api_key or os.environ.get("FLOW_NVIDIA_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = MODEL_ALIASES.get(model, model)
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"}

    def list_models(self) -> list[str]:
        with httpx.Client(timeout=30) as c:
            r = c.get(f"{self.base_url}/models", headers=self._headers())
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             temperature: float = 0.6, max_tokens: int = 4096) -> dict:
        """One chat-completions turn. Returns the raw OpenAI-style response."""
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{self.base_url}/chat/completions", headers=self._headers(),
                       json=payload)
            r.raise_for_status()
            return r.json()
