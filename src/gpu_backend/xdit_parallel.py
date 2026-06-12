"""Multi-GPU video generation using xDiT sequence parallelism.

Supports AMD MI300X (ROCm) and NVIDIA (CUDA) multi-GPU setups.
Uses Unified Sequence Parallelism (USP) to split attention across GPUs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def generate_parallel(
    prompt: str,
    output_path: str,
    num_gpus: int = 8,
    resolution: str = "720p",
    num_frames: int = 81,
    num_inference_steps: int = 30,
    model_id: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
) -> Path:
    """Generate a video using xDiT sequence parallelism across GPUs.

    This enables longer clips and higher resolution by splitting the
    attention computation across multiple GPUs.
    """
    height, width = _resolution_to_dims(resolution)

    cmd = [
        "torchrun",
        f"--nproc_per_node={num_gpus}",
        "-m", "xdit.run",
        "--model", model_id,
        "--prompt", prompt,
        "--height", str(height),
        "--width", str(width),
        "--num_frames", str(num_frames),
        "--num_inference_steps", str(num_inference_steps),
        "--output", output_path,
        "--parallelism", "usp",  # Unified Sequence Parallelism
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"xDiT generation failed: {result.stderr[:500]}"
        )

    return Path(output_path)


def generate_batch_parallel(
    prompts: list[str],
    output_dir: str,
    num_gpus: int = 8,
    resolution: str = "480p",
) -> list[Path]:
    """Generate multiple clips in parallel (one per GPU).

    Each GPU runs an independent generation — no sequence parallelism,
    just concurrent jobs for maximum throughput.
    """
    import concurrent.futures

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=num_gpus
    ) as executor:
        futures = {}
        for i, prompt in enumerate(prompts):
            out = str(output_path / f"clip_{i:03d}.mp4")
            future = executor.submit(
                _generate_single_gpu,
                prompt=prompt,
                output_path=out,
                gpu_id=i % num_gpus,
                resolution=resolution,
            )
            futures[future] = out

        for future in concurrent.futures.as_completed(futures):
            results.append(Path(futures[future]))

    return sorted(results)


def _generate_single_gpu(
    prompt: str,
    output_path: str,
    gpu_id: int,
    resolution: str = "480p",
    model_id: str = "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
) -> None:
    """Run generation on a single specific GPU."""
    import os

    height, width = _resolution_to_dims(resolution)

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    # For AMD ROCm:
    env["HIP_VISIBLE_DEVICES"] = str(gpu_id)

    cmd = [
        "python", "-c", f"""
import torch
from diffusers import WanPipeline
from diffusers.utils import export_to_video

pipe = WanPipeline.from_pretrained(
    "{model_id}", torch_dtype=torch.float16
).to("cuda")

output = pipe(
    prompt="{prompt}",
    height={height},
    width={width},
    num_frames=81,
    num_inference_steps=30,
    guidance_scale=5.0,
)
export_to_video(output.frames[0], "{output_path}", fps=16)
""",
    ]

    subprocess.run(cmd, env=env, check=True, capture_output=True)


def _resolution_to_dims(resolution: str) -> tuple[int, int]:
    resolutions = {
        "480p": (480, 832),
        "720p": (720, 1280),
        "1080p": (1080, 1920),
    }
    return resolutions.get(resolution, (480, 832))
