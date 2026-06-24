# Flow Agent Tools — Group 01: Context / Read

**Date:** 2026-06-24
**Status:** 0.3 implementation spec
**Group:** Read-only context tools (9 of 35)
**Audience:** VPS MCP server implementers + agent-loop (nanocode-pattern) authors

---

## Scope & ground rules

This document specifies the **9 read-only context tools** the Flow agent uses to
understand a project before it edits or generates anything. They are the Flow
re-imagining of Palmier's read/inspect group (`get_timeline`, `get_media`,
`inspect_media`, `inspect_timeline`, `get_transcript`, `search_media`,
`inspect_color`, `list_folders`, `list_models`).

| Flow wire-name | Palmier origin | One-line purpose |
|--|--|--|
| `get_project` | `get_timeline` | Seed the agent: project meta + ordered scenes-as-clips + audio/caption tracks + characters + `canGenerate`. |
| `get_media` | `get_media` | List library assets the agent can place/regenerate, with generation status. |
| `inspect_media` | `inspect_media` | Actually *look at* an asset: sampled frames + EXIF + transcription. |
| `inspect_timeline` | `inspect_timeline` | Composited "what the viewer sees" at a given frame/time across all tracks. |
| `get_transcript` | `get_transcript` | Timeline-wide, word-level spoken transcript in project frames. |
| `search_media` | `search_media` | Find assets by visual content **and** spoken content. |
| `inspect_color` | `inspect_color` | Measure color scopes (black/white points, clipping, means) for a scene/frame. |
| `list_folders` | `list_folders` | Library folder tree. |
| `list_models` | `list_models` | Wan2.2/VACE/voice models + full capability matrix. |

### Conventions used by every tool in this group

- **All tools are read-only.** They never mutate the project, never enqueue
  generation, and never consume credits. They therefore ignore `canGenerate` for
  their own execution but **report** it so the agent can plan.
- **IDs.** `project_id` (string, ULID), `scene_id` (string, ULID — *not* the
  legacy integer `Scene.id`; see "Mapping" notes), `media_id`, `track_id`,
  `character_id`, `folder_id`, `model_id` are all opaque strings issued by the
  Flow API. The agent must treat them as opaque and only reuse values it received.
- **Units.** Every temporal field is explicitly suffixed: `*_frame` / `*_frames`
  are integer **frames** at the project `fps`; `*_seconds` are floating **seconds**.
  Tools that accept a position accept **either** and echo back both (frames are
  canonical). This kills the single biggest class of agent timing bugs that
  Palmier's loosely-typed `startSeconds`/`frame` mix invites.
- **Token hygiene.** Defaults are omitted from outputs (speed `1.0`, opacity
  `1.0`, identity transform, empty trims). Large blobs (frames, transcripts) are
  paginated/windowed and returned as references or base64 only when explicitly
  requested.
- **Ownership.** Every tool resolves `project_id` against the authenticated
  caller; cross-tenant IDs return `error.code = "not_found"` (never "forbidden",
  to avoid leaking existence).
- **Error envelope.** Per nanocode, errors are returned as a structured result
  (the MCP tool result `content`), never an exception:
  ```json
  { "ok": false, "error": { "code": "not_found|invalid_args|unavailable|rate_limited", "message": "human-readable", "hint": "what to call instead" } }
  ```
  Successful results are `{ "ok": true, ...payload }`.

### Flow's scene/track model (shared by the whole group)

Scenes **are** the timeline. The ordered list of scenes is the **video track**;
ffmpeg concatenates them into one finished track. Two parallel tracks ride
alongside:

- **`audio` track(s)** — narration (edge-tts / MisoTTS voice clone) and music.
- **`caption` track** — styled text (captions/titles/lower-thirds).

A **scene-as-clip** therefore carries both *generation* state (prompt, model,
first/last frame, reference images, characters, generation status) and *clip*
state (start frame within the assembled timeline, duration, trims, speed,
opacity, transform, keyframes). Read tools surface both faces.

---

## 1. `get_project`  *(was `get_timeline`)*

### Purpose
The **session-seed** call. Returns everything the agent needs to reason about a
project in one shot: project meta, the ordered scenes-as-clips (the video track),
the parallel audio/caption tracks, the cast of characters, and the
`canGenerate`/credits gate. Every other tool's IDs originate here.

### When to call
- **Always first**, at the start of every agent session (mirror Palmier's
  "always call `get_timeline` first").
- After any mutating tool that the agent did not itself issue (e.g. another
  client edited the project), to re-sync.
- Prefer the cheaper `revision` check (see output) over re-pulling the full tree
  on a tight loop.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": {
      "type": "string",
      "description": "ULID of the project to load. Required.",
      "examples": ["01J9Z0M2K3QF8X7P4ABCD2EFGH"]
    },
    "include": {
      "type": "array",
      "description": "Sections to include. Omit for the default lean set (meta + scenes + tracks + canGenerate).",
      "items": {
        "type": "string",
        "enum": ["meta", "scenes", "tracks", "characters", "prompt_history", "thumbnails", "stats"]
      },
      "default": ["meta", "scenes", "tracks", "characters"],
      "examples": [["meta", "scenes", "tracks", "characters", "thumbnails"]]
    },
    "scene_fields": {
      "type": "string",
      "description": "Detail level per scene. 'summary' omits prompts/keyframes for very long projects.",
      "enum": ["summary", "standard", "full"],
      "default": "standard"
    }
  },
  "required": ["project_id"],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "project": {
    "id": "01J9Z0M2K3QF8X7P4ABCD2EFGH",
    "title": "The History of the Internet",
    "revision": 47,
    "fps": 30,
    "resolution": { "width": 1080, "height": 1920, "label": "1080x1920", "aspect_ratio": "9:16" },
    "total_frames": 1800,
    "total_seconds": 60.0,
    "status": "draft|generating|assembled|published",
    "created_at": "2026-06-24T10:00:00Z",
    "updated_at": "2026-06-24T15:30:00Z"
  },
  "tracks": [
    {
      "id": "trk_video",
      "kind": "video",
      "role": "scenes",
      "clip_count": 12,
      "note": "Ordered scenes. This track IS the assembled video."
    },
    { "id": "trk_narration", "kind": "audio", "role": "narration", "clip_count": 12 },
    { "id": "trk_music",     "kind": "audio", "role": "music",     "clip_count": 1  },
    { "id": "trk_captions",  "kind": "caption", "role": "captions", "clip_count": 12 }
  ],
  "scenes": [
    {
      "id": "scn_01J9...",
      "index": 0,
      "track_id": "trk_video",
      "start_frame": 0,
      "duration_frames": 150,
      "duration_seconds": 5.0,
      "visual_prompt": "Aerial dawn shot over ARPANET nodes blinking on a US map",
      "camera": "slow push-in",
      "model_id": "wan2.2-t2v-a14b",
      "generation": {
        "status": "ready|queued|generating|failed|stale|empty",
        "first_frame_media_id": "med_aaa",
        "last_frame_media_id": "med_bbb",
        "reference_image_media_ids": ["med_ref1"],
        "media_id": "med_clip01",
        "stale": false
      },
      "characters": ["chr_narrator"],
      "narration_segment": "It began as a way to survive a nuclear strike...",
      "clip_props": { "speed": 1.0, "opacity": 1.0 },
      "prompt_history": [
        { "revision": 31, "visual_prompt": "...", "model_id": "wan2.2-t2v-a14b" }
      ]
    }
  ],
  "characters": [
    {
      "id": "chr_narrator",
      "name": "Narrator",
      "description": "A calm middle-aged documentary voice persona, silver hair",
      "reference_image_media_id": "med_ref_narr",
      "has_reference": true,
      "voice_id": "voice_clone_narr",
      "scene_ids": ["scn_01J9...", "scn_02..."]
    }
  ],
  "canGenerate": {
    "allowed": true,
    "reason": null,
    "plan": "pro",
    "credits_remaining": 184,
    "credits_unit": "scene-generations",
    "blocked_tools": []
  }
}
```

### Behavior
- Single round-trip to the Flow scene store. `scene_fields=summary` drops
  `visual_prompt`, `prompt_history`, and per-clip keyframes for >100-scene films
  to stay within context budget.
- `start_frame` is **computed** from the ordered concatenation (sum of prior
  scene `duration_frames` after trims). It is authoritative for all positional
  tools (`split_clip`, `inspect_timeline`, `get_transcript`).
- `revision` is a monotonically increasing project version; bump on any mutation.
  The agent can pass it to mutating tools for optimistic-concurrency.
- `generation.stale = true` when the scene's prompt/model/refs changed after the
  last successful render (signals "needs regenerate").
- `canGenerate` is computed from the caller's plan + credit balance; read tools
  still work when `allowed=false`.

### Edge cases
- **Empty project** (no scenes): `scenes: []`, `total_frames: 0`, still returns
  tracks scaffold and `canGenerate`.
- **Mid-generation**: scenes with `status: generating` carry no `media_id` yet;
  `start_frame` uses the planned `duration_frames`.
- **Out-of-range `include`**: unknown enum value → `invalid_args` with the
  allowed list in `hint`.
- **Huge project**: if serialized output would exceed the context budget, the
  tool auto-downgrades to `summary` and sets `project.truncated: true` with a
  `hint` to call `get_project` per-scene-range (via `inspect_timeline`/paged
  variants).

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
This **is** the timeline serialization. `Scene.id` (legacy int) is surfaced as
`index`; the stable ULID `scn_...` is the addressable id. The video track is
literally the ordered scenes; audio/caption tracks are sidecars produced in
post-production. `start_frame`/`duration_frames` translate the abstract "ordered
scenes" into concatenation offsets so the same coordinate space serves every
timeline tool.

### How this beats Palmier
- **One call returns the cast.** Palmier's `get_timeline` has no character
  concept; Flow folds the character bank (name, description, reference image,
  cloned `voice_id`, and which scenes each appears in) into the seed so the agent
  is casting-aware from turn one.
- **Generation-native scene state.** Each clip exposes `model_id`,
  first/last-frame media, reference images, `prompt_history`, and a `stale` flag —
  enabling "regenerate in place" reasoning Palmier can't express for 3rd-party
  models.
- **Dual-unit, computed coordinates.** Both frames and seconds, plus a
  server-computed `start_frame` per scene, remove the agent's need to sum
  durations itself (a frequent Palmier failure mode).
- **`revision` for cheap re-sync + optimistic concurrency**, vs Palmier's
  full-pull-only model.
- **Self-throttling output** (`summary` auto-downgrade + `truncated` flag) keeps
  60-minute, 700-scene films inside the model's context window.

---

## 2. `get_media`

### Purpose
List the project's **media library**: every asset the agent can place, inspect,
regenerate, or attach — generated clips, extracted frames, imported stock,
narration/music audio, reference images. The source of every `media_id`.

### When to call
- After `get_project`, when the agent needs to reference assets not inlined in
  the scene tree (e.g. orphaned generations, imported stock, alternate takes).
- Before `inspect_media` / `search_media` to discover candidate `media_id`s.
- To poll `generation_status` of async jobs kicked off by generate tools.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "folder_id": {
      "type": "string",
      "description": "Restrict to one folder. Omit for the whole library.",
      "default": null
    },
    "kind": {
      "type": "array",
      "description": "Filter by media kind. Omit for all kinds.",
      "items": { "type": "string", "enum": ["video", "image", "audio", "frame", "reference", "lottie"] }
    },
    "generation_status": {
      "type": "array",
      "items": { "type": "string", "enum": ["none", "queued", "generating", "downloading", "ready", "failed"] },
      "description": "Filter by async generation state. 'none' = imported/static asset."
    },
    "used": {
      "type": "string",
      "enum": ["any", "used", "unused"],
      "default": "any",
      "description": "'unused' surfaces orphaned generations not attached to any scene/track."
    },
    "limit":  { "type": "integer", "minimum": 1, "maximum": 200, "default": 50 },
    "cursor": { "type": "string", "description": "Opaque pagination cursor from a prior call." },
    "sort":   { "type": "string", "enum": ["created_desc", "created_asc", "name", "duration"], "default": "created_desc" }
  },
  "required": ["project_id"],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "media": [
    {
      "id": "med_clip01",
      "kind": "video",
      "name": "scene-01-take-2.mp4",
      "folder_id": "fld_renders",
      "generation_status": "ready",
      "duration_frames": 150,
      "duration_seconds": 5.0,
      "width": 1080, "height": 1920, "fps": 30,
      "has_audio": false,
      "codec": "h264",
      "bytes": 4192304,
      "thumbnail_media_id": "med_thumb01",
      "source": { "type": "generated", "model_id": "wan2.2-t2v-a14b", "prompt": "Aerial dawn shot..." },
      "used_by": { "scene_ids": ["scn_01J9..."], "track_ids": ["trk_video"] },
      "created_at": "2026-06-24T11:02:00Z"
    },
    {
      "id": "med_narr01",
      "kind": "audio",
      "name": "narration-scene-01.wav",
      "generation_status": "ready",
      "duration_seconds": 4.8,
      "sample_rate": 24000,
      "source": { "type": "tts", "engine": "miso", "voice_id": "voice_clone_narr" },
      "used_by": { "track_ids": ["trk_narration"] }
    }
  ],
  "next_cursor": "eyJvIjoxMDB9",
  "total": 87
}
```

### Behavior
- Returns **metadata only** — never pixel/audio data (use `inspect_media`).
- `source` discriminates `generated` (Wan2.2/VACE, carries `model_id`+`prompt`),
  `tts` (edge-tts/miso, carries `engine`+`voice_id`), `imported`, `extracted`
  (a frame pulled from a clip), or `upscaled`.
- `used_by` is computed by reverse-index over scenes/tracks — powers
  "delete unused takes" and "find the clip behind scene 3" reasoning.
- Pagination is cursor-based and stable across the page even if new generations
  complete mid-iteration.

### Edge cases
- **`failed` generations** are included (so the agent can diagnose/retry) with a
  `source.error` string.
- **`downloading`**: model finished on Modal, asset still transferring to the
  VPS; duration/dims may be `null` until `ready`.
- **Empty library**: `media: []`, `total: 0`.
- Invalid `cursor` → `invalid_args`.

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Media is the asset pool that scenes and audio/caption tracks **point into**.
A scene's rendered clip, its first/last conditioning frames, and reference images
are all media rows; `used_by` reconstructs the scene↔media graph.

### How this beats Palmier
- **Provenance-rich `source`.** Palmier exposes `generationStatus` but Flow owns
  the pipeline, so every generated asset carries the exact `model_id`, `prompt`,
  TTS `engine`/`voice_id` — the agent can re-roll or re-voice with full fidelity.
- **`used_by` reverse index** turns garbage-collection and "which take is live"
  into a single field instead of a cross-reference the agent must compute.
- **`used: unused` filter** is a first-class orphan finder; Palmier requires the
  agent to diff library vs timeline manually.
- **Typed, paginated, sortable** with explicit dual-unit durations vs Palmier's
  flat list.

---

## 3. `inspect_media`

### Purpose
Actually **look at / listen to** a single asset before acting on it: sampled
video frames (storyboard or windowed zoom), image pixels + EXIF, and audio
transcription. This is how the agent grounds visual/aural decisions instead of
trusting filenames.

### When to call
- Before regenerating or trimming a scene, to confirm what the current clip looks
  like ("does scene 3 actually show the character facing left?").
- To read text/EXIF off an image, or to transcribe a standalone audio asset.
- To pick a good split/trim point by eyeballing sampled frames.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "media_id":   { "type": "string", "description": "Asset from get_media / get_project." },
    "mode": {
      "type": "string",
      "enum": ["overview", "window", "single_frame", "audio_only"],
      "default": "overview",
      "description": "overview=evenly-spaced storyboard; window=dense frames in a time range; single_frame=one frame; audio_only=skip frames, transcribe only."
    },
    "start_seconds": { "type": "number", "minimum": 0, "description": "Window start (mode=window)." },
    "end_seconds":   { "type": "number", "minimum": 0, "description": "Window end (mode=window)." },
    "at_frame":      { "type": "integer", "minimum": 0, "description": "Frame to sample (mode=single_frame). Media-local frames." },
    "max_frames": {
      "type": "integer", "minimum": 1, "maximum": 32, "default": 8,
      "description": "Cap on returned frames. Frames are downscaled to <=512px long edge."
    },
    "include_exif":          { "type": "boolean", "default": true,  "description": "Images only." },
    "include_transcription": { "type": "boolean", "default": true,  "description": "Video/audio only." },
    "include_color_summary": { "type": "boolean", "default": false, "description": "Cheap per-frame mean/luma; full scopes via inspect_color." }
  },
  "required": ["project_id", "media_id"],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "media_id": "med_clip01",
  "kind": "video",
  "duration_seconds": 5.0,
  "duration_frames": 150,
  "fps": 30,
  "frames": [
    {
      "index": 0,
      "media_local_frame": 0,
      "at_seconds": 0.0,
      "image_b64": "data:image/jpeg;base64,...",
      "width": 288, "height": 512,
      "color_summary": { "mean_luma": 0.41, "dominant_hex": "#2b3a55" }
    }
  ],
  "transcription": {
    "language": "en",
    "text": "It began as a way to survive a nuclear strike.",
    "words": [ { "text": "It", "start_seconds": 0.12, "end_seconds": 0.28 } ],
    "engine": "whisper-local"
  },
  "exif": null,
  "note": "overview: 8 frames evenly spaced across 5.0s"
}
```

### Behavior
- `overview` samples `max_frames` evenly across the asset (storyboard).
  `window` packs `max_frames` between `start_seconds`/`end_seconds` for a zoomed
  look. `single_frame` returns exactly one. `audio_only` skips frame extraction.
- Frames are JPEG, downscaled to ≤512px long edge to control token cost; the agent
  can request a tighter `window` for detail rather than more pixels.
- Transcription runs on-device (whisper-local) and is cached per media revision.
- For **images**, `frames` holds the single decoded image; `exif` carries camera/
  dimensions/orientation/embedded prompt if present.

### Edge cases
- **`mode=window` on an image** → `invalid_args` (no time axis); hint to use
  `single_frame` or default.
- **`window` out of range** → clamped to `[0, duration]`, `note` records the clamp.
- **Silent/musical audio** → `transcription.text: ""`, `words: []`,
  `transcription.note: "no speech detected"`.
- **Asset still `generating`/`downloading`** → `unavailable` with a hint to poll
  `get_media`.
- **`max_frames` > available frames** → returns all frames, no error.

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Operates on a single media row (a scene's clip, a conditioning frame, a narration
file). To inspect "scene N", the agent resolves `scene.generation.media_id` from
`get_project`, then calls this. Windowed frames use **media-local** time; the
composited timeline view is `inspect_timeline`'s job.

### How this beats Palmier
- **Explicit sampling modes with hard frame caps + downscale**, so a single call
  has predictable token cost — Palmier's `overview`+`startSeconds/endSeconds` is
  re-expressed as a typed `mode` enum with ranges and a `max_frames` ceiling.
- **Per-frame `color_summary`** inline (opt-in) gives the agent a cheap luma/
  dominant-color read without a second `inspect_color` round-trip.
- **Embedded generation prompt in EXIF** for Flow-generated images closes the
  loop back to regeneration.
- **Revision-cached transcription** avoids re-running whisper on every glance.

---

## 4. `inspect_timeline`

### Purpose
Show **what the viewer actually sees and hears at a given moment** — the
composited result of all tracks (active scene clip + caption overlay + which
audio is playing) at a specific timeline frame/second. The "playhead screenshot".

### When to call
- To verify a composite: "at 12s, is the lower-third title overlapping the
  character's face?"
- To find which scene owns a timeline position before splitting/trimming.
- To preview a transition boundary between two scenes.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "at_frame":   { "type": "integer", "minimum": 0, "description": "Timeline frame (project coords). Provide this OR at_seconds." },
    "at_seconds": { "type": "number",  "minimum": 0, "description": "Timeline seconds. Converted to frame at project fps." },
    "render_composite": {
      "type": "boolean", "default": true,
      "description": "Rasterize the stacked frame (scene + caption overlays). false = structural answer only, no pixels."
    },
    "include_audio_state": { "type": "boolean", "default": true },
    "window_frames": {
      "type": "integer", "minimum": 0, "maximum": 30, "default": 0,
      "description": "If >0, also return composites at +/- this many frames to inspect a transition boundary."
    }
  },
  "required": ["project_id"],
  "oneOf": [ { "required": ["at_frame"] }, { "required": ["at_seconds"] } ],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "at_frame": 360,
  "at_seconds": 12.0,
  "active": {
    "scene_id": "scn_03...",
    "scene_index": 2,
    "scene_local_frame": 60,
    "media_id": "med_clip03",
    "clip_props": { "opacity": 1.0, "transform": { "scale": 1.0 } }
  },
  "overlays": [
    {
      "track_id": "trk_captions",
      "kind": "caption",
      "text": "The first message was 'LO'",
      "style": "lower_third",
      "bbox_norm": { "x": 0.1, "y": 0.78, "w": 0.8, "h": 0.12 }
    }
  ],
  "audio_state": [
    { "track_id": "trk_narration", "media_id": "med_narr03", "playing": true,  "gain": 1.0, "word": "message" },
    { "track_id": "trk_music",     "media_id": "med_music",  "playing": true,  "gain": 0.18 }
  ],
  "composite_b64": "data:image/jpeg;base64,...",
  "boundary": null
}
```

### Behavior
- Resolves the timeline frame → owning scene via the computed `start_frame`
  offsets, then composites the scene frame with caption overlays (respecting
  z-order/opacity/transform) using the same ffmpeg filter graph as final render,
  at preview resolution.
- `audio_state` reports which audio clips are audible and, for narration, the
  current spoken `word` (from the aligned transcript) — lets the agent reason
  about narration↔visual sync.
- `window_frames>0` returns a `boundary` object with composites at
  `at_frame ± window_frames` (clamped), for inspecting cuts/transitions.

### Edge cases
- **Position past `total_frames`** → `invalid_args` with `total_frames` in `hint`.
- **Gap** (no active scene, e.g. project mid-edit) → `active: null`,
  `composite_b64` is a black frame, `note` explains the gap.
- **`render_composite=false`** → omit `composite_b64`; pure structural answer
  (cheap, no rasterization).
- Both `at_frame` and `at_seconds` supplied → `at_frame` wins; `note` records it.

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
This is the **only** read tool that crosses tracks: it stacks the active video
scene with the caption track and reports concurrent audio. Because scenes are the
video track, "the frame at time T" is "the T-owning scene's local frame,
composited with overlays" — computed through the same assembly graph that
produces the final ffmpeg output, guaranteeing preview==render fidelity.

### How this beats Palmier
- **Preview==render guarantee.** Flow composites through the *actual* ffmpeg
  assembly filter graph, so what the agent inspects is byte-for-byte what renders.
- **Audio-aware composite.** Palmier's `inspect_timeline` is visual-only; Flow
  adds `audio_state` including the live narration `word`, enabling narration/visual
  sync edits in one call.
- **Transition window** (`window_frames`) returns the cut neighborhood in a single
  call rather than three separate frame inspections.
- **Dual-unit `oneOf` input** enforces exactly one of frame/second at the schema
  level — Palmier's untyped frame field allows ambiguous calls.

---

## 5. `get_transcript`

### Purpose
The **timeline-wide, word-level spoken transcript** in project-frame coordinates
(post-edit). Powers transcript-driven editing: filler/dead-air removal, quote
finding, caption authoring, and narration↔scene alignment.

### When to call
- Before transcript-driven cuts (`ripple_delete_ranges` of "um"/silence).
- To locate a quote/phrase and map it to a timeline frame range.
- To author captions (`add_captions`) aligned to spoken narration.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "track_id": {
      "type": "string",
      "description": "Limit to one audio track (e.g. trk_narration). Omit to merge all speech tracks.",
      "default": null
    },
    "granularity": {
      "type": "string",
      "enum": ["word", "segment", "scene"],
      "default": "word",
      "description": "word=per-word timing; segment=sentence/phrase; scene=one block of narration per scene."
    },
    "start_frame": { "type": "integer", "minimum": 0, "description": "Restrict to a timeline range (inclusive)." },
    "end_frame":   { "type": "integer", "minimum": 0, "description": "Restrict to a timeline range (inclusive)." },
    "include_non_speech": {
      "type": "boolean", "default": false,
      "description": "Include detected silence/[music]/[noise] markers as zero-text events (for dead-air removal)."
    }
  },
  "required": ["project_id"],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "fps": 30,
  "source_tracks": ["trk_narration"],
  "granularity": "word",
  "items": [
    { "text": "It",      "start_frame": 4,   "end_frame": 9,   "start_seconds": 0.13, "end_seconds": 0.30, "scene_id": "scn_01...", "confidence": 0.98 },
    { "text": "began",   "start_frame": 10,  "end_frame": 22,  "scene_id": "scn_01...", "confidence": 0.97 }
  ],
  "non_speech": [
    { "kind": "silence", "start_frame": 145, "end_frame": 168, "duration_seconds": 0.77 }
  ],
  "full_text": "It began as a way to survive a nuclear strike...",
  "word_count": 142
}
```

### Behavior
- Aligns each audio clip's local transcription (whisper-local) onto **timeline
  frames** using the clip's placement on its audio track, so word timings match
  what `inspect_timeline` reports.
- `granularity=scene` collapses to one item per scene (the scene's
  `narration_segment`), giving a compact map for high-level reasoning.
- `non_speech` (opt-in) surfaces silence/music gaps as rangeable events — the
  fast path feeding `ripple_delete_ranges`.
- Cached per project `revision`; invalidated when audio tracks change.

### Edge cases
- **No audio tracks / no narration yet** → `items: []`, `full_text: ""`,
  `note: "no speech tracks"`.
- **Range with no words** → empty `items`, still echoes the requested range.
- **Multiple overlapping speech tracks** with `track_id` omitted → merged and
  sorted by `start_frame`; each item keeps its `track_id` for disambiguation.
- `start_frame > end_frame` → `invalid_args`.

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Reads the **audio track(s)** (narration/music) and projects word timings into the
shared timeline-frame space defined by the ordered scenes. Each word carries its
owning `scene_id`, bridging the spoken layer back to the video track so
transcript edits can target the right scene.

### How this beats Palmier
- **Per-word `scene_id` ownership.** Flow maps every word to the scene playing
  beneath it, so "trim the sentence about ARPANET" resolves directly to a scene +
  frame range. Palmier's transcript is frame-only.
- **`granularity` enum incl. `scene`** gives a compact narration map for long
  films without dumping thousands of words.
- **`include_non_speech`** makes dead-air a first-class, rangeable event rather
  than something the agent infers from gaps.
- **Dual-unit timings + revision caching** vs Palmier's frame-only, recompute-each-time
  transcript.

---

## 6. `search_media`

### Purpose
Find assets in the library by **content** — both **visual** (what's on screen)
and **spoken** (what's said) — rather than filename. Lets the agent answer "find
the clip where the character looks at the camera" or "where do we say 'TCP/IP'".

### When to call
- To locate b-roll/takes matching a described shot.
- To find spoken phrases across all media (not just the current timeline — that's
  `get_transcript`).
- To pick reference frames/images for character or scene conditioning.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "query": {
      "type": "string",
      "description": "Natural-language description and/or spoken phrase.",
      "examples": ["wide shot of city skyline at dusk", "the phrase 'nuclear strike'"]
    },
    "modalities": {
      "type": "array",
      "items": { "type": "string", "enum": ["visual", "spoken"] },
      "default": ["visual", "spoken"],
      "description": "Search visual embeddings, spoken transcript, or both."
    },
    "kind": {
      "type": "array",
      "items": { "type": "string", "enum": ["video", "image", "audio", "frame", "reference"] },
      "description": "Restrict to media kinds."
    },
    "folder_id": { "type": "string", "default": null },
    "top_k":     { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
    "min_score": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.2 }
  },
  "required": ["project_id", "query"],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "query": "wide shot of city skyline at dusk",
  "results": [
    {
      "media_id": "med_brl12",
      "kind": "video",
      "score": 0.83,
      "matched_on": ["visual"],
      "best_frame": { "media_local_frame": 45, "at_seconds": 1.5, "thumbnail_media_id": "med_thumb12" },
      "name": "skyline-take-3.mp4",
      "used_by": { "scene_ids": [] }
    },
    {
      "media_id": "med_narr07",
      "kind": "audio",
      "score": 0.71,
      "matched_on": ["spoken"],
      "spoken_match": { "text": "...over the city at dusk...", "start_seconds": 2.1, "end_seconds": 3.0 }
    }
  ],
  "count": 2
}
```

### Behavior
- **Visual** search runs over per-asset frame embeddings (CLIP-class), returning
  the `best_frame` that matched. **Spoken** search runs over cached
  transcriptions, returning the matched span.
- Results fuse both modalities into one ranked list with `matched_on` provenance;
  `score` is normalized 0–1, filtered by `min_score`.
- Indexes are built lazily on first inspect/generation and refreshed when an asset
  changes.

### Edge cases
- **Modality requested but unindexed** (e.g. spoken search on assets never
  transcribed) → those assets skipped; `note` lists how many were unindexed.
- **No results above `min_score`** → `results: []`, `count: 0` (not an error).
- **Query that's only a quoted phrase** with `modalities=["visual"]` → still runs
  visual; `note` suggests adding `spoken`.

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Searches the media pool that scenes and audio tracks draw from. `used_by`
reveals whether a hit is already on the video track or a free b-roll/reference
candidate the agent can attach.

### How this beats Palmier
- **True multimodal fusion** with `matched_on` provenance and a `best_frame`/
  `spoken_match` locator per hit — Palmier returns visual+spoken matches but Flow
  pinpoints the exact frame/span and fuses scores into one ranked list.
- **`min_score`/`top_k` typed knobs** give deterministic, budget-bounded results.
- **Generation-aware**: image/reference hits feed directly into Flow's character/
  scene conditioning (the result is a ready `media_id` for `attach_character`/
  `regenerate_scene`).

---

## 7. `inspect_color`

### Purpose
Measure **color scopes** for a scene or specific timeline frame: black/white
points, clipping, per-channel means, luma histogram, dominant palette. The
quantitative basis for grading decisions (`apply_color`).

### When to call
- Before grading: "is scene 4 crushed in the shadows / clipped in highlights?"
- To match looks across scenes ("make scene 5 match scene 2's white point").
- To validate a grade after `apply_color`.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "target": {
      "type": "string",
      "enum": ["scene", "timeline_frame", "media"],
      "description": "What to measure: a whole scene (averaged + sampled), one timeline frame, or a media asset."
    },
    "scene_id":   { "type": "string", "description": "Required when target=scene." },
    "media_id":   { "type": "string", "description": "Required when target=media." },
    "at_frame":   { "type": "integer", "minimum": 0, "description": "Required when target=timeline_frame (project coords)." },
    "scopes": {
      "type": "array",
      "items": { "type": "string", "enum": ["luma_histogram", "rgb_parade", "black_white_points", "clipping", "channel_means", "dominant_palette", "saturation"] },
      "default": ["black_white_points", "clipping", "channel_means", "luma_histogram"]
    },
    "histogram_bins": { "type": "integer", "minimum": 16, "maximum": 256, "default": 64 }
  },
  "required": ["project_id", "target"],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "target": "scene",
  "scene_id": "scn_04...",
  "sampled_frames": 5,
  "scopes": {
    "black_white_points": { "black": 0.04, "white": 0.93, "range": 0.89 },
    "clipping": { "shadow_clip_pct": 1.2, "highlight_clip_pct": 0.3 },
    "channel_means": { "r": 0.46, "g": 0.41, "b": 0.52, "luma": 0.44 },
    "luma_histogram": { "bins": 64, "counts": [/* 64 ints, normalized 0-1 */], "peak_bin": 18 },
    "dominant_palette": [ { "hex": "#2b3a55", "weight": 0.34 }, { "hex": "#c9a06b", "weight": 0.21 } ],
    "saturation": { "mean": 0.38, "max": 0.91 }
  },
  "note": "scene measured over 5 evenly-sampled frames"
}
```

### Behavior
- `target=scene` samples several frames across the scene and averages scope
  values (with per-frame variance available on request) — robust to a single
  outlier frame. `timeline_frame` measures one composited frame. `media`
  measures a raw asset (pre-composite).
- Values are normalized 0–1 (not 8-bit) so they're resolution/bit-depth agnostic.
- `clipping` percentages are the fraction of pixels at the extremes — the key
  signal for "fix the blown highlights".

### Edge cases
- **`target=scene` with no rendered clip** (scene still generating) →
  `unavailable`, hint to poll `get_project`.
- **Mismatched required field** (e.g. `target=scene` without `scene_id`) →
  `invalid_args`.
- **Solid-color/black frame** → valid scopes (range ≈ 0), `note` flags low range.

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Measures the video track. `target=scene` is the natural Flow unit (one scene = one
clip), while `timeline_frame` measures the *composited* output (post overlays),
matching `inspect_timeline`. Both feed `apply_color` which grades per-scene.

### How this beats Palmier
- **Scene-native, multi-frame averaging.** Palmier measures a frame; Flow measures
  a *scene* across sampled frames with variance, matching its primitive and
  resisting outlier frames.
- **Richer scope set** (dominant palette + saturation + normalized histogram)
  enables look-*matching* between scenes, not just inspection.
- **Composite-vs-raw `target` distinction** lets the agent grade pre- or
  post-overlay deliberately.

---

## 8. `list_folders`

### Purpose
Return the library's **folder tree** so the agent can navigate, scope searches,
and target media-management tools (`create_folder`, `move_to_folder`, etc.).

### When to call
- Before organizing media or scoping `get_media`/`search_media` to a folder.
- To resolve a human folder name ("the b-roll folder") to a `folder_id`.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string" },
    "parent_id": {
      "type": "string",
      "description": "List children of this folder. Omit for the root tree.",
      "default": null
    },
    "depth": {
      "type": "integer", "minimum": 1, "maximum": 10, "default": 3,
      "description": "How many levels of the tree to return."
    },
    "include_counts": { "type": "boolean", "default": true, "description": "Include media counts per folder." }
  },
  "required": ["project_id"],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "root": { "id": "fld_root", "name": "/", "media_count": 87 },
  "folders": [
    {
      "id": "fld_renders", "name": "Renders", "parent_id": "fld_root",
      "media_count": 24, "depth": 1,
      "children": [
        { "id": "fld_takes", "name": "Alt Takes", "parent_id": "fld_renders", "media_count": 9, "depth": 2, "children": [] }
      ]
    },
    { "id": "fld_broll", "name": "B-Roll", "parent_id": "fld_root", "media_count": 31, "depth": 1, "children": [] }
  ],
  "truncated": false
}
```

### Behavior
- Returns a nested tree (children inlined up to `depth`); deeper nodes are omitted
  and the parent flags `has_more_children: true`.
- `media_count` is recursive (folder + descendants) when `include_counts`.
- System folders (e.g. auto-created `Renders`, `Narration`) are marked
  `system: true` (omitted when false) so the agent avoids renaming/deleting them.

### Edge cases
- **No folders** (flat library) → `folders: []`, all media under `root`.
- **`parent_id` not found** → `not_found`.
- **Tree deeper than `depth`** → `truncated: true`, deepest returned nodes carry
  `has_more_children`.

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Folders organize the **media pool**, orthogonal to the scene/track timeline. They
don't affect playback; they're an authoring convenience that scopes the other
read tools.

### How this beats Palmier
- **Recursive counts + `system` flags** protect Flow's auto-managed folders
  (Renders/Narration) from destructive media-mgmt tools — Palmier lists folders
  without guarding pipeline-owned ones.
- **Bounded `depth` with explicit `truncated`/`has_more_children`** keeps large
  libraries inside the context budget deterministically.

---

## 9. `list_models`

### Purpose
Expose the **generation model catalog** — Flow-owned Wan2.2 (T2V/I2V/FLF2V/S2V) +
Wan2.1 VACE + voice models — with a full **capability matrix** so the agent picks
the right model for a generate call (and knows what each can/can't do).

### When to call
- Before `generate_video`/`generate_image`/`regenerate_scene` to choose a
  `model_id` matching the needed conditioning (first-frame, last-frame, reference,
  subject consistency).
- Before voice work, to list available/cloned voices.
- To check supported durations/resolutions/aspect ratios for a target platform.

### Input schema
```json
{
  "type": "object",
  "properties": {
    "project_id": { "type": "string", "description": "Optional: filters voices to those available to the project's owner." },
    "category": {
      "type": "array",
      "items": { "type": "string", "enum": ["video", "image", "voice", "upscale", "music"] },
      "description": "Restrict to model categories. Omit for all."
    },
    "capability": {
      "type": "array",
      "items": { "type": "string", "enum": ["text_to_video", "image_to_video", "first_last_frame", "subject_consistency", "reference_image", "voice_clone"] },
      "description": "Only return models supporting ALL listed capabilities."
    },
    "include_voices": { "type": "boolean", "default": true }
  },
  "required": [],
  "additionalProperties": false
}
```

### Output schema
```json
{
  "ok": true,
  "models": [
    {
      "id": "wan2.2-t2v-a14b",
      "repo": "Wan-AI/Wan2.2-T2V-A14B-Diffusers",
      "category": "video",
      "display_name": "Wan 2.2 T2V 14B",
      "capabilities": ["text_to_video"],
      "durations_seconds": { "min": 1, "max": 5, "step": 1, "default": 5 },
      "resolutions": [ { "label": "480p", "width": 832, "height": 480 }, { "label": "720p", "width": 1280, "height": 720 } ],
      "aspect_ratios": ["16:9", "9:16", "1:1"],
      "fps": 16,
      "conditioning": { "first_frame": false, "last_frame": false, "reference_image": false, "subject": false },
      "backend": "modal",
      "cost": { "credits_per_second": 1, "approx_usd_per_clip": 0.15 },
      "speed": { "approx_seconds_per_clip_a100": 54 },
      "default_for": ["scene_generation"]
    },
    {
      "id": "wan2.2-i2v-a14b",
      "category": "video",
      "display_name": "Wan 2.2 I2V 14B",
      "capabilities": ["image_to_video", "first_last_frame"],
      "conditioning": { "first_frame": true, "last_frame": true, "reference_image": false, "subject": false },
      "note": "Used for scene chaining (FLF2V) — last frame of prev scene conditions next."
    },
    {
      "id": "wan2.1-vace-14b",
      "category": "video",
      "display_name": "Wan 2.1 VACE 14B",
      "capabilities": ["text_to_video", "image_to_video", "reference_image", "subject_consistency"],
      "conditioning": { "first_frame": true, "last_frame": true, "reference_image": true, "subject": true },
      "note": "Reference/subject-driven — powers character consistency (S2V-style)."
    },
    {
      "id": "voice-miso-8b",
      "category": "voice",
      "display_name": "MisoTTS 8B (voice clone)",
      "capabilities": ["voice_clone"],
      "engine": "miso",
      "sample_rate": 24000,
      "needs_reference_audio": true
    },
    {
      "id": "voice-edge",
      "category": "voice",
      "display_name": "Edge TTS",
      "capabilities": [],
      "engine": "edge-tts",
      "cost": { "credits_per_second": 0 }
    }
  ],
  "voices": [
    { "id": "voice_clone_narr", "name": "Narrator (cloned)", "model_id": "voice-miso-8b", "language": "en", "cloned": true, "reference_audio_media_id": "med_voiceref" },
    { "id": "en-US-GuyNeural", "name": "Guy (Edge)", "model_id": "voice-edge", "language": "en", "cloned": false }
  ],
  "canGenerate": { "allowed": true, "plan": "pro", "credits_remaining": 184 }
}
```

### Behavior
- Static capability data is served from a server-side registry kept in sync with
  the GPU backend (`MODEL_T2V`/`MODEL_I2V`/`MODEL_VACE` repos); `voices` is
  per-owner (cloned voices + Edge presets).
- `capability` filtering is **AND** semantics: only models supporting *all*
  requested capabilities are returned — so "I need last-frame + subject" yields
  exactly VACE.
- `cost`/`speed` are advisory estimates (from benchmarks) to let the agent budget
  before hitting the `canGenerate` gate.

### Edge cases
- **`capability` combo no model satisfies** → `models: []`, `note` explains which
  capability has no provider.
- **`include_voices=false`** → omit `voices`.
- **No project_id** → returns the global catalog with default voices only (no
  cloned voices).

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Models are what *produce* scene clips and audio-track narration. The capability
matrix maps directly to scene generation state: `first_frame`/`last_frame` →
scene chaining (FLF2V) between ordered scenes; `subject`/`reference_image` →
character attachment; voice models → the narration audio track.

### How this beats Palmier
- **Generation-native truth.** Flow *owns* the models, so capabilities
  (first/last-frame, subject-consistency, reference) are authoritative, not a
  best-effort description of a proxied 3rd-party API. Palmier can only relay what
  an external provider advertises.
- **`capability` AND-filter** turns model selection into one query ("give me a
  model that does last-frame + subject") instead of the agent parsing a list.
- **First-class voice catalog** including the user's **cloned** voices
  (MisoTTS) with reference-audio provenance — Palmier has voices but no
  ownership/cloning model.
- **Cost/speed advisories + `canGenerate`** let the agent budget a multi-scene
  plan before any credit is spent.

---

## Group summary — how 01-context-read beats Palmier's read group

| Dimension | Palmier read group | Flow 01-context-read |
|--|--|--|
| Typing | Loose dicts, mixed frame/second fields | Full JSON-Schema: enums, ranges, `oneOf`, dual-unit (frames **and** seconds) everywhere |
| Seed call | `get_timeline` (clips/tracks) | `get_project` adds **characters + voices + per-scene generation state + revision** |
| Generation awareness | Proxies 3rd-party models | Native Wan2.2/VACE/voice capability truth; every asset carries `model_id`/prompt/voice provenance |
| Casting | No character concept | Characters surfaced in `get_project`, `list_models` voices, `search_media` references |
| Composite fidelity | Visual-only `inspect_timeline` | `inspect_timeline` composites through the **real ffmpeg graph** + audio state + live narration word |
| Transcript | Frame-only, per-call recompute | Per-word `scene_id` ownership, dual-unit, non-speech events, revision-cached |
| Token budget | Manual | Self-throttling (`summary` auto-downgrade, `truncated`, bounded `depth`/`top_k`/`max_frames`) |
| Safety | `canGenerate` gate | Same gate **reported** by every read tool; `system` folder guards; ownership-scoped IDs |

All nine tools are **read-only** (no undo, no credits) and exposed by the VPS MCP
server (loopback + auth, per Palmier's binding model), driven by the
nanocode-pattern agent loop calling the NVIDIA build API (default model `kimi`,
OpenAI-style tool-calling).
