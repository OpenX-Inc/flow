"""Background job runner — executes real generation and writes results to the store.

When a generation tool runs with a GenerationService present, it spawns a daemon
thread here that performs the real Modal/edge-tts call and, on completion, loads
the project, fills the real URL + flips status to ready/done (or failed), and
persists. This is real async generation (the GPU actually runs) — not a mock that
stays pending forever.
"""

from __future__ import annotations

import threading

from flow.store.media import GenerationStatus
from flow.store.models import ClipStatus


def _finish(store, project_id, *, media_id=None, clip_id=None, url=None,
            last_frame=None, duration_frames=None, failed=False):
    proj = store.load(project_id)
    if proj is None:
        return
    if media_id and (m := proj.get_media(media_id)):
        m.generation_status = GenerationStatus.failed if failed else GenerationStatus.ready
        if url:
            m.url = url
        if duration_frames:
            m.duration_frames = duration_frames
    if clip_id and (c := proj.get_clip(clip_id)):
        c.status = ClipStatus.failed if failed else ClipStatus.done
        if url:
            c.video_url = url
        if last_frame:
            c.last_frame_ref = last_frame
    proj.touch()
    store.save(proj)


def _video_worker(service, store, project_id, clip_id, media_id, prompt, mode,
                  resolution, duration_s, fps):
    try:
        out = service.generate_video(prompt, mode=mode, resolution=resolution,
                                     duration_s=duration_s)
        _finish(store, project_id, media_id=media_id, clip_id=clip_id,
                url=out["video_url"], last_frame=out.get("last_frame_url"),
                duration_frames=duration_s * fps)
    except Exception:  # noqa: BLE001 — record failure in the store
        _finish(store, project_id, media_id=media_id, clip_id=clip_id, failed=True)


def _audio_worker(service, store, project_id, media_id, text, voice):
    try:
        out = service.generate_narration(text, voice)
        _finish(store, project_id, media_id=media_id, url=out["audio_url"])
    except Exception:  # noqa: BLE001
        _finish(store, project_id, media_id=media_id, failed=True)


def submit_video(service, store, project_id, *, clip_id, media_id, prompt,
                 mode="t2v", resolution="480p", duration_s=5, fps=16) -> None:
    threading.Thread(
        target=_video_worker,
        args=(service, store, project_id, clip_id, media_id, prompt, mode,
              resolution, duration_s, fps),
        daemon=True,
    ).start()


def submit_narration(service, store, project_id, *, media_id, text, voice=None) -> None:
    threading.Thread(
        target=_audio_worker,
        args=(service, store, project_id, media_id, text, voice),
        daemon=True,
    ).start()
