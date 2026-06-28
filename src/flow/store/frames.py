"""Frame math — frames (in the project's fps) are the authoritative time unit.

Tools accept either ``*_frames`` (int, authoritative) or ``*_seconds`` (float,
convenience); the store always converts to and stores frames so edits are
exact and deterministic. Default fps is 16 to match Wan 2.2 output
(``num_frames = duration_seconds * 16``).
"""

from __future__ import annotations

DEFAULT_FPS = 16


def seconds_to_frames(seconds: float, fps: int = DEFAULT_FPS) -> int:
    """Convert seconds to whole frames, rounding half-up.

    >>> seconds_to_frames(1.0, 16)
    16
    >>> seconds_to_frames(0.03125, 16)  # exactly half a frame -> rounds up
    1
    """
    if seconds < 0:
        raise ValueError("seconds must be >= 0")
    if fps <= 0:
        raise ValueError("fps must be > 0")
    return int(seconds * fps + 0.5)


def frames_to_seconds(frames: int, fps: int = DEFAULT_FPS) -> float:
    """Convert whole frames to seconds.

    >>> frames_to_seconds(16, 16)
    1.0
    """
    if frames < 0:
        raise ValueError("frames must be >= 0")
    if fps <= 0:
        raise ValueError("fps must be > 0")
    return frames / fps


def resolve_time(
    *,
    frames: int | None = None,
    seconds: float | None = None,
    fps: int = DEFAULT_FPS,
) -> int:
    """Resolve a dual frames/seconds tool input to authoritative frames.

    Exactly one of ``frames`` or ``seconds`` must be provided.
    """
    if (frames is None) == (seconds is None):
        raise ValueError("provide exactly one of frames or seconds")
    return frames if frames is not None else seconds_to_frames(seconds, fps)


def clamp_frame(frame: int, total_frames: int) -> int:
    """Clamp a frame index into ``[0, total_frames]``."""
    return max(0, min(frame, total_frames))


def span_frames(start_frame: int, end_frame: int) -> int:
    """Length of the half-open interval ``[start_frame, end_frame)`` in frames."""
    if end_frame < start_frame:
        raise ValueError("end_frame must be >= start_frame")
    return end_frame - start_frame


def overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """True if half-open intervals ``[a_start, a_end)`` and ``[b_start, b_end)`` overlap."""
    return a_start < b_end and b_start < a_end
