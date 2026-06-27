"""Real generation service — calls the Modal GPU backend for video and edge-tts
for narration, writes real media files, and reports back URLs.

No mocks: ``generate_video`` POSTs to the deployed Modal endpoints
(``https://{workspace}--{label}.modal.run``) and decodes the returned MP4;
``generate_narration`` synthesizes speech with edge-tts (CPU, free). Output files
land under ``FLOW_MEDIA_DIR`` and are exposed at ``FLOW_MEDIA_BASE_URL``.
"""

from __future__ import annotations

import asyncio
import base64
import os
import uuid
from pathlib import Path

import httpx

WORKSPACE = os.environ.get("FLOW_MODAL_WORKSPACE", "stanlinktechhub")
MEDIA_DIR = Path(os.path.expanduser(os.environ.get("FLOW_MEDIA_DIR", "~/.flow/media")))
MEDIA_BASE_URL = os.environ.get("FLOW_MEDIA_BASE_URL", "").rstrip("/")
DEFAULT_VOICE = os.environ.get("FLOW_TTS_VOICE", "en-US-AriaNeural")

_LABELS = {"t2v": "t2v", "i2v": "i2v", "flf2v": "flf2v", "vace": "vace"}


class GenerationError(RuntimeError):
    pass


class GenerationService:
    def __init__(self, workspace: str = WORKSPACE, timeout: float = 900.0) -> None:
        self.workspace = workspace
        self.timeout = timeout
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    def _endpoint(self, label: str) -> str:
        return f"https://{self.workspace}--{label}.modal.run"

    def _url_for(self, path: Path) -> str:
        return f"{MEDIA_BASE_URL}/{path.name}" if MEDIA_BASE_URL else str(path)

    def health(self) -> bool:
        try:
            with httpx.Client(timeout=20) as c:
                return c.get(self._endpoint("health")).status_code == 200
        except httpx.HTTPError:
            return False

    def generate_video(self, prompt: str, *, mode: str = "t2v", resolution: str = "480p",
                       duration_s: int = 5, first_frame_b64: str | None = None,
                       reference_b64: str | None = None) -> dict:
        """Call Modal, decode the MP4 + last frame, write files, return URLs."""
        label = _LABELS.get(mode, "t2v")
        payload: dict = {"prompt": prompt, "resolution": resolution, "duration": duration_s}
        if first_frame_b64:
            payload["first_frame_b64"] = first_frame_b64
        if reference_b64:
            payload["reference_b64"] = reference_b64
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(self._endpoint(label), json=payload)
            r.raise_for_status()
            data = r.json()
        if "error" in data:
            raise GenerationError(data["error"])
        if "video_b64" not in data:
            raise GenerationError("backend returned no video")
        vid = MEDIA_DIR / f"{uuid.uuid4().hex}.mp4"
        vid.write_bytes(base64.b64decode(data["video_b64"]))
        out = {"video_url": self._url_for(vid), "video_path": str(vid)}
        if data.get("last_frame_b64"):
            frame = MEDIA_DIR / f"{vid.stem}_last.png"
            frame.write_bytes(base64.b64decode(data["last_frame_b64"]))
            out["last_frame_url"] = self._url_for(frame)
        return out

    def generate_narration(self, text: str, voice: str | None = None) -> dict:
        """Synthesize narration with edge-tts; returns the audio URL/path."""
        import edge_tts

        out = MEDIA_DIR / f"{uuid.uuid4().hex}.mp3"

        async def _run() -> None:
            await edge_tts.Communicate(text, voice or DEFAULT_VOICE).save(str(out))

        asyncio.run(_run())
        if not out.exists() or out.stat().st_size == 0:
            raise GenerationError("edge-tts produced no audio")
        return {"audio_url": self._url_for(out), "audio_path": str(out)}
