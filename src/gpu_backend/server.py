"""GPU Backend — FastAPI HTTP server wrapping Modal functions.

This is a standalone HTTP server that can be used with any GPU provider
(RunPod, self-hosted, etc.) as an alternative to Modal's native deployment.
"""

from __future__ import annotations

import base64
import io
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Flow GPU Backend", version="0.1.0")

# Global pipeline references (loaded on startup)
_t2v_pipeline = None
_i2v_pipeline = None


class T2VRequest(BaseModel):
    prompt: str
    resolution: str = "480p"
    duration: int = 5
    num_inference_steps: int = 30


class I2VRequest(BaseModel):
    prompt: str
    first_frame: str  # base64 encoded image
    resolution: str = "480p"
    duration: int = 5
    num_inference_steps: int = 30


class GenerationResponse(BaseModel):
    job_id: str
    video_url: str
    last_frame_url: str


@app.on_event("startup")
async def load_models():
    """Load models on server startup."""
    global _t2v_pipeline, _i2v_pipeline
    import torch
    from diffusers import WanPipeline

    device = "cuda"
    dtype = torch.float16

    _t2v_pipeline = WanPipeline.from_pretrained(
        "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
        torch_dtype=dtype,
    ).to(device)

    _i2v_pipeline = WanPipeline.from_pretrained(
        "Wan-AI/Wan2.2-I2V-A14B-Diffusers",
        torch_dtype=dtype,
    ).to(device)


@app.get("/health")
async def health():
    return {"status": "ok", "model": "Wan2.2-14B"}


@app.post("/generate/t2v", response_model=GenerationResponse)
async def generate_t2v(req: T2VRequest):
    """Generate video from text prompt."""
    if _t2v_pipeline is None:
        raise HTTPException(503, "Model not loaded")

    import torch

    height, width = _resolution_to_dims(req.resolution)
    num_frames = req.duration * 16

    with torch.inference_mode():
        output = _t2v_pipeline(
            prompt=req.prompt,
            height=height,
            width=width,
            num_frames=num_frames,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=5.0,
        )

    return _save_and_respond(output)


@app.post("/generate/i2v", response_model=GenerationResponse)
async def generate_i2v(req: I2VRequest):
    """Generate video from first frame + prompt."""
    if _i2v_pipeline is None:
        raise HTTPException(503, "Model not loaded")

    import torch
    from PIL import Image

    height, width = _resolution_to_dims(req.resolution)
    num_frames = req.duration * 16

    image_data = base64.b64decode(req.first_frame)
    first_frame = Image.open(io.BytesIO(image_data)).convert("RGB")
    first_frame = first_frame.resize((width, height))

    with torch.inference_mode():
        output = _i2v_pipeline(
            prompt=req.prompt,
            image=first_frame,
            height=height,
            width=width,
            num_frames=num_frames,
            num_inference_steps=req.num_inference_steps,
            guidance_scale=5.0,
        )

    return _save_and_respond(output)


def _save_and_respond(output) -> GenerationResponse:
    """Save output and return response with file URLs."""
    from diffusers.utils import export_to_video
    from PIL import Image

    job_id = str(uuid.uuid4())
    output_dir = Path("/tmp/flow_outputs")
    output_dir.mkdir(exist_ok=True)

    # Save video
    video_path = output_dir / f"{job_id}.mp4"
    export_to_video(output.frames[0], str(video_path), fps=16)

    # Save last frame
    last_frame = output.frames[0][-1]
    if not isinstance(last_frame, Image.Image):
        last_frame = Image.fromarray(last_frame)
    last_frame_path = output_dir / f"{job_id}_last.png"
    last_frame.save(str(last_frame_path))

    return GenerationResponse(
        job_id=job_id,
        video_url=f"/files/{job_id}.mp4",
        last_frame_url=f"/files/{job_id}_last.png",
    )


def _resolution_to_dims(resolution: str) -> tuple[int, int]:
    resolutions = {
        "480p": (480, 832),
        "720p": (720, 1280),
    }
    return resolutions.get(resolution, (480, 832))
