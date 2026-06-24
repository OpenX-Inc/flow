"""Context/read tools — give the agent full project state. Read-only, never gated.

``get_project`` is the "always call first" tool: it returns project settings, the
ordered video track (scenes-as-clips), audio/text tracks, the cast, and what's
generatable — the IDs every other tool needs. Compact dumps omit defaults.
"""

from __future__ import annotations

from src.flow.store.models import Clip
from src.flow.tools import result
from src.flow.tools.context import ToolContext
from src.flow.tools.registry import tool

# Static capability matrix — what the GPU backend can do (beats Palmier by being
# generation-native: our own Wan2.2/VACE + voice, not 3rd-party proxies).
MODELS = [
    {"id": "wan22", "kind": "video", "modes": ["t2v", "i2v", "flf2v"],
     "resolutions": ["480p", "720p"], "aspect_ratios": ["9:16", "16:9", "1:1"],
     "max_duration_s": 10, "first_last_frame": True, "reference": True},
    {"id": "wan22_fast", "kind": "video", "modes": ["t2v"],
     "resolutions": ["480p"], "max_duration_s": 6, "note": "quicker, lower cost"},
    {"id": "vace", "kind": "video", "modes": ["vace"], "resolutions": ["480p", "720p"],
     "reference": True, "note": "reference/edit/compose"},
    {"id": "edge-tts", "kind": "audio", "modes": ["tts"], "voice_clone": False,
     "note": "free narration"},
    {"id": "miso-8b", "kind": "audio", "modes": ["tts"], "voice_clone": True,
     "note": "one-shot voice cloning"},
]


def _clip_view(c: Clip) -> dict:
    return c.model_dump(exclude_defaults=True)


@tool("get_project", "Always call first. Returns project settings (fps, resolution, "
      "revision), the ordered video track (scenes as clips with prompt/model/status/"
      "duration), audio + text tracks, the character cast, and can_generate. The "
      "clip_id/track_id/media_id values here are what every other tool accepts.",
      {"project_id": "string?"})
def get_project(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    return result.ok(
        project={
            "project_id": p.project_id,
            "title": p.title,
            "fps": p.fps,
            "resolution": f"{p.width}x{p.height}",
            "revision": p.revision,
            "total_frames": p.total_frames(),
            "can_generate": ctx.can_generate,
        },
        scenes=[_clip_view(c) for c in p.ordered_clips()],
        tracks=[t.model_dump(exclude_defaults=True) for t in p.tracks],
        characters=sorted(p.characters.keys()),
    )


@tool("get_media", "List media-library assets (generated/imported) with type, "
      "dimensions, generation_status, and used_by (which clips reference them). "
      "Every media_ref other tools use comes from here.",
      {"project_id": "string?",
       "unused_only": {"type": "boolean", "optional": True,
                       "description": "only assets not referenced by any clip"}})
def get_media(ctx: ToolContext, args: dict) -> dict:
    assets = [m for m in ctx.project.media if not m.trashed]
    if args.get("unused_only"):
        assets = [m for m in assets if not m.used_by]
    return result.ok(media=[m.model_dump(exclude_defaults=True) for m in assets])


@tool("list_characters", "List the project's reusable cast (name, description, "
      "whether a reference image is attached). Use names with attach_character_to_scene.",
      {"project_id": "string?"})
def list_characters(ctx: ToolContext, args: dict) -> dict:
    return result.ok(characters=[
        {"name": name, "description": ch.description,
         "has_reference": bool(ch.reference_image)}
        for name, ch in ctx.project.characters.items()
    ])


@tool("list_models", "List available generation models and their capabilities "
      "(video: modes/resolutions/durations/first-last-frame/reference; audio: "
      "tts + voice_clone). Use before choosing a model for generate_* tools.",
      {"kind": {"type": "string", "enum": ["video", "audio"], "optional": True}})
def list_models(ctx: ToolContext, args: dict) -> dict:
    kind = args.get("kind")
    models = [m for m in MODELS if not kind or m["kind"] == kind]
    return result.ok(models=models)
