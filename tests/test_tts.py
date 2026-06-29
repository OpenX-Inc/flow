"""Tests for the pluggable TTS provider layer."""

from pathlib import Path

import pytest

from flow.config import TTSConfig
from flow.tts import (
    EdgeTTSProvider,
    MisoTTSProvider,
    TTSProvider,
    available_providers,
    get_tts_provider,
    register_provider,
)


def test_builtin_providers_registered():
    assert "edge" in available_providers()
    assert "miso" in available_providers()


def test_get_edge_provider():
    p = get_tts_provider(TTSConfig(provider="edge"))
    assert isinstance(p, EdgeTTSProvider)
    assert p.name == "edge"
    assert p.output_ext == "mp3"
    assert p.supports_cloning is False


def test_get_miso_provider():
    p = get_tts_provider(TTSConfig(provider="miso"))
    assert isinstance(p, MisoTTSProvider)
    assert p.output_ext == "wav"
    assert p.supports_cloning is True


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        get_tts_provider(TTSConfig(provider="does-not-exist"))


def test_miso_endpoint_resolution():
    # Explicit miso_endpoint wins over the video gpu_backend_url.
    p = get_tts_provider(
        TTSConfig(provider="miso", miso_endpoint="http://miso:9000"),
        gpu_backend_url="http://video:8000",
    )
    assert p._endpoint() == "http://miso:9000"
    # Falls back to gpu_backend_url when miso_endpoint is unset.
    p2 = get_tts_provider(TTSConfig(provider="miso"), gpu_backend_url="http://video:8000")
    assert p2._endpoint() == "http://video:8000"


def test_register_custom_provider():
    class DummyProvider(TTSProvider):
        name = "dummy-test"
        output_ext = "ogg"

        def synthesize(self, text, output_path, **kwargs):
            Path(output_path).write_text(text)
            return Path(output_path)

    register_provider(DummyProvider)
    assert "dummy-test" in available_providers()
    p = get_tts_provider(TTSConfig(provider="dummy-test"))
    assert isinstance(p, DummyProvider)


def test_register_requires_name():
    class Nameless(TTSProvider):
        def synthesize(self, text, output_path, **kwargs):
            return Path(output_path)

    with pytest.raises(ValueError, match="non-empty"):
        register_provider(Nameless)


def test_edge_synthesize_uses_selected_voice(monkeypatch, tmp_path):
    """Edge provider passes the chosen voice to edge_tts and writes the file."""
    calls = {}

    class FakeCommunicate:
        def __init__(self, text, voice):
            calls["text"] = text
            calls["voice"] = voice

        async def save(self, path):
            Path(path).write_bytes(b"audio")

    import sys

    fake_edge = type(sys)("edge_tts")
    fake_edge.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake_edge)

    out = tmp_path / "n.mp3"
    p = get_tts_provider(TTSConfig(provider="edge", voice="en-US-Default"))
    result = p.synthesize("hello", out, voice="en-GB-Custom")
    assert result == out
    assert out.read_bytes() == b"audio"
    assert calls["text"] == "hello"
    assert calls["voice"] == "en-GB-Custom"  # explicit voice overrides config


def test_miso_via_backend(monkeypatch, tmp_path):
    """Miso provider posts to {endpoint}/tts/generate and writes decoded audio."""
    import base64

    posted = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"audio_b64": base64.b64encode(b"wavbytes").decode()}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):
            posted["url"] = url
            posted["json"] = json
            return FakeResp()

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)

    out = tmp_path / "n.wav"
    p = get_tts_provider(TTSConfig(provider="miso", miso_endpoint="http://miso:9000"))
    result = p.synthesize("say this", out)
    assert result == out
    assert out.read_bytes() == b"wavbytes"
    assert posted["url"] == "http://miso:9000/tts/generate"
    assert posted["json"]["text"] == "say this"
