"""NVIDIA build API client (OpenAI-compatible chat completions + model listing).

Default model alias ``kimi`` resolves to ``moonshotai/kimi-k2.6``. Reads the key
from ``FLOW_NVIDIA_API_KEY``.
"""

from __future__ import annotations

import json
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

    def chat_stream(self, messages: list[dict], tools: list[dict] | None = None,
                    temperature: float = 0.6, max_tokens: int = 4096):
        """Stream a chat-completions turn. Yields ``{"type":"content","text":...}``
        for each token delta, then one ``{"type":"final","message":{...}}`` with the
        fully assembled assistant message (content + any tool_calls). Lets callers
        type the reply out live instead of waiting for the whole response."""
        payload: dict = {
            "model": self.model, "messages": messages,
            "temperature": temperature, "max_tokens": max_tokens, "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        parts: list[str] = []
        tool_calls: dict[int, dict] = {}
        with httpx.Client(timeout=self.timeout) as c:
            with c.stream("POST", f"{self.base_url}/chat/completions",
                          headers=self._headers(), json=payload) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        choice = json.loads(data)["choices"][0]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        parts.append(delta["content"])
                        yield {"type": "content", "text": delta["content"]}
                    for tc in (delta.get("tool_calls") or []):
                        idx = tc.get("index", 0)
                        slot = tool_calls.setdefault(
                            idx, {"id": "", "type": "function",
                                  "function": {"name": "", "arguments": ""}})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            slot["function"]["arguments"] += fn["arguments"]

        message: dict = {"role": "assistant", "content": "".join(parts)}
        if tool_calls:
            message["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
        yield {"type": "final", "message": message}
