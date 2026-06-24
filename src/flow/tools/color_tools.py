"""Color/FX tools — author a scene's color grade and effect chain.

Records the grade/effects on the clip; the ffmpeg filtergraph compiler applies
them at assembly (branching off the fast concat path only when a look exists).
inspect_color returns the applied look now; numeric scopes layer on later via the
render+analysis service.
"""

from __future__ import annotations

from src.flow.store.models import ColorGrade, Effect
from src.flow.tools import result
from src.flow.tools.context import ToolContext
from src.flow.tools.registry import tool

_GRADE_FIELDS = ("exposure", "temperature", "contrast", "saturation", "brightness", "lut")


@tool("apply_color", "Author/refine a scene's color grade (exposure, temperature, "
      "contrast, saturation, brightness, lut). Merges with any existing grade.",
      {"project_id": "string?", "clip_id": "string",
       "exposure": {"type": "number", "minimum": -4, "maximum": 4, "optional": True,
                    "description": "stops"},
       "temperature": {"type": "number", "minimum": -100, "maximum": 100, "optional": True},
       "contrast": {"type": "number", "minimum": 0, "maximum": 4, "optional": True},
       "saturation": {"type": "number", "minimum": 0, "maximum": 4, "optional": True},
       "brightness": {"type": "number", "minimum": -1, "maximum": 1, "optional": True},
       "lut": {"type": "string", "optional": True}},
      mutating=True)
def apply_color(ctx: ToolContext, args: dict) -> dict:
    clip = ctx.project.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    grade = clip.color_grade or ColorGrade()
    changed = [f for f in _GRADE_FIELDS if f in args]
    if not changed:
        return result.error("invalid", "provide at least one grade control")
    for f in changed:
        setattr(grade, f, args[f])
    clip.color_grade = grade
    return result.ok(summary=f"graded {clip.clip_id} ({', '.join(changed)})")


@tool("apply_effect", "Add a look/FX to a scene's effect chain (e.g. blur, sharpen, "
      "vignette, grain, glow). Returns a stable effect_id.",
      {"project_id": "string?", "clip_id": "string",
       "effect": {"type": "string",
                  "enum": ["blur", "sharpen", "vignette", "grain", "glow",
                           "black_white", "sepia", "mirror"]},
       "params": {"type": "object", "optional": True}},
      mutating=True)
def apply_effect(ctx: ToolContext, args: dict) -> dict:
    clip = ctx.project.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    fx = Effect(name=args["effect"], params=args.get("params", {}))
    clip.effects.append(fx)
    return result.ok(summary=f"applied {fx.name} to {clip.clip_id}", effect_id=fx.effect_id)


@tool("inspect_color", "Return a scene's current grade + effect chain. (Numeric "
      "scopes — histogram/waveform — come from the render+analysis service.)",
      {"project_id": "string?", "clip_id": "string"})
def inspect_color(ctx: ToolContext, args: dict) -> dict:
    clip = ctx.project.get_clip(args["clip_id"])
    if clip is None:
        return result.error("not_found", f"no clip {args['clip_id']}")
    return result.ok(
        clip_id=clip.clip_id,
        color_grade=clip.color_grade.model_dump() if clip.color_grade else None,
        effects=[e.model_dump() for e in clip.effects],
        scopes_available=False,
    )
