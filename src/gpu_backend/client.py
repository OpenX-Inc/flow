"""GPU Backend client abstraction — supports Modal, RunPod, self-hosted."""

from __future__ import annotations

from typing import Protocol

import httpx


class GPUBackend(Protocol):
    """Protocol for GPU backend implementations."""

    def generate_t2v(
        self, prompt: str, resolution: str, duration: int
    ) -> dict: ...

    def generate_i2v(
        self, prompt: str, first_frame_b64: str, resolution: str, duration: int
    ) -> dict: ...


class HTTPBackend:
    """Generic HTTP backend (works with self-hosted FastAPI server)."""

    def __init__(self, url: str, api_key: str = "") -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        h: dict[str, str] = {}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def generate_t2v(
        self, prompt: str, resolution: str = "480p", duration: int = 5
    ) -> dict:
        with httpx.Client(timeout=600) as client:
            resp = client.post(
                f"{self.url}/generate/t2v",
                json={
                    "prompt": prompt,
                    "resolution": resolution,
                    "duration": duration,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def generate_i2v(
        self,
        prompt: str,
        first_frame_b64: str,
        resolution: str = "480p",
        duration: int = 5,
    ) -> dict:
        with httpx.Client(timeout=600) as client:
            resp = client.post(
                f"{self.url}/generate/i2v",
                json={
                    "prompt": prompt,
                    "first_frame": first_frame_b64,
                    "resolution": resolution,
                    "duration": duration,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()


class ModalBackend:
    """Modal serverless backend — calls deployed Modal functions."""

    def __init__(self, url: str, api_key: str = "") -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        h: dict[str, str] = {}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def generate_t2v(
        self, prompt: str, resolution: str = "480p", duration: int = 5
    ) -> dict:
        with httpx.Client(timeout=900) as client:
            resp = client.post(
                f"{self.url}/generate_t2v",
                json={
                    "prompt": prompt,
                    "resolution": resolution,
                    "duration": duration,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def generate_i2v(
        self,
        prompt: str,
        first_frame_b64: str,
        resolution: str = "480p",
        duration: int = 5,
    ) -> dict:
        with httpx.Client(timeout=900) as client:
            resp = client.post(
                f"{self.url}/generate_i2v",
                json={
                    "prompt": prompt,
                    "first_frame_b64": first_frame_b64,
                    "resolution": resolution,
                    "duration": duration,
                },
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()


def create_backend(provider: str, url: str, api_key: str = "") -> GPUBackend:
    """Factory: create the appropriate backend client."""
    backends = {
        "modal": ModalBackend,
        "runpod": HTTPBackend,
        "self-hosted": HTTPBackend,
    }
    cls = backends.get(provider, HTTPBackend)
    return cls(url=url, api_key=api_key)
