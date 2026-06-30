"""Tests for the scene-level (per-scene) generation API."""

from pathlib import Path

from flow.config import Config
from flow.generator import Generator
from flow.keyframes import KeyframeGenerator
from flow.schemas import GeneratedClip


def test_generate_clip_delegates_and_passes_conditioning(monkeypatch):
    """generate_clip() renders one scene and forwards the first-frame for chaining."""
    g = Generator(Config())
    captured: dict = {}

    def fake_retry(*, scene_id, prompt, camera, characters, first_frame_path=None):
        captured.update(
            scene_id=scene_id, prompt=prompt, camera=camera,
            characters=characters, first_frame_path=first_frame_path,
        )
        return GeneratedClip(
            scene_id=scene_id, path="clip.mp4", duration=5,
            last_frame_path="clip_last.png",
        )

    monkeypatch.setattr(g, "_generate_with_retry", fake_retry)

    clip = g.generate_clip(
        "a sunset over the ocean", scene_id=3, camera="slow dolly",
        first_frame_path="prev_last.png",
    )

    assert isinstance(clip, GeneratedClip)
    assert clip.scene_id == 3
    assert clip.last_frame_path == "clip_last.png"  # fed to the next scene
    assert captured["prompt"] == "a sunset over the ocean"
    assert captured["first_frame_path"] == "prev_last.png"  # i2v conditioning
    assert captured["camera"] == "slow dolly"


def test_generate_clip_defaults_no_conditioning(monkeypatch):
    g = Generator(Config())
    captured: dict = {}

    def fake_retry(**kw):
        captured.update(kw)
        return GeneratedClip(
            scene_id=kw["scene_id"], path="c.mp4", duration=5, last_frame_path=None
        )

    monkeypatch.setattr(g, "_generate_with_retry", fake_retry)
    g.generate_clip("opening shot")
    assert captured["first_frame_path"] is None  # first scene → t2v, no conditioning
    assert captured["characters"] == []


def test_generate_keyframe_delegates(monkeypatch, tmp_path):
    kg = KeyframeGenerator(Config())
    seen: dict = {}
    monkeypatch.setattr(
        kg, "_generate_image",
        lambda prompt, path: seen.update({"prompt": prompt, "path": Path(path)}),
    )

    out = kg.generate_keyframe("library under stars, closing frame", tmp_path / "kf.png")

    assert out == tmp_path / "kf.png"
    assert seen["prompt"] == "library under stars, closing frame"
    assert seen["path"] == tmp_path / "kf.png"


def test_fetch_asset_decodes_base64():
    """Serverless backends (e.g. Modal) return inline base64."""
    import base64

    g = Generator(Config())
    payload = b"\x00\x01video-bytes"
    result = {"video_b64": base64.b64encode(payload).decode()}
    assert g._fetch_asset(result, "video") == payload


def test_fetch_asset_downloads_url(monkeypatch):
    """A file-serving backend returns a URL; absolute URLs download as-is."""
    g = Generator(Config())
    seen = {}

    def fake_download(url):
        seen["url"] = url
        return b"downloaded"

    monkeypatch.setattr(g, "_download", fake_download)
    out = g._fetch_asset({"video_url": "https://cdn.example/clip.mp4"}, "video")
    assert out == b"downloaded"
    assert seen["url"] == "https://cdn.example/clip.mp4"


def test_fetch_asset_resolves_relative_url(monkeypatch):
    """Relative URLs resolve against the backend base URL."""
    cfg = Config()
    cfg.gpu_backend.url = "https://gpu.example/"
    g = Generator(cfg)
    seen = {}
    monkeypatch.setattr(g, "_download", lambda url: seen.setdefault("url", url) or b"x")
    g._fetch_asset({"last_frame_url": "/files/abc_last.png"}, "last_frame")
    assert seen["url"] == "https://gpu.example/files/abc_last.png"


def test_fetch_asset_missing_returns_none():
    g = Generator(Config())
    assert g._fetch_asset({}, "last_frame") is None
