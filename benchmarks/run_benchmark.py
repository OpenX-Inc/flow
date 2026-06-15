"""
OpenX Flow Benchmark — Wan 2.2 TI2V-5B on Modal A100.

Generates a video clip from a brand image + prompt.
Records timing and saves the output.

Usage:
    modal run benchmarks/run_benchmark.py
"""

import json
import time
from pathlib import Path

import modal

app = modal.App("openx-flow-benchmark")

wan_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.6.0",
        "torchvision",
        "diffusers>=0.33.0",
        "transformers>=4.49.0",
        "accelerate>=1.4.0",
        "sentencepiece",
        "imageio[ffmpeg]",
        "Pillow",
        "numpy",
        "ftfy",
    )
)


@app.function(
    image=wan_image,
    gpu="A100-40GB",
    timeout=900,
    memory=32768,
)
def generate_clip(prompt: str, first_frame_bytes: bytes | None = None) -> dict:
    """Generate a single 5s clip with Wan 2.2 TI2V-5B."""
    import torch
    import imageio
    import numpy as np
    import io
    from PIL import Image

    t_start = time.time()

    from diffusers import WanImageToVideoPipeline, WanPipeline

    if first_frame_bytes:
        pipe = WanImageToVideoPipeline.from_pretrained(
            "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
            torch_dtype=torch.float16,
        )
        pipe.to("cuda")

        image = Image.open(io.BytesIO(first_frame_bytes)).convert("RGB").resize((832, 480))
        t_load = time.time()

        output = pipe(
            image=image,
            prompt=prompt,
            num_frames=81,
            guidance_scale=5.0,
            num_inference_steps=30,
        )
    else:
        pipe = WanPipeline.from_pretrained(
            "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
            torch_dtype=torch.float16,
        )
        pipe.to("cuda")
        t_load = time.time()

        output = pipe(
            prompt=prompt,
            num_frames=81,
            guidance_scale=5.0,
            num_inference_steps=30,
            height=480,
            width=832,
        )

    t_gen = time.time()

    # Export frames to mp4
    frames = output.frames[0]
    buf = io.BytesIO()
    writer = imageio.get_writer(buf, format="mp4", fps=16, codec="libx264")
    for frame in frames:
        writer.append_data(np.array(frame))
    writer.close()
    video_bytes = buf.getvalue()

    t_end = time.time()

    return {
        "model_load_time": round(t_load - t_start, 1),
        "generation_time": round(t_gen - t_load, 1),
        "export_time": round(t_end - t_gen, 1),
        "total_time": round(t_end - t_start, 1),
        "num_frames": 81,
        "video_size_kb": round(len(video_bytes) / 1024, 1),
        "video_bytes": video_bytes,
    }


@app.local_entrypoint()
def main():
    """Run benchmark: 1 scene to prove the pipeline works."""
    prompts_file = Path("benchmarks/prompts/openx-intro-15s.json")
    results_dir = Path("benchmarks/results")
    samples_dir = results_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    with open(prompts_file) as f:
        config = json.load(f)

    scene = config["scenes"][0]

    print("🎬 OpenX Flow Benchmark")
    print(f"   Model: Wan2.2-TI2V-5B")
    print(f"   Resolution: 832x480")
    print(f"   Frames: 81 (5s @ 16fps)")
    print(f"   Steps: 30")
    print(f"   Scene: {scene['type'].upper()}")
    print(f"   Prompt: {scene['prompt'][:60]}...")
    print()

    first_frame_bytes = None
    if scene.get("first_frame"):
        frame_path = Path("benchmarks") / scene["first_frame"]
        if frame_path.exists():
            first_frame_bytes = frame_path.read_bytes()
            print(f"   First frame: {frame_path} ({len(first_frame_bytes)//1024}KB)")

    print()
    print("⏳ Starting generation (this includes cold start + model download)...")
    t_wall_start = time.time()

    result = generate_clip.remote(
        prompt=scene["prompt"],
        first_frame_bytes=first_frame_bytes,
    )

    t_wall_end = time.time()
    wall_time = round(t_wall_end - t_wall_start, 1)

    # Save video
    video_path = samples_dir / "scene_1_i2v.mp4"
    video_path.write_bytes(result["video_bytes"])

    # Save metrics
    metrics = {
        "model": "Wan2.2-TI2V-5B",
        "gpu": "A100-40GB",
        "resolution": "832x480",
        "num_frames": 81,
        "fps": 16,
        "inference_steps": 30,
        "type": scene["type"],
        "prompt": scene["prompt"],
        "model_load_time_s": result["model_load_time"],
        "generation_time_s": result["generation_time"],
        "export_time_s": result["export_time"],
        "total_gpu_time_s": result["total_time"],
        "wall_clock_time_s": wall_time,
        "video_size_kb": result["video_size_kb"],
        "estimated_cost_usd": round(wall_time / 3600 * 1.90, 4),
    }

    metrics_path = results_dir / "benchmark-results.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"✓ Video saved: {video_path} ({result['video_size_kb']:.0f} KB)")
    print()
    print("📊 Results:")
    print(f"   Model load:   {result['model_load_time']}s")
    print(f"   Generation:   {result['generation_time']}s")
    print(f"   Export:       {result['export_time']}s")
    print(f"   Total (GPU):  {result['total_time']}s")
    print(f"   Wall clock:   {wall_time}s")
    print(f"   Est. cost:    ${metrics['estimated_cost_usd']:.4f}")
