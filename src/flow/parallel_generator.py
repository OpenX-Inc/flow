"""Parallel FLF2V generator — generates all scenes simultaneously."""

from __future__ import annotations

import base64
import concurrent.futures
import tempfile
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from flow.config import Config
from flow.schemas import GeneratedClip, ShotList
from flow.validation import detect_black_frames, validate_clip

console = Console()

MAX_RETRIES = 2


class ParallelGenerator:
    """Generates all scenes in parallel using FLF2V.

    Requires keyframes (scene boundary images) to be pre-generated.
    Each scene is generated independently: FLF2V(start_frame, end_frame).
    """

    def __init__(self, config: Config, max_workers: int = 8) -> None:
        self.config = config
        self.backend_url = config.gpu_backend.url
        self.max_workers = max_workers
        self.clip_dir = Path(tempfile.mkdtemp(prefix="flow_parallel_"))

    def generate_scenes(
        self,
        shot_list: ShotList,
        keyframes: list[Path],
    ) -> list[GeneratedClip]:
        """Generate all scenes in parallel using FLF2V.

        keyframes[i] = start frame of scene i
        keyframes[i+1] = end frame of scene i
        """
        jobs = []
        for i, scene in enumerate(shot_list.scenes):
            if i + 1 >= len(keyframes):
                break
            jobs.append({
                "scene_id": scene.id,
                "prompt": scene.visual_prompt,
                "camera": scene.camera,
                "start_frame": keyframes[i],
                "end_frame": keyframes[i + 1],
            })

        clips: list[GeneratedClip] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Parallel generation...", total=len(jobs)
            )

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                futures = {
                    executor.submit(self._generate_one, job): job
                    for job in jobs
                }

                for future in concurrent.futures.as_completed(futures):
                    clip = future.result()
                    clips.append(clip)
                    progress.advance(task)

        # Sort by scene ID to maintain order
        clips.sort(key=lambda c: c.scene_id)
        return clips

    def _generate_one(self, job: dict) -> GeneratedClip:
        """Generate a single scene via FLF2V with retry."""
        for attempt in range(MAX_RETRIES + 1):
            clip = self._call_flf2v(job)
            if validate_clip(clip.path) and not detect_black_frames(
                clip.path
            ):
                return clip
            if attempt < MAX_RETRIES:
                console.print(
                    f"    ⚠ Scene {job['scene_id']} retry "
                    f"({attempt + 1}/{MAX_RETRIES})"
                )
        return clip

    def _call_flf2v(self, job: dict) -> GeneratedClip:
        """Call the GPU backend FLF2V endpoint."""
        start_b64 = base64.b64encode(
            job["start_frame"].read_bytes()
        ).decode()
        end_b64 = base64.b64encode(
            job["end_frame"].read_bytes()
        ).decode()

        full_prompt = job["prompt"]
        if job["camera"]:
            full_prompt += f", {job['camera']}"

        with httpx.Client(timeout=600) as client:
            resp = client.post(
                f"{self.backend_url.rstrip('/')}/generate/flf2v",
                json={
                    "prompt": full_prompt,
                    "first_frame": start_b64,
                    "last_frame": end_b64,
                    "resolution": self.config.gpu_backend.resolution,
                    "duration": self.config.gpu_backend.clip_duration,
                },
                headers={
                    "Authorization": (
                        f"Bearer {self.config.gpu_backend.api_key}"
                    )
                },
            )
            resp.raise_for_status()
            result = resp.json()

        clip_path = self.clip_dir / f"scene_{job['scene_id']:03d}.mp4"
        video_data = base64.b64decode(result["video_b64"])
        clip_path.write_bytes(video_data)

        return GeneratedClip(
            scene_id=job["scene_id"],
            path=str(clip_path),
            duration=self.config.gpu_backend.clip_duration,
        )
