"""Main pipeline orchestrator for Flow."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from rich.console import Console

from flow.config import Config
from flow.generator import Generator
from flow.keyframes import KeyframeGenerator
from flow.parallel_generator import ParallelGenerator
from flow.postproduction import PostProduction
from flow.publisher import Publisher
from flow.writer import Writer

console = Console()


class Pipeline:
    """Orchestrates the full video generation pipeline."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.writer = Writer(config)
        self.postproduction = PostProduction(config)
        self.publisher = Publisher(config)

    def run(self, topic: str, duration: int = 60) -> Path:
        """Run the full pipeline: topic → final video."""
        start = time.time()

        # Stage 1: Write script and shot list
        console.print("\n[bold]Stage 1/4:[/] Writing script...")
        shot_list = self.writer.generate(topic=topic, duration=duration)
        console.print(
            f"  ✓ Generated {len(shot_list.scenes)} scenes, "
            f"{len(shot_list.characters)} characters"
        )

        # Stage 2: Generate video clips
        if self.config.generation_mode == "parallel_flf2v":
            clips = self._generate_parallel(shot_list)
        elif self.config.generation_mode == "pipelined_flf2v":
            clips = self._generate_pipelined(shot_list)
        else:
            clips = self._generate_sequential(shot_list)

        # Stage 3: Post-production (TTS, subtitles, assembly)
        console.print("\n[bold]Stage 3/4:[/] Post-production...")
        video_path = self.postproduction.assemble(
            shot_list=shot_list,
            clips=clips,
            aspect_ratio=self.config.aspect_ratio,
        )
        console.print(f"  ✓ Assembled video: {video_path}")

        # Stage 4: Publish (if enabled)
        if self.config.publish.enabled:
            console.print("\n[bold]Stage 4/4:[/] Publishing...")
            self.publisher.upload(video_path, shot_list)
            console.print("  ✓ Published")
        else:
            console.print("\n[bold]Stage 4/4:[/] Publishing skipped")

        elapsed = time.time() - start
        console.print(f"\n[bold green]Done![/] Total time: {elapsed:.1f}s")
        return video_path

    def _generate_sequential(self, shot_list):
        """Sequential generation with last-frame conditioning."""
        console.print(
            "\n[bold]Stage 2/4:[/] Generating clips (sequential)..."
        )
        generator = Generator(self.config)
        clips = generator.generate_scenes(shot_list)
        console.print(f"  ✓ Generated {len(clips)} clips")
        return clips

    def _generate_parallel(self, shot_list):
        """Two-pass parallel generation with FLF2V."""
        console.print(
            "\n[bold]Stage 2/4:[/] Generating clips (parallel FLF2V)..."
        )

        # Pass 1: Generate keyframes
        console.print("  Pass 1: Generating keyframes...")
        keyframe_dir = Path(tempfile.mkdtemp(prefix="flow_kf_"))
        kf_gen = KeyframeGenerator(self.config)
        keyframes = kf_gen.generate_keyframes(shot_list, keyframe_dir)
        console.print(f"  ✓ {len(keyframes)} keyframes generated")

        # Pass 2: Parallel FLF2V infill
        console.print("  Pass 2: Parallel video generation...")
        par_gen = ParallelGenerator(self.config)
        clips = par_gen.generate_scenes(shot_list, keyframes)
        console.print(f"  ✓ Generated {len(clips)} clips in parallel")
        return clips

    def _generate_pipelined(self, shot_list):
        """Pipelined generation: start video gen as keyframes become ready."""
        import concurrent.futures

        console.print(
            "\n[bold]Stage 2/4:[/] Generating clips (pipelined FLF2V)..."
        )

        keyframe_dir = Path(tempfile.mkdtemp(prefix="flow_kf_"))
        keyframe_dir.mkdir(parents=True, exist_ok=True)
        kf_gen = KeyframeGenerator(self.config)
        par_gen = ParallelGenerator(self.config, max_workers=7)

        # Generate keyframes one by one; as soon as a pair is ready,
        # submit video job to the parallel generator's thread pool.
        prompts = kf_gen._build_keyframe_prompts(shot_list)
        keyframes: list[Path] = []
        video_futures: list[concurrent.futures.Future] = []
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=7)

        for i, prompt in enumerate(prompts):
            path = keyframe_dir / f"keyframe_{i:04d}.png"
            kf_gen._generate_image(prompt, path)
            keyframes.append(path)
            console.print(f"  Keyframe {i + 1}/{len(prompts)} ✓")

            # Once we have a pair, submit video generation
            if i > 0 and i - 1 < len(shot_list.scenes):
                scene = shot_list.scenes[i - 1]
                job = {
                    "scene_id": scene.id,
                    "prompt": scene.visual_prompt,
                    "camera": scene.camera,
                    "start_frame": keyframes[i - 1],
                    "end_frame": keyframes[i],
                }
                future = executor.submit(par_gen._generate_one, job)
                video_futures.append(future)

        # Collect results
        clips = [f.result() for f in video_futures]
        executor.shutdown(wait=False)
        clips.sort(key=lambda c: c.scene_id)
        console.print(f"  ✓ Generated {len(clips)} clips (pipelined)")
        return clips
