"""Backwards-compatible shim for the MisoTTS backend.

Deprecated: prefer ``flow.tts.get_tts_provider`` or
``flow.tts.MisoTTSProvider``. This module is kept so existing imports of
``generate_speech`` keep working.
"""

from __future__ import annotations

from pathlib import Path

from flow.config import TTSConfig


def generate_speech(
    text: str,
    output_path: Path,
    config: TTSConfig,
    gpu_backend_url: str = "",
) -> Path:
    """Generate speech with MisoTTS. Thin wrapper over :class:`MisoTTSProvider`."""
    from flow.tts.miso import MisoTTSProvider

    return MisoTTSProvider(config, gpu_backend_url=gpu_backend_url).synthesize(
        text, Path(output_path)
    )
