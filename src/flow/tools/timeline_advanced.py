"""Advanced timeline tools — keyframes, single-clip move, insert from media,
ripple-delete ranges, and track removal. All mutating; pure store ops.
"""

from __future__ import annotations

import math

from src.flow.store.models import Clip, Easing, Keyframe
from src.flow.tools import result
from src.flow.tools.context import ToolContext
from src.flow.tools.registry import tool

_KF_PROPS = {"opacity", "volume", "scale", "x", "y", "rotation"}


def _reindex(clips: list[Clip]) -> None:
    for i, c in enumerate(sorted(clips, key=lambda c: c.order_index)):
        c.order_index = i


@tool("set_keyframes", "Set animation keyframes for one property of a scene "
      "(replaces existing keyframes for that property). Frames are clip-relative.",
      {"project_id": "string?", "clip_id": "string",
       "property": {"type": "string", "enum": sorted(_KF_PROPS)},
       "keyframes": {"type": "array",
                     "description": "[{frame, value, easing?}]",
                     "items": {"type": "object"}}},
      mutating=True)
def set_keyframes(ctx: ToolContext, args: dict) -> dict:
    clip = ctx.project.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    prop = args["property"]
    span = clip.effective_frames
    new_kfs = []
    for kf in args["keyframes"]:
        frame = int(kf["frame"])
        if frame < 0 or frame > span:
            return result.error("invalid", f"keyframe frame {frame} out of range [0,{span}]")
        new_kfs.append(Keyframe(
            property=prop, frame=frame, value=float(kf["value"]),
            easing=Easing(kf.get("easing", "linear")),
        ))
    clip.keyframes = [k for k in clip.keyframes if k.property != prop] + new_kfs
    return result.ok(summary=f"set {len(new_kfs)} {prop} keyframes on {clip.clip_id}")


@tool("move_clips", "Move a scene to a new position (0-based) in the video track.",
      {"project_id": "string?", "clip_id": "string",
       "to_position": {"type": "integer", "minimum": 0}},
      mutating=True)
def move_clips(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    ordered = p.ordered_clips()
    idx = next((i for i, c in enumerate(ordered) if c.clip_id == args["clip_id"]), None)
    if idx is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    clip = ordered.pop(idx)
    pos = max(0, min(args["to_position"], len(ordered)))
    ordered.insert(pos, clip)
    for i, c in enumerate(ordered):
        c.order_index = i
    p.clips = ordered
    return result.ok(summary=f"moved {clip.clip_id} to {pos}")


@tool("insert_clip", "Insert an existing library video asset as a new scene at a "
      "position (default end). Ripples later scenes right.",
      {"project_id": "string?", "media_id": "string",
       "position": {"type": "integer", "minimum": 0, "optional": True}},
      mutating=True)
def insert_clip(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    asset = p.get_media(args["media_id"])
    if asset is None:
        return result.error("not_found", f"no media {args['media_id']}")
    frames = asset.duration_frames or 0
    clip = Clip(source_media_id=asset.media_id, source_duration_frames=frames,
                out_frame=frames, video_url=asset.url or None)
    asset.used_by = sorted(set(asset.used_by + [clip.clip_id]))
    ordered = p.ordered_clips()
    pos = args.get("position")
    if pos is None or pos >= len(ordered):
        clip.order_index = p.next_order_index()
        p.clips.append(clip)
    else:
        ordered.insert(pos, clip)
        p.clips = ordered
        _reindex(p.clips)
    return result.ok(summary=f"inserted scene {clip.clip_id}", clip_id=clip.clip_id)


@tool("ripple_delete_ranges", "Cut a clip-relative time range out of a scene and "
      "close the gap. Whole-clip range deletes the scene; head/tail trims; a middle "
      "range splits the scene. Later scenes shift automatically.",
      {"project_id": "string?", "clip_id": "string",
       "start_frame": {"type": "integer", "minimum": 0},
       "end_frame": {"type": "integer", "minimum": 1}},
      mutating=True)
def ripple_delete_ranges(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    clip = p.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    start, end = args["start_frame"], args["end_frame"]
    span = clip.effective_frames
    if not (0 <= start < end <= span):
        return result.error("invalid", f"range must satisfy 0<=start<end<={span}")

    # map clip-relative timeline frames to source offsets (speed-aware)
    s_src = clip.in_frame + math.ceil(start * clip.speed)
    e_src = clip.in_frame + math.ceil(end * clip.speed)

    if start == 0 and end == span:  # whole clip
        p.clips = [c for c in p.clips if c.clip_id != clip.clip_id]
        _reindex(p.clips)
        return result.ok(summary=f"deleted scene {clip.clip_id} (full range)")
    if start == 0:  # head
        clip.in_frame = e_src
        return result.ok(summary=f"trimmed head of {clip.clip_id}")
    if end == span:  # tail
        clip.out_frame = s_src
        return result.ok(summary=f"trimmed tail of {clip.clip_id}")
    # middle: keep [in, s_src) and [e_src, out) as two clips
    second = clip.model_copy(deep=True)
    second.clip_id = Clip().clip_id
    second.keyframes = []
    clip.out_frame = s_src
    second.in_frame = e_src
    ordered = p.ordered_clips()
    idx = next(i for i, c in enumerate(ordered) if c.clip_id == clip.clip_id)
    ordered.insert(idx + 1, second)
    p.clips = ordered
    _reindex(p.clips)
    return result.ok(summary=f"cut middle of {clip.clip_id}", new_clip_id=second.clip_id)


@tool("remove_track", "Remove an audio or text track and all its items.",
      {"project_id": "string?", "track_id": "string"}, mutating=True)
def remove_track(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    if not any(t.track_id == args["track_id"] for t in p.tracks):
        return result.error("not_found", f"no track {args['track_id']}")
    p.tracks = [t for t in p.tracks if t.track_id != args["track_id"]]
    return result.ok(summary=f"removed track {args['track_id']}")
