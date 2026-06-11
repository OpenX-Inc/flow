"""Post-production module — TTS, subtitles, music, and video assembly."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from flow.config import Config
from flow.schemas import GeneratedClip, ShotList


class PostProduction:
    """Handles TTS generation, subtitle creation, and final assembly."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.work_dir = Path(tempfile.mkdtemp(prefix="flow_post_"))

    def assemble(
        self,
        shot_list: ShotList,
        clips: list[GeneratedClip],
        aspect_ratio: str = "9:16",
    ) -> Path:
        """Assemble clips into a final video with narration and subtitles."""
        # Generate TTS narration
        narration_path = self._generate_tts(shot_list.narration)

        # Generate subtitles
        subtitle_path = self._generate_subtitles(shot_list)

        # Assemble with FFmpeg
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{_slugify(shot_list.title)}.mp4"

        self._ffmpeg_assemble(
            clips=clips,
            narration_path=narration_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            aspect_ratio=aspect_ratio,
        )
        return output_path

    def _generate_tts(self, text: str) -> Path:
        """Generate TTS audio from narration text."""
        output_path = self.work_dir / "narration.mp3"

        if self.config.tts.provider == "edge":
            asyncio.run(self._edge_tts(text, output_path))
        else:
            raise NotImplementedError(
                f"TTS provider '{self.config.tts.provider}' not yet supported"
            )

        return output_path

    async def _edge_tts(self, text: str, output_path: Path) -> None:
        """Generate TTS using Edge TTS (free, Microsoft)."""
        import edge_tts

        communicate = edge_tts.Communicate(text, self.config.tts.voice)
        await communicate.save(str(output_path))

    def _generate_subtitles(self, shot_list: ShotList) -> Path:
        """Generate SRT subtitles from scene narration segments."""
        subtitle_path = self.work_dir / "subtitles.srt"
        lines: list[str] = []
        time_offset = 0.0

        for i, scene in enumerate(shot_list.scenes, 1):
            if not scene.narration_segment:
                time_offset += scene.duration
                continue

            start = _format_srt_time(time_offset)
            end = _format_srt_time(time_offset + scene.duration)
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(scene.narration_segment)
            lines.append("")
            time_offset += scene.duration

        subtitle_path.write_text("\n".join(lines))
        return subtitle_path

    def _ffmpeg_assemble(
        self,
        clips: list[GeneratedClip],
        narration_path: Path,
        subtitle_path: Path,
        output_path: Path,
        aspect_ratio: str,
    ) -> None:
        """Assemble final video using FFmpeg."""
        import subprocess

        # Create concat file
        concat_file = self.work_dir / "concat.txt"
        concat_lines = [f"file '{clip.path}'" for clip in clips]
        concat_file.write_text("\n".join(concat_lines))

        # Concat clips
        concat_output = self.work_dir / "concat.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(concat_output),
            ],
            capture_output=True,
            check=True,
        )

        # Mix audio and burn subtitles
        cmd = [
            "ffmpeg", "-y",
            "-i", str(concat_output),
            "-i", str(narration_path),
            "-vf", f"subtitles={subtitle_path}",
            "-map", "0:v",
            "-map", "1:a",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    import re

    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:80]
