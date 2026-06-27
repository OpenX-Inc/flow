"""Generation tools — Wan2.2/VACE video, images, audio/TTS, upscale, import.

These are the gated (``generates=True``) tools. They record intent in the store
(pending MediaAsset + scene wiring) and return a job handle; the actual GPU/TTS
execution is performed by the generation service (wired in the runtime) which
flips status to ``ready`` and fills ``video_url`` via callback. Importing is the
exception — it lands a ready asset immediately.
"""

from __future__ import annotations

from src.flow.store.frames import seconds_to_frames
from src.flow.store.media import GenerationStatus, MediaAsset, MediaType
from src.flow.store.models import Clip, ClipStatus
from src.flow.tools import result
from src.flow.tools.context import ToolContext
from src.flow.tools.registry import tool


def _pending_asset(ctx: ToolContext, mtype: MediaType, *, model: str, prompt: str,
                   refs: list[str] | None = None) -> MediaAsset:
    asset = MediaAsset(
        type=mtype, model=model, prompt=prompt,
        reference_images=refs or [],
        generation_status=GenerationStatus.generating,
    )
    ctx.project.media.append(asset)
    return asset


@tool("generate_video", "Generate (or regenerate) a scene's video with Wan2.2/VACE. "
      "Pass scene_id to regenerate that scene in place; omit it to append a new "
      "scene. Returns a job handle; status becomes 'ready' when the GPU finishes.",
      {"project_id": "string?",
       "prompt": "string",
       "model": {"type": "string", "optional": True, "default": "wan22"},
       "mode": {"type": "string", "enum": ["t2v", "i2v", "flf2v", "vace"],
                "optional": True, "default": "t2v"},
       "duration_s": {"type": "number", "minimum": 1, "maximum": 30, "optional": True,
                      "default": 5},
       "scene_id": {"type": "string", "optional": True},
       "first_frame_ref": {"type": "string", "optional": True},
       "reference_images": {"type": "array", "items": "string", "optional": True},
       "character_ids": {"type": "array", "items": "string", "optional": True}},
      mutating=True, generates=True)
def generate_video(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    frames = seconds_to_frames(args.get("duration_s", 5), p.fps)
    model = args.get("model", "wan22")
    refs = args.get("reference_images", [])
    asset = _pending_asset(ctx, MediaType.video, model=model, prompt=args["prompt"], refs=refs)

    if args.get("scene_id"):
        clip = p.get_clip(args["scene_id"])
        if clip is None:
            return result.error("not_found", f"no scene {args['scene_id']}")
    else:
        clip = Clip(order_index=p.next_order_index(), source_duration_frames=frames,
                    out_frame=frames)
        p.clips.append(clip)

    clip.visual_prompt = args["prompt"]
    clip.model = model
    clip.reference_images = refs
    clip.characters = args.get("character_ids", clip.characters)
    clip.first_frame_ref = args.get("first_frame_ref")
    clip.source_media_id = asset.media_id
    clip.status = ClipStatus.generating
    asset.used_by = [clip.clip_id]

    # Real execution: if a generation service is present, run the GPU job in the
    # background and write the real URL back to the store on completion.
    if ctx.services is not None and hasattr(ctx.services, "generate_video"):
        from src.flow.agent import jobs
        ctx.store.save(ctx.project)  # persist pending rows before the worker loads
        jobs.submit_video(
            ctx.services, ctx.store, ctx.project.project_id,
            clip_id=clip.clip_id, media_id=asset.media_id, prompt=args["prompt"],
            mode=args.get("mode", "t2v"), duration_s=int(args.get("duration_s", 5)),
            fps=ctx.project.fps,
        )
    return result.ok(summary=f"queued {args.get('mode', 't2v')} for {clip.clip_id}",
                     job_id=asset.media_id, clip_id=clip.clip_id, media_id=asset.media_id)


@tool("generate_image", "Generate an image (keyframe, character reference, or title "
      "card). Returns pending media id(s).",
      {"project_id": "string?", "prompt": "string",
       "purpose": {"type": "string",
                   "enum": ["keyframe", "character_reference", "title_card", "generic"],
                   "optional": True, "default": "generic"},
       "n": {"type": "integer", "minimum": 1, "maximum": 4, "optional": True, "default": 1},
       "character_id": {"type": "string", "optional": True}},
      mutating=True, generates=True)
def generate_image(ctx: ToolContext, args: dict) -> dict:
    ids = []
    for _ in range(args.get("n", 1)):
        asset = _pending_asset(ctx, MediaType.image, model="image", prompt=args["prompt"])
        if args.get("character_id"):
            asset.character_id = args["character_id"]
        ids.append(asset.media_id)
    return result.ok(summary=f"queued {len(ids)} image(s)", media_ids=ids)


@tool("generate_audio", "Generate narration (edge-tts / MisoTTS), music, or sfx. "
      "Lands a pending audio asset; place it on the audio track with set_narration "
      "or it auto-attaches when from_scene_id is given.",
      {"project_id": "string?",
       "kind": {"type": "string", "enum": ["narration", "music", "sfx"],
                "optional": True, "default": "narration"},
       "text": {"type": "string", "optional": True, "description": "TTS text"},
       "from_scene_id": {"type": "string", "optional": True,
                         "description": "use this scene's narration_segment as text"},
       "voice": {"type": "string", "optional": True},
       "model": {"type": "string", "optional": True, "default": "edge-tts"}},
      mutating=True, generates=True)
def generate_audio(ctx: ToolContext, args: dict) -> dict:
    text = args.get("text", "")
    if args.get("from_scene_id"):
        clip = ctx.project.get_clip(args["from_scene_id"])
        if clip is None:
            return result.error("not_found", f"no scene {args['from_scene_id']}")
        text = clip.narration_segment or text
    if args.get("kind", "narration") == "narration" and not text:
        return result.error("invalid", "narration requires text or a from_scene_id with narration")
    asset = _pending_asset(ctx, MediaType.audio, model=args.get("model", "edge-tts"), prompt=text)
    if ctx.services is not None and hasattr(ctx.services, "generate_narration") \
            and args.get("kind", "narration") == "narration":
        from src.flow.agent import jobs
        ctx.store.save(ctx.project)
        jobs.submit_narration(ctx.services, ctx.store, ctx.project.project_id,
                              media_id=asset.media_id, text=text, voice=args.get("voice"))
    return result.ok(summary=f"queued {args.get('kind', 'narration')} audio",
                     job_id=asset.media_id, media_id=asset.media_id)


@tool("upscale_media", "Upscale an existing video/image asset to a higher resolution "
      "(creates a new pending version).",
      {"project_id": "string?", "media_id": "string",
       "model": {"type": "string", "optional": True, "default": "upscaler"}},
      mutating=True, generates=True)
def upscale_media(ctx: ToolContext, args: dict) -> dict:
    src = ctx.project.get_media(args["media_id"])
    if src is None:
        return result.error("not_found", f"no media {args['media_id']}")
    asset = _pending_asset(ctx, src.type, model=args.get("model", "upscaler"),
                           prompt=f"upscale of {src.media_id}")
    return result.ok(summary=f"queued upscale of {src.media_id}", media_id=asset.media_id)


@tool("import_media", "Import an external asset (stock, music, web, another MCP "
      "server) into the library by URL. Lands a ready asset immediately.",
      {"project_id": "string?", "url": "string",
       "type": {"type": "string", "enum": ["video", "image", "audio"]},
       "filename": {"type": "string", "optional": True}},
      mutating=True)
def import_media(ctx: ToolContext, args: dict) -> dict:
    asset = MediaAsset(
        type=MediaType(args["type"]), url=args["url"],
        filename=args.get("filename", args["url"].rsplit("/", 1)[-1]),
        generation_status=GenerationStatus.ready,
    )
    ctx.project.media.append(asset)
    return result.ok(summary=f"imported {asset.filename}", media_id=asset.media_id)
