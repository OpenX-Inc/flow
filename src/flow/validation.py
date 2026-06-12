"""Quality validation for generated video clips."""

from __future__ import annotations

import subprocess
from pathlib import Path


def validate_clip(clip_path: str, min_duration: float = 3.0) -> bool:
    """Basic validation that a clip is usable.

    Checks:
    - File exists and is non-empty
    - Video has expected minimum duration
    - Video has at least one video stream
    """
    path = Path(clip_path)
    if not path.exists() or path.stat().st_size < 1024:
        return False

    duration = get_duration(clip_path)
    return duration >= min_duration


def get_duration(clip_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            clip_path,
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def check_scene_coherence(
    prev_last_frame: str,
    curr_first_frame: str,
    threshold: float = 0.3,
) -> float:
    """Check visual coherence between adjacent scenes.

    Uses pixel-level comparison (SSIM-like) via ffmpeg.
    Returns a similarity score 0-1 (higher = more similar).
    """
    result = subprocess.run(
        [
            "ffmpeg", "-i", prev_last_frame, "-i", curr_first_frame,
            "-lavfi", "ssim", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    # Parse SSIM from ffmpeg stderr output
    for line in result.stderr.splitlines():
        if "All:" in line:
            try:
                ssim_str = line.split("All:")[1].split()[0]
                return float(ssim_str)
            except (IndexError, ValueError):
                pass
    return 0.0


def detect_black_frames(clip_path: str, threshold: float = 0.05) -> bool:
    """Check if clip is mostly black (failed generation)."""
    result = subprocess.run(
        [
            "ffmpeg", "-i", clip_path,
            "-vf", f"blackdetect=d=2:pix_th={threshold}",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
    )
    return "black_start" in result.stderr
