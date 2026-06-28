# Flow Agent Tools — Group 04: Color / FX + Media Management

**Date:** 2026-06-24
**Scope:** 0.3 agentic editing tool surface — the **colorist** and **librarian**
tools. Nine wire-tools:
`apply_color`, `apply_effect`, `inspect_color`,
`create_folder`, `move_to_folder`, `rename_media`, `rename_folder`,
`delete_media`, `delete_folder`.

**Read first (every stage):**
`docs/research/agentic-video-editing-analysis.md`,
`docs/research/agent-tool-loop-nanocode.md`,
`docs/research/palmier-video-tools-catalog.md`.

These tools are exposed by the **VPS MCP server** (loopback + auth, à la Palmier),
driven by the in-app **agent loop** (nanocode pattern) calling **NVIDIA build,
default model `kimi`**, OpenAI-style tool-calling. Each beats Palmier's
equivalent: richer JSON Schema (enums, ranges, units, examples), generation-native,
character-aware, undoable, with a `canGenerate`/credits gate.

> Palmier color/FX tools (`apply_color`, `apply_effect`, `inspect_color`) and the
> six media-management tools (`create_folder`, `move_to_folder`, `rename_media`,
> `rename_folder`, `delete_media`, `delete_folder`) are the reference menu. Flow
> re-implements all nine richer.

---

## 0. Foundations (read before the per-tool specs)

### 0.1 Scenes ARE the timeline — where color/FX live

Flow does **not** rebuild a generic NLE. The ordered scenes are the **video
track**; ffmpeg assembly concatenates them into one complete track
(`postproduction.py::_ffmpeg_assemble`), with parallel **audio** (narration/music
via edge-tts / MisoTTS) and **caption/text** tracks composited on top.

Color and effects therefore attach at **two scopes**:

| Scope | Where stored | Renders as | Typical use |
|--|--|--|--|
| **Scene-level** | `Scene.color_grade`, `Scene.effects[]` | per-segment filter chain, applied to that scene's decoded stream before `concat` | fix one shot, stylize a beat |
| **Project-level** | `Project.color_grade`, `Project.effects[]` | one filter chain applied to the concatenated track (post-concat, pre-mux) | global "look", LUT, letterbox |

There is no separate "adjustment-layer track." A project grade is just a grade
that compiles onto the post-concat node. This keeps the mental model = scenes +
one master, nothing more.

### 0.2 The scene/track model extension (0.3)

`schemas.py::Scene` today is minimal (`id, duration, visual_prompt, camera,
narration_segment, characters`). 0.3 extends it with the clip/grade fields the
Palmier data model proves out (every clip remembers its look so it can be
re-rolled / re-graded in place):

```python
class ColorGrade(BaseModel):          # additive, all fields optional/neutral
    exposure: float = 0.0             # stops, [-3.0, 3.0]
    contrast: float = 1.0             # [0.0, 4.0], 1.0 = neutral
    saturation: float = 1.0           # [0.0, 3.0]
    vibrance: float = 0.0             # [-2.0, 2.0]
    temperature: int = 6500           # Kelvin [1000, 40000], 6500 = neutral
    tint: float = 0.0                 # green<->magenta [-1.0, 1.0]
    hue_shift: float = 0.0            # degrees [-180, 180]
    gamma: float = 1.0                # [0.1, 10.0]
    lift:  RGB = (0,0,0)              # shadows  per-channel [-1,1]
    gamma_rgb: RGB = (0,0,0)          # midtones per-channel [-1,1]
    gain:  RGB = (0,0,0)             # highlights per-channel [-1,1]
    lut: str | None = None            # media_id of a .cube 3D LUT asset
    lut_strength: float = 1.0         # [0.0, 1.0] mix
    curves: Curves | None = None      # control points per channel

class Effect(BaseModel):
    id: str                           # stable id for undo / re-order
    name: str                         # enum, see apply_effect
    params: dict                      # validated against the effect's sub-schema
    enabled: bool = True
    range: FrameRange | None = None   # None = whole scene
    order: int                        # position in the chain (lower = earlier)

class Scene(BaseModel):
    id: int
    duration: int = 5
    visual_prompt: str
    camera: str = ""
    narration_segment: str = ""
    characters: list[str] = []
    # --- 0.3 timeline/look fields ---
    color_grade: ColorGrade | None = None
    effects: list[Effect] = []
    edit_history: list[EditOp] = []   # undo stack (see 0.5)
```

Defaults that are neutral/identity are **omitted from tool payloads** (token
hygiene, Palmier habit): a scene with no grade serializes `color_grade: null`,
not a full neutral object.

### 0.3 How color/effects compile into the ffmpeg render

Today `_ffmpeg_assemble` does a fast `concat` demuxer pass with `-c copy`, then a
second pass for audio + subtitle burn. Stream-copy **cannot** carry per-scene
filters. 0.3 introduces a deterministic **filtergraph compiler**:

**Render strategy selection**
- If **no** scene grade/effect and **no** project grade/effect exist → keep the
  fast `concat -c copy` path (unchanged, zero regression).
- If **any** color/FX is present → switch the affected stage to the
  `filter_complex` concat path below. Scenes with no look still decode but pass
  through an identity chain (or are pre-baked once and cached — see 0.6).

**Filtergraph build order (per scene, then concat):**
```
[i:v] →
  1. geometry      (scale/crop/transform/trim/speed  ← clip props, set_clip_properties)
  2. color_grade   (apply_color)                       ← THIS GROUP
  3. effects[]     (apply_effect, ordered by .order)   ← THIS GROUP
  4. fps/format    (normalize to project fps + yuv420p + SAR)
→ [v_i]
... concat=n=N:v=1:a=0 [vcat]
[vcat] → project color_grade → project effects[] → [vout]
[vout] + caption/text overlays (text track) → mux with audio track → output
```

Color is applied **before** effects so looks (grain, vignette, bloom) sit on top
of the graded image — the order a colorist expects. Geometry is first so grades
measure the final framing.

**`ColorGrade` → ffmpeg filter mapping (canonical):**

| Control | ffmpeg filter fragment |
|--|--|
| exposure (stops) | `eq=brightness=<stops*0.10>` (also feeds `gain` mids) |
| contrast | `eq=contrast=<contrast>` |
| saturation | `eq=saturation=<saturation>` |
| vibrance | `vibrance=intensity=<vibrance>` |
| temperature | `colortemperature=temperature=<K>:mix=1` |
| tint | `colorbalance=gm=<tint>` (green↔magenta on mids) |
| hue_shift | `hue=h=<deg>` |
| gamma (master) | `eq=gamma=<gamma>` |
| lift (shadows R/G/B) | `colorbalance=rs=<r>:gs=<g>:bs=<b>` |
| gamma_rgb (mids) | `colorbalance=rm=<r>:gm=<g>:bm=<b>` |
| gain (highlights) | `colorbalance=rh=<r>:gh=<g>:bh=<b>` |
| curves | `curves=r='<pts>':g='<pts>':b='<pts>'` |
| lut + lut_strength | `lut3d=file=<cube>` blended via `[a][b]blend=all_opacity=<strength>` |

**`Effect.name` → ffmpeg mapping** is enumerated under `apply_effect` (§2).

The compiler is pure and deterministic: same `(ColorGrade, effects[])` →
identical filter string → cache key. Generative effects (AI relight, style
transfer) are the exception: they bake a new asset (see §2 / credits gate).

### 0.4 Units convention (frames vs seconds) — beats Palmier's looseness

Every time-valued field is **explicit about units**. Default unit is **frames**
(the timeline's native unit). A sibling `unit` enum (`"frames" | "seconds"`)
flips interpretation; conversions use the project fps:
`frame = round(seconds * fps)`. Project fps is in `get_project` (default 24 if
unset — Flow scenes are 5 s clips). Ranges are `[start, end)` half-open, end
exclusive. Tools reject out-of-range frames with a clear error string (fed back
to the model for self-correction — the nanocode error-as-string trick).

### 0.5 Undo semantics (every edit is one reversible action)

Mirrors Palmier's "one undoable action" + `undo` tool, extended:
- Every mutating call (`apply_color`, `apply_effect`, all media-mgmt writes)
  produces **one** `EditOp` pushed onto a per-project undo stack and returns an
  `undo_token`.
- `EditOp` stores `{tool, target_id, before, after, ts}` — a full inverse, so the
  group-05 `undo` tool restores the exact prior state (grade object, effect list,
  folder tree, asset name/location).
- Deletes are **soft** (Trash, surfaced in the web app's Trash page): `delete_media`
  / `delete_folder` move to Trash and are restorable by `undo` or an explicit
  restore; hard purge is a separate, gated, non-agent action.
- Color/FX undo never touches pixels of source assets — it edits the
  scene/project look object; the next render reflects it. Generative bakes
  (§2) keep the prior asset, so undo just re-points the scene back.

### 0.6 `canGenerate` / credits gate

Read-only tools (`inspect_color`) **always** work. Pure-ffmpeg color/FX (CPU,
local on the VPS) are **free** — no credits, work even when signed-out/over-quota.
**Generative** effects (AI relight, style transfer, generative grain via VACE,
upscaling looks) route to OpenX Cloud → Modal GPU and are **gated**: the tool
checks `canGenerate` + credits first and, if blocked, returns a structured
`needs: {reason, action_url}` instead of running (clear "subscribe/top-up"
message, never a silent no-op). Every tool response carries a `gate` block so the
agent can reason about cost before acting.

### 0.7 Common response envelope

All nine tools return:
```jsonc
{
  "ok": true,
  "undo_token": "op_8f3...",        // null for read-only tools
  "gate": { "free": true, "canGenerate": true, "credits_charged": 0 },
  "warnings": ["..."],               // non-fatal (e.g., clipping introduced)
  "result": { /* tool-specific, see each output schema */ }
}
```
On failure: `{ "ok": false, "error": "<message>", "code": "<enum>" }` — the
message is human-readable and model-actionable.

---

## 1. `apply_color` — named color-grade controls

**wire-name:** `apply_color`

**purpose:** Author or refine a **color grade** on a scene or the whole project
using named, physically-meaningful controls (exposure in stops, temperature in
Kelvin, lift/gamma/gain, LUT). Compiles to the `eq`/`colorbalance`/`colortemperature`/`curves`/`lut3d`
fragments in §0.3.

**when-to-call:** When the user asks to fix or stylize color ("warm this up",
"crush the blacks", "match scene 3 to scene 1", "apply the teal-orange LUT",
"too dark, lift exposure"). Call `inspect_color` first when the ask is corrective
("fix the exposure") so the grade is measured, not guessed.

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "target": {
      "type": "object",
      "description": "Where the grade applies. Exactly one of scene_id or project.",
      "properties": {
        "scene_id": { "type": "integer", "minimum": 0,
                      "description": "Grade this scene. Omit for project-wide." },
        "project":  { "type": "boolean",
                      "description": "true = master grade on concatenated track." }
      }
    },
    "mode": {
      "type": "string", "enum": ["set", "merge", "reset"], "default": "merge",
      "description": "merge=apply over current grade; set=replace; reset=neutral."
    },
    "range": {
      "type": "object",
      "description": "Sub-range within target (frames default). Omit = whole target.",
      "properties": {
        "start": { "type": "integer", "minimum": 0 },
        "end":   { "type": "integer", "minimum": 1 },
        "unit":  { "type": "string", "enum": ["frames","seconds"], "default": "frames" }
      }
    },
    "grade": {
      "type": "object",
      "description": "Named controls. Omitted fields are unchanged (merge) / neutral (set).",
      "properties": {
        "exposure":    { "type": "number", "minimum": -3.0, "maximum": 3.0, "default": 0.0,
                         "description": "Stops. +1.0 doubles light. unit:stops" },
        "contrast":    { "type": "number", "minimum": 0.0, "maximum": 4.0, "default": 1.0 },
        "saturation":  { "type": "number", "minimum": 0.0, "maximum": 3.0, "default": 1.0,
                         "description": "0=greyscale, 1=neutral." },
        "vibrance":    { "type": "number", "minimum": -2.0, "maximum": 2.0, "default": 0.0,
                         "description": "Smart saturation, protects skin tones." },
        "temperature": { "type": "integer", "minimum": 1000, "maximum": 40000, "default": 6500,
                         "description": "Kelvin. <6500 warmer, >6500 cooler. unit:kelvin" },
        "tint":        { "type": "number", "minimum": -1.0, "maximum": 1.0, "default": 0.0,
                         "description": "-1 green ... +1 magenta." },
        "hue_shift":   { "type": "number", "minimum": -180, "maximum": 180, "default": 0.0,
                         "description": "Degrees. unit:degrees" },
        "gamma":       { "type": "number", "minimum": 0.1, "maximum": 10.0, "default": 1.0 },
        "lift":  { "type": "array", "items": {"type":"number","minimum":-1,"maximum":1},
                   "minItems": 3, "maxItems": 3, "description": "Shadows [R,G,B]." },
        "gamma_rgb": { "type": "array", "items": {"type":"number","minimum":-1,"maximum":1},
                   "minItems": 3, "maxItems": 3, "description": "Midtones [R,G,B]." },
        "gain":  { "type": "array", "items": {"type":"number","minimum":-1,"maximum":1},
                   "minItems": 3, "maxItems": 3, "description": "Highlights [R,G,B]." },
        "lut":          { "type": "string", "description": "media_id of a .cube 3D LUT asset." },
        "lut_strength": { "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 1.0 },
        "curves": {
          "type": "object",
          "description": "Per-channel control points, x/y in [0,1].",
          "properties": {
            "master": { "type": "array", "items": { "type":"array","items":{"type":"number"},
                        "minItems":2, "maxItems":2 } },
            "r": { "type": "array" }, "g": { "type": "array" }, "b": { "type": "array" }
          }
        }
      }
    },
    "match_to_scene_id": {
      "type": "integer", "minimum": 0,
      "description": "Optional: auto-derive a grade that matches this reference scene's "
                     "scopes (uses inspect_color internally). Overrides individual controls."
    },
    "preset": {
      "type": "string",
      "enum": ["teal_orange","bleach_bypass","warm_film","cool_night","high_key",
               "low_key","vintage_fade","neutral_correct"],
      "description": "Named starting grade; further controls merge on top."
    }
  },
  "required": ["target"],
  "examples": [
    { "target": {"scene_id": 3}, "grade": {"exposure": 0.7, "temperature": 5200} },
    { "target": {"project": true}, "preset": "teal_orange", "grade": {"contrast": 1.15} },
    { "target": {"scene_id": 5}, "match_to_scene_id": 1 }
  ]
}
```

**output schema:**
```jsonc
{
  "ok": true,
  "undo_token": "op_...",
  "gate": { "free": true, "canGenerate": true, "credits_charged": 0 },
  "result": {
    "target": { "scene_id": 3 },
    "applied_grade": { "exposure": 0.7, "temperature": 5200, "contrast": 1.0 },
    "ffmpeg_chain": "eq=brightness=0.07,colortemperature=temperature=5200:mix=1",
    "preview_url": "https://.../previews/scene3_grade_8f3.jpg",  // 1-frame proxy
    "clipping": { "highlight_pct": 0.4, "shadow_pct": 0.0 }       // post-grade
  }
}
```

**behavior:**
1. Resolve target (scene or project), load current `ColorGrade`.
2. If `preset`, seed from preset table. If `match_to_scene_id`, run an internal
   `inspect_color` on both scenes and solve exposure/temp/contrast deltas to
   minimize scope distance; merge solved values.
3. Apply `mode` (merge/set/reset) with the explicit controls.
4. Validate ranges; compile to the §0.3 fragment string; render a single
   mid-scene **preview frame** (fast, one `-vframes 1` decode) so the agent/user
   sees the result without a full render.
5. Persist grade on the scene/project, push `EditOp`, return chain + preview +
   post-grade clipping stats.

**edge cases:**
- Both `scene_id` and `project` set → error `AMBIGUOUS_TARGET`.
- `range` on a `project` target → grade applies to those frames of the master
  track via `enable='between(t,..)'` gating on the filter.
- `lut` media_id not a `.cube`/not found → `INVALID_LUT`.
- `match_to_scene_id` references a scene with no rendered frames yet (still
  generating) → `SOURCE_NOT_READY`, suggests retry after generation.
- Grade that drives >2% highlight clipping → succeeds but emits a `warnings`
  entry with the clip %.
- `reset` with no existing grade → no-op success, `undo_token: null`.

**undo semantics:** One `EditOp` storing `before`/`after` `ColorGrade`. `undo`
restores the prior object exactly (including `null`). No pixels touched — the
look is re-derived at render.

**scene/track mapping:** Scene target → fragment injected at node **2** of that
scene's per-segment chain (§0.3), before effects. Project target → fragment on
the post-`concat` `[vcat]` node. `range` → wrapped in `enable='between(...)'`.

**How this beats Palmier:** Palmier's `apply_color` is a free-form colorist
description handed to a model. Flow exposes **named, ranged, unit-tagged controls**
(exposure in *stops*, temperature in *Kelvin*, lift/gamma/gain), deterministic
ffmpeg compilation, a one-frame **preview** in the response, **`match_to_scene_id`**
auto-matching driven by real scopes, and **clipping feedback** so the agent self-
corrects. It is reproducible and undoable to the exact prior object — Palmier's
prose grade is neither measurable nor diffable.

---

## 2. `apply_effect` — looks / FX

**wire-name:** `apply_effect`

**purpose:** Add, configure, reorder, or remove a stylistic/technical **effect**
on a scene or the project. Covers CPU ffmpeg looks (grain, vignette, blur,
sharpen, glow, b/w, sepia, letterbox, fade, denoise, stabilize, chromatic
aberration, VHS/glitch) **and** Flow-native **generative** looks (AI relight,
style transfer, generative film-stock) that bake via Wan2.2/VACE on Modal.

**when-to-call:** "make it cinematic / add bars", "add film grain", "blur the
background", "give it a VHS look", "stabilize the shaky shot", "fade out the last
scene", "relight scene 4 to golden hour" (generative).

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "target": {
      "type": "object",
      "properties": {
        "scene_id": { "type": "integer", "minimum": 0 },
        "project":  { "type": "boolean" }
      },
      "description": "Exactly one of scene_id / project."
    },
    "action": {
      "type": "string", "enum": ["add","update","remove","reorder","toggle"],
      "default": "add"
    },
    "effect_id": {
      "type": "string",
      "description": "Required for update/remove/reorder/toggle. From a prior add."
    },
    "name": {
      "type": "string",
      "description": "Effect type (required for add).",
      "enum": [
        "film_grain","vignette","blur","sharpen","glow","black_white","sepia",
        "letterbox","fade","chromatic_aberration","vhs","glitch","denoise",
        "stabilize","ai_relight","style_transfer","ai_film_stock"
      ]
    },
    "params": {
      "type": "object",
      "description": "Validated against the chosen effect's sub-schema (see table).",
      "examples": [
        { "intensity": 0.3 },
        { "type": "in", "duration": 12, "unit": "frames" },
        { "ratio": "2.39:1", "color": "black" },
        { "style_prompt": "Studio Ghibli watercolor", "strength": 0.6 }
      ]
    },
    "range": {
      "type": "object",
      "properties": {
        "start": { "type": "integer", "minimum": 0 },
        "end":   { "type": "integer", "minimum": 1 },
        "unit":  { "type": "string", "enum": ["frames","seconds"], "default": "frames" }
      },
      "description": "Sub-range; omit = whole target."
    },
    "order": {
      "type": "integer", "minimum": 0,
      "description": "Position in the effect chain (reorder / add). Lower = earlier."
    },
    "enabled": { "type": "boolean", "default": true }
  },
  "required": ["target"],
  "examples": [
    { "target": {"scene_id": 2}, "name": "film_grain", "params": {"intensity": 0.25} },
    { "target": {"project": true}, "name": "letterbox", "params": {"ratio": "2.39:1"} },
    { "target": {"scene_id": 9}, "name": "fade", "params": {"type":"out","duration":18} },
    { "target": {"scene_id": 4}, "name": "ai_relight",
      "params": {"lighting": "golden hour, low sun camera-left", "strength": 0.7} },
    { "target": {"scene_id": 2}, "action": "remove", "effect_id": "fx_7a1" }
  ]
}
```

**Per-effect `params` sub-schemas + ffmpeg mapping (CPU effects are free):**

| name | params (typed) | ffmpeg / engine | gate |
|--|--|--|--|
| `film_grain` | `intensity` 0–1, `size` 0–1 | `noise=alls=<i*60>:allf=t+u` | free |
| `vignette` | `amount` 0–1, `angle` rad | `vignette=angle=<a>` (+`eq` for amount) | free |
| `blur` | `sigma` 0–50, `region` enum(all/bg) | `gblur=sigma=<s>` (`bg`→mask) | free |
| `sharpen` | `amount` 0–3 | `unsharp=5:5:<a>:5:5:0` | free |
| `glow` | `threshold` 0–1, `intensity` 0–1 | split→`gblur`→`blend=screen` | free |
| `black_white` | `tone` enum(neutral/warm/cool) | `hue=s=0` (+colorbalance) | free |
| `sepia` | `strength` 0–1 | `colorchannelmixer=.393:.769:.189:...` | free |
| `letterbox` | `ratio` enum(2.39:1/2.35:1/1.85:1/16:9), `color` | `pad`/`crop` bars | free |
| `fade` | `type` enum(in/out), `duration` int, `unit`, `color` | `fade=t=<type>:st=:d=` | free |
| `chromatic_aberration` | `amount` px 0–20 | `rgbashift=rh=<a>:bh=-<a>` | free |
| `vhs` | `intensity` 0–1 | chain: `rgbashift`+`noise`+`curves`+`gblur` | free |
| `glitch` | `intensity` 0–1, `seed` int | `noise`+`rgbashift` keyed on `enable` | free |
| `denoise` | `strength` 0–1 | `hqdn3d=<s*8>` (or `nlmeans`) | free |
| `stabilize` | `smoothing` 0–100 | 2-pass `vidstabdetect`+`vidstabtransform` | free |
| `ai_relight` | `lighting` str, `strength` 0–1 | **VACE** re-light bake | **gated** |
| `style_transfer` | `style_prompt` str, `strength` 0–1, `character_lock` bool | **Wan2.2 i2v / VACE** bake | **gated** |
| `ai_film_stock` | `stock` enum(kodak2383/fuji3513/...), `strength` | learned LUT + grain bake | **gated** |

**output schema:**
```jsonc
{
  "ok": true,
  "undo_token": "op_...",
  "gate": { "free": false, "canGenerate": true, "credits_charged": 12 },  // generative
  "result": {
    "target": { "scene_id": 4 },
    "effect": { "id": "fx_9c2", "name": "ai_relight", "order": 1, "enabled": true,
                "params": { "lighting": "golden hour...", "strength": 0.7 } },
    "chain_after": ["film_grain", "ai_relight"],     // resolved order on target
    "ffmpeg_chain": "noise=alls=15:allf=t+u",         // CPU portion only
    "generation_job_id": "gen_44a",                    // present for generative
    "preview_url": "https://.../previews/scene4_fx_9c2.jpg"
  }
}
```

**behavior:**
- `add` — validate `params` against the effect sub-schema, assign `effect_id` +
  `order` (append if unset), push onto `Scene.effects[]` / project. CPU effects
  compile immediately into the chain (§0.3 node 3). Generative effects enqueue a
  Modal job (after the gate passes); the scene's source asset is **replaced** by
  the baked output on completion, with the original retained for undo.
- `update`/`toggle`/`reorder`/`remove` — mutate the existing entry by `effect_id`;
  reorder rewrites `.order` and recompiles the chain.
- Always returns a preview frame (CPU) or a `generation_job_id` (generative) the
  agent can poll via the generate-group tools.

**edge cases:**
- `add` without `name` → `MISSING_EFFECT_NAME`.
- `update`/`remove` with unknown `effect_id` → `EFFECT_NOT_FOUND`.
- Unknown `params` key or out-of-range value → `INVALID_PARAMS` naming the key.
- `stabilize` on a scene shorter than the analysis window → succeeds with reduced
  smoothing + warning.
- Two conflicting effects (e.g., `black_white` + `style_transfer` color style) →
  succeeds but warns; chain order decides the visible result.
- Generative effect when `canGenerate=false` or credits insufficient → no job
  enqueued, returns `{ok:false, code:"GATE_BLOCKED", needs:{reason, action_url}}`.
- `character_lock:true` on `style_transfer` with no character attached → warns and
  proceeds without subject preservation.

**undo semantics:** Each action = one `EditOp`. `add`→inverse `remove`;
`remove`→re-insert with stored params/order; `reorder`→restore prior order array;
generative bake→`before` keeps the original asset id so `undo` re-points the
scene back (and cancels/ignores the job output). Credits already spent on a
completed bake are **not** refunded by undo (documented; the gate response stated
the cost up front).

**scene/track mapping:** CPU effects = filter fragments at node **3** of the
scene chain (or post-concat for project), ordered by `.order`, range-gated via
`enable='between(...)'`. Generative effects **re-bake the scene's video asset**
(the scene is still the same timeline slot; only its source clip changes), so the
fast `concat` path can resume for that scene afterward.

**How this beats Palmier:** Palmier's `apply_effect` is a generic "looks/FX"
proxy. Flow ships a **typed effect registry** (per-effect param sub-schemas,
enums, ranges, frame/second units), an explicit **ordered, reorderable chain**
with stable `effect_id`s, a **free-vs-gated** split surfaced in every response,
and — uniquely — **generation-native, character-aware** effects (`ai_relight`,
`style_transfer` with `character_lock`, `ai_film_stock`) that bake through
Flow-owned Wan2.2/VACE rather than a third-party black box. Every effect is
individually undoable and previewable.

---

## 3. `inspect_color` — scopes

**wire-name:** `inspect_color`

**purpose:** Measure color/exposure of a scene, a frame, or the project's
composited output — numeric scope stats **and** rendered scope images
(histogram, waveform, vectorscope, RGB parade). Read-only; the eyes behind
`apply_color`.

**when-to-call:** Before a corrective grade ("is this clipping?", "what's the
white balance?"), to compare two scenes for matching, or to verify a grade
("did that fix the crushed blacks?"). Always cheap, always allowed.

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "target": {
      "type": "object",
      "properties": {
        "scene_id": { "type": "integer", "minimum": 0 },
        "project":  { "type": "boolean", "description": "Composited final track." },
        "media_id": { "type": "string", "description": "A library asset directly." }
      },
      "description": "Exactly one of scene_id / project / media_id."
    },
    "at": {
      "type": "object",
      "description": "Sample point. Omit = representative mid-frame.",
      "properties": {
        "frame":  { "type": "integer", "minimum": 0 },
        "seconds":{ "type": "number",  "minimum": 0 },
        "mode":   { "type": "string", "enum": ["single","average","overview"],
                    "default": "single",
                    "description": "average=mean over the target; overview=storyboard of N samples." }
      }
    },
    "scopes": {
      "type": "array",
      "items": { "type": "string",
                 "enum": ["histogram","waveform","vectorscope","parade","stats"] },
      "default": ["stats","histogram"],
      "description": "Which scopes to compute/render. 'stats' is numeric-only (no image)."
    },
    "post_grade": {
      "type": "boolean", "default": true,
      "description": "true = measure AFTER the current grade/effects; false = raw source."
    }
  },
  "required": ["target"],
  "examples": [
    { "target": {"scene_id": 3} },
    { "target": {"project": true}, "scopes": ["waveform","parade","stats"] },
    { "target": {"scene_id": 1}, "at": {"mode":"average"}, "post_grade": false }
  ]
}
```

**output schema:**
```jsonc
{
  "ok": true,
  "undo_token": null,
  "gate": { "free": true, "canGenerate": true, "credits_charged": 0 },
  "result": {
    "target": { "scene_id": 3 },
    "sampled": { "frame": 60, "seconds": 2.5, "mode": "single", "post_grade": true },
    "stats": {
      "luma":  { "min": 6,  "max": 251, "mean": 118, "median": 121, "stdev": 47 },  // 0-255
      "rgb_mean": { "r": 130, "g": 116, "b": 99 },
      "black_point": 6, "white_point": 251,
      "clipping": { "shadow_pct": 0.2, "highlight_pct": 1.3 },
      "saturation_mean": 0.41, "saturation_max": 0.93,
      "white_balance": { "temperature_est_k": 5400, "tint_est": 0.05 },
      "exposure_assessment": "balanced"   // enum: underexposed|balanced|overexposed
    },
    "scopes": {
      "histogram":   "https://.../scopes/s3_hist.png",
      "waveform":    "https://.../scopes/s3_wave.png",
      "vectorscope": "https://.../scopes/s3_vec.png",
      "parade":      "https://.../scopes/s3_parade.png"
    }
  }
}
```

**behavior:**
1. Resolve target → a decoded frame (or N frames for average/overview). For
   `project` with `post_grade`, decode the composited filtergraph output at `at`.
2. Numeric `stats` via ffmpeg `signalstats` (YMIN/YMAX/YAVG, SATMAX, HUE) +
   per-channel means; derive black/white points, clipping %, and a white-balance
   estimate; classify exposure.
3. Render requested scope images with `histogram`, `waveform`, `vectorscope`,
   and a `parade` (RGB) filter to PNG proxies; return URLs.
4. Never mutates anything; `undo_token: null`.

**edge cases:**
- Target still generating / no frames → `SOURCE_NOT_READY`.
- `frame` beyond target length → clamps to last frame + warning.
- `media_id` is audio/non-visual → `NOT_VISUAL`.
- `overview` on a 5 s scene → returns a small storyboard (e.g., 5 samples), not
  hundreds.
- Both `frame` and `seconds` set and disagree → `frame` wins, warning emitted.

**undo semantics:** None — read-only. Listed for contract completeness.

**scene/track mapping:** `post_grade=true` measures the exact §0.3 chain output
(geometry→grade→effects), so the agent sees what the render will produce, not the
raw clip. `project` measures the post-concat master node — the composited track
the viewer sees.

**How this beats Palmier:** Palmier's `inspect_color` returns scope measurements.
Flow adds (a) **rendered scope images** (histogram/waveform/vectorscope/parade)
the model can attach/show, not just numbers; (b) a **`post_grade` toggle** to
measure before *or* after the live filter chain — closing the
inspect→grade→verify loop on the real render; (c) a **white-balance estimate +
exposure classification** so the agent gets an opinion, not raw bytes; and (d)
`overview`/`average` sampling modes for whole-scene assessment. Units are explicit
(0–255 luma, Kelvin, percentages).

---

## 4. `create_folder`

**wire-name:** `create_folder`

**purpose:** Create a folder in the project's **media library** (the asset tree
that holds generated/imported clips, images, LUTs, audio — distinct from the
scene timeline). Folders organize assets; they are not timeline tracks.

**when-to-call:** "make a folder for B-roll", "organize the LUTs", before a bulk
`move_to_folder`.

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "name": { "type": "string", "minLength": 1, "maxLength": 120,
              "description": "Folder name. Unique among siblings." },
    "parent_id": { "type": "string",
                   "description": "Parent folder id. Omit = library root." },
    "if_exists": { "type": "string", "enum": ["error","reuse","suffix"],
                   "default": "error",
                   "description": "On name collision: fail / return existing / append ' (2)'." }
  },
  "required": ["name"],
  "examples": [
    { "name": "B-roll" },
    { "name": "LUTs", "parent_id": "fld_root", "if_exists": "reuse" }
  ]
}
```

**output schema:**
```jsonc
{
  "ok": true,
  "undo_token": "op_...",
  "result": { "folder": { "id": "fld_3a", "name": "B-roll", "parent_id": null,
                          "path": "/B-roll", "created_at": "..." },
              "reused": false }
}
```

**behavior:** Validates name (trim, no `/`, length), resolves parent, enforces
sibling-name uniqueness per `if_exists`, creates the node, returns it with its
computed `path`.

**edge cases:** invalid/empty name → `INVALID_NAME`; missing parent →
`PARENT_NOT_FOUND`; collision with `if_exists:error` → `NAME_CONFLICT`;
`reuse`→returns existing with `reused:true` and `undo_token:null`; max depth
(e.g., 16) → `MAX_DEPTH`.

**undo semantics:** Inverse = delete the created (empty) folder. `undo` removes it.

**scene/track mapping:** Library-only — does **not** touch scenes or tracks.
Folders are an asset-organization concern; the timeline references assets by
`media_id` regardless of folder.

**How this beats Palmier:** Adds an **`if_exists` policy** (error/reuse/suffix —
idempotent automation instead of blind failure), explicit **depth/length limits**,
returns the computed **path**, and is undoable. Palmier's `create_folder` is a
bare create.

---

## 5. `move_to_folder`

**wire-name:** `move_to_folder`

**purpose:** Move one or more media assets and/or folders into a destination
folder (re-parent in the library tree). Bulk-capable, transactional.

**when-to-call:** "move all the night shots into B-roll", "put these LUTs in the
LUTs folder", organizing after import/generation.

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array", "minItems": 1, "maxItems": 500,
      "items": {
        "type": "object",
        "properties": {
          "media_id":  { "type": "string" },
          "folder_id": { "type": "string", "description": "Move a whole subtree." }
        },
        "description": "Each item is exactly one of media_id / folder_id."
      }
    },
    "destination_id": { "type": "string",
                        "description": "Target folder id. null/omitted = library root." },
    "on_conflict": { "type": "string", "enum": ["rename","skip","error"],
                     "default": "rename",
                     "description": "If a same-named item already exists at destination." }
  },
  "required": ["items"],
  "examples": [
    { "items": [{"media_id":"m_1"},{"media_id":"m_2"}], "destination_id": "fld_3a" },
    { "items": [{"folder_id":"fld_9"}], "destination_id": null, "on_conflict": "skip" }
  ]
}
```

**output schema:**
```jsonc
{
  "ok": true,
  "undo_token": "op_...",
  "result": {
    "moved": [ { "media_id": "m_1", "from": "fld_root", "to": "fld_3a" } ],
    "skipped": [], "renamed": [],
    "destination": { "id": "fld_3a", "path": "/B-roll" }
  }
}
```

**behavior:** Validates every item exists and destination exists; rejects cycles
(moving a folder into its own descendant); applies `on_conflict`; performs all
moves atomically (all-or-nothing on `error`, per-item on rename/skip); records
each item's prior parent for undo.

**edge cases:** unknown item/destination → `NOT_FOUND` (names the id); cycle →
`CYCLE_DETECTED`; moving an asset **referenced by a scene** is allowed (timeline
refs by id, not path) but emits an informational warning; empty after filter →
`NOTHING_TO_MOVE`.

**undo semantics:** One `EditOp` capturing each item's `{id, from_parent}`. `undo`
restores every item to its original parent.

**scene/track mapping:** Library-only; scene `media_id` references are unaffected
by folder location (decoupled by design) — so reorganizing never breaks a render.

**How this beats Palmier:** **Bulk + mixed** (assets *and* folders) in one
transactional call, **cycle detection**, an **`on_conflict` policy**, and a
single undo that reverses the whole batch. It also guarantees timeline integrity
(refs survive moves) and warns when moving scene-referenced assets — context
Palmier doesn't surface.

---

## 6. `rename_media`

**wire-name:** `rename_media`

**purpose:** Rename a media asset's display name in the library (metadata only;
underlying file path/`media_id` unchanged so scene references survive).

**when-to-call:** "rename clip 4 to 'hero shot'", cleaning up auto-generated
asset names after generation/import.

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "media_id": { "type": "string" },
    "name":     { "type": "string", "minLength": 1, "maxLength": 200 },
    "on_conflict": { "type": "string", "enum": ["allow","error","suffix"],
                     "default": "allow",
                     "description": "Library allows duplicate display names by default." }
  },
  "required": ["media_id", "name"],
  "examples": [ { "media_id": "m_4", "name": "hero shot — sunset" } ]
}
```

**output schema:**
```jsonc
{ "ok": true, "undo_token": "op_...",
  "result": { "media_id": "m_4", "old_name": "wan_t2v_0042.mp4", "new_name": "hero shot — sunset" } }
```

**behavior:** Trims/validates the name, updates the asset's `name` metadata,
records old name. Does not touch the file, `media_id`, or any scene reference.

**edge cases:** unknown id → `MEDIA_NOT_FOUND`; empty/oversized → `INVALID_NAME`;
`on_conflict:error` + duplicate sibling name → `NAME_CONFLICT`; renaming the
asset that is a scene's source → allowed, no render impact (warning optional).

**undo semantics:** `EditOp{old_name → new_name}`; `undo` restores `old_name`.

**scene/track mapping:** Pure metadata; the timeline binds by `media_id`, so a
rename never affects scenes or render output.

**How this beats Palmier:** Explicit **`media_id` vs display-name** separation
(rename is metadata-only — guarantees scene refs and the render are untouched),
an **`on_conflict` policy**, length validation, and undo to the exact prior name.
Palmier renames without clarifying the path/ref-safety contract.

---

## 7. `rename_folder`

**wire-name:** `rename_folder`

**purpose:** Rename a library folder. Updates the folder's name and the computed
`path` of its descendants (paths are derived, not stored on assets, so no asset
rewrite needed).

**when-to-call:** "rename 'untitled folder' to 'Act 2'", tidying the tree.

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "folder_id": { "type": "string" },
    "name":      { "type": "string", "minLength": 1, "maxLength": 120 },
    "on_conflict": { "type": "string", "enum": ["error","suffix"], "default": "error",
                     "description": "Sibling folder names must be unique." }
  },
  "required": ["folder_id", "name"],
  "examples": [ { "folder_id": "fld_9", "name": "Act 2 — B-roll" } ]
}
```

**output schema:**
```jsonc
{ "ok": true, "undo_token": "op_...",
  "result": { "folder_id": "fld_9", "old_name": "untitled folder",
              "new_name": "Act 2 — B-roll", "new_path": "/Act 2 — B-roll",
              "descendants_repathed": 12 } }
```

**behavior:** Validates name + sibling uniqueness, updates the node, recomputes
descendant paths, returns the count repathed.

**edge cases:** unknown id → `FOLDER_NOT_FOUND`; root folder rename → `CANNOT_RENAME_ROOT`;
collision under `error` → `NAME_CONFLICT`; no-op (same name) → success, `undo_token:null`.

**undo semantics:** `EditOp{old_name → new_name}`; `undo` restores the name (paths
recompute back automatically).

**scene/track mapping:** Library-only; since asset paths are derived and scenes
reference `media_id`, renaming a folder never affects the timeline or render.

**How this beats Palmier:** Reports **`descendants_repathed`** so the agent knows
the blast radius, protects the **root**, enforces sibling uniqueness with a policy,
and is undoable. Derived-path design means a folder rename is always render-safe —
an invariant Palmier leaves implicit.

---

## 8. `delete_media`

**wire-name:** `delete_media`

**purpose:** Remove media assets from the library — **soft-delete to Trash** by
default (restorable; matches the web app's Trash page), with an explicit guard
when an asset is referenced by a scene.

**when-to-call:** "delete the failed generations", "remove unused B-roll".

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "media_ids": { "type": "array", "items": {"type":"string"},
                   "minItems": 1, "maxItems": 500 },
    "mode": { "type": "string", "enum": ["trash","purge"], "default": "trash",
              "description": "trash=soft (restorable); purge=permanent (gated, confirm req)." },
    "on_referenced": { "type": "string", "enum": ["block","detach","force"],
                       "default": "block",
                       "description": "If a scene uses the asset: block (default), "
                                      "detach (clear the scene's source first), or force." },
    "confirm": { "type": "boolean", "default": false,
                 "description": "Required true for mode:purge." }
  },
  "required": ["media_ids"],
  "examples": [
    { "media_ids": ["m_10","m_11"] },
    { "media_ids": ["m_5"], "on_referenced": "detach" }
  ]
}
```

**output schema:**
```jsonc
{
  "ok": true,
  "undo_token": "op_...",
  "result": {
    "trashed": ["m_10","m_11"], "purged": [], "blocked": [],
    "referenced": [ { "media_id": "m_5", "scene_ids": [4], "action": "detached" } ],
    "restore_until": "2026-07-24T00:00:00Z"   // trash retention window
  }
}
```

**behavior:** For each id: resolve references across scenes; if referenced, apply
`on_referenced` (block→skip+report; detach→null the scene's source first; force→
soft-delete anyway and mark those scenes "missing source"). `trash` moves to
Trash with a retention window; `purge` requires `confirm:true` and the
`canGenerate`/account gate (irreversible), and is flagged high-impact.

**edge cases:** unknown id → reported in `blocked` with reason, not a hard fail;
`purge` without `confirm` → `CONFIRM_REQUIRED`; deleting a LUT in use by a grade →
treated as referenced (grade detaches to neutral with warning); empty resolved set
→ `NOTHING_TO_DELETE`.

**undo semantics:** `trash` is fully reversible — `EditOp` stores prior
folder/ref state; `undo` restores assets from Trash **and** re-attaches any
detached scene sources. `purge` is **not** undoable (documented; requires
explicit `confirm`, never the default).

**scene/track mapping:** This is where library and timeline intersect: the tool
**knows** which scenes reference an asset and refuses to silently break a render
(`block` default). `detach` leaves the scene present but source-less (re-generate
or re-attach later); the timeline structure (scene order/count) is untouched.

**How this beats Palmier:** **Soft-delete + Trash retention + full undo** (incl.
re-attaching detached scene sources), a **reference-aware guard** (`block`/`detach`/
`force`) so the agent can't accidentally orphan a scene, an explicit **`purge`
confirm gate** for the irreversible path, and **bulk** operation with per-item
reporting. Palmier deletes without scene-reference awareness or a restore path.

---

## 9. `delete_folder`

**wire-name:** `delete_folder`

**purpose:** Delete a library folder — soft-delete to Trash by default, with
controlled handling of its contents (assets + subfolders) and scene references.

**when-to-call:** "delete the empty 'old takes' folder", "remove the scratch
folder and everything in it".

**input schema:**
```jsonc
{
  "type": "object",
  "properties": {
    "folder_id": { "type": "string" },
    "contents": { "type": "string", "enum": ["require_empty","trash_all","move_up"],
                  "default": "require_empty",
                  "description": "require_empty=fail if non-empty; trash_all=recursively "
                                 "trash contents; move_up=re-parent contents to this folder's parent first." },
    "mode": { "type": "string", "enum": ["trash","purge"], "default": "trash" },
    "on_referenced": { "type": "string", "enum": ["block","detach","force"],
                       "default": "block",
                       "description": "Applies to any contained asset a scene uses." },
    "confirm": { "type": "boolean", "default": false,
                 "description": "Required true for mode:purge OR contents:trash_all on a "
                                "non-empty folder." }
  },
  "required": ["folder_id"],
  "examples": [
    { "folder_id": "fld_old" },
    { "folder_id": "fld_scratch", "contents": "trash_all", "confirm": true },
    { "folder_id": "fld_x", "contents": "move_up" }
  ]
}
```

**output schema:**
```jsonc
{
  "ok": true,
  "undo_token": "op_...",
  "result": {
    "deleted_folder": { "id": "fld_scratch", "path": "/scratch" },
    "trashed_assets": 7, "trashed_subfolders": 2,
    "moved_up": 0, "blocked": [],
    "referenced": [ { "media_id": "m_22", "scene_ids": [8], "action": "blocked" } ],
    "restore_until": "2026-07-24T00:00:00Z"
  }
}
```

**behavior:** Resolves the subtree. `require_empty`→error if any content.
`move_up`→re-parent all direct contents to the folder's parent, then delete the
now-empty folder. `trash_all`→recursively soft-delete the subtree (requires
`confirm`), applying `on_referenced` to each contained asset. `purge`→permanent,
requires `confirm` + account gate, high-impact flagged.

**edge cases:** unknown/root folder → `FOLDER_NOT_FOUND` / `CANNOT_DELETE_ROOT`;
non-empty under `require_empty` → `FOLDER_NOT_EMPTY` (lists counts);
`trash_all`/`purge` without `confirm` → `CONFIRM_REQUIRED`; a referenced asset
under `on_referenced:block` → that asset and the folder deletion are blocked,
reported in `referenced`/`blocked` (partial-safe, no orphaned scenes).

**undo semantics:** `trash`/`trash_all` are reversible — one `EditOp` records the
full subtree (folder, asset parents, detached scene refs); `undo` restores the
entire structure and re-attaches detached sources. `move_up` undo re-nests the
moved contents and recreates the folder. `purge` is **not** undoable.

**scene/track mapping:** Recursion is **scene-reference-aware** at every leaf —
deleting a folder can't silently orphan a scene's source (default `block`).
Timeline structure is never modified; only asset bindings (via `detach`) can
change, and only when explicitly requested.

**How this beats Palmier:** A **`contents` policy** (require_empty / move_up /
trash_all) instead of an ambiguous recursive delete, **recursive
scene-reference awareness**, **soft-delete + full-subtree undo** (including
re-attach), and **layered confirm gates** for the destructive paths. Palmier's
`delete_folder` offers none of this safety scaffolding.

---

## Appendix A — Group-wide "beats Palmier" summary

| Dimension | Palmier | Flow 04 |
|--|--|--|
| Schema richness | loose dicts / prose | enums, ranges, **units (frames vs seconds, stops, Kelvin)**, examples on every field |
| Color controls | free-form description | **named** exposure/temp/lift-gamma-gain/LUT/curves → deterministic ffmpeg |
| Verify loop | scopes (numbers) | scopes **+ rendered images** + `post_grade` toggle + WB/exposure opinion |
| Generation | 3rd-party proxy | **Flow-owned** `ai_relight`/`style_transfer`/`ai_film_stock` via Wan2.2/VACE |
| Character awareness | none | `character_lock` on generative effects |
| Undo | single `undo` | per-op inverse, **soft-delete + Trash + re-attach** of detached scene sources |
| Safety | delete = gone | reference-aware guards, `on_referenced`, layered `confirm`, `purge` gate |
| Cost transparency | `canGenerate` flag | per-call **`gate` block** (free vs credits_charged) before acting |
| Render integrity | implicit | folder ops **decoupled from `media_id`** → never break a render |

## Appendix B — Render integration checklist (for the implementer)

1. Extend `schemas.py`: add `ColorGrade`, `Effect`, `Curves`, `FrameRange`,
   `EditOp`; add `color_grade`, `effects[]`, `edit_history[]` to `Scene`; add a
   `Project`-level grade/effects holder. Write a migration; keep neutral defaults
   omitted from serialization.
2. Add a **filtergraph compiler** module: `(ColorGrade, effects[], clip_props) →
   filter string`, pure/deterministic, cache-keyed. Unit-test each mapping in §0.3
   / §2 against golden ffmpeg strings.
3. Modify `postproduction.py::_ffmpeg_assemble`: branch to the `filter_complex`
   concat path when any look exists; keep the `concat -c copy` fast path otherwise.
   Apply project grade/effects on the post-concat node; caption/text track and
   audio mux unchanged.
4. Implement a **media library** store (folders tree + assets with `media_id`,
   `name`, `folder_id`, `type`, `path` derived) + a **Trash** with retention.
5. Wire all nine as **MCP tools** (loopback + auth) with the §0.7 envelope; route
   generative effects through the `canGenerate`/credits gate to OpenX Cloud →
   Modal; everything else runs CPU-local on the VPS.
6. Implement the per-op **undo** (push `EditOp`; the group-05 `undo` tool consumes
   the stack), including soft-delete restore + scene-source re-attach.
