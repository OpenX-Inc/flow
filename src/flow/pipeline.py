"""Main pipeline orchestrator for Flow."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console

from flow.config import Config
from flow.generator import Generator
from flow.postproduction import PostProduction
from flow.publisher import Publisher
from flow.writer import Writer

console = Console()


class Pipeline:
    """Orchestrates the full video generation pipeline."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.writer = Writer(config)
        self.generator = Generator(config)
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

        # Stage 2: Generate video clips for each scene
        console.print("\n[bold]Stage 2/4:[/] Generating video clips...")
        clips = self.generator.generate_scenes(shot_list)
        console.print(f"  ✓ Generated {len(clips)} clips")

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
            console.print("\n[bold]Stage 4/4:[/] Publishing skipped (disabled)")

        elapsed = time.time() - start
        console.print(f"\n[bold green]Done![/] Total time: {elapsed:.1f}s")
        return video_path
