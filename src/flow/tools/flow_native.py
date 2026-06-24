"""Flow-native tools — beyond Palmier: casting, narration, autonomous planning,
voice cloning, and batch generation.

These make Flow autonomous-first (vs Palmier's assist-only): the agent plans a
whole video, casts a reusable character into scenes, sets narration, and kicks
off batch generation — concepts Palmier has no equivalent for.
"""

from __future__ import annotations

from src.flow.schemas import Character
from src.flow.store.frames import seconds_to_frames
from src.flow.store.media import GenerationStatus, MediaAsset, MediaType
from src.flow.store.models import Clip, ClipStatus
from src.flow.tools import result
from src.flow.tools.context import ToolContext
from src.flow.tools.registry import tool


@tool("attach_character_to_scene", "Cast a character (from the project's reusable "
      "cast) into a scene for subject consistency. Set regenerate to re-roll now.",
      {"project_id": "string?", "scene_id": "string", "character_name": "string",
       "regenerate": {"type": "boolean", "optional": True, "default": False}},
      mutating=True)
def attach_character_to_scene(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    name = args["character_name"]
    if name not in p.characters:
        return result.error("not_found", f"no character {name!r} in the cast",
                            hint="add it first or list_characters")
    clip = p.get_clip(args["scene_id"])
    if clip is None:
        return result.error("not_found", f"no scene {args['scene_id']}")
    if name not in clip.characters:
        clip.characters.append(name)
    if args.get("regenerate"):
        clip.status = ClipStatus.pending  # marks for re-roll via start_generation
    return result.ok(summary=f"cast {name} into {clip.clip_id}")


@tool("set_narration", "Set a scene's narration text (and optional voice). Generate "
      "the audio with generate_audio or batch via start_generation.",
      {"project_id": "string?", "scene_id": "string", "text": "string",
       "voice": {"type": "string", "optional": True}},
      mutating=True)
def set_narration(ctx: ToolContext, args: dict) -> dict:
    clip = ctx.project.get_clip(args["scene_id"])
    if clip is None:
        return result.error("not_found", f"no scene {args['scene_id']}")
    clip.narration_segment = args["text"]
    return result.ok(summary=f"set narration on {clip.clip_id}")


@tool("plan_video", "Lay out a whole video as scenes on the track (you plan the "
      "shots; this persists them). mode=replace clears existing scenes, append adds.",
      {"project_id": "string?",
       "title": {"type": "string", "optional": True},
       "mode": {"type": "string", "enum": ["replace", "append"], "optional": True,
                "default": "replace"},
       "scenes": {"type": "array",
                  "description": "ordered shots",
                  "items": {"type": "object"}}},
      mutating=True)
def plan_video(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    if args.get("title"):
        p.title = args["title"]
    if args.get("mode", "replace") == "replace":
        p.clips = []
    base = p.next_order_index()
    created = []
    for i, spec in enumerate(args["scenes"]):
        frames = seconds_to_frames(spec.get("duration_s", 5), p.fps)
        clip = Clip(
            order_index=base + i,
            visual_prompt=spec.get("prompt", ""),
            narration_segment=spec.get("narration", ""),
            characters=spec.get("characters", []),
            source_duration_frames=frames,
            out_frame=frames,
            status=ClipStatus.pending,
        )
        p.clips.append(clip)
        created.append(clip.clip_id)
    return result.ok(summary=f"planned {len(created)} scenes", clip_ids=created)


@tool("clone_voice", "Clone a voice from a short audio sample (MisoTTS). Optionally "
      "bind it to a character so their scenes narrate in that voice.",
      {"project_id": "string?", "name": "string", "sample_url": "string",
       "transcript": {"type": "string", "optional": True},
       "bind_character": {"type": "string", "optional": True}},
      mutating=True, generates=True)
def clone_voice(ctx: ToolContext, args: dict) -> dict:
    asset = MediaAsset(
        type=MediaType.audio, model="miso-8b",
        filename=f"voice:{args['name']}", url=args["sample_url"],
        prompt=args.get("transcript", ""),
        generation_status=GenerationStatus.generating,
    )
    if args.get("bind_character"):
        asset.character_id = args["bind_character"]
    ctx.project.media.append(asset)
    return result.ok(summary=f"cloning voice {args['name']}", voice_id=asset.media_id)


@tool("start_generation", "Batch-generate scenes. scope: pending (default), all, or "
      "failed. Queues each as a video job and marks it generating.",
      {"project_id": "string?",
       "scope": {"type": "string", "enum": ["pending", "all", "failed"],
                 "optional": True, "default": "pending"}},
      mutating=True, generates=True)
def start_generation(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    scope = args.get("scope", "pending")
    targets = [
        c for c in p.ordered_clips()
        if scope == "all"
        or (scope == "pending" and c.status == ClipStatus.pending)
        or (scope == "failed" and c.status == ClipStatus.failed)
    ]
    if not targets:
        return result.error("nothing_to_generate", f"no scenes match scope={scope}")
    jobs = []
    for clip in targets:
        asset = MediaAsset(
            type=MediaType.video, model=clip.model or "wan22",
            prompt=clip.visual_prompt, generation_status=GenerationStatus.generating,
            used_by=[clip.clip_id],
        )
        p.media.append(asset)
        clip.source_media_id = asset.media_id
        clip.status = ClipStatus.generating
        jobs.append({"clip_id": clip.clip_id, "job_id": asset.media_id})
    return result.ok(summary=f"queued {len(jobs)} scene(s)", jobs=jobs)
