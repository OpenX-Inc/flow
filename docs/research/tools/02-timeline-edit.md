# Flow Agentic Tools — Group 02: Timeline-Edit Tools

**Date:** 2026-06-24
**Scope:** The 11 timeline-mutation tools of Flow 0.3, re-imagined from Palmier's
edit-timeline group. These operate on **scenes-as-clips**: the ordered scene list
*is* the video track. They are exposed by the **VPS MCP server** and driven by the
in-app agent loop (nanocode pattern → NVIDIA build, default model `kimi`,
OpenAI-style tool-calling).

Tools covered: `add_clips`, `insert_clips`, `remove_clips`, `remove_tracks`,
`move_clips`, `set_clip_properties`, `set_keyframes`, `split_clip`,
`ripple_delete_ranges`, `sync_audio`, `undo`.

> Read first (every stage): `agentic-video-editing-analysis.md`,
> `agent-tool-loop-nanocode.md`, `palmier-video-tools-catalog.md`.

---

## 1. Flow's timeline model (what these tools mutate)

Flow does **not** rebuild a generic NLE. The existing `Scene` model already *is*
the timeline. We layer clip/track semantics onto it.

### 1.1 Tracks

| Track id | Kind | Backing data | Render role |
|----------|------|--------------|-------------|
| `video.main` | video | Ordered `Scene[]` (each scene = one clip) | ffmpeg concat → the single complete video track |
| `audio.narration` | audio | TTS output (edge-tts / MisoTTS) per scene + project-level | mixed over video |
| `audio.music` | audio | Imported/generated music bed | mixed under narration |
| `text.captions` | text | Caption/title items with frame ranges | burned via `subtitles=`/drawtext |

Today only `video.main` is first-class. The 0.3 model promotion (build step 1 in
the catalog) extends `Scene` with clip properties + keyframes and adds the
parallel `audio.*` / `text.captions` tracks with their own item lists. The
timeline-edit tools below are written against that promoted model.

### 1.2 Scene → Clip (the promoted `Scene`)

Current `Scene`: `id, duration(int s, default 5), visual_prompt, camera,
narration_segment, characters[]`. Promoted clip fields the edit tools read/write:

```jsonc
{
  "clip_id": "scn_0007",        // stable string id (was int Scene.id)
  "track_id": "video.main",
  "order_index": 6,              // 0-based position in track (the timeline order)
  "source_duration_frames": 120, // intrinsic length of generated media @ project fps
  "in_frame": 0,                 // trim head: first source frame used (inclusive)
  "out_frame": 120,              // trim tail: last source frame used (exclusive)
  "speed": 1.0,                  // playback rate multiplier
  "volume": 1.0,                 // 0..1 linear gain on the clip's embedded audio
  "opacity": 1.0,                // 0..1
  "transform": { "x":0,"y":0,"scale":1.0,"rotation":0,"anchor":"center" },
  "fade_in_frames": 0,
  "fade_out_frames": 0,
  "keyframes": [],               // see set_keyframes
  // generation provenance (Palmier parity + Flow extension):
  "visual_prompt": "...", "camera": "...", "narration_segment": "...",
  "characters": ["nova"], "model": "wan2.2-i2v", "first_frame": "...png",
  "last_frame": "...png", "reference_images": ["..."]
}
```

**Timeline (effective) duration of a clip**, in frames:

```
trimmed = out_frame - in_frame
effective_frames = ceil(trimmed / speed)
```

`speed` re-times the trimmed span: 2.0 halves it, 0.5 doubles it. The video
track's effective duration is the sum of all clips' `effective_frames`.

---

## 2. Frame math & units (precise, shared by every tool)

This is the contract every tool obeys. Palmier's tools take raw `frames`; Flow
takes **either** and is explicit about it.

### 2.1 Project frame rate

- The project carries `fps` (frames per second). Default **`fps = 24`** (Wan 2.2
  clips are generated at 24 fps in Flow; `clip_duration = 5 s` ⇒ 120 frames).
  Allowed enum: `[24, 25, 30, 60]`. `fps` is fixed for the project; tools never
  change it.
- All **frame** values are integers. All **second** values are numbers (floats
  allowed).

### 2.2 frame ↔ second conversion

```
frame  = round(seconds * fps)      # seconds → frames (round half up)
seconds = frame / fps              # frames → seconds (exact)
```

Rounding rule: **round-half-up** to the nearest integer frame. A duration given
in seconds that does not land on a frame boundary is snapped to the nearest
frame, and the tool reports the snapped value in its output (`snapped_from`).

### 2.3 The `TimeValue` union (units are never ambiguous)

Every time-typed input field accepts a tagged object so the model can speak in
whichever unit is natural, and the server resolves to frames deterministically:

```jsonc
// JSON Schema fragment reused everywhere below as $TimeValue
{
  "type": "object",
  "oneOf": [
    { "required": ["frame"],   "properties": { "frame":   { "type": "integer", "minimum": 0 } } },
    { "required": ["seconds"], "properties": { "seconds": { "type": "number",  "minimum": 0 } } }
  ],
  "additionalProperties": false,
  "examples": [ { "frame": 48 }, { "seconds": 2.0 } ]
}
```

- Exactly one of `frame` / `seconds` must be present.
- The server always resolves to a canonical **frame** internally and echoes both
  `frame` and `seconds` in outputs.

### 2.4 Frame coordinate conventions

- **Half-open intervals** `[start_frame, end_frame)`: start inclusive, end
  exclusive. A clip occupying frames 0..120 means frames 0–119 inclusive,
  `end_frame = 120`, length 120.
- **Timeline frame** = absolute position on a track, measured from track start
  (frame 0). **Source frame** = position inside a clip's source media
  (`in_frame`/`out_frame` live in source space).
- A timeline frame `T` falls in the clip whose
  `[timeline_start, timeline_start + effective_frames)` contains `T`. Mapping
  timeline→source inside that clip:
  `source = in_frame + round((T - timeline_start) * speed)`.

### 2.5 Position addressing on the video track

Because the video track is *contiguous* (scenes concatenate with no gaps), a clip
position can be addressed three ways; tools accept the union `$Position`:

```jsonc
{
  "oneOf": [
    { "required": ["order_index"], "properties": { "order_index": { "type":"integer","minimum":0 } } },
    { "required": ["before_clip_id"], "properties": { "before_clip_id": { "type":"string" } } },
    { "required": ["after_clip_id"],  "properties": { "after_clip_id":  { "type":"string" } } },
    { "required": ["at"], "properties": { "at": { "$ref":"#/$defs/TimeValue" } } }  // timeline time → split point
  ]
}
```

`order_index` and `before/after_clip_id` are gap-free integer positions; `at`
(a timeline `TimeValue`) is resolved to the boundary at or nearest the given
time. Audio/text tracks are time-addressed (`start`), since they may contain
gaps.

---

## 3. Shared envelope (all timeline-edit tools)

### 3.1 Common input fields

| Field | Type | Notes |
|-------|------|-------|
| `project_id` | string (req) | scope; ownership-checked by MCP server |
| `dry_run` | boolean (default false) | validate + return the would-be diff without mutating |
| `client_edit_id` | string (optional) | idempotency key; replaying returns the same `edit_id` |

### 3.2 Common output envelope

```jsonc
{
  "ok": true,
  "edit_id": "edt_01HF…",        // one undoable action; pass to undo
  "affected_clip_ids": ["scn_0007"],
  "timeline": {                   // post-edit summary (defaults omitted, token hygiene)
    "fps": 24,
    "video_duration_frames": 720,
    "video_duration_seconds": 30.0,
    "clip_count": 6
  },
  "diff": [                       // ordered, reversible operations applied
    { "op":"update_clip","clip_id":"scn_0007","before":{…},"after":{…} }
  ],
  "warnings": [],
  "snapped": [ { "field":"duration","from_seconds":2.03,"to_frame":49 } ]
}
```

On failure: `{ "ok": false, "error": { "code": "...", "message": "...", "hint": "..." } }`.
Error codes are stable strings (e.g. `CLIP_NOT_FOUND`, `OUT_OF_RANGE`,
`UNIT_AMBIGUOUS`, `CANNOT_GENERATE`, `LOCKED_TRACK`).

### 3.3 Undo model (shared)

Every mutating tool records **one** `edit_id` onto a per-project undo stack with
the inverse `diff` (the `before` states). `undo` pops and re-applies inverses.
This mirrors Palmier's "one undoable action" but is **persisted server-side and
keyed**, so it survives reconnects and is per-user/per-project scoped. Generation
side effects are reverted logically (clip removed/reverted) while generated media
is retained in the library and garbage-collected later — undo never blocks on a
GPU job.

### 3.4 `canGenerate` / credits gate (shared)

Pure timeline edits (reorder, trim, remove, properties, keyframes, split, ripple,
sync, undo) are **free** and always work for the project owner. Only tools that
*trigger generation* gate on credits. In this group, **only `add_clips`/
`insert_clips` with `source: {generate: …}`** can incur generation; they consult
`canGenerate` and fail fast with `CANNOT_GENERATE` + a clear sign-in/subscribe
hint (Palmier parity), placing a *placeholder* clip only if `allow_placeholder`
is true.

---

## 4. Tool: `add_clips`

- **Wire-name:** `add_clips`
- **Purpose:** Place one or more clips onto a track. On the video track this
  appends/positions scenes; the source can be existing library media **or a
  Flow generation request** (Wan 2.2 t2v/i2v, optionally character-conditioned).
- **When to call:** The agent wants to extend the video ("add a closing shot of
  the skyline"), drop a music bed onto `audio.music`, or stage new generated
  scenes. Use `insert_clips` instead when later clips must ripple to make room at
  an interior point (`add_clips` defaults to append/non-rippling placement).

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","clips"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "track_id":{"type":"string","default":"video.main",
      "enum":["video.main","audio.narration","audio.music","text.captions"]},
    "allow_placeholder":{"type":"boolean","default":true,
      "description":"If generation is gated/queued, insert a placeholder clip that the job later fills."},
    "clips":{
      "type":"array","minItems":1,"maxItems":50,
      "items":{
        "type":"object",
        "required":["source"],
        "properties":{
          "source":{
            "oneOf":[
              {"required":["media_id"],"properties":{"media_id":{"type":"string","description":"Existing library asset (from get_media)."}}},
              {"required":["generate"],"properties":{"generate":{
                "type":"object","required":["prompt"],
                "properties":{
                  "prompt":{"type":"string"},
                  "model":{"type":"string","enum":["wan2.2-t2v","wan2.2-i2v","wan2.2-vace","wan2.2-flf2v"],"default":"wan2.2-t2v"},
                  "characters":{"type":"array","items":{"type":"string"},"description":"Character names to cast (subject consistency)."},
                  "first_frame":{"type":"string","description":"media_id/url of opening keyframe (i2v/flf2v)."},
                  "last_frame":{"type":"string","description":"media_id/url of closing keyframe (flf2v)."},
                  "reference_images":{"type":"array","items":{"type":"string"}}
                }}}}
            ]
          },
          "position":{"$ref":"#/$defs/Position","description":"Where on the track. Default: append to end."},
          "duration":{"$ref":"#/$defs/TimeValue","description":"Target clip duration. Video default 5s/120f; ignored for media that has fixed length unless trims given."},
          "in_frame":{"type":"integer","minimum":0,"description":"Source trim head (frames). Default 0."},
          "out_frame":{"type":"integer","minimum":1,"description":"Source trim tail exclusive (frames). Default = source end."},
          "properties":{"$ref":"#/$defs/ClipProperties","description":"Initial speed/volume/opacity/transform/fades (see set_clip_properties)."}
        }
      }
    }
  }
}
```

### Output schema

Common envelope. `affected_clip_ids` lists newly created clips in track order.
For generation sources, each new clip carries `"generation": {"job_id":"…",
"status":"queued|generating|ready|failed"}`; placeholder clips report
`"placeholder": true` and a `poster` frame.

### Behavior

1. Resolve `track_id`; reject text/audio sources placed on `video.main` and vice
   versa (`TRACK_KIND_MISMATCH`).
2. For each item: resolve `position` → insertion index/time. On `video.main`,
   appended clips take the next `order_index`; multiple items keep their array
   order. **`add_clips` does not ripple** existing interior clips — if a
   `position` collides with an occupied interior slot on the video track, it
   appends after the target and emits a warning suggesting `insert_clips`.
3. Resolve `duration`/trims to frames (snap, report `snapped`).
4. `generate` sources: check `canGenerate`. If allowed, enqueue a Modal job and
   create a clip (placeholder if not yet ready). If gated, fail
   (`CANNOT_GENERATE`) unless `allow_placeholder` queued behavior applies.
5. Append inverse (remove-these-clips) to the undo stack as one `edit_id`.

### Edge cases

- Empty `clips` → `EMPTY_BATCH`. >50 → `BATCH_TOO_LARGE`.
- `out_frame <= in_frame` → `INVALID_TRIM`.
- `media_id` not found / still `generating` in library → `MEDIA_NOT_READY`
  (allowed as placeholder if `allow_placeholder`).
- Unknown character name → `CHARACTER_NOT_FOUND` (suggests `list_characters`).
- Audio/text item without `start` position → defaults to track start (0), may
  overlap; overlap on audio tracks is allowed (mixed), on `text.captions`
  overlapping items stack and a warning is emitted.

### Undo semantics

Inverse = delete the created clips (and cancel any still-queued generation jobs).
Library media generated by the (now-undone) job is **retained** for reuse.

### Maps onto Flow

`video.main` add = create a new `Scene` (append or positioned) with prompt/model/
characters; the generation path is literally Flow's `generator` + `characters`
pipeline. Audio add = attach a narration/music asset to the audio track. Text add
= a caption/title item (overlaps `add_texts`, but `add_clips` is the
asset-placement primitive).

### How this beats Palmier

Palmier's `add_clips` places **library** assets only; generation is a separate
async `generate_video`. Flow fuses them: a single `add_clips` can **generate a
character-cast scene in place** (Wan 2.2 + S2V/VACE), with first/last-frame
conditioning as typed fields. Richer schema (model enum, frame-vs-second
`duration`, explicit trims, character casting) and an explicit `allow_placeholder`
contract so the timeline stays coherent while GPU work is in flight.

---

## 5. Tool: `insert_clips`

- **Wire-name:** `insert_clips`
- **Purpose:** Insert clips at an interior point and **ripple** all later clips
  on the track to the right (push them later by the inserted effective duration).
- **When to call:** "Add a reaction shot between scene 3 and 4", "drop a 2s sting
  before the outro" — anywhere the rest of the video must shift to make room.
  Use `add_clips` when appending or when ripple is undesired.

### Input schema

Same item shape as `add_clips`, plus required interior anchor and ripple controls:

```jsonc
{
  "type":"object",
  "required":["project_id","clips","position"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "track_id":{"type":"string","default":"video.main","enum":["video.main","audio.narration","audio.music","text.captions"]},
    "position":{"$ref":"#/$defs/Position","description":"Insertion anchor (interior allowed)."},
    "ripple_scope":{"type":"string","enum":["track","all_tracks"],"default":"track",
      "description":"track = shift only this track's later items; all_tracks = also shift downstream audio/text items so sync is preserved."},
    "clips":{"$ref":"#/add_clips/properties/clips"}
  }
}
```

### Output schema

Common envelope; `diff` includes the inserted clips plus `shift` ops for every
rippled item: `{ "op":"shift","clip_id":"…","by_frames":120 }`. `timeline` shows
the new longer duration.

### Behavior

1. Resolve insertion index/time. Compute inserted total `effective_frames`.
2. Insert new clips; **increment `order_index`** of all later video clips (or
   add the frame delta to `start` of later audio/text items).
3. If `ripple_scope = all_tracks`, shift downstream items on `audio.*`/
   `text.captions` whose `start >= insertion_time` by the same frame delta so
   narration/captions stay aligned to their scenes.
4. One `edit_id`; inverse removes inserted clips and shifts everything back.

### Edge cases

- Insert at `order_index = 0` / `before_clip_id` of first clip → prepend.
- Insert at a `TimeValue` falling *inside* a clip → snaps to the nearest clip
  boundary (video track is clip-contiguous, no mid-clip insert without a split);
  emits `snapped` and a hint to use `split_clip` first for a true mid-clip insert.
- `ripple_scope=all_tracks` with locked downstream track → `LOCKED_TRACK`.

### Undo semantics

Inverse = remove inserted clips **and** reverse all recorded `shift` ops exactly
(stored deltas), restoring original order/positions across affected tracks.

### Maps onto Flow

Reordering/renumbering scenes is Flow's `reorder_scenes` mechanic; `insert_clips`
= create scene(s) at index `k` and renumber `k..n`. `all_tracks` ripple keeps
per-scene narration/captions glued to their scene — important because Flow's
captions derive from `narration_segment` time offsets.

### How this beats Palmier

Palmier ripples the single track it inserts on. Flow's `ripple_scope=all_tracks`
keeps **narration and captions synchronized** to the scene grid automatically
(Flow knows captions belong to scenes), and the insert can itself be a generated,
character-cast scene. Units are explicit and the shift deltas are stored for exact
undo rather than recomputed.

---

## 6. Tool: `remove_clips`

- **Wire-name:** `remove_clips`
- **Purpose:** Delete one or more clips from a track. Two gap policies: **lift**
  (leave a gap) or **ripple** (close the gap by pulling later clips left).
- **When to call:** "Delete scene 5", "remove that music clip". For deleting
  *time ranges that may span/cut clips*, use `ripple_delete_ranges`.

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","clip_ids"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "clip_ids":{"type":"array","minItems":1,"items":{"type":"string"}},
    "gap_policy":{"type":"string","enum":["ripple","lift"],"default":"ripple",
      "description":"ripple = close gap (default for video.main, which must stay contiguous); lift = leave a gap (audio/text only)."}
  }
}
```

### Output schema

Common envelope; `diff` has `remove_clip` ops (with full `before` for undo) plus
`shift` ops if `gap_policy=ripple`.

### Behavior

1. Validate all `clip_ids` exist and belong to `project_id` (atomic: if any
   missing, nothing is removed → `CLIP_NOT_FOUND`).
2. Remove them. On `video.main`, `lift` is rejected (`GAP_NOT_ALLOWED`) — the
   video track is contiguous; deletion always ripples. Renumber `order_index`.
3. On audio/text, honor `gap_policy`.
4. One `edit_id`.

### Edge cases

- Removing **all** video clips → allowed; results in empty timeline (warning).
- Duplicate ids in array → de-duplicated, warning.
- Removing a clip mid-generation → cancels its Modal job; warning.

### Undo semantics

Inverse re-inserts removed clips at their original `order_index`/`start` with all
properties/keyframes and reverses ripple shifts. Full `before` snapshots make this
lossless.

### Maps onto Flow

`video.main` removal = `delete_scene` + renumber, which is exactly today's scene
deletion semantics. Audio/text removal detaches an item from its track.

### How this beats Palmier

Palmier removes clips on a free-form track (gaps possible everywhere). Flow
encodes the **invariant that the video track is gap-free** (`lift` rejected on
`video.main`), preventing a class of "black gap" bugs, while still allowing gaps
on audio/text where they're legitimate. Atomic batch + lossless property/keyframe
restore on undo.

---

## 7. Tool: `remove_tracks`

- **Wire-name:** `remove_tracks`
- **Purpose:** Remove an entire auxiliary track (all its items) — e.g. drop the
  music bed or clear all captions in one action.
- **When to call:** "Remove the background music", "delete all captions",
  "strip narration".

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","track_ids"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "track_ids":{"type":"array","minItems":1,
      "items":{"type":"string","enum":["audio.narration","audio.music","text.captions"]}}
  }
}
```

### Output schema

Common envelope; `diff` is one `remove_track` op per track carrying the full item
list for undo.

### Behavior

1. `video.main` is **not removable** (`PROTECTED_TRACK`) — it is the video; an
   empty video has zero clips but the track persists.
2. Remove each named track and all its items in one `edit_id`.

### Edge cases

- Track already empty/absent → no-op for that track, warning.
- Removing `audio.narration` orphans caption timing derived from narration → a
  warning recommends regenerating captions.

### Undo semantics

Inverse recreates each track with its full item list (positions, properties,
keyframes) from the stored snapshot.

### Maps onto Flow

Audio/caption tracks are the parallel tracks ffmpeg mixes/burns at assembly;
removing one simply means that input is omitted from the final ffmpeg graph.

### How this beats Palmier

Palmier can delete any track. Flow **protects `video.main`** (the scene track can
never be destroyed out from under the project) and understands cross-track
consequences (removing narration affects caption timing), surfacing them as
actionable warnings. Whole-track snapshot/undo is lossless.

---

## 8. Tool: `move_clips`

- **Wire-name:** `move_clips`
- **Purpose:** Reorder clips on the video track (move a scene to a new position)
  and/or move an item to a different track/time. On `video.main` this is a pure
  **reorder** with automatic gap-close + renumber.
- **When to call:** "Move the intro to the end", "swap scenes 2 and 3", "put the
  logo sting first", "move that music clip to start at 0:10".

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","moves"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "moves":{
      "type":"array","minItems":1,
      "items":{
        "type":"object",
        "required":["clip_id"],
        "properties":{
          "clip_id":{"type":"string"},
          "to_track":{"type":"string","enum":["video.main","audio.narration","audio.music","text.captions"],
            "description":"Cross-track move. Must match clip kind. Omit to stay on current track."},
          "to_position":{"$ref":"#/$defs/Position","description":"Target slot (video) or time (audio/text). Required."}
        },
        "required":["clip_id","to_position"]
      }
    }
  }
}
```

### Output schema

Common envelope; `diff` carries `reorder` ops (`{clip_id, from_index, to_index}`)
for video and `move` ops (`{clip_id, from_track, to_track, from_start, to_start}`)
for audio/text, plus the cascading `shift`/renumber ops.

### Behavior

1. Moves are applied **in array order**, each against the state left by the prior
   move (deterministic). Positions refer to indices/times *after* prior moves.
2. **Video reorder:** remove clip from its slot, reinsert at `to_position`,
   renumber `order_index` to stay contiguous (gap-free). Cross-track moves onto
   `video.main` require a video-kind source.
3. **Audio/text move:** change `track_id`/`start`; overlaps allowed per track
   rules.
4. One `edit_id` for the whole batch.

### Edge cases

- `to_position` resolving to the clip's own current slot → no-op, warning.
- Cross-track kind mismatch (e.g. move audio onto `video.main`) →
  `TRACK_KIND_MISMATCH`.
- Two moves targeting the same index → resolved in array order; second lands
  after the first (documented, not an error).
- Moving a video clip "to a time" (`at`) snaps to the nearest scene boundary.

### Undo semantics

Inverse replays the recorded index/track/start transitions in reverse order,
restoring exact original ordering and positions.

### Maps onto Flow

Direct `reorder_scenes`: ordered scenes are the timeline, so moving a scene *is*
re-cutting the film. Cross-track moves cover relocating a music/caption item.

### How this beats Palmier

Palmier `move_clips` moves to a `(track, frame)` on a free track. Flow's video
reorder is **position-semantic** (`order_index` / `before/after_clip_id`), which
is how an autonomous agent actually thinks about scenes ("move scene 2 after
scene 5") — no frame arithmetic needed — while still accepting time addressing.
Batch moves are order-deterministic with exact-replay undo.

---

## 9. Tool: `set_clip_properties`

- **Wire-name:** `set_clip_properties`
- **Purpose:** Set static (non-animated) properties on one or more clips: speed,
  volume, opacity, transform (x/y/scale/rotation/anchor), trims
  (`in_frame`/`out_frame`), and fades.
- **When to call:** "Speed scene 3 up 2×", "mute scene 4", "zoom the logo to
  120%", "trim the first 12 frames of the opener", "fade the outro out over 1s".

### Input schema (`$ClipProperties` reused by add/insert)

```jsonc
{
  "type":"object",
  "required":["project_id","clip_ids","properties"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "clip_ids":{"type":"array","minItems":1,"items":{"type":"string"}},
    "merge":{"type":"boolean","default":true,
      "description":"true = only overwrite provided fields; false = reset omitted fields to defaults."},
    "properties":{
      "type":"object","minProperties":1,
      "properties":{
        "speed":{"type":"number","minimum":0.1,"maximum":10,"default":1.0,
          "description":"Playback rate. >1 faster/shorter, <1 slower/longer. Unit: multiplier. Re-times effective_frames."},
        "volume":{"type":"number","minimum":0,"maximum":1,"default":1.0,"description":"Linear gain on clip's embedded audio (0=mute)."},
        "opacity":{"type":"number","minimum":0,"maximum":1,"default":1.0},
        "transform":{
          "type":"object",
          "properties":{
            "x":{"type":"number","description":"Horizontal offset in pixels (+right). Default 0."},
            "y":{"type":"number","description":"Vertical offset in pixels (+down). Default 0."},
            "scale":{"type":"number","minimum":0.01,"maximum":10,"default":1.0,"description":"Uniform scale multiplier."},
            "rotation":{"type":"number","minimum":-360,"maximum":360,"description":"Degrees clockwise. Default 0."},
            "anchor":{"type":"string","enum":["center","top_left","top_right","bottom_left","bottom_right"],"default":"center"}
          }
        },
        "in_frame":{"type":"integer","minimum":0,"description":"Source trim head (frames, inclusive)."},
        "out_frame":{"type":"integer","minimum":1,"description":"Source trim tail (frames, exclusive)."},
        "fade_in":{"$ref":"#/$defs/TimeValue","description":"Fade-in duration (video opacity + audio gain ramp)."},
        "fade_out":{"$ref":"#/$defs/TimeValue","description":"Fade-out duration."}
      },
      "additionalProperties":false
    }
  }
}
```

### Output schema

Common envelope; `diff` has one `update_clip` op per clip with `before`/`after`
property maps. `timeline` reflects any duration change caused by `speed`/trims.

### Behavior

1. Apply `properties` to each clip in `clip_ids`. With `merge=true` only provided
   keys change; `merge=false` resets the clip to defaults then applies (defaults
   omitted from storage for token hygiene).
2. `speed`/`in_frame`/`out_frame` change `effective_frames`; on `video.main` this
   re-times the scene and **ripples later scenes** to stay contiguous (shift ops
   recorded). Trims are clamped to `[0, source_duration_frames]`.
3. Fades convert to frames (snap, report). One `edit_id`.

### Edge cases

- `out_frame <= in_frame` → `INVALID_TRIM`. `out_frame > source_duration_frames`
  → clamp + warning.
- `fade_in + fade_out > effective_frames` → fades clamped to split the clip
  50/50, warning.
- `speed` on a clip with no audio: volume ignored silently.
- Conflicting keyframed property (see `set_keyframes`): a static set on a property
  that has keyframes → `PROPERTY_ANIMATED` (must clear keyframes first), unless
  the static value is interpreted as a global offset (documented: rejected by
  default).

### Undo semantics

Inverse restores the `before` property map per clip and reverses any ripple
shifts caused by speed/trim duration changes.

### Maps onto Flow

These map to ffmpeg assembly parameters: `speed`→`setpts`/`atempo`, `volume`→
`volume`, `opacity`/`transform`→`overlay`/`scale`/`rotate`, trims→input seek
(`-ss`/`-to` in source frames), fades→`fade`/`afade`. They become per-scene
render directives the assembler reads.

### How this beats Palmier

Palmier sets these on a generic clip. Flow ties **speed/trim to the contiguous
scene invariant** (auto-ripple keeps the film gap-free, with exact-undo), uses
**typed ranges/units** (speed 0.1–10×, opacity 0–1, fades as frame-or-second
`TimeValue`), and a `merge` flag for predictable partial updates. Properties are
declared once as `$ClipProperties` and reused by `add/insert_clips`.

---

## 10. Tool: `set_keyframes`

- **Wire-name:** `set_keyframes`
- **Purpose:** Animate **one** property of **one** clip over time by setting
  keyframes (value at a timeline-relative frame, with an interpolation/easing).
- **When to call:** "Slowly zoom scene 2 from 100% to 120%" (Ken Burns), "pan the
  logo left to right", "ramp volume down across the outro", "fade opacity in".

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","clip_id","property","keyframes"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "clip_id":{"type":"string"},
    "property":{"type":"string",
      "enum":["opacity","volume","speed","transform.x","transform.y","transform.scale","transform.rotation"],
      "description":"Exactly one animatable channel. Dotted paths address transform sub-fields."},
    "replace":{"type":"boolean","default":true,
      "description":"true = replace this property's keyframe track; false = merge new keys into existing."},
    "keyframes":{
      "type":"array","minItems":1,"maxItems":200,
      "items":{
        "type":"object",
        "required":["time","value"],
        "properties":{
          "time":{"$ref":"#/$defs/TimeValue","description":"Clip-relative time (0 = clip start). Resolved to a frame; must be within the clip's effective span."},
          "value":{"type":"number","description":"Target value for the property at this time. Range = the property's static range."},
          "easing":{"type":"string","enum":["linear","ease_in","ease_out","ease_in_out","hold","bezier"],"default":"linear",
            "description":"Interpolation from THIS key to the next."},
          "bezier":{"type":"array","items":{"type":"number"},"minItems":4,"maxItems":4,
            "description":"[x1,y1,x2,y2] control points; required iff easing=bezier."}
        }
      }
    }
  }
}
```

### Output schema

Common envelope; `diff` is one `set_keyframes` op `{clip_id, property,
before_track, after_track}`. Echoes each key's resolved `frame` (clip-relative)
and the implied absolute timeline frame.

### Behavior

1. Validate `clip_id` and that `property` is animatable. Resolve each `time` to a
   clip-relative frame; **sort by frame**; reject duplicate frames
   (`DUPLICATE_KEYFRAME`).
2. Clamp/validate each `value` against the property's range (e.g. opacity 0–1).
3. `replace=true` swaps the whole track for `property`; `replace=false` merges
   (new keys overwrite same-frame keys). A single keyframe = a constant
   (equivalent to a static set from that time on).
4. Keyframed properties take precedence over the static value; `set_clip_properties`
   on the same property is rejected until keyframes are cleared (set empty track).
5. One `edit_id`.

### Edge cases

- `time` outside `[0, effective_frames)` → `OUT_OF_RANGE` (hint: split or extend
  clip). Keys are clip-relative so they survive ripple/reorder.
- `easing=bezier` without `bezier` array → `MISSING_BEZIER`.
- Animating `speed` changes `effective_frames` non-trivially (variable retime):
  allowed but emits a warning that downstream ripple uses the *integral* of the
  speed curve to compute duration.
- Empty `keyframes` with `replace=true` → clears animation (valid way to
  de-animate).

### Undo semantics

Inverse restores the property's prior keyframe track (`before_track`), including
the "no keyframes" state.

### Maps onto Flow

Compiles to ffmpeg time-varying expressions at assembly: `scale`/`overlay`/
`rotate`/`fade` driven by `if/lerp` on `t` (or `sendcmd`/`zoompan` for Ken
Burns), `volume`/`afade` for audio. Keyframes are stored on the scene's `keyframes`
list (promoted model) and read by the assembler.

### How this beats Palmier

Palmier animates one property per call too, but Flow adds **typed easing enum +
bezier control points**, **clip-relative time** (animations survive scene
reorders/ripples — Palmier's absolute frames break when clips move), per-property
range validation, and a clean `replace`/de-animate contract. It integrates with
Flow's render compiler rather than a Metal/CoreImage graph.

---

## 11. Tool: `split_clip`

- **Wire-name:** `split_clip`
- **Purpose:** Split one clip into two at a given time, producing two contiguous
  clips that share the source (left = `in_frame..cut`, right = `cut..out_frame`).
- **When to call:** "Split scene 3 at 2 seconds so I can speed up only the second
  half", "cut this scene where the action changes so I can insert a beat between".

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","clip_id","at"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "clip_id":{"type":"string"},
    "at":{"$ref":"#/$defs/TimeValue","description":"Clip-relative split point (0<at<effective_frames). Resolved to a frame on the boundary BEFORE which the right clip begins."},
    "carry_keyframes":{"type":"boolean","default":true,
      "description":"true = split the keyframe tracks at the cut (re-baselined to each new clip's start); false = drop keyframes on both halves."}
  }
}
```

### Output schema

Common envelope; `affected_clip_ids = [left_id, right_id]` (left keeps the
original `clip_id`; right gets a new id). `diff` = one `split_clip` op storing the
original clip for undo.

### Behavior

1. Resolve `at` to a clip-relative frame `c` (snap; report). Require `0 < c <
   effective_frames` else `INVALID_SPLIT`.
2. Map `c` through `speed`/trims to a **source frame** `s = in_frame +
   round(c * speed)`. Left clip = `[in_frame, s)`, right = `[s, out_frame)`,
   both inherit `speed`/`volume`/`opacity`/`transform`/`model`/prompt provenance.
3. Insert right clip immediately after left; **renumber** following video clips
   (no total-duration change → no ripple of later clips, only re-index).
4. `carry_keyframes`: partition keys by `c`; re-baseline right-clip key times to
   `time - c`; interpolate a boundary key at `c` for both halves so values are
   continuous.
5. One `edit_id`.

### Edge cases

- `at` at 0 or `effective_frames` → `INVALID_SPLIT` (no-op split).
- Splitting a placeholder/still-generating clip → allowed; both halves reference
  the same pending job and fill together.
- Audio/text item split: splits the item's time span; captions split text at the
  nearest word boundary (warning if mid-word).

### Undo semantics

Inverse merges the two halves back into the original single clip (restores
`in/out_frame`, original id, and the un-split keyframe track) from the stored
snapshot.

### Maps onto Flow

A scene becomes two scenes covering the same generated media via different source
trims — both render from the same clip file with different `-ss/-to`. Enables
"regenerate only the second half" or "insert between halves" workflows.

### How this beats Palmier

Palmier splits at an absolute frame. Flow splits at a **clip-relative `TimeValue`**
(unit-explicit), correctly maps the cut through `speed`/trims to source frames,
and **intelligently partitions keyframes with a continuity boundary key** so
animations don't jump at the cut. Word-aware caption splitting is Flow-specific.

---

## 12. Tool: `ripple_delete_ranges`

- **Wire-name:** `ripple_delete_ranges`
- **Purpose:** Delete one or more **timeline time ranges** (which may span clip
  boundaries and cut through clips) and **close the gaps** by pulling later
  content left. The fast path for filler-word / dead-air / "cut 0:10–0:14"
  removal.
- **When to call:** Transcript-driven trims ("remove every 'um'"), removing dead
  air, "cut the boring middle from 0:30 to 0:45". Combine with `get_transcript`
  output (word frame ranges) for speech edits.

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","ranges"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "ranges":{
      "type":"array","minItems":1,"maxItems":500,
      "items":{
        "type":"object",
        "required":["start","end"],
        "properties":{
          "start":{"$ref":"#/$defs/TimeValue","description":"Timeline range start (inclusive)."},
          "end":{"$ref":"#/$defs/TimeValue","description":"Timeline range end (exclusive). Must be > start."}
        }
      }
    },
    "ripple_scope":{"type":"string","enum":["video_only","all_tracks"],"default":"all_tracks",
      "description":"all_tracks = also delete the same time spans from audio/captions and pull them left (keeps sync). video_only = cut video, leave audio (then re-sync manually)."},
    "min_gap_frames":{"type":"integer","minimum":0,"default":0,
      "description":"Merge ranges separated by <= this many frames into one cut (cleans up tight filler-word lists)."}
  }
}
```

### Output schema

Common envelope; `diff` lists the resulting clip splits/removals/trims and
`shift` ops. Output includes `removed_frames_total` and the new
`video_duration_frames`.

### Behavior

1. Resolve every range to timeline `[start,end)` frames; **normalize**: sort,
   merge overlapping or `<= min_gap_frames`-apart ranges (descending order for
   safe in-place edits).
2. For each merged range: clips fully inside are removed; clips partially covered
   are **trimmed** (adjust `in_frame`/`out_frame`); a range interior to one clip
   splits it and drops the middle.
3. Close gaps: later clips shift left by the removed length; `order_index`
   renumbered to stay contiguous.
4. `all_tracks`: apply the same time-range deletion + left-shift to
   `audio.*`/`text.captions`, so narration and captions stay aligned.
5. One `edit_id` (a single undoable action for the whole multi-range cut).

### Edge cases

- `end <= start` in any range → `INVALID_RANGE`.
- Ranges beyond timeline end → clamped, warning.
- Deleting an entire clip's span = same as `remove_clips` ripple for that clip.
- Cutting through a clip with keyframes → keyframes after the cut re-baseline to
  the new (shorter) timeline; boundary keys interpolated (as in `split_clip`).
- `video_only` leaves audio longer than video → warning + hint to `sync_audio`.

### Undo semantics

Inverse restores every trimmed/removed/split clip from stored `before`
snapshots and reverses all shifts — the whole cut reverts in one `undo`.

### Maps onto Flow

This is the transcript-edit superpower over the scene grid: a single tool turns
"word frame ranges from `get_transcript`" into scene trims + ripple. Renders as
per-scene `-ss/-to` source trims plus dropped scenes, concatenated gap-free.

### How this beats Palmier

Same fast-path intent, but Flow adds **`min_gap_frames` merging** (turns a noisy
filler-word list into clean cuts), **`all_tracks` sync-preserving ripple** (Flow
knows captions/narration belong to the scene grid), unit-explicit ranges, and a
500-range batch as **one undoable action** — ideal for an agent applying a whole
transcript cleanup in a single call.

---

## 13. Tool: `sync_audio`

- **Wire-name:** `sync_audio`
- **Purpose:** Align clips/tracks in time against a reference by audio
  cross-correlation (find the offset that best matches waveforms), then shift the
  target so they line up. Also used to re-align narration to video after edits.
- **When to call:** "Sync the music to the beat of the action", "the narration
  drifted after I trimmed — re-align it", multi-take alignment, or aligning an
  imported audio bed to the cut.

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id","reference","targets"],
  "properties":{
    "project_id":{"type":"string"},
    "dry_run":{"type":"boolean","default":false},
    "client_edit_id":{"type":"string"},
    "reference":{
      "type":"object",
      "description":"What to align against.",
      "oneOf":[
        {"required":["clip_id"],"properties":{"clip_id":{"type":"string"}}},
        {"required":["track_id"],"properties":{"track_id":{"type":"string","enum":["video.main","audio.narration","audio.music"]}}}
      ]
    },
    "targets":{"type":"array","minItems":1,"items":{"type":"string","description":"clip_ids to shift into alignment."}},
    "max_offset":{"$ref":"#/$defs/TimeValue","description":"Max shift to search in either direction. Default 5s."},
    "mode":{"type":"string","enum":["shift","shift_and_ripple"],"default":"shift",
      "description":"shift = move target only (may overlap, ok on audio); shift_and_ripple = also ripple to absorb the shift on contiguous tracks."},
    "min_confidence":{"type":"number","minimum":0,"maximum":1,"default":0.6,
      "description":"Reject alignment if cross-correlation peak confidence is below this."}
  }
}
```

### Output schema

Common envelope plus per-target results: `[{ "clip_id":"…",
"offset_frames": -7, "offset_seconds": -0.29, "confidence": 0.82, "applied": true }]`.
Low-confidence targets report `applied:false` with reason `LOW_CONFIDENCE`.

### Behavior

1. Decode reference + each target audio to mono PCM; compute normalized
   cross-correlation within `±max_offset`; pick the peak offset and confidence.
2. If `confidence >= min_confidence`, shift the target by `offset_frames`
   (snap to frame). `shift` moves only the target; `shift_and_ripple` adjusts the
   contiguous track to absorb it.
3. Targets below `min_confidence` are skipped (reported, not applied).
4. One `edit_id` for all applied shifts.

### Edge cases

- Reference or target has no audio → `NO_AUDIO` for that pair, skipped.
- Best offset hits `±max_offset` boundary → warning (true offset may exceed
  search window; suggest larger `max_offset`).
- All targets below confidence → `ok:true` but `affected_clip_ids:[]` + warning.

### Undo semantics

Inverse reverses each applied shift by its recorded `offset_frames` (and any
ripple).

### Maps onto Flow

Most common Flow use: after `ripple_delete_ranges`/speed changes, re-align the
`audio.narration` track to `video.main` so TTS lines up with the scenes again.
The offset is applied as an audio start delay/trim in the ffmpeg mix.

### How this beats Palmier

Palmier syncs by cross-correlation. Flow exposes a **typed confidence gate
(`min_confidence`)** so the agent won't blindly apply a bad alignment, returns
**per-target offset + confidence** for the model to reason about, supports
**track-level references** (align a whole track, not just clip-to-clip), and
integrates with the narration/scene model so "re-sync narration after a cut" is a
first-class flow.

---

## 14. Tool: `undo`

- **Wire-name:** `undo`
- **Purpose:** Revert the most recent timeline edit(s) made in this project,
  using the persisted, keyed undo stack.
- **When to call:** "Undo that", "revert the last two changes", "that reorder was
  wrong, take it back".

### Input schema

```jsonc
{
  "type":"object",
  "required":["project_id"],
  "properties":{
    "project_id":{"type":"string"},
    "steps":{"type":"integer","minimum":1,"maximum":50,"default":1,
      "description":"How many edits to revert (LIFO)."},
    "edit_id":{"type":"string",
      "description":"Optional: revert back THROUGH this specific edit_id (must be on the stack). Mutually exclusive with steps."},
    "dry_run":{"type":"boolean","default":false}
  }
}
```

### Output schema

Common envelope; `reverted_edit_ids` lists the edits undone (newest first) and
`timeline` shows the restored state. A `redo_token` is returned so the agent can
offer to redo.

### Behavior

1. Pop `steps` edits (or pop until and including `edit_id`) off the project's
   undo stack and apply their stored inverse `diff`s in LIFO order.
2. Reverted edits move to a redo stack (cleared by the next forward edit).
3. Pure-timeline edits revert immediately. For undone edits that had triggered
   generation, the clip is removed/reverted; in-flight Modal jobs are cancelled;
   already-generated media stays in the library.
4. `undo` itself is **not** pushed as a new undoable edit (it manipulates the
   stacks), but it is recorded in the audit log.

### Edge cases

- Empty stack → `ok:true`, `reverted_edit_ids:[]`, warning `NOTHING_TO_UNDO`.
- `steps` > stack depth → revert all available, warning.
- `edit_id` not on stack → `EDIT_NOT_FOUND`.
- Both `steps` and `edit_id` provided → `AMBIGUOUS_UNDO`.

### Undo semantics

`undo` is the reversal primitive itself; its own inverse is **redo** (via
`redo_token`).

### Maps onto Flow

Each tool's recorded inverse `diff` (scene re-create / reorder restore / property
restore / shift reversal) is replayed against the scene store. Because the stack
is persisted per project/user, undo works across sessions and reconnects.

### How this beats Palmier

Palmier's `undo` reverts the assistant's most recent edit (single, in-memory).
Flow's undo is **multi-step**, **target an `edit_id`**, **persisted &
per-project/user scoped** (survives reconnects, safe under concurrent users),
**redo-capable**, and correctly handles **generation side effects** (cancel
in-flight jobs, keep media) — none of which a single in-memory undo offers.

---

## 15. Appendix — shared `$defs` (JSON Schema)

These are referenced (`$ref`) by every tool above and registered once on the MCP
server so kimi sees consistent types.

```jsonc
{
  "$defs": {
    "TimeValue": {
      "type":"object",
      "oneOf":[
        {"required":["frame"],  "properties":{"frame":  {"type":"integer","minimum":0}}},
        {"required":["seconds"],"properties":{"seconds":{"type":"number","minimum":0}}}
      ],
      "additionalProperties":false,
      "examples":[{"frame":48},{"seconds":2.0}]
    },
    "Position": {
      "oneOf":[
        {"required":["order_index"],   "properties":{"order_index":{"type":"integer","minimum":0}}},
        {"required":["before_clip_id"],"properties":{"before_clip_id":{"type":"string"}}},
        {"required":["after_clip_id"], "properties":{"after_clip_id": {"type":"string"}}},
        {"required":["at"],            "properties":{"at":{"$ref":"#/$defs/TimeValue"}}}
      ]
    },
    "ClipProperties": { "$comment":"see set_clip_properties §9 .properties" }
  }
}
```

### Frame-math reference card (for implementers)

```
fps default 24; enum [24,25,30,60]; fixed per project.
frame  = round(seconds * fps)            # round-half-up; report snapped_from
seconds = frame / fps                     # exact
Intervals half-open: [start, end)  → length = end - start.
Clip effective length: effective_frames = ceil((out_frame - in_frame)/speed).
Timeline→source inside clip: src = in_frame + round((T - timeline_start)*speed).
Video track is gap-free & contiguous: deletes/speed/trims always ripple+renumber.
Audio/text tracks are time-addressed and may contain gaps/overlaps.
Keyframe times are CLIP-RELATIVE (survive reorder/ripple).
```

### Tool → Flow scene/track mapping (summary)

| Tool | Video track (scenes) | Audio/Text tracks | One undoable action |
|------|----------------------|-------------------|---------------------|
| `add_clips` | create scene (opt. generate) | attach audio/caption item | yes |
| `insert_clips` | create scene at k + renumber + ripple | shift downstream (all_tracks) | yes |
| `remove_clips` | delete scene + ripple/renumber | detach item (gap ok) | yes |
| `remove_tracks` | n/a (video.main protected) | drop whole aux track | yes |
| `move_clips` | reorder scenes (gap-free) | move item track/time | yes |
| `set_clip_properties` | per-scene render directives + retime ripple | per-item gain/etc. | yes |
| `set_keyframes` | animate one scene channel | animate audio gain | yes |
| `split_clip` | scene → two scenes (shared source) | split item span | yes |
| `ripple_delete_ranges` | trim/drop scenes + close gaps | sync-preserving cut | yes |
| `sync_audio` | reference for alignment | shift narration/music | yes |
| `undo` | replay inverse diffs | replay inverse diffs | n/a (redo-able) |
