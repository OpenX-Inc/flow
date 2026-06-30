"""GPU Backend — Wan 2.2 inference server for Modal deployment.

Deploys as a **single FastAPI ASGI app** with path-based routes
(``POST /generate/t2v|i2v|flf2v``, ``GET /health``) returning **base64** — the
same contract the self-hosted ``server.py`` and the ``flow.Generator`` consumer
use. One deployment = one base URL; no per-endpoint subdomains to stitch
together.

Parameterized via env so you can deploy several **named** instances into one
account (e.g. an A100 pool and an H100 pool, or one per tenant)::

    FLOW_GPU_APP_NAME=flow-gpu-a100 FLOW_GPU_TYPE=A100-80GB \
        modal deploy src/gpu_backend/modal_server.py

The deployed base URL is ``https://<workspace>--<app-name>.modal.run``. Point
``[gpu_backend].url`` (or a named compute instance) at it.
"""

from __future__ import annotations

import base64
import io
import os
import tempfile
import uuid
from pathlib import Path

import modal

# --- Parameterization (read at deploy/import time) ---------------------------
APP_NAME = os.environ.get("FLOW_GPU_APP_NAME", "flow-gpu-backend")
GPU_TYPE = os.environ.get("FLOW_GPU_TYPE", "A100-80GB")
MODEL_T2V = os.environ.get("FLOW_MODEL_T2V", "Wan-AI/Wan2.2-T2V-A14B-Diffusers")
MODEL_I2V = os.environ.get("FLOW_MODEL_I2V", "Wan-AI/Wan2.2-I2V-A14B-Diffusers")
SCALEDOWN_WINDOW = int(os.environ.get("FLOW_GPU_SCALEDOWN", "300"))

app = modal.App(APP_NAME)

# Model weights volume (persistent storage for downloaded weights), namespaced
# per instance so named deployments don't clobber each other.
volume = modal.Volume.from_name(f"{APP_NAME}-weights", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "torch>=2.6.0",
        "diffusers>=0.33.0",
        "transformers>=4.50.0",
        "accelerate>=1.5.0",
        "safetensors",
        "pillow",
        "fastapi[standard]",
        "numpy",
    )
    .apt_install("ffmpeg")
)


@app.cls(
    image=image,
    gpu=GPU_TYPE,
    volumes={"/models": volume},
    timeout=900,
    scaledown_window=SCALEDOWN_WINDOW,
)
class WanServer:
    """Wan 2.2 inference server — serves one base64 HTTP contract on Modal."""

    @modal.enter()
    def load_models(self):
        """Load the T2V pipeline on container startup; I2V/VACE load lazily."""
        import torch
        from diffusers import WanPipeline

        self.device = "cuda"
        self.dtype = torch.float16
        self.t2v = WanPipeline.from_pretrained(
            MODEL_T2V, torch_dtype=self.dtype, cache_dir="/models"
        ).to(self.device)
        self._i2v = None
        self._vace = None

    @property
    def i2v(self):
        if self._i2v is None:
            import torch
            from diffusers import WanPipeline

            # Offload T2V to CPU to make room (both can't fit in 80GB at once).
            self.t2v.to("cpu")
            torch.cuda.empty_cache()
            self._i2v = WanPipeline.from_pretrained(
                MODEL_I2V, torch_dtype=self.dtype, cache_dir="/models"
            ).to(self.device)
        return self._i2v

    @modal.asgi_app(label=APP_NAME)
    def web(self):
        """Single FastAPI app: path-based routes, base64 responses."""
        from fastapi import FastAPI, HTTPException

        api = FastAPI(title="Flow GPU Backend", version="0.2.0")

        @api.get("/health")
        def health() -> dict:
            return {
                "status": "ok",
                "model": "Wan2.2-14B",
                "app": APP_NAME,
                "endpoints": ["t2v", "i2v", "flf2v"],
            }

        @api.post("/generate/t2v")
        def t2v(body: dict) -> dict:
            if not body.get("prompt"):
                raise HTTPException(400, "prompt is required")
            return self._generate_t2v(
                prompt=body["prompt"],
                resolution=body.get("resolution", "480p"),
                duration=body.get("duration", 5),
            )

        @api.post("/generate/i2v")
        def i2v(body: dict) -> dict:
            first = body.get("first_frame") or body.get("first_frame_b64")
            if not body.get("prompt") or not first:
                raise HTTPException(400, "prompt and first_frame are required")
            return self._generate_i2v(
                prompt=body["prompt"],
                first_frame_b64=first,
                resolution=body.get("resolution", "480p"),
                duration=body.get("duration", 5),
            )

        # FLF2V conditions on a first frame (last-frame anchoring is best-effort
        # via the I2V pipeline) — same handler, kept as a distinct route so the
        # contract matches the t2v/i2v/flf2v vocabulary callers expect.
        api.post("/generate/flf2v")(i2v)

        return api

    def _generate_t2v(
        self, prompt: str, resolution: str = "480p", duration: int = 5,
        num_inference_steps: int = 30,
    ) -> dict:
        import torch

        height, width = _resolution_to_dims(resolution)
        with torch.inference_mode():
            output = self.t2v(
                prompt=prompt, height=height, width=width,
                num_frames=duration * 16, num_inference_steps=num_inference_steps,
                guidance_scale=5.0,
            )
        return self._save_output(output)

    def _generate_i2v(
        self, prompt: str, first_frame_b64: str, resolution: str = "480p",
        duration: int = 5, num_inference_steps: int = 30,
    ) -> dict:
        import torch
        from PIL import Image

        height, width = _resolution_to_dims(resolution)
        image_data = base64.b64decode(first_frame_b64)
        first_frame = Image.open(io.BytesIO(image_data)).convert("RGB")
        first_frame = first_frame.resize((width, height))
        with torch.inference_mode():
            output = self.i2v(
                prompt=prompt, image=first_frame, height=height, width=width,
                num_frames=duration * 16, num_inference_steps=num_inference_steps,
                guidance_scale=5.0,
            )
        return self._save_output(output)

    def _save_output(self, output) -> dict:
        """Save generated video + last frame and return them as base64."""
        from diffusers.utils import export_to_video
        from PIL import Image

        job_id = str(uuid.uuid4())
        tmp_dir = Path(tempfile.mkdtemp())
        video_path = tmp_dir / f"{job_id}.mp4"
        export_to_video(output.frames[0], str(video_path), fps=16)

        last_frame = output.frames[0][-1]
        if not isinstance(last_frame, Image.Image):
            last_frame = Image.fromarray(last_frame)
        last_frame_path = tmp_dir / f"{job_id}_last.png"
        last_frame.save(str(last_frame_path))

        return {
            "job_id": job_id,
            "video_b64": base64.b64encode(video_path.read_bytes()).decode(),
            "last_frame_b64": base64.b64encode(last_frame_path.read_bytes()).decode(),
        }


def _resolution_to_dims(resolution: str) -> tuple[int, int]:
    """Convert resolution string to (height, width)."""
    return {"480p": (480, 832), "720p": (720, 1280)}.get(resolution, (480, 832))
