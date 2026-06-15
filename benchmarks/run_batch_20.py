"""
OpenX Flow — 20-clip Benchmark Batch

Generates 20 diverse clips across 4 themes to showcase range.
All Wan2.2-TI2V-5B on A100-40GB, 50 steps.

Usage:
    modal run benchmarks/run_batch_20.py
"""

import time
import io
from pathlib import Path

import modal

app = modal.App("openx-flow-batch-20")

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

PROMPTS = [
    # Underwater (4)
    "Cinematic shot of a giant whale shark gliding through crystal blue water with schools of tiny silver fish parting around it. Sunbeams pierce through the surface above. Slow majestic movement, shot on IMAX underwater rig, photorealistic, no text.",
    "Extreme close-up of a coral reef at night. Fluorescent corals pulse with neon pink and electric blue bioluminescence. Tiny shrimp crawl along the branches. Macro lens, photorealistic, dark water background, no text.",
    "A sea turtle swimming gracefully through a kelp forest. Shafts of green-gold sunlight filter through the swaying kelp fronds. Peaceful slow motion, camera tracks alongside. Shot on RED, photorealistic, no text.",
    "An octopus rapidly changing colors and textures as it moves across a rocky ocean floor. Shifting from red to white to camouflaged stone pattern. Close tracking shot, photorealistic, dramatic rim lighting, no text.",
    # Space (4)
    "Cinematic shot of the International Space Station orbiting Earth at sunset. The thin blue atmosphere line glows on the horizon. Solar panels catch golden light. Slow orbital movement, photorealistic, IMAX quality, no text.",
    "A rocket launch viewed from a distance. The massive vehicle lifts off with brilliant orange flame and billowing white smoke clouds. Camera slowly tilts up following the ascent. Golden hour lighting, photorealistic, no text.",
    "Close-up of an astronaut's gloved hand floating in zero gravity inside a spacecraft. Tiny water droplets float past catching light. Warm interior lighting, shallow depth of field, photorealistic, no text.",
    "A timelapse of stars rotating above a radio telescope dish in a desert. The Milky Way arcs across the sky. The telescope slowly rotates to track. Long exposure style, photorealistic, no text.",
    # Nature (4)
    "A lone wolf walking through a snowy forest at dawn. Breath visible in the cold air. Soft pink light filtering through frosted pine trees. Cinematic tracking shot, photorealistic, shallow depth of field, no text.",
    "Extreme slow motion of a hummingbird hovering at a red flower. Wings beating creating subtle air distortion. Iridescent green feathers catching sunlight. Macro shot, 1000fps slow motion, photorealistic, no text.",
    "A massive thunderstorm cell rotating over flat prairie land at sunset. Lightning flashes illuminate the supercell structure. Dramatic orange and purple sky. Timelapse speed, wide cinematic shot, photorealistic, no text.",
    "Cherry blossom petals falling in slow motion through warm spring sunlight in a Japanese garden. A stone path and wooden bridge visible in soft focus. Dreamy atmosphere, photorealistic, no text.",
    # Cinematic/Abstract (4)
    "Liquid mercury flowing and pooling on a black surface. Perfect mirror reflections distort and reform. Mesmerizing fluid dynamics. Macro shot, studio lighting, photorealistic, dark background, no text.",
    "A single candle flame flickering in complete darkness. The warm orange glow illuminates wisps of smoke curling upward. Ultra slow motion, extreme close-up, shallow depth of field, photorealistic, no text.",
    "Ink drops falling into water in slow motion. Deep blue and crimson inks billowing and mixing into fractal patterns. White background, studio macro photography, photorealistic, no text.",
    "A vinyl record spinning on a turntable. The needle tracks the groove. Warm amber lighting, shallow depth of field on the grooves. Camera slowly orbits. Nostalgic cinematic mood, photorealistic, no text.",
    # Urban (4)
    "A busy Tokyo street crossing at night in the rain. Hundreds of umbrellas, neon signs reflecting in wet pavement. Slow motion crowd movement. Cinematic wide shot from above, photorealistic, no text.",
    "Steam rising from a New York City manhole cover on a cold morning. Yellow taxi passes through the steam. Golden dawn light backlighting the scene. Cinematic street-level shot, photorealistic, no text.",
    "An empty subway train car in motion. Fluorescent lights flicker. Through the windows, tunnel lights streak by. Moody blue-green color grade. Smooth handheld camera, photorealistic, no text.",
    "A lone saxophone player performing under a streetlight on a rainy cobblestone street. Water droplets catch the warm amber light. Long shadows stretch behind. Cinematic medium shot, photorealistic, no text.",
]


@app.function(image=wan_image, gpu="A100-40GB", timeout=3600, memory=32768)
def generate_batch(prompts: list[str]) -> list[dict]:
    """Generate all clips sequentially."""
    import torch
    import imageio
    import numpy as np
    from diffusers import WanPipeline

    t_start = time.time()
    print(f"Loading model for {len(prompts)} clips...")
    pipe = WanPipeline.from_pretrained("Wan-AI/Wan2.2-TI2V-5B-Diffusers", torch_dtype=torch.float16)
    pipe.to("cuda")
    load_time = round(time.time() - t_start, 1)
    print(f"Model loaded in {load_time}s")

    results = []
    for i, prompt in enumerate(prompts):
        t = time.time()
        print(f"\n▶ Clip {i+1}/{len(prompts)}: {prompt[:50]}...")
        output = pipe(prompt=prompt, num_frames=81, guidance_scale=5.0, num_inference_steps=50, height=480, width=832)
        frames = output.frames[0]
        buf = io.BytesIO()
        writer = imageio.get_writer(buf, format="mp4", fps=16, codec="libx264")
        for frame in frames:
            arr = np.array(frame)
            if arr.dtype != np.uint8:
                arr = (arr * 255).clip(0, 255).astype(np.uint8)
            writer.append_data(arr)
        writer.close()
        gen_time = round(time.time() - t, 1)
        results.append({"id": i + 1, "time": gen_time, "bytes": buf.getvalue()})
        print(f"  ✓ {gen_time}s ({len(buf.getvalue())//1024}KB)")

    return results


@app.local_entrypoint()
def main():
    samples_dir = Path("benchmarks/results/samples")
    samples_dir.mkdir(parents=True, exist_ok=True)

    print(f"🎬 Generating 20 clips...")
    t_start = time.time()
    results = generate_batch.remote(PROMPTS)
    wall = round(time.time() - t_start, 1)

    for r in results:
        path = samples_dir / f"clip_{r['id']:02d}.mp4"
        path.write_bytes(r["bytes"])
        print(f"✓ clip_{r['id']:02d}.mp4 ({len(r['bytes'])//1024}KB, {r['time']}s)")

    total_gen = sum(r["time"] for r in results)
    print(f"\n📊 Done: 20 clips, {wall}s wall, ~${wall/3600*1.90:.2f}")
