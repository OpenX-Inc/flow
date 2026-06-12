"""MisoTTS 8B — Natural speech generation with voice cloning."""

from __future__ import annotations

from pathlib import Path

from flow.config import TTSConfig


def generate_speech(
    text: str,
    output_path: Path,
    config: TTSConfig,
    gpu_backend_url: str = "",
) -> Path:
    """Generate speech using MisoTTS 8B.

    If a voice_sample is configured, uses one-shot voice cloning.
    Otherwise generates with the default model voice.
    Can run locally (GPU required) or via the GPU backend API.
    """
    if gpu_backend_url:
        return _generate_via_backend(text, output_path, config, gpu_backend_url)
    return _generate_local(text, output_path, config)


def _generate_local(
    text: str,
    output_path: Path,
    config: TTSConfig,
) -> Path:
    """Generate speech locally using MisoTTS."""
    import torch
    import torchaudio
    from generator import Segment, load_miso_8b

    device = "cuda" if torch.cuda.is_available() else "cpu"
    generator = load_miso_8b(
        device=device,
        model_path_or_repo_id=config.miso_model,
    )

    # Build context from voice sample (for cloning)
    context: list = []
    if config.voice_sample and Path(config.voice_sample).exists():
        ref_audio, sr = torchaudio.load(config.voice_sample)
        if sr != generator.sample_rate:
            ref_audio = torchaudio.functional.resample(
                ref_audio, sr, generator.sample_rate
            )
        context = [
            Segment(
                text=config.voice_transcript,
                audio=ref_audio.squeeze(),
            )
        ]

    # Generate speech
    audio = generator.generate(
        text=text,
        context=context,
        max_audio_length_ms=len(text) * 100,  # rough estimate
    )

    # Save output
    torchaudio.save(
        str(output_path),
        audio.unsqueeze(0).cpu(),
        generator.sample_rate,
    )
    return output_path


def _generate_via_backend(
    text: str,
    output_path: Path,
    config: TTSConfig,
    backend_url: str,
) -> Path:
    """Generate speech via the GPU backend API."""
    import base64

    import httpx

    payload: dict = {
        "text": text,
        "model": config.miso_model,
        "precision": config.miso_precision,
    }

    # Include voice sample for cloning
    if config.voice_sample and Path(config.voice_sample).exists():
        audio_b64 = base64.b64encode(
            Path(config.voice_sample).read_bytes()
        ).decode()
        payload["voice_sample"] = audio_b64
        payload["voice_transcript"] = config.voice_transcript

    with httpx.Client(timeout=120) as client:
        resp = client.post(
            f"{backend_url.rstrip('/')}/tts/generate",
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()

    # Decode and save audio
    audio_bytes = base64.b64decode(result["audio_b64"])
    output_path.write_bytes(audio_bytes)
    return output_path
