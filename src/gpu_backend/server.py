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
    video_b64: str
    last_frame_b64: str


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
    """Save output and return it as base64 (matches the Modal backend contract).

    Serverless/ephemeral containers can't reliably serve files back, so the
    unified contract returns the assets inline as base64 — the ``flow.Generator``
    consumer decodes them directly.
    """
    import tempfile

    from diffusers.utils import export_to_video
    from PIL import Image

    job_id = str(uuid.uuid4())
    output_dir = Path(tempfile.mkdtemp(prefix="flow_outputs_"))

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
        video_b64=base64.b64encode(video_path.read_bytes()).decode(),
        last_frame_b64=base64.b64encode(last_frame_path.read_bytes()).decode(),
    )


class TTSRequest(BaseModel):
    text: str
    model: str = "MisoLabs/MisoTTS"
    precision: str = "int8"
    voice_sample: str = ""  # base64 audio for cloning
    voice_transcript: str = ""


class TTSResponse(BaseModel):
    audio_b64: str


@app.post("/tts/generate", response_model=TTSResponse)
async def generate_tts(req: TTSRequest):
    """Generate speech using MisoTTS 8B."""
    import base64
    import tempfile

    import torchaudio
    from generator import Segment, load_miso_8b

    device = "cuda"
    generator = load_miso_8b(device=device, model_path_or_repo_id=req.model)

    context: list = []
    if req.voice_sample:
        audio_bytes = base64.b64decode(req.voice_sample)
        tmp = Path(tempfile.mktemp(suffix=".wav"))
        tmp.write_bytes(audio_bytes)
        ref_audio, sr = torchaudio.load(str(tmp))
        if sr != generator.sample_rate:
            ref_audio = torchaudio.functional.resample(
                ref_audio, sr, generator.sample_rate
            )
        context = [Segment(text=req.voice_transcript, audio=ref_audio.squeeze())]
        tmp.unlink()

    audio = generator.generate(
        text=req.text,
        context=context,
        max_audio_length_ms=len(req.text) * 100,
    )

    out_path = Path(tempfile.mktemp(suffix=".wav"))
    torchaudio.save(str(out_path), audio.unsqueeze(0).cpu(), generator.sample_rate)
    audio_b64 = base64.b64encode(out_path.read_bytes()).decode()
    out_path.unlink()

    return TTSResponse(audio_b64=audio_b64)


def _resolution_to_dims(resolution: str) -> tuple[int, int]:
    resolutions = {
        "480p": (480, 832),
        "720p": (720, 1280),
    }
    return resolutions.get(resolution, (480, 832))
