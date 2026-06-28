"""MisoTTS provider — natural speech with one-shot voice cloning.

Runs locally (GPU required) or against an HTTP endpoint that exposes
``POST /tts/generate`` (see ``src/gpu_backend/server.py``). The endpoint is
taken from ``TTSConfig.miso_endpoint`` and falls back to the video
``gpu_backend_url`` passed at construction.
"""

from __future__ import annotations

import base64
from pathlib import Path

from flow.tts.base import TTSProvider


class MisoTTSProvider(TTSProvider):
    name = "miso"
    output_ext = "wav"
    supports_cloning = True

    def _endpoint(self) -> str:
        return self.config.miso_endpoint or self.gpu_backend_url

    def synthesize(
        self,
        text: str,
        output_path: Path,
        *,
        voice: str | None = None,
        reference_audio: str | Path | None = None,
        reference_transcript: str | None = None,
    ) -> Path:
        # An explicit reference overrides the configured sample, so callers can
        # clone any voice without mutating config.
        ref = str(reference_audio) if reference_audio else self.config.voice_sample
        transcript = (
            reference_transcript
            if reference_transcript is not None
            else self.config.voice_transcript
        )
        endpoint = self._endpoint()
        if endpoint:
            return self._via_backend(text, output_path, ref, transcript, endpoint)
        return self._local(text, output_path, ref, transcript)

    def _local(self, text: str, output_path: Path, ref: str, transcript: str) -> Path:
        """Generate speech in-process (requires a CUDA GPU + the MisoTTS model)."""
        import torch
        import torchaudio
        from generator import Segment, load_miso_8b

        device = "cuda" if torch.cuda.is_available() else "cpu"
        generator = load_miso_8b(device=device, model_path_or_repo_id=self.config.miso_model)

        context: list = []
        if ref and Path(ref).exists():
            ref_audio, sr = torchaudio.load(ref)
            if sr != generator.sample_rate:
                ref_audio = torchaudio.functional.resample(ref_audio, sr, generator.sample_rate)
            context = [Segment(text=transcript, audio=ref_audio.squeeze())]

        audio = generator.generate(
            text=text,
            context=context,
            max_audio_length_ms=len(text) * 100,
        )
        torchaudio.save(str(output_path), audio.unsqueeze(0).cpu(), generator.sample_rate)
        return output_path

    def _via_backend(
        self, text: str, output_path: Path, ref: str, transcript: str, endpoint: str
    ) -> Path:
        """Generate speech via an HTTP MisoTTS endpoint."""
        import httpx

        payload: dict = {
            "text": text,
            "model": self.config.miso_model,
            "precision": self.config.miso_precision,
        }
        if ref and Path(ref).exists():
            payload["voice_sample"] = base64.b64encode(Path(ref).read_bytes()).decode()
            payload["voice_transcript"] = transcript

        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{endpoint.rstrip('/')}/tts/generate", json=payload)
            resp.raise_for_status()
            result = resp.json()

        output_path.write_bytes(base64.b64decode(result["audio_b64"]))
        return output_path
