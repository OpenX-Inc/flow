# Palmier's Video-Editing Tools → Flow's Agent Tool Set

**Date:** 2026-06-24
**Why this doc:** nanocode's tools are *coding* ops (read/write/edit/bash). The
**video** tool vocabulary comes from Palmier (`Agent/Tools/ToolDefinitions.swift`,
35 tools). This catalogs them and maps to Flow's **scene-based** model.

---

## The 35 tools in the Palmier repo (canonical wire-names, grouped)

### Read / inspect (give the agent project context)
- `get_timeline` — "Always call at the start of a session." Returns project
  settings (fps, resolution, totalFrames), track list, all clips with frames +
  properties, and `canGenerate`. The clipId/trackId values here are what every
  other tool accepts.
- `get_media` — list library assets; every mediaRef other tools use comes from
  here. Exposes `generationStatus` (generating|downloading|failed|none).
- `inspect_media` — actually *look at* an asset before editing: image+EXIF,
  video sample frames + audio transcription, audio transcription, Lottie frames.
  Supports `overview` storyboard + windowed `startSeconds/endSeconds` zoom.
- `inspect_timeline` — composited view: what the user actually sees at a given
  frame (tracks stacked with transforms/opacity/crop).
- `get_transcript` — spoken transcript of the **current timeline** in project
  frames (post-edit), word-level `[text,startFrame,endFrame]`. Powers
  transcript-driven edits (filler/dead-air removal, quote finding).
- `search_media` — search library by content: on-screen (visual) + spoken.
- `inspect_color` — measure color scopes (black/white points, clipping, means).
- `list_folders`, `list_models` — library folders; AI models + capabilities
  (durations, aspect ratios, resolutions, first/last-frame & reference support,
  voices).

### Edit the timeline
- `add_clips` — place assets on the timeline (one undoable action).
- `insert_clips` — insert at a point and **ripple** (push later clips right).
- `remove_clips`, `remove_tracks` — delete clips / whole tracks.
- `move_clips` — move clips to a new track and/or frame.
- `set_clip_properties` — set speed, volume, opacity, transform, trims, fades…
- `set_keyframes` — animate one property of one clip.
- `split_clip` — split a clip at a frame.
- `ripple_delete_ranges` — cut ranges and close gaps (fast path for
  filler-word / dead-air removal).
- `sync_audio` — align clips to a reference by audio cross-correlation.
- `undo` — revert the assistant's most recent timeline edit.

### Text
- `add_texts` — titles / captions / lower-thirds.
- `add_captions` — auto-caption spoken audio (on-device transcribe → styled
  caption clips on a new track).

### Generate (the paid pipeline)
- `generate_video` — async AI video generation.
- `generate_image` — async AI image generation.
- `generate_audio` — async TTS / text-to-music / video-to-music.
- `upscale_media` — AI upscale an existing video/image.
- `import_media` — bring in external assets (the bridge for other MCP servers:
  stock, music, web search).

### Color / effects
- `apply_color` — author/refine a color grade (the colorist path).
- `apply_effect` — looks / FX.

### Media management
- `create_folder`, `move_to_folder`, `rename_media`, `rename_folder`,
  `delete_media`, `delete_folder`.

### Design notes worth copying
- **`get_timeline` first, always** — one call seeds the agent with full project
  context and the IDs every other tool needs. (We do the same with a
  `get_project` that returns scenes + characters.)
- **Defaults omitted** from payloads to keep context small (speed 1, opacity 1,
  identity transform… not serialized). Good token hygiene for our scene payloads.
- **Everything is "one undoable action"** + an `undo` tool. We want the same:
  scene edits should be reversible.
- **`canGenerate` gate** — read-only tools always work; generation tools fail
  with a clear "sign in / subscribe" message. Mirror with our plan/credits gate.

---

## Flow's tool set — ALL 35 (0.3 scope, "beat Palmier")

Decision: Flow's agentic editor ships the **full** tool surface — every Palmier
tool, re-implemented richer, plus Flow-specific casting tools. This is the **0.3**
release (0.2.0 is tagged; these `feat:` commits bump the minor to 0.3.0).

### Foundation: scenes ARE the timeline (no NLE rebuild)
Key realization: Flow's scene model is **not** a constraint to escape — the
ordered scenes already *are* the video track. After ffmpeg assembly they
concatenate into one complete track. So we don't build a generic from-scratch
NLE; we layer timeline semantics onto what we have:
- **Video track = ordered scenes.** Each scene is a clip carrying frame/duration,
  trims, speed, opacity, transform, and keyframes.
- **Audio track(s) = narration / music** (edge-tts / MisoTTS / imported).
- **Text track = captions / titles.**
- **Render = ffmpeg** composes the tracks → the final video (the "complete
  track" the scenes assemble into).

So timeline tools operate on scenes-as-clips: `move_clips`→reorder scenes,
`split_clip`→split a scene, `ripple_delete_ranges`→cut a time range across
scenes, `set_clip_properties`/`set_keyframes`→per-scene props/animation,
`add_clips`/`insert_clips`→add scene/media at a position. Build order:
1. **Extend the scene/timeline model** (scenes gain clip props + keyframes; add
   audio + caption tracks) + migrations. No generic NLE engine needed.
2. **VPS MCP server** exposing all tools (loopback + auth, à la Palmier).
3. **Agent loop** (nanocode pattern) → NVIDIA build, default `kimi`.
4. **Per-tool deep specs** (below) → implementations, each richer than Palmier's.

### "Stand out" bar (how each tool beats Palmier's)
- **Richer types:** full JSON-Schema with enums, ranges, units (frames vs
  seconds), and examples — not loose dicts.
- **Generation-native:** Flow tools know about Wan2.2/VACE + characters + voice
  cloning (Palmier proxies 3rd-party models; we own the pipeline).
- **Casting/consistency:** first-class `attach_character` / subject-consistency
  (S2V, reference frames) — Palmier has no character concept.
- **Autonomy:** a `plan_video`/orchestrator tool (script→scenes) — Palmier is
  assist-only; Flow is autonomous-first.
- Keep Palmier's good habits: `get_project` first, defaults omitted, every edit
  undoable, `canGenerate`/credits gate.

### The full 35 (mapped, all in scope)
Read/context: `get_project`(was get_timeline), `get_media`, `inspect_media`,
`inspect_timeline`, `get_transcript`, `search_media`, `inspect_color`,
`list_folders`, `list_models`
Timeline edit: `add_clips`, `insert_clips`, `remove_clips`, `remove_tracks`,
`move_clips`, `set_clip_properties`, `set_keyframes`, `split_clip`,
`ripple_delete_ranges`, `sync_audio`, `undo`
Text: `add_texts`, `add_captions`
Generate: `generate_video`, `generate_image`, `generate_audio`, `upscale_media`,
`import_media`
Color/FX: `apply_color`, `apply_effect`
Media mgmt: `create_folder`, `move_to_folder`, `rename_media`, `rename_folder`,
`delete_media`, `delete_folder`
Flow-specific (beyond Palmier): `list_characters`, `attach_character_to_scene`,
`plan_video` (orchestrator), `set_narration`/voice-clone

Per-group deep specs live in `docs/research/tools/` (one doc per group), each
with full schemas, behaviors, edge cases, and the Flow-vs-Palmier upgrade.

These tools are exposed by the **VPS MCP server**; the agent loop (kimi via
NVIDIA build) drives them with full project + character context.
