"""
OpenX Flow — Scene Chaining Demo (T2V only, 14B)

Generates 3 scenes with Wan 2.2 T2V-A14B on a single Modal A100.
All scenes generated in one function call to avoid multiple cold starts.

Usage:
    modal run benchmarks/run_chaining_demo.py
"""

import json
import time
from pathlib import Path

import modal

app = modal.App("openx-flow-chaining-demo")

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
    timeout=1200,
    memory=32768,
)
def generate_all_scenes(prompts: list[str], steps: int = 40) -> list[dict]:
    """Generate multiple scenes sequentially on the same GPU."""
    import torch
    import imageio
    import numpy as np
    import io
    from diffusers import WanPipeline

    t_start = time.time()
    print("Loading Wan2.2-TI2V-5B...")

    pipe = WanPipeline.from_pretrained(
        "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
        torch_dtype=torch.float16,
    )
    pipe.to("cuda")

    t_load = time.time()
    print(f"Model loaded in {t_load - t_start:.1f}s")

    results = []
    for i, prompt in enumerate(prompts):
        t_gen_start = time.time()
        print(f"\n▶ Scene {i+1}/{len(prompts)}")
        print(f"  {prompt[:80]}...")

        output = pipe(
            prompt=prompt,
            num_frames=81,
            guidance_scale=5.0,
            num_inference_steps=steps,
            height=480,
            width=832,
        )

        t_gen_end = time.time()

        frames = output.frames[0]
        buf = io.BytesIO()
        writer = imageio.get_writer(buf, format="mp4", fps=16, codec="libx264")
        for frame in frames:
            arr = np.array(frame)
            if arr.dtype != np.uint8:
                arr = (arr * 255).clip(0, 255).astype(np.uint8)
            writer.append_data(arr)
        writer.close()

        gen_time = round(t_gen_end - t_gen_start, 1)
        results.append({
            "scene_id": i + 1,
            "generation_time": gen_time,
            "video_bytes": buf.getvalue(),
        })
        print(f"  ✓ Done in {gen_time}s ({len(buf.getvalue())//1024}KB)")

    return results


@app.local_entrypoint()
def main():
    prompts_file = Path("benchmarks/prompts/water-chaining-demo.json")
    results_dir = Path("benchmarks/results")
    samples_dir = results_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    with open(prompts_file) as f:
        config = json.load(f)

    prompts = [s["prompt"] for s in config["scenes"]]

    print(f"🎬 OpenX Flow — Scene Chaining Demo")
    print(f"   Title: {config['title']}")
    print(f"   Scenes: {len(prompts)}")
    print(f"   Model: Wan2.2-TI2V-5B")
    print(f"   Steps: {config['inference_steps']}")
    print(f"   Resolution: 832x480, 81 frames, 16fps")
    print()

    t_start = time.time()
    results = generate_all_scenes.remote(prompts, steps=config["inference_steps"])
    t_end = time.time()
    wall_time = round(t_end - t_start, 1)

    total_gen = 0
    for r in results:
        path = samples_dir / f"water_scene_{r['scene_id']}.mp4"
        path.write_bytes(r["video_bytes"])
        total_gen += r["generation_time"]
        print(f"✓ Scene {r['scene_id']}: {path.name} ({len(r['video_bytes'])//1024}KB, {r['generation_time']}s)")

    metrics = {
        "title": config["title"],
        "model": "Wan2.2-TI2V-5B",
        "gpu": "A100-40GB",
        "resolution": "832x480",
        "num_frames_per_scene": 81,
        "fps": 16,
        "inference_steps": config["inference_steps"],
        "scenes": len(prompts),
        "total_generation_time_s": round(total_gen, 1),
        "wall_clock_time_s": wall_time,
        "estimated_cost_usd": round(wall_time / 3600 * 1.90, 4),
        "per_scene": [{"scene_id": r["scene_id"], "generation_time_s": r["generation_time"], "size_kb": len(r["video_bytes"])//1024} for r in results],
    }

    with open(results_dir / "chaining-demo-results.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print()
    print(f"📊 Results:")
    print(f"   Total gen time:  {total_gen:.1f}s")
    print(f"   Wall clock:      {wall_time}s")
    print(f"   Est. cost:       ${metrics['estimated_cost_usd']:.4f}")
    print(f"   Per clip (warm): ~{total_gen/3:.0f}s = ~${total_gen/3/3600*1.90:.3f}")
