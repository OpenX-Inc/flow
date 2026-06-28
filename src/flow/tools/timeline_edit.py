"""Timeline-edit tools — operate on scenes-as-clips (the video track).

All mutating; dispatch records undo + persists automatically. Frames are
authoritative; tools accept seconds where natural and convert via the project fps.
"""

from __future__ import annotations

from flow.store.frames import seconds_to_frames
from flow.store.models import Clip, ClipStatus
from flow.tools import result
from flow.tools.context import ToolContext
from flow.tools.registry import tool


@tool("create_scene", "Add a new scene (pending generation) to the video track. "
      "Appends at the end unless 'position' (0-based order index) is given.",
      {"project_id": "string?",
       "prompt": {"type": "string", "description": "visual prompt for the scene"},
       "duration_s": {"type": "number", "minimum": 1, "maximum": 30, "optional": True,
                      "default": 5},
       "model": {"type": "string", "optional": True, "default": "wan22"},
       "narration": {"type": "string", "optional": True},
       "position": {"type": "integer", "minimum": 0, "optional": True}},
      mutating=True)
def create_scene(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    frames = seconds_to_frames(args.get("duration_s", 5), p.fps)
    clip = Clip(
        visual_prompt=args["prompt"],
        model=args.get("model", "wan22"),
        narration_segment=args.get("narration", ""),
        source_duration_frames=frames,
        out_frame=frames,
        status=ClipStatus.pending,
    )
    pos = args.get("position")
    ordered = p.ordered_clips()
    if pos is None or pos >= len(ordered):
        clip.order_index = p.next_order_index()
        p.clips.append(clip)
    else:
        ordered.insert(pos, clip)
        for i, c in enumerate(ordered):
            c.order_index = i
        p.clips = ordered
    return result.ok(summary=f"added scene {clip.clip_id}", clip_id=clip.clip_id)


@tool("update_scene", "Update a scene's prompt, duration, model, or narration. "
      "Changing the prompt does not auto-regenerate — call regenerate_scene for that.",
      {"project_id": "string?", "clip_id": "string",
       "prompt": {"type": "string", "optional": True},
       "duration_s": {"type": "number", "minimum": 1, "maximum": 30, "optional": True},
       "model": {"type": "string", "optional": True},
       "narration": {"type": "string", "optional": True}},
      mutating=True)
def update_scene(ctx: ToolContext, args: dict) -> dict:
    clip = ctx.project.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    if "prompt" in args:
        clip.visual_prompt = args["prompt"]
    if "model" in args:
        clip.model = args["model"]
    if "narration" in args:
        clip.narration_segment = args["narration"]
    if "duration_s" in args:
        frames = seconds_to_frames(args["duration_s"], ctx.project.fps)
        clip.source_duration_frames = frames
        clip.out_frame = frames
        clip.in_frame = 0
    return result.ok(summary=f"updated scene {clip.clip_id}")


@tool("delete_scene", "Remove a scene from the video track (re-indexes the rest).",
      {"project_id": "string?", "clip_id": "string"}, mutating=True)
def delete_scene(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    if p.get_clip(args["clip_id"]) is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    p.clips = [c for c in p.clips if c.clip_id != args["clip_id"]]
    for i, c in enumerate(p.ordered_clips()):
        c.order_index = i
    return result.ok(summary=f"deleted scene {args['clip_id']}")


@tool("reorder_scenes", "Set a new order for the video track. 'order' must be a "
      "permutation of all current clip_ids (front to back).",
      {"project_id": "string?",
       "order": {"type": "array", "items": "string",
                 "description": "all clip_ids in the desired order"}},
      mutating=True)
def reorder_scenes(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    order = args["order"]
    existing = {c.clip_id for c in p.clips}
    if set(order) != existing or len(order) != len(existing):
        return result.error(
            "invalid", "order must be a permutation of all current clip_ids",
            hint=f"current: {sorted(existing)}")
    rank = {cid: i for i, cid in enumerate(order)}
    for c in p.clips:
        c.order_index = rank[c.clip_id]
    return result.ok(summary=f"reordered {len(order)} scenes")


@tool("set_clip_properties", "Set playback/visual properties on a scene: speed, "
      "volume, opacity, fades, or transition-in. Only provided fields change.",
      {"project_id": "string?", "clip_id": "string",
       "speed": {"type": "number", "minimum": 0.1, "maximum": 8, "optional": True},
       "volume": {"type": "number", "minimum": 0, "maximum": 4, "optional": True},
       "opacity": {"type": "number", "minimum": 0, "maximum": 1, "optional": True},
       "fade_in_frames": {"type": "integer", "minimum": 0, "optional": True},
       "fade_out_frames": {"type": "integer", "minimum": 0, "optional": True},
       "transition": {"type": "string", "optional": True,
                      "description": "transition INTO this clip, e.g. crossfade"}},
      mutating=True)
def set_clip_properties(ctx: ToolContext, args: dict) -> dict:
    clip = ctx.project.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    for prop in ("speed", "volume", "opacity", "fade_in_frames",
                 "fade_out_frames", "transition"):
        if prop in args:
            setattr(clip, prop, args[prop])
    return result.ok(summary=f"set properties on {clip.clip_id}")


@tool("split_clip", "Split a scene into two at a clip-relative frame (timeline "
      "frames into the clip). Both halves share the source; later scenes shift.",
      {"project_id": "string?", "clip_id": "string",
       "at_frame": {"type": "integer", "minimum": 1,
                    "description": "clip-relative timeline frame to cut at"}},
      mutating=True)
def split_clip(ctx: ToolContext, args: dict) -> dict:
    import math

    p = ctx.project
    clip = p.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    at = args["at_frame"]
    if at <= 0 or at >= clip.effective_frames:
        return result.error(
            "invalid", f"at_frame must be within (0, {clip.effective_frames})")

    # Map the clip-relative timeline frame to a source-frame offset (speed-aware).
    source_offset = math.ceil(at * clip.speed)
    cut = clip.in_frame + source_offset

    second = clip.model_copy(deep=True)
    second.clip_id = Clip().clip_id  # fresh id
    # First half ends at cut; second half starts at cut.
    clip.out_frame = cut
    second.in_frame = cut
    # Split keyframes at the cut (clip-relative), rebase the second half.
    clip.keyframes = [k for k in clip.keyframes if k.frame < at]
    second.keyframes = [
        k.model_copy(update={"frame": k.frame - at})
        for k in second.keyframes if k.frame >= at
    ]
    # Insert the second half right after the first; re-index.
    ordered = p.ordered_clips()
    idx = next(i for i, c in enumerate(ordered) if c.clip_id == clip.clip_id)
    ordered.insert(idx + 1, second)
    for i, c in enumerate(ordered):
        c.order_index = i
    p.clips = ordered
    return result.ok(summary=f"split {clip.clip_id}", new_clip_id=second.clip_id)
