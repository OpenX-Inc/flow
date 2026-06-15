"""
OpenX Flow — Full Benchmark Suite (5B model, optimized)

Tests:
1. Multi-scene T2V — 3 cinematic scenes (50 steps)
2. Steps comparison — 30 vs 50 steps (same prompt)
3. Multi-scene storytelling — 5 connected scenes

All using Wan2.2-TI2V-5B on A100-40GB for speed and cost efficiency.

Usage:
    modal run benchmarks/run_full_benchmark.py
"""

import json
import time
import io
from pathlib import Path

import modal

app = modal.App("openx-flow-full-benchmark")

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

# ─── Prompts ───────────────────────────────────────────────────────────────────

WATER_SCENES = [
    "Cinematic extreme close-up of a single water droplet falling in ultra slow motion against a pure black background. The droplet is perfectly spherical with visible internal caustic light refractions. Dramatic white rim lighting from the side. Shot on RED Komodo at 240fps, macro lens, razor-thin depth of field, photorealistic, no text, no watermark.",
    "Cinematic slow motion shot of a water droplet hitting a perfectly still dark reflective water surface. Beautiful concentric ripples expanding outward. A crown splash forming with tiny satellite droplets suspended in mid-air. Deep blue-black water, dramatic side lighting creating silver highlights on the ripples. Shot on Phantom Flex4K high-speed camera, photorealistic, no text.",
    "Breathtaking cinematic wide shot of a vast calm ocean at golden hour. Camera slowly dollies backward revealing the endless horizon. Gentle waves catch warm amber and deep violet light from the sunset. Volumetric god rays pierce through distant clouds. Atmospheric haze on the horizon. Shot on ARRI Alexa with anamorphic lens, subtle film grain, photorealistic, no text.",
]

STORY_SCENES = [
    "A lone astronaut in a white spacesuit walks across an endless red desert on Mars. Footprints trail behind in the fine rusty dust. The sky is a hazy salmon pink. Camera follows from behind at waist level. Cinematic slow steady tracking shot, shot on IMAX, photorealistic, volumetric dust particles catching sunlight, no text.",
    "The astronaut stops and looks up at the sky. Camera tilts up with them revealing Earth as a tiny blue dot among stars in the dusky Martian sky. Emotional moment of solitude. Warm golden light from the setting sun casts a long shadow. Cinematic medium shot, shallow depth of field on the visor reflection, photorealistic, no text.",
    "Close-up of the astronaut's gloved hand reaching down to pick up a small iridescent rock from the red soil. Dust particles float in the thin atmosphere catching the light. Careful deliberate movement. Cinematic macro shot, shallow depth of field, warm lighting, photorealistic, no text.",
    "The astronaut places the rock into a specimen container on their belt. Camera pulls back to reveal the vast empty Martian landscape stretching to the horizon. Wind picks up slightly, creating a thin veil of dust. Cinematic wide shot transitioning from close to wide, golden hour, photorealistic, no text.",
    "Final wide establishing shot looking down from a cliff edge. The tiny figure of the astronaut walks toward their lander in the distance, leaving a trail of footprints in the red sand. The sun sets behind distant mountains casting everything in deep orange. Cinematic aerial perspective, epic scale, photorealistic, film grain, no text.",
]


@app.function(image=wan_image, gpu="A100-40GB", timeout=2400, memory=32768)
def generate_scenes(prompts: list[str], steps: int = 50, label: str = "") -> dict:
    """Generate multiple scenes sequentially with Wan2.2-TI2V-5B."""
    import torch
    import imageio
    import numpy as np
    from diffusers import WanPipeline

    t_start = time.time()
    print(f"Loading Wan2.2-TI2V-5B... [{label}]")

    pipe = WanPipeline.from_pretrained(
        "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
        torch_dtype=torch.float16,
    )
    pipe.to("cuda")
    t_load = time.time()
    load_time = round(t_load - t_start, 1)
    print(f"Model loaded in {load_time}s")

    results = []
    for i, prompt in enumerate(prompts):
        t_gen_start = time.time()
        print(f"\n▶ [{label}] Scene {i+1}/{len(prompts)}: {prompt[:50]}...")

        output = pipe(
            prompt=prompt,
            num_frames=81,
            guidance_scale=5.0,
            num_inference_steps=steps,
            height=480,
            width=832,
        )
        t_gen_end = time.time()
        gen_time = round(t_gen_end - t_gen_start, 1)

        frames = output.frames[0]
        buf = io.BytesIO()
        writer = imageio.get_writer(buf, format="mp4", fps=16, codec="libx264")
        for frame in frames:
            arr = np.array(frame)
            if arr.dtype != np.uint8:
                arr = (arr * 255).clip(0, 255).astype(np.uint8)
            writer.append_data(arr)
        writer.close()

        results.append({
            "scene_id": i + 1,
            "generation_time": gen_time,
            "video_bytes": buf.getvalue(),
        })
        print(f"  ✓ Done in {gen_time}s ({len(buf.getvalue())//1024}KB)")

    total = time.time() - t_start
    return {"load_time": load_time, "total_time": round(total, 1), "scenes": results}


@app.local_entrypoint()
def main():
    results_dir = Path("benchmarks/results")
    samples_dir = results_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    all_metrics = {}
    t_suite_start = time.time()

    # ━━━ TEST 1: Water — 3 scenes, 50 steps ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("=" * 60)
    print("TEST 1: Water — 3 cinematic scenes (50 steps)")
    print("=" * 60)

    result = generate_scenes.remote(WATER_SCENES, steps=50, label="water-50")

    for s in result["scenes"]:
        path = samples_dir / f"water_scene_{s['scene_id']}_50steps.mp4"
        path.write_bytes(s["video_bytes"])
        print(f"  ✓ Scene {s['scene_id']}: {path.name} ({len(s['video_bytes'])//1024}KB, {s['generation_time']}s)")

    all_metrics["test1_water_3scenes"] = {
        "model": "Wan2.2-TI2V-5B",
        "gpu": "A100-40GB",
        "resolution": "832x480",
        "steps": 50,
        "frames": 81,
        "fps": 16,
        "scenes": 3,
        "model_load_time_s": result["load_time"],
        "per_scene_generation_s": [s["generation_time"] for s in result["scenes"]],
        "total_time_s": result["total_time"],
        "cost_usd": round(result["total_time"] / 3600 * 1.90, 4),
    }

    # ━━━ TEST 2: Steps comparison — 30 vs 50 (same prompt) ━━━━━━━━━━━━━━━━━━━━
    print("\n" + "=" * 60)
    print("TEST 2: Steps comparison — 30 steps (same water drop prompt)")
    print("=" * 60)

    result_30 = generate_scenes.remote([WATER_SCENES[0]], steps=30, label="water-30")
    s30 = result_30["scenes"][0]
    path = samples_dir / "water_scene_1_30steps.mp4"
    path.write_bytes(s30["video_bytes"])
    print(f"  ✓ 30 steps: {path.name} ({len(s30['video_bytes'])//1024}KB, {s30['generation_time']}s)")

    all_metrics["test2_steps_comparison"] = {
        "prompt": WATER_SCENES[0][:100] + "...",
        "30_steps": {"generation_time_s": s30["generation_time"], "total_time_s": result_30["total_time"]},
        "50_steps": {"generation_time_s": result["scenes"][0]["generation_time"]},
        "speedup": round(result["scenes"][0]["generation_time"] / s30["generation_time"], 2) if s30["generation_time"] > 0 else 0,
    }

    # ━━━ TEST 3: Mars Story — 5 connected scenes ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print("\n" + "=" * 60)
    print("TEST 3: Mars Story — 5 scene narrative (50 steps)")
    print("=" * 60)

    result_story = generate_scenes.remote(STORY_SCENES, steps=50, label="mars-story")

    for s in result_story["scenes"]:
        path = samples_dir / f"mars_scene_{s['scene_id']}_50steps.mp4"
        path.write_bytes(s["video_bytes"])
        print(f"  ✓ Scene {s['scene_id']}: {path.name} ({len(s['video_bytes'])//1024}KB, {s['generation_time']}s)")

    all_metrics["test3_mars_5scenes"] = {
        "model": "Wan2.2-TI2V-5B",
        "gpu": "A100-40GB",
        "resolution": "832x480",
        "steps": 50,
        "frames": 81,
        "fps": 16,
        "scenes": 5,
        "model_load_time_s": result_story["load_time"],
        "per_scene_generation_s": [s["generation_time"] for s in result_story["scenes"]],
        "total_time_s": result_story["total_time"],
        "cost_usd": round(result_story["total_time"] / 3600 * 1.90, 4),
        "cost_per_scene_usd": round(result_story["total_time"] / 3600 * 1.90 / 5, 4),
    }

    # ━━━ Summary ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    t_suite_end = time.time()
    suite_wall = round(t_suite_end - t_suite_start, 1)

    # Compute totals
    total_scenes = 3 + 1 + 5  # water + steps + mars
    total_gen_time = sum(s["generation_time"] for s in result["scenes"]) + s30["generation_time"] + sum(s["generation_time"] for s in result_story["scenes"])

    all_metrics["summary"] = {
        "total_wall_clock_s": suite_wall,
        "total_estimated_cost_usd": round(suite_wall / 3600 * 1.90, 2),
        "total_videos_generated": total_scenes,
        "total_video_duration_s": total_scenes * 5,
        "avg_generation_per_scene_s": round(total_gen_time / total_scenes, 1),
        "cost_per_scene_usd": round(suite_wall / 3600 * 1.90 / total_scenes, 4),
        "cost_per_minute_of_video_usd": round((suite_wall / 3600 * 1.90) / (total_scenes * 5 / 60), 2),
    }

    with open(results_dir / "full-benchmark-results.json", "w") as f:
        json.dump(all_metrics, f, indent=2)

    print("\n" + "=" * 60)
    print("📊 BENCHMARK COMPLETE")
    print("=" * 60)
    print(f"  Videos:        {total_scenes} clips ({total_scenes * 5}s total)")
    print(f"  Avg gen/scene: {all_metrics['summary']['avg_generation_per_scene_s']}s")
    print(f"  Wall clock:    {suite_wall}s ({suite_wall/60:.1f} min)")
    print(f"  Total cost:    ${all_metrics['summary']['total_estimated_cost_usd']}")
    print(f"  Cost/scene:    ${all_metrics['summary']['cost_per_scene_usd']}")
    print(f"  Cost/minute:   ${all_metrics['summary']['cost_per_minute_of_video_usd']}")
