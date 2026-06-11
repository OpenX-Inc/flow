"""Generator module — Video generation via GPU backend."""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from flow.config import Config
from flow.schemas import GeneratedClip, ShotList

console = Console()


class Generator:
    """Generates video clips by calling the GPU backend API."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.backend_url = config.gpu_backend.url
        self.clip_dir = Path(tempfile.mkdtemp(prefix="flow_clips_"))

    def generate_scenes(self, shot_list: ShotList) -> list[GeneratedClip]:
        """Generate video clips for all scenes with frame conditioning."""
        clips: list[GeneratedClip] = []
        last_frame_path: str | None = None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating...", total=len(shot_list.scenes))

            for scene in shot_list.scenes:
                progress.update(
                    task,
                    description=f"Scene {scene.id}/{len(shot_list.scenes)}",
                )

                clip = self._generate_single(
                    scene_id=scene.id,
                    prompt=scene.visual_prompt,
                    camera=scene.camera,
                    characters=[
                        shot_list.characters[c]
                        for c in scene.characters
                        if c in shot_list.characters
                    ],
                    first_frame_path=last_frame_path,
                )
                clips.append(clip)
                last_frame_path = clip.last_frame_path
                progress.advance(task)

        return clips

    def _generate_single(
        self,
        scene_id: int,
        prompt: str,
        camera: str,
        characters: list,
        first_frame_path: str | None = None,
    ) -> GeneratedClip:
        """Generate a single video clip via the GPU backend."""
        full_prompt = prompt
        if camera:
            full_prompt += f", {camera}"

        endpoint = "/generate/t2v"
        payload: dict = {
            "prompt": full_prompt,
            "resolution": self.config.gpu_backend.resolution,
            "duration": self.config.gpu_backend.clip_duration,
        }

        if first_frame_path:
            endpoint = "/generate/i2v"
            payload["first_frame"] = self._encode_image(first_frame_path)

        # Call GPU backend
        url = f"{self.backend_url.rstrip('/')}{endpoint}"
        with httpx.Client(timeout=600) as client:
            resp = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self.config.gpu_backend.api_key}"},
            )
            resp.raise_for_status()
            result = resp.json()

        # Save clip
        clip_path = self.clip_dir / f"scene_{scene_id:03d}.mp4"
        video_data = self._download(result["video_url"])
        clip_path.write_bytes(video_data)

        # Save last frame for next scene's conditioning
        last_frame_path_out = self.clip_dir / f"scene_{scene_id:03d}_last.png"
        if "last_frame_url" in result:
            frame_data = self._download(result["last_frame_url"])
            last_frame_path_out.write_bytes(frame_data)
        else:
            self._extract_last_frame(clip_path, last_frame_path_out)

        return GeneratedClip(
            scene_id=scene_id,
            path=str(clip_path),
            duration=self.config.gpu_backend.clip_duration,
            last_frame_path=str(last_frame_path_out),
        )

    def _download(self, url: str) -> bytes:
        """Download a file from URL."""
        with httpx.Client(timeout=120) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content

    def _encode_image(self, path: str) -> str:
        """Encode image to base64 for API payload."""
        import base64

        data = Path(path).read_bytes()
        return base64.b64encode(data).decode()

    def _extract_last_frame(self, video_path: Path, output_path: Path) -> None:
        """Extract the last frame of a video using ffmpeg."""
        import subprocess

        subprocess.run(
            [
                "ffmpeg", "-y", "-sseof", "-0.1",
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                str(output_path),
            ],
            capture_output=True,
            check=True,
        )
