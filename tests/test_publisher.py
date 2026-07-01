"""Tests for the Meta Graph API publishers (Instagram Reels + Facebook Page)."""

from pathlib import Path

from flow.config import Config
from flow.publisher import Publisher
from flow.schemas import ShotList


class _Resp:
    def __init__(self, payload=None):
        self._payload = payload or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _shotlist():
    return ShotList(title="My Reel", narration="A short story.", scenes=[])


def test_instagram_publishes_via_graph_api(monkeypatch):
    cfg = Config()
    cfg.publish.platforms = ["instagram"]
    cfg.publish.meta_page_access_token = "tok"
    cfg.publish.instagram_business_account_id = "ig123"
    calls = []

    def fake_post(url, data=None, timeout=None, **kw):
        calls.append(url)
        if url.endswith("/media"):
            return _Resp({"id": "creation1"})
        return _Resp({"id": "published1"})

    def fake_get(url, params=None, timeout=None, **kw):
        return _Resp({"status_code": "FINISHED"})

    monkeypatch.setattr("flow.publisher.httpx.post", fake_post)
    monkeypatch.setattr("flow.publisher.httpx.get", fake_get)

    Publisher(cfg).upload(Path("clip.mp4"), _shotlist(), video_url="https://cdn/x.mp4")

    assert any(u.endswith("/ig123/media") for u in calls)
    assert any(u.endswith("/ig123/media_publish") for u in calls)


def test_instagram_skips_without_public_url(monkeypatch):
    cfg = Config()
    cfg.publish.platforms = ["instagram"]
    cfg.publish.meta_page_access_token = "tok"
    cfg.publish.instagram_business_account_id = "ig123"
    called = []
    monkeypatch.setattr("flow.publisher.httpx.post", lambda *a, **k: called.append(1))

    Publisher(cfg).upload(Path("clip.mp4"), _shotlist())  # no video_url
    assert called == []  # honest skip, no API call


def test_instagram_skips_when_unconfigured(monkeypatch):
    cfg = Config()
    cfg.publish.platforms = ["instagram"]
    called = []
    monkeypatch.setattr("flow.publisher.httpx.post", lambda *a, **k: called.append(1))

    Publisher(cfg).upload(Path("clip.mp4"), _shotlist(), video_url="https://cdn/x.mp4")
    assert called == []  # no token/ig id -> skip


def test_facebook_publishes_by_file_url(monkeypatch):
    cfg = Config()
    cfg.publish.platforms = ["facebook"]
    cfg.publish.meta_page_access_token = "tok"
    cfg.publish.facebook_page_id = "page123"
    seen = {}

    def fake_post(url, data=None, timeout=None, **kw):
        seen["url"] = url
        seen["data"] = data
        return _Resp({"id": "vid1"})

    monkeypatch.setattr("flow.publisher.httpx.post", fake_post)

    Publisher(cfg).upload(Path("clip.mp4"), _shotlist(), video_url="https://cdn/x.mp4")
    assert seen["url"].endswith("/page123/videos")
    assert seen["data"]["file_url"] == "https://cdn/x.mp4"


def test_facebook_skips_when_unconfigured(monkeypatch):
    cfg = Config()
    cfg.publish.platforms = ["facebook"]
    called = []
    monkeypatch.setattr("flow.publisher.httpx.post", lambda *a, **k: called.append(1))

    Publisher(cfg).upload(Path("clip.mp4"), _shotlist(), video_url="https://cdn/x.mp4")
    assert called == []
