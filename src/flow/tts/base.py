"""Pluggable text-to-speech provider interface.

A :class:`TTSProvider` turns text into spoken audio. Providers are *stateless*
with respect to any application: they take text — and optionally a named voice
or a reference audio clip to clone — and write an audio file. The core pipeline
never reaches into application state, so self-hosters can select a provider via
config and register their own backend without modifying Flow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from flow.config import TTSConfig


class TTSProvider(ABC):
    """Base class for text-to-speech backends.

    Subclasses set the class attributes below and implement :meth:`synthesize`.
    """

    #: Stable identifier used in config (``[tts] provider = "..."``).
    name: ClassVar[str] = ""
    #: Container format the provider writes — used to name output files.
    output_ext: ClassVar[str] = "mp3"
    #: Whether this provider can clone a voice from a reference clip.
    supports_cloning: ClassVar[bool] = False

    def __init__(self, config: TTSConfig, *, gpu_backend_url: str = "") -> None:
        self.config = config
        self.gpu_backend_url = gpu_backend_url

    @abstractmethod
    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice: str | None = None,
        reference_audio: str | Path | None = None,
        reference_transcript: str | None = None,
    ) -> Path:
        """Render ``text`` to speech at ``output_path`` and return that path.

        Args:
            text: The text to speak.
            output_path: Where to write the audio file.
            voice: Selects a named built-in voice (provider-specific). When
                ``None`` the provider's configured default voice is used.
            reference_audio: Path to a reference clip to clone. Providers that
                do not support cloning ignore it.
            reference_transcript: Optional transcript of ``reference_audio``;
                some cloning models use it for better fidelity.
        """
        raise NotImplementedError
