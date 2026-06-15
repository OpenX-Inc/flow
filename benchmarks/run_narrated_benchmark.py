"""
OpenX Flow — Full Pipeline Benchmark (Video + Narration + Assembly)

Demonstrates the complete pipeline:
1. Generate narration audio (Edge TTS — free)
2. Generate video scenes (Wan 2.2 on Modal — ~$0.06/scene)
3. Assemble final video with narration overlay (ffmpeg — local)

Usage:
    modal run benchmarks/run_narrated_benchmark.py
"""

import asyncio
import json
import time
import io
import subprocess
from pathlib import Path

import modal

app = modal.App("openx-flow-narrated-benchmark")

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

# ─── Script ────────────────────────────────────────────────────────────────────

SCRIPT = {
    "title": "The Deep Ocean",
    "scenes": [
        {
            "narration": "Beneath the surface of the ocean lies a world untouched by sunlight. A world where darkness itself becomes alive.",
            "prompt": "Cinematic underwater shot descending into the deep dark ocean. Beams of fading blue sunlight pierce through from above, growing dimmer. Particles and marine snow drift slowly past the camera. Smooth slow downward camera movement, shot on RED underwater housing, photorealistic, volumetric light rays, deep blue to black gradient, no text.",
        },
        {
            "narration": "Here, in the crushing depths, creatures have evolved their own light. Bioluminescent organisms pulse with ethereal blue and green glows.",
            "prompt": "Cinematic close-up of bioluminescent deep sea jellyfish pulsing with ethereal blue and cyan light in pitch black water. Multiple translucent jellyfish with glowing tendrils drift slowly. Tiny bioluminescent particles scatter like stars. Shot on macro lens in deep ocean, photorealistic, volumetric bioluminescence, pure black background, no text.",
        },
        {
            "narration": "Each flash of light is a signal — a language written in photons, spoken by creatures that have never seen the sun.",
            "prompt": "Cinematic shot of a deep sea anglerfish with its bioluminescent lure glowing bright blue-white in the absolute darkness of the deep ocean. The fish drifts slowly, its lure swaying hypnotically. Other tiny bioluminescent dots scattered in the distant background. Dramatic single-source lighting from the lure only, shot on IMAX deep sea camera, photorealistic, no text.",
        },
    ],
}


# ─── GPU Function ──────────────────────────────────────────────────────────────

@app.function(image=wan_image, gpu="A100-40GB", timeout=1200, memory=32768)
def generate_scenes(prompts: list[str]) -> list[bytes]:
    """Generate video scenes with Wan2.2-TI2V-5B."""
    import torch
    import imageio
    import numpy as np
    from diffusers import WanPipeline

    t_start = time.time()
    print("Loading Wan2.2-TI2V-5B...")
    pipe = WanPipeline.from_pretrained(
        "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
        torch_dtype=torch.float16,
    )
    pipe.to("cuda")
    print(f"Model loaded in {time.time() - t_start:.1f}s")

    results = []
    for i, prompt in enumerate(prompts):
        t = time.time()
        print(f"\n▶ Scene {i+1}/{len(prompts)}: {prompt[:50]}...")
        output = pipe(
            prompt=prompt,
            num_frames=81,
            guidance_scale=5.0,
            num_inference_steps=50,
            height=480,
            width=832,
        )
        frames = output.frames[0]
        buf = io.BytesIO()
        writer = imageio.get_writer(buf, format="mp4", fps=16, codec="libx264")
        for frame in frames:
            arr = np.array(frame)
            if arr.dtype != np.uint8:
                arr = (arr * 255).clip(0, 255).astype(np.uint8)
            writer.append_data(arr)
        writer.close()
        results.append(buf.getvalue())
        print(f"  ✓ Done in {time.time() - t:.1f}s")

    return results


# ─── Local Entrypoint ──────────────────────────────────────────────────────────

@app.local_entrypoint()
def main():
    import edge_tts

    results_dir = Path("benchmarks/results/samples")
    results_dir.mkdir(parents=True, exist_ok=True)

    print("🎬 OpenX Flow — Narrated Video Benchmark")
    print(f"   Title: {SCRIPT['title']}")
    print(f"   Scenes: {len(SCRIPT['scenes'])}")
    print()

    t_total_start = time.time()

    # ── Step 1: Generate narration audio ──────────────────────────────────────
    print("🎙️  Step 1: Generating narration (Edge TTS)...")
    audio_files = []
    for i, scene in enumerate(SCRIPT["scenes"]):
        audio_path = results_dir / f"ocean_narration_{i+1}.mp3"
        t = time.time()
        communicate = edge_tts.Communicate(scene["narration"], "en-US-GuyNeural")
        asyncio.run(communicate.save(str(audio_path)))
        audio_files.append(audio_path)
        print(f"  ✓ Scene {i+1}: {audio_path.name} ({time.time()-t:.1f}s)")

    print()

    # ── Step 2: Generate video scenes on GPU ──────────────────────────────────
    print("🎥  Step 2: Generating video scenes (Modal A100)...")
    prompts = [s["prompt"] for s in SCRIPT["scenes"]]
    t_gpu_start = time.time()
    video_bytes_list = generate_scenes.remote(prompts)
    t_gpu_end = time.time()
    gpu_time = round(t_gpu_end - t_gpu_start, 1)

    video_files = []
    for i, vb in enumerate(video_bytes_list):
        path = results_dir / f"ocean_scene_{i+1}.mp4"
        path.write_bytes(vb)
        video_files.append(path)
        print(f"  ✓ Scene {i+1}: {path.name} ({len(vb)//1024}KB)")

    print()

    # ── Step 3: Assemble with narration ───────────────────────────────────────
    print("🔧  Step 3: Assembling final video with narration...")

    # Merge each scene with its narration
    merged_files = []
    for i, (vid, aud) in enumerate(zip(video_files, audio_files)):
        merged = results_dir / f"ocean_merged_{i+1}.mp4"
        # Overlay audio on video, trim to video length
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(vid),
            "-i", str(aud),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            "-map", "0:v", "-map", "1:a",
            str(merged),
        ], capture_output=True)
        merged_files.append(merged)
        print(f"  ✓ Merged scene {i+1}")

    # Concatenate all merged scenes
    concat_file = results_dir / "ocean_concat.txt"
    concat_file.write_text("\n".join(f"file '{f.name}'" for f in merged_files))

    final_path = results_dir / "ocean_narrated_full.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(final_path),
    ], capture_output=True)

    # Cleanup temp files
    concat_file.unlink()
    for f in merged_files:
        f.unlink()
    for f in audio_files:
        f.unlink()

    t_total_end = time.time()
    total_time = round(t_total_end - t_total_start, 1)

    print(f"\n  ✓ Final video: {final_path.name} ({final_path.stat().st_size // 1024}KB)")

    # Save metrics
    metrics = {
        "title": SCRIPT["title"],
        "pipeline": "writer → tts → generator → assembly",
        "model": "Wan2.2-TI2V-5B",
        "tts": "Edge TTS (en-US-GuyNeural)",
        "gpu": "A100-40GB",
        "scenes": len(SCRIPT["scenes"]),
        "resolution": "832x480",
        "fps": 16,
        "inference_steps": 50,
        "gpu_time_s": gpu_time,
        "total_time_s": total_time,
        "estimated_cost_usd": round(gpu_time / 3600 * 1.90, 4),
        "tts_cost": "free",
        "assembly_cost": "free (local ffmpeg)",
    }

    with open(results_dir.parent / "narrated-benchmark-results.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print()
    print("📊 Results:")
    print(f"   GPU time:    {gpu_time}s")
    print(f"   Total time:  {total_time}s ({total_time/60:.1f} min)")
    print(f"   GPU cost:    ${metrics['estimated_cost_usd']}")
    print(f"   TTS cost:    free")
    print(f"   Final video: {final_path}")
