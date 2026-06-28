"""Text tools — titles/lower-thirds (add_texts) and captions (add_captions).

add_captions derives sentence-level captions from each scene's narration, timed
to the scene's position on the assembled timeline — real now, no whisper. Word-
level karaoke from audio is layered on later via the transcription service.
"""

from __future__ import annotations

from flow.store.tracks import TextPosition, TextStyle, Track, TrackItem, TrackKind
from flow.tools import result
from flow.tools.context import ToolContext
from flow.tools.registry import tool


def _get_or_create_text_track(project, name: str) -> Track:
    track = next((t for t in project.tracks if t.kind == TrackKind.text and t.name == name), None)
    if track is None:
        track = Track(kind=TrackKind.text, name=name, order=len(project.tracks))
        project.tracks.append(track)
    return track


@tool("add_texts", "Add a title / lower-third / on-screen text at a timeline frame.",
      {"project_id": "string?", "text": "string",
       "start_frame": {"type": "integer", "minimum": 0},
       "duration_frames": {"type": "integer", "minimum": 1},
       "position": {"type": "string", "enum": ["top", "center", "bottom"],
                    "optional": True, "default": "bottom"},
       "size_pct": {"type": "number", "minimum": 1, "maximum": 40, "optional": True},
       "bold": {"type": "boolean", "optional": True}},
      mutating=True)
def add_texts(ctx: ToolContext, args: dict) -> dict:
    track = _get_or_create_text_track(ctx.project, "titles")
    style = TextStyle(position=TextPosition(args.get("position", "bottom")))
    if "size_pct" in args:
        style.size_pct = args["size_pct"]
    if "bold" in args:
        style.bold = args["bold"]
    item = TrackItem(start_frame=args["start_frame"],
                     duration_frames=args["duration_frames"],
                     text=args["text"], style=style)
    track.items.append(item)
    return result.ok(summary=f"added text on '{track.name}'", item_id=item.item_id)


@tool("add_captions", "Generate a captions track from scene narration, timed to the "
      "assembled timeline (rebuilds the captions track).",
      {"project_id": "string?",
       "position": {"type": "string", "enum": ["top", "center", "bottom"],
                    "optional": True, "default": "bottom"}},
      mutating=True)
def add_captions(ctx: ToolContext, args: dict) -> dict:
    track = _get_or_create_text_track(ctx.project, "captions")
    track.items = []
    style = TextStyle(position=TextPosition(args.get("position", "bottom")),
                      background="rgba(0,0,0,0.5)")
    frame = 0
    count = 0
    for clip in ctx.project.ordered_clips():
        length = clip.effective_frames
        if clip.narration_segment:
            track.items.append(TrackItem(
                start_frame=frame, duration_frames=length,
                text=clip.narration_segment, style=style,
            ))
            count += 1
        frame += length
    if count == 0:
        return result.error("no_narration", "no scenes have narration to caption",
                            hint="set_narration on scenes first")
    return result.ok(summary=f"added {count} captions")
