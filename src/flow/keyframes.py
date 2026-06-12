"""Keyframe generator — produces boundary images for parallel FLF2V."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from flow.config import Config
from flow.schemas import ShotList

console = Console()


class KeyframeGenerator:
    """Generates keyframe images at scene boundaries for FLF2V infill."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.backend_url = config.gpu_backend.url

    def generate_keyframes(
        self, shot_list: ShotList, output_dir: Path
    ) -> list[Path]:
        """Generate a keyframe image for each scene boundary.

        For N scenes, generates N+1 keyframes (start and end of each).
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        keyframes: list[Path] = []

        prompts = self._build_keyframe_prompts(shot_list)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Generating keyframes...", total=len(prompts)
            )

            for i, prompt in enumerate(prompts):
                progress.update(
                    task,
                    description=f"Keyframe {i + 1}/{len(prompts)}",
                )
                path = output_dir / f"keyframe_{i:04d}.png"
                self._generate_image(prompt, path)
                keyframes.append(path)
                progress.advance(task)

        return keyframes

    def _build_keyframe_prompts(self, shot_list: ShotList) -> list[str]:
        """Build prompts for each scene boundary keyframe."""
        prompts: list[str] = []
        for i, scene in enumerate(shot_list.scenes):
            # Start frame of each scene
            prompt = (
                f"{scene.visual_prompt}, "
                f"opening frame, {scene.camera}, "
                f"cinematic still photograph, high quality"
            )
            prompts.append(prompt)

        # Final frame of last scene
        if shot_list.scenes:
            last = shot_list.scenes[-1]
            prompts.append(
                f"{last.visual_prompt}, "
                f"closing frame, cinematic still, high quality"
            )
        return prompts

    def _generate_image(self, prompt: str, output_path: Path) -> None:
        """Generate a single keyframe image via GPU backend."""
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{self.backend_url.rstrip('/')}/generate/t2i",
                json={
                    "prompt": prompt,
                    "resolution": self.config.gpu_backend.resolution,
                },
                headers={
                    "Authorization": (
                        f"Bearer {self.config.gpu_backend.api_key}"
                    )
                },
            )
            resp.raise_for_status()
            result = resp.json()

        image_data = base64.b64decode(result["image_b64"])
        output_path.write_bytes(image_data)
