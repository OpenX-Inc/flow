"""Analysis/read tools derived from store state (no ffmpeg/whisper needed).

These complete the read surface: the post-edit transcript (from scene narration),
the composited clip at a frame, asset metadata, and library text search. Frame
sampling / on-device transcription / color scopes are layered on later via the
render+analysis service; these give real answers from what the store knows now.
Read-only, never gated.
"""

from __future__ import annotations

from flow.tools import result
from flow.tools.context import ToolContext
from flow.tools.registry import tool


@tool("get_transcript", "The narration transcript of the current timeline, in order, "
      "with each segment's start/end frame on the assembled video.",
      {"project_id": "string?"})
def get_transcript(ctx: ToolContext, args: dict) -> dict:
    frame = 0
    segments = []
    for clip in ctx.project.ordered_clips():
        length = clip.effective_frames
        if clip.narration_segment:
            segments.append({
                "clip_id": clip.clip_id,
                "start_frame": frame,
                "end_frame": frame + length,
                "text": clip.narration_segment,
            })
        frame += length
    return result.ok(segments=segments, total_frames=frame)


@tool("inspect_timeline", "What's on the video track at a given assembled-timeline "
      "frame: the active scene, its offset into that scene, and its properties.",
      {"project_id": "string?", "frame": {"type": "integer", "minimum": 0}})
def inspect_timeline(ctx: ToolContext, args: dict) -> dict:
    target = args["frame"]
    cursor = 0
    for clip in ctx.project.ordered_clips():
        length = clip.effective_frames
        if cursor <= target < cursor + length:
            return result.ok(
                frame=target,
                active_clip=clip.clip_id,
                offset_in_clip=target - cursor,
                clip=clip.model_dump(exclude_defaults=True),
            )
        cursor += length
    return result.ok(frame=target, active_clip=None,
                     note=f"frame is past the end ({cursor})")


@tool("inspect_media", "Inspect a library asset's metadata: type, dimensions, "
      "generation status, model/prompt provenance, and which clips use it.",
      {"project_id": "string?", "media_id": "string"})
def inspect_media(ctx: ToolContext, args: dict) -> dict:
    asset = ctx.project.get_media(args["media_id"])
    if asset is None:
        return result.error("not_found", f"no media {args['media_id']}")
    return result.ok(media=asset.model_dump(exclude_defaults=True))


@tool("search_media", "Search the library and scene prompts by text (filename, "
      "generation prompt, narration). Returns matching media and scenes.",
      {"project_id": "string?", "query": "string"})
def search_media(ctx: ToolContext, args: dict) -> dict:
    q = args["query"].lower()
    media_hits = [
        {"media_id": m.media_id, "filename": m.filename, "type": m.type}
        for m in ctx.project.media
        if not m.trashed and (q in m.filename.lower() or q in m.prompt.lower())
    ]
    scene_hits = [
        {"clip_id": c.clip_id, "prompt": c.visual_prompt}
        for c in ctx.project.ordered_clips()
        if q in c.visual_prompt.lower() or q in c.narration_segment.lower()
    ]
    return result.ok(media=media_hits, scenes=scene_hits)
