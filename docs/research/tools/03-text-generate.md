# Flow Agent Tools — Group 03: Text + Generation

**Date:** 2026-06-24
**Scope:** 0.3 agentic editing surface — the **generation-native, Flow-owned**
tools. These are where Flow leaves Palmier behind: Palmier *proxies* third-party
models; Flow *owns* the pipeline (Wan2.2 t2v/i2v/flf2v + VACE on Modal,
characters/subject-consistency, MisoTTS/edge-tts narration with voice cloning).

This doc specifies 7 wire-tools:

| Wire-name | Group role | Async? | Gated by `canGenerate`? |
|--|--|--|--|
| `add_texts` | Titles / lower-thirds onto the caption(text) track | no | no |
| `add_captions` | On-device transcribe → styled caption track | no (local STT) | no |
| `generate_video` | Wan2.2/VACE t2v·i2v·flf2v → a scene clip | **yes (job)** | **yes** |
| `generate_image` | Keyframe / reference still (first/last frame, char ref) | **yes (job)** | **yes** |
| `generate_audio` | TTS narration (edge-tts/MisoTTS, voice clone) + music | **yes (job)** | **yes** |
| `upscale_media` | AI upscale a clip/image in place | **yes (job)** | **yes** |
| `import_media` | Bridge external/other-MCP assets into the library | no | no |

> Sibling docs cover read/context (01), timeline edit (02), color/FX + media-mgmt
> (04), and Flow-specific casting/orchestration (05). Cross-references use
> `→ tool_name`.

---

## 0. Shared conventions (read once, applies to every tool below)

These conventions are what make Flow's schemas "beat Palmier": Palmier ships
loose dicts; Flow ships fully-typed JSON Schema with enums, ranges, units, and
`examples`. Every tool entry inherits the rules here instead of repeating them.

### 0.1 Units — frames vs seconds (never ambiguous)
Flow's render fps is **16** (matches the Modal backend: `num_frames = duration *
16`). Every time-valued field is suffixed and typed:
- `*_frames` → integer, project-frame index/count at 16 fps.
- `*_seconds` → number, wall-clock seconds.
- `*_ms` → integer milliseconds (audio/caption sync only).
A field schema always states `"unit": "frames" | "seconds" | "ms"` in its
`description` and pins the fps assumption (`16`). Tools accept **either**
`at_frames` or `at_seconds` for placement and resolve internally
(`frames = round(seconds * 16)`); supplying both is an error (see 0.7).

### 0.2 The scene/track model these tools write to
```
VIDEO track   = ordered scenes (scene = clip). scene.id, scene.order,
                duration_frames, trims, speed, opacity, transform, keyframes.
AUDIO track(s)= narration / music / sfx segments (start_frames, gain_db, ...).
TEXT track    = caption/title segments (start_frames, end_frames, text, style).
RENDER        = ffmpeg concatenates scenes → one complete video track, mixes
                audio tracks, burns/sidecars the text track.
```
Generation tools (`generate_video`/`generate_image`) **produce media that lands
on the VIDEO track as scenes**; `generate_audio` writes the **AUDIO track**;
`add_texts`/`add_captions` write the **TEXT track**. `import_media`/`upscale_media`
operate on the **media library** (assets referenced by `media_ref`), which is the
pool scenes and tracks draw from.

### 0.3 Identifiers
- `project_id` — implicit/scoped: the agent loop injects the active project; tools
  reject any `project_id` that is not the session's (ownership check, per
  nanocode-teardown guardrail #4).
- `scene_id` — stable int (matches `schemas.Scene.id`).
- `media_ref` — opaque library handle (`med_…`); every asset a tool returns is
  addressable by `media_ref` (mirrors Palmier's "every mediaRef comes from
  get_media").
- `track_id` — `"video"` (the scene track), or `aud_…` / `txt_…` for
  audio/text tracks.
- `job_id` — async generation handle (`job_…`), pollable via `→ get_job` (group
  01) and delivered via callback (0.5).
- `op_id` — undo handle returned by **every mutating call** (0.6).

### 0.4 The `canGenerate` / credits gate
Mirrors Palmier's `canGenerate`, extended with credits accounting. Every async
generation tool (`generate_*`, `upscale_media`) performs this gate **before**
enqueuing a job:
```jsonc
// gate failure → tool returns (not raises), so the model can relay it:
{
  "ok": false,
  "gate": "canGenerate",
  "reason": "insufficient_credits",        // | "not_signed_in" | "plan_required" | "quota_exhausted"
  "message": "This needs 12 credits; balance is 4. Top up or lower resolution.",
  "credits_required": 12,
  "credits_balance": 4,
  "upgrade_url": "https://openx.flow/billing"
}
```
Read/text tools (`add_texts`, `add_captions`, `import_media`) are **never**
gated. Every gated tool's input schema includes an optional
`confirm_credits` (boolean, default `false`): when the estimated cost exceeds the
project's `auto_spend_ceiling`, the tool returns a `needs_confirmation` result
with a quote instead of spending; the agent re-calls with `confirm_credits:true`.

### 0.5 Async job contract (generation tools)
Long-running tools return **immediately** with a job, never block the agent loop:
```jsonc
{
  "ok": true,
  "job_id": "job_8f3a…",
  "status": "queued",                 // queued | running | succeeded | failed | canceled
  "kind": "generate_video",
  "estimate": { "credits": 12, "seconds_p50": 240, "seconds_p95": 420 },
  "poll": "get_job",                  // group-01 tool to poll
  "callback": "scene.media_ready"      // server event pushed to the chat UI
}
```
- On success the backend fires `callback` with `{ job_id, media_ref,
  last_frame_ref?, scene_id?, op_id }`; the agent resumes (loop re-invoked with
  the tool-result, nanocode-style).
- Jobs are **cancelable** via `→ cancel_job` (group 01); cancel before `running`
  refunds the full estimate, during `running` refunds the unspent remainder.
- Backend mapping: enqueue → OpenX Cloud → Modal `WanServer` endpoint
  (`/t2v|/i2v|/flf2v|/vace`) or the voice/upscale workers. The Modal handlers
  return base64; the VPS job worker persists to the library and emits `media_ref`.

### 0.6 Undo semantics (everything is one undoable op)
Every mutating call returns `op_id`. `→ undo` (group 02) reverts the most recent
op; ops form a per-project stack. Specifics:
- **Track writes** (`add_texts`, `add_captions`, `generate_audio`): undo removes
  the inserted segment(s)/track and restores prior track state.
- **Scene creation** (`generate_video`/`generate_image` landing as a scene): undo
  removes the new scene and re-closes the order gap; the **generated media stays
  in the library** (so re-insert is free, no re-spend).
- **In-place media replace** (`upscale_media`, regenerate): undo restores the
  previous `media_ref` version (assets are versioned, never destroyed).
- **Async caveat:** undoing a *queued/running* generation calls `cancel_job` +
  removes the placeholder scene; undoing a *succeeded* one removes the scene but
  keeps the asset. Undo never costs credits and never deletes paid output.

### 0.7 Errors as strings (self-correcting loop)
Per the nanocode teardown, tool failures return structured results the model can
read and fix from — they do **not** throw:
```jsonc
{ "ok": false, "error": "invalid_argument",
  "field": "duration_frames",
  "message": "duration_frames=240 exceeds model max 160 (10s @16fps) for wan2.2-t2v. Use ≤160 or split into scenes.",
  "allowed": { "min": 16, "max": 160, "unit": "frames" } }
```
Common codes: `invalid_argument`, `not_found`, `gate` (0.4),
`needs_confirmation`, `conflict` (e.g., overlapping caption), `unsupported`
(capability not on chosen model — cross-check `→ list_models`).

### 0.8 Token hygiene
Like Palmier, **defaults are omitted** from echoed payloads (gain 0 dB, opacity
1.0, identity transform, `seed:null`, default style) — they are not serialized in
outputs. Schemas still declare them so the model knows the default.

---

## 1. `add_texts` — titles, lower-thirds, on-screen text

### Purpose
Place author-controlled text segments (titles, lower-thirds, kickers, end-cards,
callouts) onto the **TEXT track**. This is *deliberate* typography the creator/
agent decides — distinct from `add_captions`, which transcribes speech.

### When to call
- "Add a title card that says …", "lower-third with my name", "put a CTA at the
  end", "label this scene 'Chapter 2'".
- After `generate_video` creates scenes and the creator wants on-screen titling.
- NOT for subtitles of narration → use `add_captions`.

### Input schema
```jsonc
{
  "type": "object",
  "required": ["texts"],
  "properties": {
    "track_id": {
      "type": "string", "default": "txt_main",
      "description": "Target TEXT track. Omit to use/create the primary caption-text track."
    },
    "texts": {
      "type": "array", "minItems": 1, "maxItems": 50,
      "description": "Text segments to add as one undoable op.",
      "items": {
        "type": "object",
        "required": ["content"],
        "properties": {
          "content": { "type": "string", "maxLength": 280,
            "description": "Text to display. Newlines allowed; use \\n for line breaks." },
          "role": {
            "type": "string",
            "enum": ["title", "subtitle", "lower_third", "kicker", "callout", "end_card", "credit"],
            "default": "title",
            "description": "Semantic role → drives default style + safe-area placement." },
          "at_frames": { "type": "integer", "minimum": 0,
            "description": "Start, project frames @16fps. Mutually exclusive with at_seconds." },
          "at_seconds": { "type": "number", "minimum": 0,
            "description": "Start, seconds. Resolves to round(s*16) frames." },
          "duration_frames": { "type": "integer", "minimum": 8, "maximum": 1600, "default": 48,
            "description": "On-screen length in frames (48 = 3s @16fps)." },
          "anchor_scene_id": { "type": "integer",
            "description": "Pin to a scene: text rides with the scene through reorders. Overrides at_frames/at_seconds (uses the scene's start)." },
          "style": {
            "type": "object",
            "description": "Visual style. Omitted keys inherit role defaults.",
            "properties": {
              "font": { "type": "string", "default": "Inter",
                "description": "Font family from the project font set (→ list_fonts)." },
              "size_pct": { "type": "number", "minimum": 1, "maximum": 30, "default": 7,
                "description": "Font size as % of frame height (resolution-independent)." },
              "weight": { "type": "string", "enum": ["regular","medium","semibold","bold","black"], "default": "bold" },
              "color": { "type": "string", "pattern": "^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$", "default": "#FFFFFF",
                "description": "Hex RGB or RGBA." },
              "bg": { "type": "string", "pattern": "^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
                "description": "Optional background pill/box color (RGBA for opacity)." },
              "stroke": { "type": "object", "properties": {
                "color": {"type":"string","pattern":"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$"},
                "width_px": {"type":"number","minimum":0,"maximum":12,"default":0} } },
              "align": { "type": "string", "enum": ["left","center","right"], "default": "center" },
              "position": {
                "type": "string",
                "enum": ["top","upper_third","center","lower_third","bottom","custom"],
                "default": "lower_third",
                "description": "Safe-area-aware preset. 'custom' uses xy." },
              "xy": { "type": "array", "items": {"type":"number","minimum":0,"maximum":1}, "minItems":2, "maxItems":2,
                "description": "Normalized [x,y] center (0..1) when position='custom'." },
              "animation": {
                "type": "string",
                "enum": ["none","fade","slide_up","slide_in","typewriter","pop","karaoke"],
                "default": "fade",
                "description": "Enter/exit animation. 'karaoke' only valid with word timings." }
            }
          },
          "safe_area": { "type": "boolean", "default": true,
            "description": "Keep text inside platform safe margins (TikTok/Reels UI overlap)." }
        },
        "oneOf": [
          {"required":["at_frames"]}, {"required":["at_seconds"]}, {"required":["anchor_scene_id"]}
        ]
      }
    }
  },
  "examples": [
    { "texts": [
      { "content": "The History of the Internet", "role": "title",
        "anchor_scene_id": 1, "duration_frames": 64,
        "style": { "size_pct": 9, "animation": "slide_up", "position": "center" } },
      { "content": "Dr. Vint Cerf\nco-creator of TCP/IP", "role": "lower_third",
        "at_seconds": 12.5, "duration_frames": 80 }
    ] }
  ]
}
```

### Output schema
```jsonc
{
  "ok": true,
  "op_id": "op_a1…",
  "track_id": "txt_main",
  "added": [
    { "segment_id": "txt_seg_01", "content": "The History of the Internet",
      "start_frames": 0, "end_frames": 64, "role": "title",
      "anchor_scene_id": 1, "resolved_style": { /* full style after defaults */ } }
  ],
  "track_summary": { "segment_count": 7, "track_duration_frames": 1600 }
}
```

### Behavior
- Creates `txt_main` if no TEXT track exists. Resolves `at_seconds`→frames and
  `anchor_scene_id`→ the scene's current start frame, storing the anchor so the
  segment **moves with the scene** when `→ reorder_scenes`/`split_clip` shift it.
- Applies role-based style defaults, then merges caller `style` (caller wins).
- Renders at ffmpeg-assembly time onto the burned/sidecar text track; no
  re-encode of scene media.

### Edge cases
- **Overlap** with an existing segment at the same z/position → returns
  `ok:true` but includes `warnings:[{code:"overlap", with:"txt_seg_03"}]`
  (stacking is legal; the agent decides). Hard `conflict` only if `karaoke`
  animations collide on identical word timings.
- `content` > 280 chars → `invalid_argument` (suggest splitting / smaller size).
- `animation:"karaoke"` without word timings → `unsupported` (karaoke belongs to
  `add_captions`, which has word-level times).
- `anchor_scene_id` not found → `not_found`.
- `position:"custom"` without `xy` → `invalid_argument`.

### Undo
`undo` removes exactly the `added` segments and restores prior track state;
deletes `txt_main` only if this op created it.

### Scene/track mapping
Pure **TEXT track** writer. Never touches scenes/media. Anchoring is the bridge
to the scene model so titles survive scene reordering.

### How this beats Palmier
- Palmier's `add_texts` is a thin "place a text clip" with raw frame numbers.
  Flow adds **semantic `role`** (title/lower_third/end_card → correct safe-area +
  style presets), **resolution-independent `size_pct`**, **scene anchoring** (text
  follows a scene through reorders — impossible in a flat NLE without manual
  re-timing), dual **frames|seconds** input, and a typed `style` with hex
  validation and enumerated animations including platform-aware `safe_area`.

---

## 2. `add_captions` — on-device transcribe → styled caption track

### Purpose
Auto-generate **word- or line-timed captions** from spoken audio (narration or a
scene's audio), placed as a styled segment set on the TEXT track. On-device STT
(faster-whisper on the VPS) — no paid generation, so **not** `canGenerate`-gated.

### When to call
- "Add subtitles", "caption the narration", "burn TikTok-style word captions".
- After `generate_audio` produces narration, or for imported speech clips.

### Input schema
```jsonc
{
  "type": "object",
  "properties": {
    "source": {
      "type": "string",
      "enum": ["narration_track", "audio_media", "scene_audio", "project_mix"],
      "default": "narration_track",
      "description": "What to transcribe. 'project_mix' = full current timeline audio." },
    "source_ref": { "type": "string",
      "description": "media_ref (audio_media) or scene_id (scene_audio). Required unless source is narration_track/project_mix." },
    "track_id": { "type": "string", "default": "txt_captions",
      "description": "Destination TEXT track (separate from titles by default)." },
    "language": { "type": "string", "default": "auto",
      "description": "ISO-639-1 (e.g. 'en') or 'auto' to detect." },
    "granularity": {
      "type": "string", "enum": ["word", "phrase", "line", "sentence"],
      "default": "phrase",
      "description": "Caption chunking. 'word' enables karaoke highlight." },
    "max_chars_per_line": { "type": "integer", "minimum": 8, "maximum": 60, "default": 32 },
    "max_lines": { "type": "integer", "minimum": 1, "maximum": 3, "default": 2 },
    "style_preset": {
      "type": "string",
      "enum": ["clean","tiktok_bold","karaoke_pop","minimal","broadcast"],
      "default": "clean",
      "description": "Caption look. karaoke_pop requires granularity='word'." },
    "style_overrides": { "type": "object",
      "description": "Same shape as add_texts.style; merged over the preset." },
    "highlight_color": { "type": "string", "pattern": "^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8})$",
      "description": "Active-word color for karaoke styles." },
    "profanity_filter": { "type": "boolean", "default": false },
    "time_offset_ms": { "type": "integer", "default": 0,
      "description": "Shift all caption times to fix A/V sync drift (+later, -earlier)." },
    "replace_existing": { "type": "boolean", "default": false,
      "description": "If true, clear track_id before adding (else append/merge)." }
  },
  "examples": [
    { "source": "narration_track", "granularity": "word",
      "style_preset": "karaoke_pop", "highlight_color": "#FFE600",
      "max_chars_per_line": 24, "max_lines": 1 }
  ]
}
```

### Output schema
```jsonc
{
  "ok": true,
  "op_id": "op_b2…",
  "track_id": "txt_captions",
  "language_detected": "en",
  "segment_count": 142,
  "word_count": 410,
  "duration_frames": 1600,
  "segments_preview": [
    { "segment_id":"cap_001","text":"the history","start_ms":0,"end_ms":640,
      "start_frames":0,"end_frames":10,
      "words":[{"t":"the","start_ms":0,"end_ms":240},{"t":"history","start_ms":240,"end_ms":640}] }
  ],
  "transcript_media_ref": "med_txt_9…"   // full transcript stored as a library asset
}
```

### Behavior
- Runs faster-whisper on the VPS (CPU/GPU), word-level timestamps, then chunks per
  `granularity`/`max_chars_per_line`/`max_lines`.
- Aligns to **project frames** (16 fps) using each word's ms time + `time_offset_ms`.
- Persists the raw transcript as a library asset (`transcript_media_ref`) so other
  tools (`→ get_transcript`, transcript-driven trims in group 02) can reuse it
  without re-transcribing.

### Edge cases
- Silent/music-only source → `ok:true, segment_count:0, warnings:[{code:"no_speech"}]`.
- `source:"audio_media"`/`"scene_audio"` without `source_ref` → `invalid_argument`.
- `style_preset:"karaoke_pop"` with `granularity!="word"` → auto-upgrades to
  `word` and returns `warnings:[{code:"granularity_upgraded"}]` (self-correcting,
  not a hard error).
- Detected language ≠ requested → proceeds with detected, warns.
- Re-running without `replace_existing` on a populated track → appends and may
  overlap; warns with overlap ranges.

### Undo
`undo` removes the added caption segments (and the track if newly created) and
deletes the `transcript_media_ref` **only** if this op created it and nothing
else references it.

### Scene/track mapping
Writes the **TEXT track** (separate `txt_captions` track by default, so captions
and titles are independently editable/toggleable). Reads AUDIO track / scene
audio. Captions are time-anchored to the global mix, not to individual scenes
(they follow the audio, which is continuous across the concatenated video track).

### How this beats Palmier
- Palmier's `add_captions` does on-device transcription → caption clips. Flow
  matches that and adds: **karaoke word-level highlighting** as a first-class
  preset, **platform-native presets** (`tiktok_bold`/`karaoke_pop`),
  **`time_offset_ms`** sync nudging, **transcript persisted as a reusable asset**
  (shared with `get_transcript` and transcript-driven editing — Palmier re-derives
  transcripts per tool), `profanity_filter`, and explicit `max_chars/max_lines`
  layout control. Captions live on a **dedicated track** so they don't entangle
  with titles.

---

## 3. `generate_video` — Wan2.2 / VACE (t2v · i2v · flf2v) → a scene

### Purpose
Flow's flagship tool: generate an AI video clip with **Flow-owned** Wan2.2
(`WanServer` on Modal) and land it as a **scene** on the video track. Covers all
generation modes — text-to-video, image-to-video, first-last-frame chaining, and
VACE reference/edit/compose — through one typed surface. **Async + credit-gated.**

### When to call
- "Generate a scene of …", "make a 5s clip of the rocket launching".
- "Continue from the last scene" → `mode:"flf2v"` with `first_frame_ref` = prior
  scene's `last_frame_ref` (temporal coherence; the core scene-chaining feature).
- "Put my character in it" → pass `character_ids` (S2V/reference conditioning).
- "Re-roll scene 3 with a new prompt" → set `target_scene_id` (regenerate in place).

### Input schema
```jsonc
{
  "type": "object",
  "required": ["prompt", "mode"],
  "properties": {
    "prompt": { "type": "string", "minLength": 1, "maxLength": 2000,
      "description": "Visual description. Camera/lighting cues welcome (e.g. 'low-angle dolly, golden hour')." },
    "negative_prompt": { "type": "string", "maxLength": 1000, "default": "",
      "description": "What to avoid (artifacts, text, watermarks)." },
    "mode": {
      "type": "string", "enum": ["t2v","i2v","flf2v","vace"],
      "description": "t2v=text only; i2v=animate from first frame; flf2v=first+last frame chaining; vace=reference/edit/compose." },
    "model": {
      "type": "string",
      "enum": ["wan2.2-t2v-a14b","wan2.2-i2v-a14b","wan2.1-vace-14b"],
      "description": "Omit to auto-select by mode (t2v→t2v, i2v/flf2v→i2v, vace→vace). Cross-check capabilities via list_models." },
    "first_frame_ref": { "type": "string",
      "description": "media_ref (image) or 'scene:<id>.last' shorthand. Required for i2v/flf2v." },
    "last_frame_ref": { "type": "string",
      "description": "Target end frame for flf2v chaining (optional; improves continuity into the next beat)." },
    "reference_images": {
      "type": "array", "maxItems": 4, "items": { "type": "string" },
      "description": "media_refs for VACE reference-driven composition / style anchoring." },
    "character_ids": {
      "type": "array", "items": { "type": "string" }, "maxItems": 4,
      "description": "Character bank ids → subject consistency (their reference_image is injected as conditioning). See list_characters / attach_character_to_scene." },
    "resolution": { "type": "string", "enum": ["480p","720p"], "default": "480p",
      "description": "Maps to Modal dims: 480p=832x480, 720p=1280x720 (landscape) — orientation follows project aspect_ratio." },
    "aspect_ratio": { "type": "string", "enum": ["9:16","16:9","1:1"],
      "description": "Defaults to project aspect_ratio (config). Drives portrait vs landscape dims." },
    "duration_frames": { "type": "integer", "minimum": 16, "maximum": 160, "multipleOf": 16, "default": 80,
      "description": "Clip length in frames @16fps. 80=5s (Flow default clip). Max 160=10s per clip." },
    "fps": { "type": "integer", "enum": [16], "default": 16,
      "description": "Render fps. Fixed at 16 (Wan backend); exposed for explicitness." },
    "num_inference_steps": { "type": "integer", "minimum": 10, "maximum": 60, "default": 30,
      "description": "Denoising steps. Higher=better/slower. Backend default 30." },
    "guidance_scale": { "type": "number", "minimum": 1.0, "maximum": 12.0, "default": 5.0,
      "description": "Prompt adherence (CFG). Backend default 5.0." },
    "seed": { "type": "integer", "minimum": 0, "maximum": 4294967295,
      "description": "Omit for random. Pin for reproducible re-rolls." },
    "motion_strength": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
      "description": "i2v/flf2v: how far motion departs from the conditioning frame (0=near-still, 1=high motion)." },
    "placement": {
      "type": "object",
      "description": "Where the resulting scene lands on the video track.",
      "properties": {
        "target_scene_id": { "type": "integer",
          "description": "Regenerate IN PLACE: replace this scene's media (keeps order, narration, captions)." },
        "after_scene_id": { "type": "integer",
          "description": "Insert the new scene immediately after this one (ripples order)." },
        "at_order": { "type": "integer", "minimum": 0,
          "description": "Insert at explicit order index. Omit all → append at end." }
      }
    },
    "confirm_credits": { "type": "boolean", "default": false,
      "description": "Set true to authorize spend above the project's auto_spend_ceiling." }
  },
  "allOf": [
    { "if": { "properties": { "mode": { "enum": ["i2v","flf2v"] } } },
      "then": { "required": ["first_frame_ref"] } }
  ],
  "examples": [
    { "prompt": "a paper boat sailing down a rain-soaked gutter, cinematic, shallow depth of field",
      "mode": "t2v", "duration_frames": 80, "resolution": "720p", "aspect_ratio": "9:16" },
    { "prompt": "the same boat reaches a storm drain and tips over the edge",
      "mode": "flf2v", "first_frame_ref": "scene:3.last", "duration_frames": 80,
      "placement": { "after_scene_id": 3 } },
    { "prompt": "Detective Mara examines the clue under a desk lamp",
      "mode": "i2v", "first_frame_ref": "med_kf_22", "character_ids": ["char_mara"],
      "placement": { "target_scene_id": 7 }, "seed": 12345 }
  ]
}
```

### Output schema (async job)
```jsonc
{
  "ok": true,
  "job_id": "job_v_8f…",
  "status": "queued",
  "kind": "generate_video",
  "mode": "flf2v",
  "model": "wan2.2-i2v-a14b",
  "resolved": { "width": 480, "height": 832, "num_frames": 80, "fps": 16, "seed": 884412 },
  "placeholder_scene_id": 4,            // a placeholder scene is reserved immediately
  "op_id": "op_c3…",
  "estimate": { "credits": 12, "seconds_p50": 240, "seconds_p95": 420 },
  "poll": "get_job",
  "callback": "scene.media_ready"
}
// callback payload on success:
// { "job_id":"job_v_8f…", "scene_id":4, "media_ref":"med_vid_77",
//   "last_frame_ref":"med_kf_78", "duration_frames":80, "op_id":"op_c3…" }
```

### Behavior
1. **Gate** (0.4): estimate credits from `resolution × duration_frames × steps ×
   mode`; if over `auto_spend_ceiling` and not `confirm_credits` → `needs_confirmation`.
2. **Reserve a placeholder scene** at the resolved placement so the timeline shows
   a "generating" tile immediately (mirrors Palmier `generationStatus:generating`).
3. **Resolve conditioning:** `first_frame_ref` `scene:<id>.last` → that scene's
   stored `last_frame`; `character_ids` → inject each character's `reference_image`
   (i2v/VACE conditioning) for subject consistency.
4. **Enqueue** → OpenX Cloud → Modal endpoint (`/t2v|/i2v|/flf2v|/vace`). flf2v
   uses the i2v pipeline anchored on the first frame (per `modal_server.py`).
5. On success the worker persists the mp4 + extracted **last frame** to the
   library, fills the placeholder scene, stores `prompt/model/seed/first_last
   frame/refs` on the scene (regenerate-in-place metadata, à la Palmier's per-clip
   memory), and fires `callback`.

### Edge cases
- `duration_frames` not multiple of 16 → `invalid_argument` (frames must align to
  the 16-fps chunking; suggest nearest valid).
- `mode:"vace"` but VACE unavailable on backend → job `failed` with the backend's
  `"VACE unavailable: …"` surfaced verbatim (the `vace` endpoint is best-effort/
  isolated). Agent can retry as `t2v`+`reference_images` fallback.
- `first_frame_ref` resolves to a non-image asset → `invalid_argument`.
- `character_ids` referencing a character with no `reference_image` → proceeds but
  warns `{code:"character_unanchored", id:…}` (prompt-only consistency; suggest
  generating a reference via `generate_image` first).
- Resolution/aspect mismatch with project → uses request, warns about letterboxing
  at assembly.
- Backend timeout / black-frame output → job `failed`; Flow's `validate_clip` /
  `detect_black_frames` (from `generator.py`) auto-flag; agent may re-roll with a
  new `seed`.

### Undo
`undo` on a **new** scene removes it (re-closes order) but keeps the generated
asset in the library (re-insert is free). `undo` on a **regenerate-in-place**
(`target_scene_id`) restores the scene's previous `media_ref` version (assets are
versioned). Undoing a still-`running` job calls `cancel_job` and removes the
placeholder, refunding unspent credits (0.5/0.6).

### Scene/track mapping
This is the primary **VIDEO-track producer**: every generation becomes (or
replaces) a **scene = clip**. flf2v is literally the scene-chaining primitive —
`first_frame_ref = prior scene.last` is how ordered scenes stay temporally
coherent before ffmpeg concatenates them into the one complete video track.

### How this beats Palmier
- Palmier's `generate_video` proxies third-party closed models; Flow **owns** the
  model and exposes its real knobs: `num_inference_steps`, `guidance_scale`,
  `seed`, `motion_strength`, `negative_prompt` — none of which Palmier surfaces.
- **Character-aware** (`character_ids` → subject consistency via reference
  injection). Palmier has **no character concept** at all.
- **flf2v scene-chaining** as a first-class mode with `scene:<id>.last`
  shorthand — purpose-built for coherent multi-scene films; Palmier treats each
  generation as an isolated clip.
- **Regenerate-in-place** with full prompt/seed/model memory on the scene, and
  **versioned undo** that never re-spends credits.
- Typed, validated schema with `multipleOf:16` frame alignment, mode-conditional
  `required` (`if/then`), and resolved-dims echo — vs Palmier's loose dict.

---

## 4. `generate_image` — keyframe / reference still

### Purpose
Generate a still image: a **keyframe** (first/last frame to seed `generate_video`
i2v/flf2v), a **character reference** (anchor a character's look for subject
consistency), a **style board**, or an **end-card graphic**. Async + gated (image
gen is far cheaper than video, but still metered).

### When to call
- "Make a keyframe of the hero standing in the doorway" → then feed as
  `first_frame_ref` to `generate_video`.
- "Create a reference image for character 'Mara'" → store on the character
  (`set_reference_image` path in the character bank).
- "Generate a thumbnail / end card."

### Input schema
```jsonc
{
  "type": "object",
  "required": ["prompt", "purpose"],
  "properties": {
    "prompt": { "type": "string", "minLength": 1, "maxLength": 2000 },
    "negative_prompt": { "type": "string", "maxLength": 1000, "default": "" },
    "purpose": {
      "type": "string",
      "enum": ["keyframe","character_reference","style_board","thumbnail","end_card","generic"],
      "description": "Drives where the result is routed and what metadata is attached." },
    "model": { "type": "string", "enum": ["wan2.2-t2v-a14b","flux-1-dev","sdxl"], "default": "wan2.2-t2v-a14b",
      "description": "Default reuses the Wan T2V pipeline (single-frame); list_models reports available image models." },
    "reference_images": { "type": "array", "maxItems": 4, "items": {"type":"string"},
      "description": "media_refs to condition on (style/identity transfer)." },
    "character_id": { "type": "string",
      "description": "If purpose=character_reference, the character to attach the result to (sets its reference_image)." },
    "aspect_ratio": { "type": "string", "enum": ["9:16","16:9","1:1","4:3","3:2"],
      "description": "Defaults to project aspect_ratio." },
    "resolution": { "type": "string", "enum": ["512","768","1024","1536"], "default": "1024",
      "description": "Longest-edge pixels." },
    "num_inference_steps": { "type":"integer","minimum":10,"maximum":60,"default":30 },
    "guidance_scale": { "type":"number","minimum":1.0,"maximum":12.0,"default":5.0 },
    "seed": { "type":"integer","minimum":0,"maximum":4294967295 },
    "n": { "type":"integer","minimum":1,"maximum":4,"default":1,
      "description": "Number of variations to generate (creator picks one)." },
    "confirm_credits": { "type":"boolean","default":false }
  },
  "examples": [
    { "prompt":"portrait of Detective Mara, 40s, tired eyes, trench coat, neutral studio bg",
      "purpose":"character_reference", "character_id":"char_mara", "aspect_ratio":"3:2", "n":4 },
    { "prompt":"wide establishing shot, neon-lit alley at night, rain", "purpose":"keyframe",
      "aspect_ratio":"9:16", "seed":42 }
  ]
}
```

### Output schema (async job)
```jsonc
{
  "ok": true, "job_id": "job_i_3a…", "status": "queued", "kind": "generate_image",
  "purpose": "character_reference", "n": 4,
  "estimate": { "credits": 2, "seconds_p50": 18 },
  "op_id": "op_d4…", "poll": "get_job", "callback": "media.ready"
}
// callback on success:
// { "job_id":"job_i_3a…", "media_refs":["med_img_a","med_img_b","med_img_c","med_img_d"],
//   "selected":null, "character_id":"char_mara", "op_id":"op_d4…" }
```

### Behavior
- Generates `n` variations; returns all `media_refs` for the creator/agent to
  pick. For `purpose:"character_reference"` with `character_id`, the chosen
  image is set as that character's `reference_image` (character bank
  `set_reference_image`) — selection via `→ set_character_reference` (group 05) or
  auto-selects index 0 if `n==1`.
- Lands in the **media library only** (not a scene). To turn a keyframe into
  motion, pass its `media_ref` to `generate_video` as `first_frame_ref`.

### Edge cases
- `purpose:"character_reference"` without `character_id` → `invalid_argument`.
- `n>1` for `keyframe` used directly as a frame → only one can seed a scene; the
  agent must select (warned).
- Unsupported `model` for the requested `aspect_ratio`/`resolution` →
  `unsupported` (check `list_models`).

### Undo
`undo` removes the generated library assets (and unsets a character's
`reference_image` if this op set it, restoring the prior reference). Versioned —
prior character reference is recoverable.

### Scene/track mapping
**Library producer**, not a track writer. Feeds the VIDEO track indirectly: its
outputs become `first_frame_ref`/`reference_images`/`character.reference_image`
consumed by `generate_video`. This is the "casting & keyframe" staging area.

### How this beats Palmier
- **Purpose-routed** (`keyframe`/`character_reference`/…) so the asset carries
  intent and auto-wires into character consistency and i2v chaining — Palmier's
  `generate_image` is a bare image generator with no downstream awareness.
- **First-class character integration**: a generated reference can be bound to a
  character in the same call. Palmier has no characters.
- Real model knobs (`seed`/`steps`/`guidance`/`negative_prompt`) and `n`
  variations with explicit selection, vs Palmier's loose proxy call.

---

## 5. `generate_audio` — TTS narration (edge-tts / MisoTTS + voice clone) & music

### Purpose
Produce audio for the **AUDIO track(s)**: TTS narration (free **edge-tts** or
**MisoTTS** with one-shot **voice cloning**), or generated **music/SFX**. Lands as
a timed audio segment. Async + gated (TTS metered light; music heavier).

### When to call
- "Narrate this script", "read scene 3's narration in my cloned voice".
- "Add background music, lo-fi, 30s", "generate a whoosh SFX at the cut".

### Input schema
```jsonc
{
  "type": "object",
  "required": ["kind"],
  "properties": {
    "kind": { "type": "string", "enum": ["narration","music","sfx"],
      "description": "narration=TTS; music=text-to-music; sfx=short effect." },

    // ---- narration (TTS) ----
    "text": { "type": "string", "maxLength": 8000,
      "description": "Required for kind=narration. The script to speak." },
    "from_scenes": { "type": "array", "items": {"type":"integer"},
      "description": "Instead of text: concatenate these scenes' narration_segment fields in order." },
    "tts_provider": { "type": "string", "enum": ["edge","miso"], "default": "edge",
      "description": "edge=free Microsoft voices; miso=MisoTTS 8B (GPU) with voice cloning." },
    "voice": { "type": "string", "default": "en-US-ChristopherNeural",
      "description": "edge voice id (list_models→voices). Ignored when voice_clone_ref is set." },
    "voice_clone_ref": { "type": "string",
      "description": "media_ref to a reference audio sample → one-shot clone (miso only). Requires voice_transcript." },
    "voice_transcript": { "type": "string", "maxLength": 2000,
      "description": "Transcript of voice_clone_ref sample (improves clone fidelity)." },
    "miso_precision": { "type": "string", "enum": ["bf16","int8","int4"], "default": "int8",
      "description": "MisoTTS quantization (speed/quality/VRAM tradeoff)." },
    "language": { "type": "string", "default": "en" },
    "speed": { "type": "number", "minimum": 0.5, "maximum": 2.0, "default": 1.0,
      "description": "Speaking-rate multiplier." },
    "pitch_semitones": { "type": "number", "minimum": -12, "maximum": 12, "default": 0 },

    // ---- music / sfx ----
    "prompt": { "type": "string", "maxLength": 1000,
      "description": "Required for kind=music/sfx. Style/mood description." },
    "duration_seconds": { "type": "number", "minimum": 0.5, "maximum": 600,
      "description": "music/sfx length. narration length is derived from speech." },
    "loopable": { "type": "boolean", "default": false,
      "description": "music: render a seamless loop (for beds under longer video)." },

    // ---- placement (all kinds) ----
    "track_id": { "type": "string",
      "description": "Target audio track. Omit → 'aud_narration' for narration, 'aud_music' for music, 'aud_sfx' for sfx." },
    "at_frames": { "type":"integer","minimum":0, "description":"Start @16fps. Mutually exclusive with at_seconds." },
    "at_seconds": { "type":"number","minimum":0 },
    "anchor_scene_id": { "type":"integer", "description":"Pin start to a scene's start (rides reorders)." },
    "gain_db": { "type":"number","minimum":-60,"maximum":12,"default":0,
      "description":"Segment gain. Music beds typically -12 to -18 dB under narration." },
    "fade_in_ms": { "type":"integer","minimum":0,"maximum":10000,"default":0 },
    "fade_out_ms": { "type":"integer","minimum":0,"maximum":10000,"default":0 },
    "ducking": { "type":"object",
      "description":"Auto-duck this track under narration.",
      "properties": {
        "enabled": {"type":"boolean","default":false},
        "duck_db": {"type":"number","minimum":-40,"maximum":0,"default":-12},
        "against_track": {"type":"string","default":"aud_narration"} } },
    "confirm_credits": { "type":"boolean","default":false }
  },
  "allOf": [
    { "if": { "properties": { "kind": { "const": "narration" } } },
      "then": { "anyOf": [ {"required":["text"]}, {"required":["from_scenes"]} ] } },
    { "if": { "properties": { "kind": { "enum": ["music","sfx"] } } },
      "then": { "required": ["prompt","duration_seconds"] } }
  ],
  "examples": [
    { "kind":"narration", "from_scenes":[1,2,3,4], "tts_provider":"miso",
      "voice_clone_ref":"med_aud_myvoice", "voice_transcript":"Hello, this is a test of my voice.",
      "miso_precision":"int8", "track_id":"aud_narration", "at_frames":0 },
    { "kind":"music", "prompt":"warm lo-fi hip-hop, vinyl crackle, mellow", "duration_seconds":60,
      "loopable":true, "gain_db":-15, "fade_in_ms":1500, "fade_out_ms":2000,
      "ducking":{"enabled":true,"duck_db":-10} }
  ]
}
```

### Output schema (async job)
```jsonc
{
  "ok": true, "job_id":"job_a_5c…", "status":"queued", "kind":"generate_audio",
  "audio_kind":"narration", "provider":"miso", "voice_cloned":true,
  "estimate": { "credits": 3, "seconds_p50": 40 },
  "op_id":"op_e5…", "poll":"get_job", "callback":"audio.ready"
}
// callback on success:
// { "job_id":"job_a_5c…", "media_ref":"med_aud_88", "track_id":"aud_narration",
//   "segment_id":"aud_seg_1", "start_frames":0, "duration_frames":1600,
//   "duration_seconds":100.0, "op_id":"op_e5…" }
```

### Behavior
- **narration:** edge-tts (async `Communicate().save`) or MisoTTS via the Modal
  voice worker. `voice_clone_ref`+`voice_transcript` → one-shot clone (the
  `Segment(text, audio)` context path in `tts_miso.py`). Resulting duration is
  measured and the segment is laid on the audio track at the resolved start.
- **music/sfx:** text-to-audio worker, length = `duration_seconds`,
  optional seamless loop.
- Applies `gain_db`/fades/`ducking` as track metadata consumed at ffmpeg mix time
  (extends the current single-narration mix into multi-track audio).

### Edge cases
- `voice_clone_ref` set with `tts_provider:"edge"` → `unsupported` (cloning is
  MisoTTS-only); suggest switching provider.
- `voice_clone_ref` without `voice_transcript` → proceeds, warns
  `{code:"clone_low_fidelity"}` (transcript strongly improves clone).
- `from_scenes` includes scenes with empty `narration_segment` → skipped, warned.
- narration longer than the video → `ok` but warns `{code:"audio_longer_than_video"}`
  (assembly uses `-shortest`; agent may extend video or trim text).
- `ducking.against_track` missing → `not_found`.

### Undo
`undo` removes the added audio segment (and the track if newly created) and the
generated library asset if this op created it. Re-mix metadata reverts.

### Scene/track mapping
The **AUDIO-track producer**. narration→`aud_narration`, music→`aud_music`,
sfx→`aud_sfx` — parallel tracks under the concatenated scene/video track, mixed
by ffmpeg at assembly. `anchor_scene_id` ties an audio cue to a scene so it
survives reorders.

### How this beats Palmier
- **Voice cloning** (MisoTTS one-shot) is native — Palmier's `generate_audio`
  proxies generic TTS with no Flow-owned clone path.
- **Free tier** (edge-tts) *and* premium GPU TTS in one tool with a provider
  enum; Palmier has no free narration path.
- **`from_scenes`** wires narration directly from the script model (scene
  `narration_segment`s) — Flow is autonomous-first; Palmier has no script concept.
- First-class **multi-track audio** semantics: `gain_db`, fades, **auto-ducking**
  against narration, loopable music beds — richer than Palmier's clip-volume only.

---

## 6. `upscale_media` — AI upscale a clip or image in place

### Purpose
Increase resolution/quality of an existing video or image asset (e.g. promote a
fast 480p draft scene to a crisp 720p/1080p final before publish). Async + gated.

### When to call
- "Upscale scene 5 to 1080p", "sharpen this keyframe", "final-quality pass before
  export".
- Typically late in the workflow: draft at 480p (cheap/fast), upscale chosen
  scenes.

### Input schema
```jsonc
{
  "type": "object",
  "required": ["target"],
  "properties": {
    "target": {
      "type": "object",
      "description": "What to upscale. Exactly one of the keys.",
      "properties": {
        "media_ref": { "type":"string", "description":"Library asset (video or image)." },
        "scene_id": { "type":"integer", "description":"Upscale the scene's clip in place." }
      },
      "oneOf": [ {"required":["media_ref"]}, {"required":["scene_id"]} ]
    },
    "scale": { "type":"number", "enum":[1.5,2,3,4], "default":2,
      "description":"Multiplier. Ignored if target_resolution is set." },
    "target_resolution": { "type":"string", "enum":["720p","1080p","1440p","2160p"],
      "description":"Absolute target (overrides scale). Longest edge for images." },
    "model": { "type":"string", "enum":["realesrgan-video","realesrgan-x4","topaz-proteus"], "default":"realesrgan-video",
      "description":"Upscaler. Video assets must use a video-capable model (list_models)." },
    "denoise": { "type":"number", "minimum":0, "maximum":1, "default":0.3 },
    "preserve_fps": { "type":"boolean", "default":true,
      "description":"Keep source fps (16). false enables optional frame-interpolation models." },
    "replace_in_place": { "type":"boolean", "default":true,
      "description":"true: new version replaces the asset (versioned, undoable). false: store as a new media_ref." },
    "confirm_credits": { "type":"boolean", "default":false }
  },
  "examples": [
    { "target": { "scene_id": 5 }, "target_resolution":"1080p", "model":"realesrgan-video" },
    { "target": { "media_ref":"med_img_a" }, "scale":4, "replace_in_place":false }
  ]
}
```

### Output schema (async job)
```jsonc
{
  "ok": true, "job_id":"job_u_7d…", "status":"queued", "kind":"upscale_media",
  "from": { "width":480, "height":832 }, "to": { "width":1080, "height":1920 },
  "replace_in_place": true,
  "estimate": { "credits": 6, "seconds_p50": 120 },
  "op_id":"op_f6…", "poll":"get_job", "callback":"media.upscaled"
}
// callback: { "job_id":…, "media_ref":"med_vid_77", "version":2,
//             "previous_version":1, "scene_id":5, "op_id":"op_f6…" }
```

### Behavior
- Routes to the upscale worker; for `scene_id`, replaces the scene's clip with the
  upscaled version (new asset **version**), keeping order/narration/captions.
- `replace_in_place:false` yields a fresh `media_ref` so the original draft stays
  untouched.

### Edge cases
- Video asset + image-only model → `unsupported`.
- `target_resolution` lower than source → `invalid_argument` (this is upscale, not
  downscale; suggest a render/export setting instead).
- Source already at/above target → `ok` but warns `{code:"noop_already_high_res"}`,
  no spend.
- Mixed-resolution scenes after partial upscaling → warns at assembly (ffmpeg
  scales to project canvas; agent may upscale remaining scenes for consistency).

### Undo
`undo` restores the previous asset **version** (assets are versioned, original
never destroyed) — for `replace_in_place:true`. For `false`, undo removes the new
`media_ref`. Credit-free.

### Scene/track mapping
Operates on **library assets**; when targeting a `scene_id` it upgrades the
VIDEO-track clip in place without disturbing order or the parallel audio/text
tracks.

### How this beats Palmier
- **Versioned in-place** upscale with credit-free undo and a draft→final workflow
  baked into the scene model (480p draft, upscale chosen scenes). Palmier's
  `upscale_media` returns a new asset with no version lineage.
- Explicit `target_resolution` enum + `scale` enum, `denoise`, and
  video-vs-image model validation — vs Palmier's loose proxy.

---

## 7. `import_media` — bridge external / other-MCP assets into the library

### Purpose
Bring assets from outside Flow's generator into the library so they can become
scenes/tracks: a URL, an uploaded file, a stock clip, or an asset produced by
**another MCP server** (stock/music/web-search) the agent is also connected to.
This is the interoperability bridge. **Not gated** (no Flow generation spend).

### When to call
- "Use this video/image/audio I uploaded", "import that stock clip you found",
  "pull in the track from the music MCP".
- After another MCP tool returns an asset URL/handle the agent wants in Flow.

### Input schema
```jsonc
{
  "type": "object",
  "required": ["sources"],
  "properties": {
    "sources": {
      "type": "array", "minItems": 1, "maxItems": 20,
      "items": {
        "type": "object",
        "required": ["uri"],
        "properties": {
          "uri": { "type":"string",
            "description":"http(s):// URL, data: URI, mcp://<server>/<asset> handle, or upload://<token>." },
          "media_type": { "type":"string", "enum":["video","image","audio","auto"], "default":"auto",
            "description":"auto = sniff from content-type/extension." },
          "name": { "type":"string", "maxLength":120, "description":"Display name in the library." },
          "attribution": { "type":"string", "description":"License/credit text (e.g. stock attribution) — stored on the asset." },
          "trim": { "type":"object",
            "description":"Optional pre-trim on import (video/audio).",
            "properties": {
              "in_seconds": {"type":"number","minimum":0},
              "out_seconds": {"type":"number","minimum":0} } }
        }
      }
    },
    "folder_id": { "type":"string", "description":"Library folder to import into (→ list_folders / create_folder)." },
    "as_scene": {
      "type": "object",
      "description": "Optionally place imported VIDEO directly as a scene on the timeline.",
      "properties": {
        "enabled": {"type":"boolean","default":false},
        "after_scene_id": {"type":"integer"},
        "at_order": {"type":"integer","minimum":0} }
    },
    "transcode": { "type":"boolean", "default":true,
      "description":"Normalize to project codec/fps(16)/canvas on import (recommended for clean assembly)." }
  },
  "examples": [
    { "sources":[ {"uri":"https://stock.example/clip123.mp4","media_type":"video",
        "name":"city timelapse","attribution":"Pexels / Jane Doe"} ],
      "folder_id":"fld_stock", "as_scene":{"enabled":true,"after_scene_id":2} },
    { "sources":[ {"uri":"mcp://music-server/track/lofi-42","media_type":"audio","name":"lofi bed"} ] }
  ]
}
```

### Output schema
```jsonc
{
  "ok": true, "op_id":"op_g7…",
  "imported": [
    { "media_ref":"med_ext_5", "media_type":"video", "name":"city timelapse",
      "width":1080, "height":1920, "duration_frames":480, "fps":16,
      "transcoded":true, "attribution":"Pexels / Jane Doe",
      "scene_id":3 }                        // present only if as_scene.enabled
  ],
  "failed": [],                              // per-source errors (partial success)
  "folder_id":"fld_stock"
}
```

### Behavior
- Fetches each `uri` (http/data/`mcp://`/`upload://`), sniffs/validates type,
  optionally **transcodes** to project codec/fps(16)/canvas via ffmpeg (so
  imported media concatenates cleanly with generated scenes — critical because
  assembly uses `-c copy` concat that requires uniform streams).
- Stores in the library (+ optional folder), records `attribution`. If
  `as_scene.enabled` and the asset is video, also inserts a scene at the placement
  (ripples order).
- **Partial success:** valid sources import; failures are returned per-source in
  `failed[]` (the op still succeeds for the rest — self-correcting).

### Edge cases
- Unreachable/403 `uri` → that source lands in `failed[]` with the HTTP reason;
  others proceed.
- `mcp://` handle from a server the agent isn't connected to → `failed` with
  `{code:"mcp_source_unavailable"}`.
- `media_type:"auto"` sniff inconclusive → `failed` `{code:"unknown_media_type"}`.
- `as_scene.enabled` on a non-video asset → imported to library, scene skipped,
  warned.
- `trim.out_seconds` ≤ `in_seconds` → `invalid_argument`.
- Untrusted/oversized file → rejected by size/type guardrails (`{code:"rejected_by_policy"}`).

### Undo
`undo` removes the imported assets from the library and any scene created via
`as_scene` (re-closing order). Original external source is untouched.

### Scene/track mapping
Primarily a **library producer**; with `as_scene` it can place imported video
straight onto the **VIDEO track** as a scene, and imported audio is then
placeable on AUDIO tracks via `generate_audio`-adjacent placement / group-02
tools. The **transcode-on-import** step is what lets external media coexist with
generated scenes in the uniform concat pipeline.

### How this beats Palmier
- **`mcp://` source handles** make Flow a true hub for *other* MCP servers
  (stock/music/web-search) — the agent composes ecosystems. Palmier's
  `import_media` imports files; it doesn't model cross-MCP asset handles.
- **Transcode-on-import to project fps/canvas** guarantees clean concatenation
  with generated scenes (Flow's assembly is concat-based) — Palmier leaves
  normalization to the NLE.
- **`attribution` capture**, **per-source partial success**, **pre-trim**, and
  **direct as_scene placement** in one typed call.

---

## Appendix — group-level cross-cutting notes

### Capability discovery
All generation tools defer to `→ list_models` (group 01) for the authoritative
matrix of model × {modes, max duration, resolutions, aspect ratios, first/last-
frame & reference support, voices}. Schemas above pin the **current** Modal
deployment (Wan2.2-T2V-A14B / I2V-A14B / Wan2.1-VACE-14B, edge-tts/MisoTTS); the
enums are the source of truth the agent should validate against at call time, but
`list_models` reflects live availability (e.g. VACE best-effort).

### Cost estimation (credits)
Estimates are produced server-side before the gate (0.4). Rough drivers:
`generate_video` ∝ `resolution × duration_frames × num_inference_steps × mode`;
`generate_image` ∝ `resolution × steps × n`; `generate_audio` narration ∝
characters (edge ~free, miso metered by GPU-seconds), music ∝ `duration_seconds`;
`upscale_media` ∝ `output_pixels × frames`. `import_media`/`add_texts`/
`add_captions` cost **0** credits.

### Async + the agent loop
Per the nanocode pattern, the agent loop does not block on jobs: a generation tool
returns a `job_id`; the loop continues (can queue more scenes in parallel), and the
`callback` event resumes reasoning when media is ready. `→ get_job` polls;
`→ cancel_job` aborts with refund. This keeps multi-scene films generating
concurrently rather than serially.

### Determinism & re-rolls
Every generative tool accepts `seed`. Scenes persist their generation params
(prompt/model/seed/steps/guidance/conditioning) so `generate_video` with
`target_scene_id` can reproduce or deliberately vary a result — the
regenerate-in-place capability Flow inherits from Palmier's per-clip memory and
extends with full parameter lineage and versioned, credit-free undo.
