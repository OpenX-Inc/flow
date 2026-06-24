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

## Flow's tool set (scene-based subset — what we actually build)

Flow's primitive is the **scene** (not multi-track clips), so we take the
*read-context + generate + arrange + cast* subset and drop NLE-only tools
(keyframes, color scopes, ripple, tracks).

| Flow tool | Mirrors Palmier | Notes |
|--|--|--|
| `get_project` | `get_timeline` | returns scenes (id, order, prompt, duration, status, video_url) + project meta + **characters**; call first |
| `list_scenes` | (subset of get_timeline) | scenes only |
| `inspect_scene` | `inspect_media` | sample frames + (later) transcript of one scene |
| `list_characters` | — (Flow-specific) | the user's reusable cast |
| `list_models` | `list_models` | generation models (Wan2.2/VACE) + their caps |
| `create_scene` | `add_clips` | add a scene (prompt, duration) |
| `update_scene` | `set_clip_properties` | prompt / duration / narration |
| `regenerate_scene` | `generate_video` (re-roll) | re-run with prompt/model/refs in place |
| `reorder_scenes` | `move_clips` | change scene order |
| `delete_scene` | `remove_clips` | remove a scene |
| `attach_character_to_scene` | — (Flow-specific) | subject consistency (S2V/refs) |
| `set_narration` / `add_captions` | `generate_audio` / `add_captions` | TTS narration + captions |
| `start_generation` | `generate_video` (batch) | generate all pending scenes |
| `undo` | `undo` | reversible scene edits |

**Explicitly NOT building (NLE-only, out of scope for v1):** `set_keyframes`,
`apply_color`/`inspect_color`, `split_clip`, `ripple_delete_ranges`,
`sync_audio`, `remove_tracks`, multi-track `move_clips`, folder management.

These are the tools the **VPS MCP server** exposes; the agent loop (kimi via
NVIDIA build) calls them with full project + character context.
