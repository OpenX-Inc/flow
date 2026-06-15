"""
OpenX Flow — Short Film: "The Last Library"

A 30-scene narrated short film (~2.5 min) demonstrating full pipeline:
1. Edge TTS narration (free)
2. Wan 2.2 video generation (30 clips on A100)
3. ffmpeg assembly with narration overlay

Story: A forgotten library at the edge of civilization where
ancient books come alive at night, their stories manifesting
as light and shadow.

Usage:
    modal run benchmarks/run_short_film.py
"""

import asyncio
import time
import io
import subprocess
from pathlib import Path

import modal

app = modal.App("openx-flow-short-film")

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

FILM = [
    # ACT 1: Discovery (scenes 1-10)
    {
        "narration": "At the edge of a dying world, where rust-colored dunes stretch to every horizon, there stands a building that should not exist.",
        "prompt": "Cinematic aerial shot of endless rust-orange sand dunes stretching to the horizon under a hazy amber sky. A single ancient stone building sits alone in the vast desert. Dust swirls slowly. Shot on ARRI Alexa 65, golden hour, epic scale, photorealistic, no text.",
    },
    {
        "narration": "A library. Impossibly old. Its walls carved from stone that predates the desert itself.",
        "prompt": "Cinematic slow push-in toward a massive ancient stone library building in the desert. Ornate carved columns and weathered archways. Sand drifts against the base. Warm golden sunset light casting long shadows. Shot on anamorphic lens, photorealistic, no text.",
    },
    {
        "narration": "No one remembers who built it. No one remembers when the last reader came.",
        "prompt": "Close-up of weathered stone carvings on the library entrance. Ancient symbols eroded by millennia of sand and wind. A heavy wooden door slightly ajar. Dust particles floating in a shaft of light. Cinematic macro detail, photorealistic, no text.",
    },
    {
        "narration": "But tonight, as the last sun sets on this forgotten place, something stirs.",
        "prompt": "Cinematic wide shot of the desert library silhouetted against a dramatic sunset. Deep orange and purple sky. The last rays of light disappear below the horizon. Stars beginning to appear. Timelapse feeling, photorealistic, epic scale, no text.",
    },
    {
        "narration": "The doors open on their own. Dust cascades from hinges that haven't moved in centuries.",
        "prompt": "Cinematic shot of massive ancient wooden doors slowly creaking open inward. Dust and debris cascade from the top. A warm amber glow emanates from within. Camera at ground level looking up at the towering doorway. Dramatic lighting, photorealistic, no text.",
    },
    {
        "narration": "Inside, the air is thick with the scent of forgotten pages. Thousands of books line walls that reach impossibly high.",
        "prompt": "Cinematic wide interior shot of a vast ancient library. Towering bookshelves reaching up into darkness. Thousands of old leather-bound books. Warm candlelight glow from unseen sources. Dust motes floating. Camera slowly tilts upward. Cathedral-like scale, photorealistic, no text.",
    },
    {
        "narration": "Moonlight cuts through a shattered dome above, painting silver lines across the floor.",
        "prompt": "Cinematic shot looking up at a broken glass dome ceiling in an ancient library. Moonlight streams through the cracks creating dramatic silver light beams cutting through dusty air. Stars visible through gaps. Gothic architecture, photorealistic, no text.",
    },
    {
        "narration": "And then it begins. A soft glow. Barely perceptible at first.",
        "prompt": "Cinematic close-up of old leather book spines on a dusty shelf. One book begins to emit a faint warm golden glow from between its pages. The light pulses gently like a heartbeat. Dark moody atmosphere, shallow depth of field, photorealistic, no text.",
    },
    {
        "narration": "One by one, the books begin to wake.",
        "prompt": "Cinematic medium shot of an entire library shelf. Multiple books begin glowing different colors — gold, blue, soft green. The light grows stronger, illuminating the surrounding darkness. Magical atmosphere, photorealistic, cinematic lighting, no text.",
    },
    {
        "narration": "Their stories, long unread, refuse to be forgotten.",
        "prompt": "Cinematic wide shot of the entire library interior now alive with hundreds of softly glowing books. Different colors of light create a constellation effect across the massive shelved walls. Ethereal magical atmosphere, photorealistic, no text.",
    },
    # ACT 2: The Stories Come Alive (scenes 11-20)
    {
        "narration": "A book of oceans opens itself. Water pours from its pages like a living waterfall.",
        "prompt": "Cinematic shot of an ancient book floating open in mid-air. Crystal blue water pours from its glowing pages cascading downward like a miniature waterfall. The water dissolves into light before hitting the floor. Magical realism, dramatic lighting, photorealistic, no text.",
    },
    {
        "narration": "Waves crash in miniature, and tiny ships sail across the library floor.",
        "prompt": "Cinematic close-up of a miniature ocean spreading across a stone library floor. Tiny perfect waves with foam. Microscopic sailing ships riding the waves between chair legs. Bioluminescent glow from below. Tilt-shift macro photography feel, photorealistic, no text.",
    },
    {
        "narration": "A book of stars erupts overhead, filling the broken dome with galaxies that never existed.",
        "prompt": "Cinematic shot looking upward inside the library as thousands of tiny stars and nebulae burst from an open floating book. Purple and blue galaxies spiral across the domed ceiling. Stars reflect off everything below. Cosmic spectacle, photorealistic, no text.",
    },
    {
        "narration": "Constellations form stories of their own — heroes and monsters traced in points of light.",
        "prompt": "Cinematic shot of glowing constellation patterns forming in the air inside the library. Lines of light connect stars into shapes of mythical creatures and warriors. They move slowly, acting out silent battles. Dark background with brilliant light points, photorealistic, no text.",
    },
    {
        "narration": "A book of forests grows a tree in seconds. Its roots crack through the stone floor.",
        "prompt": "Cinematic timelapse-style shot of a luminous golden tree rapidly growing from an open book on the floor. Roots spread across stone, branches reach upward. Glowing leaves unfurl. The tree fills the space between bookshelves. Magical bioluminescent growth, photorealistic, no text.",
    },
    {
        "narration": "Fireflies emerge from its branches, carrying fragments of old poems in their light.",
        "prompt": "Cinematic close-up of dozens of glowing fireflies emerging from luminous tree branches inside the library. Each firefly trails a small wisp of golden light with faint text visible within. Dreamy bokeh, shallow depth of field, warm tones, photorealistic, no text.",
    },
    {
        "narration": "A book of storms unleashes silent lightning between the shelves.",
        "prompt": "Cinematic wide shot of silent purple and white lightning arcing between library bookshelves. The bolts illuminate rows of books in brief flashes. Energy crackles along metal railings. No destruction, pure contained energy. Dramatic contrast, photorealistic, no text.",
    },
    {
        "narration": "Rain falls indoors, but only in a column of silver light. Each drop carries a memory.",
        "prompt": "Cinematic shot of rain falling in a perfect cylindrical column of moonlight inside the library. Silver rain drops catch light as they fall. The floor around the column stays perfectly dry. Surreal and beautiful. Photorealistic, no text.",
    },
    {
        "narration": "A book of time opens, and the library sees itself young again. Readers fill its halls like ghosts.",
        "prompt": "Cinematic shot of translucent ghostly figures of people reading and walking through the library. They glow with soft warm light, semi-transparent. The library around them appears newer, restored. Past and present overlapping. Ethereal double exposure effect, photorealistic, no text.",
    },
    {
        "narration": "Children laugh silently. Scholars argue in forgotten languages. Lovers hide notes between pages.",
        "prompt": "Cinematic montage-style shot of ghostly translucent figures in the library. A child reaching for a book, scholars gesturing at a table, a hand sliding a note into a book spine. All glowing softly, overlapping in time. Beautiful melancholy, photorealistic, no text.",
    },
    # ACT 3: Dawn (scenes 21-30)
    {
        "narration": "But stories cannot last forever. As the first light of dawn touches the horizon, the magic begins to fade.",
        "prompt": "Cinematic wide shot through a library window showing the first pale blue light of dawn on the desert horizon. Inside, the magical lights from books begin dimming. A transition between night magic and morning reality. Melancholy beautiful, photorealistic, no text.",
    },
    {
        "narration": "The ocean recedes back into its pages. The stars fold themselves away.",
        "prompt": "Cinematic shot of the miniature ocean on the library floor being drawn back into a closing book like water flowing in reverse. Stars above spiral inward disappearing into another book. The magic retreating. Beautiful and sad, photorealistic, no text.",
    },
    {
        "narration": "The tree of light dissolves into golden dust that settles on the shelves like pollen.",
        "prompt": "Cinematic shot of a luminous tree dissolving from top to bottom into millions of tiny golden particles. The particles drift down slowly like snow, settling on book spines and shelves. Dawn light mixing with the last golden glow. Photorealistic, no text.",
    },
    {
        "narration": "The ghosts smile one last time before fading into morning light.",
        "prompt": "Cinematic close-up of a translucent ghostly figure smiling peacefully as morning light passes through them. They dissolve into particles of warm light. Emotional, intimate, shallow depth of field. Bittersweet beauty, photorealistic, no text.",
    },
    {
        "narration": "One by one, the books close. Their covers settle. Their light dims to nothing.",
        "prompt": "Cinematic shot of glowing books on shelves slowly closing one by one in sequence. Each book's light fades as it shuts. A wave of darkness following the closing books down the long shelf. Satisfying sequential motion, photorealistic, no text.",
    },
    {
        "narration": "Silence returns to the library. The dust resumes its slow eternal dance.",
        "prompt": "Cinematic wide shot of the library interior now completely dark and still again. Only faint dawn light through the dome. Dust motes floating slowly in a single beam of pale light. Complete stillness and peace. Photorealistic, no text.",
    },
    {
        "narration": "The doors close. Not with force, but with the gentleness of a page being turned.",
        "prompt": "Cinematic shot from outside as the massive library doors slowly close. The last sliver of warm interior light narrows and disappears. The stone building sealed again. Dawn desert light. Gentle, final, photorealistic, no text.",
    },
    {
        "narration": "Outside, the desert is unchanged. The dunes don't know what happened. The wind doesn't care.",
        "prompt": "Cinematic wide shot of the desert at dawn. Soft pink and blue light across endless sand dunes. The library small in the distance. Wind blows fine sand across the frame. Vast emptiness and solitude. Epic landscape, photorealistic, no text.",
    },
    {
        "narration": "But inside those walls, between those covers, the stories are patient. They will wait another thousand years if they must.",
        "prompt": "Cinematic extreme close-up of a single ancient book on a dusty shelf. A barely perceptible warm glow pulses once from within its pages then fades. As if the book is breathing in its sleep. Intimate, mysterious, shallow depth of field, photorealistic, no text.",
    },
    {
        "narration": "Because stories never truly die. They only wait for someone brave enough to read them.",
        "prompt": "Cinematic final wide shot. The ancient library alone in the vast desert under a sky full of stars. The Milky Way arcs overhead. A single tiny warm light glows from one window. The building small but eternal against the cosmos. Epic scale, photorealistic, no text.",
    },
]


@app.function(image=wan_image, gpu="A100-40GB", timeout=5400, memory=32768)
def generate_film_scenes(prompts: list[str]) -> list[bytes]:
    """Generate all 30 film scenes."""
    import torch
    import imageio
    import numpy as np
    from diffusers import WanPipeline

    t_start = time.time()
    print(f"Loading model for {len(prompts)}-scene short film...")
    pipe = WanPipeline.from_pretrained("Wan-AI/Wan2.2-TI2V-5B-Diffusers", torch_dtype=torch.float16)
    pipe.to("cuda")
    print(f"Model loaded in {time.time() - t_start:.1f}s")

    results = []
    for i, prompt in enumerate(prompts):
        t = time.time()
        print(f"\n▶ Scene {i+1}/{len(prompts)}: {prompt[:50]}...")
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
        results.append(buf.getvalue())
        print(f"  ✓ {time.time()-t:.1f}s ({len(buf.getvalue())//1024}KB)")

    return results


@app.local_entrypoint()
def main():
    import edge_tts

    samples_dir = Path("benchmarks/results/samples/film")
    samples_dir.mkdir(parents=True, exist_ok=True)

    print("🎬 THE LAST LIBRARY — 30-Scene Short Film")
    print(f"   Scenes: {len(FILM)}")
    print()

    t_total = time.time()

    # Step 1: Narration
    print("🎙️  Generating narration...")
    audio_files = []
    for i, scene in enumerate(FILM):
        path = samples_dir / f"narr_{i+1:02d}.mp3"
        asyncio.run(edge_tts.Communicate(scene["narration"], "en-US-GuyNeural").save(str(path)))
        audio_files.append(path)
    print(f"  ✓ {len(audio_files)} narration clips generated")

    # Step 2: Video
    print("\n🎥  Generating video (this will take ~45 min)...")
    prompts = [s["prompt"] for s in FILM]
    t_gpu = time.time()
    video_bytes_list = generate_film_scenes.remote(prompts)
    gpu_time = round(time.time() - t_gpu, 1)
    print(f"  ✓ {len(video_bytes_list)} scenes generated in {gpu_time}s")

    # Save individual scenes
    video_files = []
    for i, vb in enumerate(video_bytes_list):
        path = samples_dir / f"scene_{i+1:02d}.mp4"
        path.write_bytes(vb)
        video_files.append(path)

    # Step 3: Assembly
    print("\n🔧  Assembling film...")
    merged = []
    for i, (vid, aud) in enumerate(zip(video_files, audio_files)):
        out = samples_dir / f"merged_{i+1:02d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", str(vid), "-i", str(aud), "-c:v", "copy", "-c:a", "aac", "-shortest", "-map", "0:v", "-map", "1:a", str(out)], capture_output=True)
        merged.append(out)

    # Concat
    concat_file = samples_dir / "concat.txt"
    concat_file.write_text("\n".join(f"file '{f.name}'" for f in merged))
    final = samples_dir / "the_last_library.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(final)], capture_output=True)

    # Cleanup temp
    concat_file.unlink()
    for f in merged:
        f.unlink()
    for f in audio_files:
        f.unlink()

    wall = round(time.time() - t_total, 1)
    print(f"\n✅ FILM COMPLETE: {final}")
    print(f"   Size: {final.stat().st_size // 1024}KB")
    print(f"   GPU time: {gpu_time}s")
    print(f"   Wall time: {wall}s ({wall/60:.1f} min)")
    print(f"   Cost: ~${gpu_time/3600*1.90:.2f}")
