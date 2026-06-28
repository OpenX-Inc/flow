"""Edge TTS provider — free Microsoft online voices (no cloning)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from flow.tts.base import TTSProvider


class EdgeTTSProvider(TTSProvider):
    """Synthesize speech with Microsoft Edge TTS.

    Free and CPU-only (calls Microsoft's online service). Offers a large set of
    named voices but cannot clone a voice — ``reference_audio`` is ignored.
    """

    name = "edge"
    output_ext = "mp3"
    supports_cloning = False

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice: str | None = None,
        reference_audio: str | Path | None = None,
        reference_transcript: str | None = None,
    ) -> Path:
        import edge_tts

        selected = voice or self.config.voice

        async def _run() -> None:
            await edge_tts.Communicate(text, selected).save(str(output_path))

        try:
            asyncio.run(_run())
        except RuntimeError:
            # Already inside a running event loop — run on a fresh one.
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_run())
            finally:
                loop.close()
        return output_path
