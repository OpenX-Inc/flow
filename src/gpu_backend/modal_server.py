"""GPU Backend — Wan 2.2 inference server for Modal deployment."""

from __future__ import annotations

import base64
import io
import tempfile
import uuid
from pathlib import Path

import modal

app = modal.App("flow-gpu-backend")

# Model weights volume (persistent storage for downloaded weights)
volume = modal.Volume.from_name("flow-model-weights", create_if_missing=True)

# Container image with all dependencies
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

# Separate, lighter image for voice cloning (no diffusers; Coqui XTTS-v2)
voice_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("ffmpeg")
    .pip_install("coqui-tts", "fastapi[standard]", "torch>=2.6.0")
    .env({"COQUI_TOS_AGREED": "1"})
)

MODEL_T2V = "Wan-AI/Wan2.2-T2V-A14B-Diffusers"
MODEL_I2V = "Wan-AI/Wan2.2-I2V-A14B-Diffusers"
MODEL_VACE = "Wan-AI/Wan2.1-VACE-14B-diffusers"


@app.cls(
    image=image,
    gpu="A100-80GB",
    volumes={"/models": volume},
    timeout=900,
    scaledown_window=300,
)
class WanServer:
    """Wan 2.2 inference server running on Modal."""

    @modal.enter()
    def load_models(self):
        """Load models on container startup."""
        import torch
        from diffusers import WanPipeline

        self.device = "cuda"
        self.dtype = torch.float16

        # Load T2V pipeline (primary — used for most generation)
        self.t2v = WanPipeline.from_pretrained(
            MODEL_T2V,
            torch_dtype=self.dtype,
            cache_dir="/models",
        ).to(self.device)

        # I2V loaded lazily on first use (can't fit both in 80GB simultaneously)
        self._i2v = None

    @property
    def i2v(self):
        if self._i2v is None:
            import torch
            from diffusers import WanPipeline

            # Offload T2V to CPU to make room
            self.t2v.to("cpu")
            torch.cuda.empty_cache()

            self._i2v = WanPipeline.from_pretrained(
                MODEL_I2V,
                torch_dtype=self.dtype,
                cache_dir="/models",
            ).to(self.device)
        return self._i2v

    @modal.fastapi_endpoint(method="POST", label="t2v")
    def generate_t2v_endpoint(self, body: dict) -> dict:
        """HTTP endpoint: text-to-video."""
        return self._generate_t2v(
            prompt=body["prompt"],
            resolution=body.get("resolution", "480p"),
            duration=body.get("duration", 5),
        )

    @modal.fastapi_endpoint(method="POST", label="i2v")
    def generate_i2v_endpoint(self, body: dict) -> dict:
        """HTTP endpoint: image-to-video."""
        return self._generate_i2v(
            prompt=body["prompt"],
            first_frame_b64=body["first_frame_b64"],
            resolution=body.get("resolution", "480p"),
            duration=body.get("duration", 5),
        )

    @modal.fastapi_endpoint(method="POST", label="flf2v")
    def generate_flf2v_endpoint(self, body: dict) -> dict:
        """HTTP endpoint: first-last-frame to video (scene chaining).

        Conditions on a first frame (and optional last frame) for temporal
        continuity. Uses the I2V pipeline with the first frame as the anchor.
        """
        return self._generate_i2v(
            prompt=body["prompt"],
            first_frame_b64=body["first_frame_b64"],
            resolution=body.get("resolution", "480p"),
            duration=body.get("duration", 5),
        )

    @modal.fastapi_endpoint(method="POST", label="vace")
    def generate_vace_endpoint(self, body: dict) -> dict:
        """HTTP endpoint: Wan VACE — reference/edit/compose to video.

        Best-effort: lazily loads WanVACEPipeline. Isolated from t2v/i2v so a
        VACE/diffusers version mismatch never affects the proven paths.
        """
        try:
            return self._generate_vace(
                prompt=body["prompt"],
                reference_b64=body.get("reference_b64") or body.get("first_frame_b64"),
                resolution=body.get("resolution", "480p"),
                duration=body.get("duration", 5),
            )
        except Exception as e:  # noqa: BLE001
            return {"error": f"VACE unavailable: {e}"}

    @modal.fastapi_endpoint(method="GET", label="health")
    def health_endpoint(self) -> dict:
        """Health check endpoint."""
        return {"status": "ok", "model": "Wan2.2-14B", "endpoints": ["t2v", "i2v", "flf2v", "vace"]}

    def _generate_t2v(
        self,
        prompt: str,
        resolution: str = "480p",
        duration: int = 5,
        num_inference_steps: int = 30,
    ) -> dict:
        """Generate video from text prompt."""
        import torch

        height, width = _resolution_to_dims(resolution)
        num_frames = duration * 16  # 16 fps

        with torch.inference_mode():
            output = self.t2v(
                prompt=prompt,
                height=height,
                width=width,
                num_frames=num_frames,
                num_inference_steps=num_inference_steps,
                guidance_scale=5.0,
            )

        return self._save_output(output)

    def _generate_i2v(
        self,
        prompt: str,
        first_frame_b64: str,
        resolution: str = "480p",
        duration: int = 5,
        num_inference_steps: int = 30,
    ) -> dict:
        """Generate video from first frame + prompt."""
        import torch
        from PIL import Image

        height, width = _resolution_to_dims(resolution)
        num_frames = duration * 16

        # Decode first frame
        image_data = base64.b64decode(first_frame_b64)
        first_frame = Image.open(io.BytesIO(image_data)).convert("RGB")
        first_frame = first_frame.resize((width, height))

        with torch.inference_mode():
            output = self.i2v(
                prompt=prompt,
                image=first_frame,
                height=height,
                width=width,
                num_frames=num_frames,
                num_inference_steps=num_inference_steps,
                guidance_scale=5.0,
            )

        return self._save_output(output)

    def _generate_vace(
        self,
        prompt: str,
        reference_b64: str | None,
        resolution: str = "480p",
        duration: int = 5,
        num_inference_steps: int = 30,
    ) -> dict:
        """Generate/edit video with Wan VACE (reference-driven composition)."""
        import torch
        from diffusers import WanVACEPipeline
        from PIL import Image

        if getattr(self, "_vace", None) is None:
            self.t2v.to("cpu")
            if self._i2v is not None:
                self._i2v.to("cpu")
            torch.cuda.empty_cache()
            self._vace = WanVACEPipeline.from_pretrained(
                MODEL_VACE, torch_dtype=self.dtype, cache_dir="/models"
            ).to(self.device)

        height, width = _resolution_to_dims(resolution)
        num_frames = duration * 16
        kwargs = dict(
            prompt=prompt, height=height, width=width,
            num_frames=num_frames, num_inference_steps=num_inference_steps,
        )
        if reference_b64:
            ref = Image.open(io.BytesIO(base64.b64decode(reference_b64))).convert("RGB").resize((width, height))
            kwargs["reference_images"] = [ref]
        with torch.inference_mode():
            output = self._vace(**kwargs)
        return self._save_output(output)

    def _save_output(self, output) -> dict:
        """Save generated video and extract last frame."""
        from diffusers.utils import export_to_video
        from PIL import Image

        job_id = str(uuid.uuid4())
        tmp_dir = Path(tempfile.mkdtemp())

        # Save video
        video_path = tmp_dir / f"{job_id}.mp4"
        export_to_video(output.frames[0], str(video_path), fps=16)

        # Extract last frame
        last_frame = output.frames[0][-1]
        if not isinstance(last_frame, Image.Image):
            last_frame = Image.fromarray(last_frame)
        last_frame_path = tmp_dir / f"{job_id}_last.png"
        last_frame.save(str(last_frame_path))

        # Encode outputs as base64
        video_b64 = base64.b64encode(
            video_path.read_bytes()
        ).decode()
        last_frame_b64 = base64.b64encode(
            last_frame_path.read_bytes()
        ).decode()

        return {
            "job_id": job_id,
            "video_b64": video_b64,
            "last_frame_b64": last_frame_b64,
        }


def _resolution_to_dims(resolution: str) -> tuple[int, int]:
    """Convert resolution string to (height, width)."""
    resolutions = {
        "480p": (480, 832),
        "720p": (720, 1280),
    }
    return resolutions.get(resolution, (480, 832))
