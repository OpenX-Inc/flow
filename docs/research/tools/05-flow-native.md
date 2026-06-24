# Flow-Native Agent Tools — Beyond Palmier (Group 05)

**Date:** 2026-06-24
**Scope:** OpenX Flow 0.3 agentic editing surface — the **differentiator** tools
that have **no Palmier equivalent**. Palmier Pro is *assist-only* and has no
concept of a reusable cast, an autonomous planner, owned voice cloning, or a
one-shot "generate everything pending" action. These five tools are where Flow
stops being "Palmier on Linux" and becomes an **autonomous, generation-native,
character-aware** video agent.

Read first (every stage):
- `docs/research/agentic-video-editing-analysis.md` (Palmier teardown + Flow arch)
- `docs/research/agent-tool-loop-nanocode.md` (the model↔tool loop we run)
- `docs/research/palmier-video-tools-catalog.md` (the 35-tool reference menu)

This doc covers:

| Wire-name | One-liner | Palmier has it? |
|--|--|--|
| `list_characters` | Read the reusable cast (cross-project) + consistency status | ❌ no character concept |
| `attach_character_to_scene` | Cast a character into a scene (S2V/reference conditioning) | ❌ |
| `plan_video` | Autonomous orchestrator: topic/script → scenes + shot list | ❌ assist-only |
| `set_narration` | Author/replace narration on the audio track (+ voice select) | partial (`generate_audio` only) |
| `clone_voice` | Register a cloned voice from a sample (project/character-scoped) | ❌ |
| `start_generation` | Batch-generate **all pending** scenes in one undoable job | ❌ (per-clip only) |

---

## 0. Shared conventions (apply to every tool below)

These mirror Palmier's good habits and the "stand-out bar" from the catalog, and
are assumed by every schema in this doc rather than repeated each time.

### 0.1 Units — frames vs seconds (explicit, always)
Flow's primitive is the **scene measured in seconds** (`Scene.duration`, default
`5`). The timeline track, however, is rendered at a fixed project `fps`. To kill
the frames-vs-seconds ambiguity that loose APIs suffer from:

- Every duration/offset field is **suffixed with its unit** in the schema name:
  `*_seconds` (float) or `*_frames` (integer).
- Tools accept **either** unit where sensible and echo back **both** in outputs
  (`{ "seconds": 5.0, "frames": 120 }` at `fps: 24`).
- `frame = round(seconds * fps)`. The canonical store is **seconds**; frames are
  a derived view for frame-accurate ops (`split_clip`, keyframes — see group 02).

### 0.2 The `canGenerate` / credits gate (every generation-capable tool)
Read-only tools (`list_characters`) **never** gate. Any tool that spends GPU
(`plan_video` when `auto_generate=true`, `clone_voice`, `start_generation`,
`attach_character_to_scene` when it triggers a re-roll) returns a **pre-flight
gate** and refuses cleanly when the user cannot pay:

```jsonc
"credits_gate": {
  "can_generate": false,
  "reason": "insufficient_credits",     // | "not_signed_in" | "plan_limit" | "ok"
  "estimated_credits": 18,              // cost of THIS call if it proceeded
  "balance": 4,                         // user's current balance
  "message": "Generating 6 scenes costs ~18 credits; you have 4. Upgrade or buy credits.",
  "upgrade_url": "https://flow.stanl.ink/billing"
}
```

When `can_generate` is `false`, the tool performs **no work**, mutates nothing,
and returns `status: "blocked"` so the agent can relay a clear message instead of
silently failing (Palmier just errors "sign in / subscribe"; we return a
**typed, actionable** gate with a cost estimate the model can quote).

### 0.3 Undo — every mutation returns an `undo_token`
Like Palmier ("everything is one undoable action" + an `undo` tool), every
mutating Flow tool returns:

```jsonc
"undo": { "undo_token": "u_9f3c…", "label": "Cast 'Mei' into scenes 2,4,7", "reversible": true }
```

`undo` (group 02) reverses the **single most recent** assistant action by token.
Tools that kick off **async GPU jobs** (`start_generation`, `clone_voice`) are
reversible at two levels: **cancel** while running (`job_id`) and **revert** the
resulting artifacts after completion (`undo_token`). Both are returned.

### 0.4 Ownership & scoping (guardrails nanocode lacks)
Every tool is bound to the **current `project_id`** from the agent session and
verifies the caller owns the project, scenes, and characters it touches. The cast
(`list_characters`) is the one surface that can read **cross-project** (the user's
whole roster) but writes are always project-scoped.

### 0.5 Common error envelope
```jsonc
{ "status": "error", "error_code": "scene_not_found",
  "message": "Scene id 9 is not in project p_123 (scenes: 0–7).",
  "recoverable": true }
```
Errors are returned **as tool results** (nanocode's "error-as-string" robustness
trick), never thrown, so the model can self-correct in the loop.

---

## 1. `list_characters`

### Purpose
Return the user's **reusable cast** — characters that persist across scenes *and
across videos* (backed by `CharacterBank`, `config/characters/manifest.json`) —
with each character's description, reference image, and **consistency readiness**
(does it have a usable reference frame / S2V embedding yet?). This is the casting
counterpart to Palmier's `get_media`: it seeds the agent with the IDs every
casting call needs.

### When to call
- Early in any session that mentions people/characters ("make the narrator
  appear in scene 3", "keep the same robot throughout").
- Before `attach_character_to_scene` (to resolve a name → `character_id` and
  check `consistency_status`).
- Before `plan_video` when the user wants existing cast reused.

### Input schema
```jsonc
{
  "type": "object",
  "properties": {
    "scope": {
      "type": "string",
      "enum": ["project", "account"],
      "default": "project",
      "description": "project = cast attached to or used in this project; account = the user's entire reusable roster across all videos."
    },
    "include_unreferenced": {
      "type": "boolean",
      "default": true,
      "description": "Include characters that exist by description only (no reference image / embedding yet)."
    },
    "with_thumbnails": {
      "type": "boolean",
      "default": false,
      "description": "Include short-lived signed thumbnail URLs for each reference frame (adds latency)."
    }
  },
  "additionalProperties": false,
  "examples": [
    { "scope": "account", "with_thumbnails": true }
  ]
}
```

### Output schema
```jsonc
{
  "characters": [
    {
      "character_id": "ch_mei",
      "name": "Mei",
      "description": "young astronaut, short black hair, orange flight suit, freckles",
      "consistency_status": "ready",        // "ready" | "description_only" | "pending_extraction" | "failed"
      "consistency_method": "s2v",          // "s2v" | "reference_frame" | "none"
      "reference_image": "config/characters/Mei_ref.png",
      "reference_thumbnail_url": "https://…/thumb/ch_mei.jpg?exp=…",   // only if with_thumbnails
      "embedding_present": true,            // S2V subject embedding cached on GPU backend
      "used_in_scenes": [2, 4, 7],          // within current project
      "used_in_projects": 3,                // account scope insight
      "created_at": "2026-06-20T09:11:00Z"
    }
  ],
  "count": 1,
  "scope": "account"
}
```

### Behavior
- Reads `CharacterBank.list_characters()`; enriches each with
  `consistency_status` derived from `has_reference()` **and** whether an S2V
  subject embedding is cached on the GPU backend.
- `consistency_method` tells the agent *how* a character will be conditioned if
  cast now: `s2v` (subject-driven, strongest), `reference_frame` (I2V/FLF2V seed),
  or `none` (text-only — description injected into the prompt).
- Defaults omitted for token hygiene: identity fields with no value are dropped.
- Read-only → **never** gates on credits.

### Edge cases
- Empty roster → `{ "characters": [], "count": 0 }` (not an error).
- `with_thumbnails` but a reference file is missing on disk →
  `consistency_status: "failed"`, `reference_thumbnail_url` omitted, and a
  per-character `warning: "reference_image_missing"`.
- A character exists in the manifest but its image path no longer resolves → it
  is downgraded to `description_only` (self-healing read; no mutation).

### Undo semantics
None — read-only.

### Mapping onto Flow's scene/track model
Characters are **not** track elements; they are **casting metadata** that
conditions how a scene (video-track clip) is generated. `used_in_scenes` links a
character to specific clips on the video track so the agent can reason about
continuity ("Mei is in 2,4,7 — scene 5 breaks her arc").

### How this beats Palmier
Palmier has **no character primitive at all** — continuity is the editor's manual
problem. `list_characters` exposes a first-class, cross-project cast with an
explicit, machine-readable **`consistency_status`/`consistency_method`** the
model can plan around. Palmier's `get_media` lists raw assets; this lists *who is
in the film and whether we can keep them looking the same*.

---

## 2. `attach_character_to_scene`

### Purpose
Cast one or more characters into one or more scenes so they are **generated
consistently** — via S2V subject-driven conditioning when an embedding exists, or
reference-frame (I2V/FLF2V) seeding otherwise. Optionally re-roll the affected
scenes immediately so the change is visible.

### When to call
- "Put Mei in scenes 4 and 5", "make the narrator the same person throughout",
  "swap the villain in scene 6 for the one from scene 2".
- After `plan_video` to bind planned roles to concrete cast members.
- Before `start_generation` to ensure pending scenes carry the right cast.

### Input schema
```jsonc
{
  "type": "object",
  "properties": {
    "character_id": {
      "type": "string",
      "description": "Character to cast (from list_characters). Use character_ids[] to cast several at once."
    },
    "character_ids": {
      "type": "array", "items": { "type": "string" },
      "description": "Multiple characters into the same scene(s). Mutually exclusive with character_id."
    },
    "scene_ids": {
      "type": "array",
      "items": { "type": "integer", "minimum": 0 },
      "minItems": 1,
      "description": "Target scenes (Scene.id). These are positions on the video track."
    },
    "method": {
      "type": "string",
      "enum": ["auto", "s2v", "reference_frame", "prompt_only"],
      "default": "auto",
      "description": "auto picks the strongest available: s2v > reference_frame > prompt_only. Force one to override."
    },
    "role": {
      "type": "string",
      "maxLength": 60,
      "description": "Optional narrative role label for the cast in these scenes (e.g. 'pilot', 'narrator on-screen')."
    },
    "placement_hint": {
      "type": "string",
      "enum": ["center", "left", "right", "background", "foreground", "as_described"],
      "default": "as_described",
      "description": "Compositional hint folded into the generation prompt; 'as_described' lets the scene prompt decide."
    },
    "strength": {
      "type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.8,
      "description": "Subject-consistency weight. 1.0 = lock appearance hard (may fight the scene); 0.5 = looser, more scene-driven. Unitless."
    },
    "regenerate": {
      "type": "string",
      "enum": ["now", "mark_pending", "never"],
      "default": "mark_pending",
      "description": "now = re-roll affected scenes immediately (gated); mark_pending = flag dirty for next start_generation; never = metadata only."
    }
  },
  "oneOf": [ { "required": ["character_id", "scene_ids"] },
             { "required": ["character_ids", "scene_ids"] } ],
  "additionalProperties": false,
  "examples": [
    { "character_id": "ch_mei", "scene_ids": [4, 5], "method": "auto", "regenerate": "now" },
    { "character_ids": ["ch_mei", "ch_rover"], "scene_ids": [7], "strength": 0.9, "regenerate": "mark_pending" }
  ]
}
```

### Output schema
```jsonc
{
  "status": "ok",                          // | "blocked" | "error"
  "attached": [
    { "scene_id": 4, "character_id": "ch_mei", "method_used": "s2v", "role": "pilot" },
    { "scene_id": 5, "character_id": "ch_mei", "method_used": "s2v" }
  ],
  "scenes_marked_pending": [4, 5],         // when regenerate=mark_pending
  "regeneration": {                        // present only when regenerate=now
    "job_id": "job_re_22",
    "scene_ids": [4, 5],
    "status": "queued"
  },
  "credits_gate": { "can_generate": true, "reason": "ok", "estimated_credits": 6, "balance": 40 },
  "undo": { "undo_token": "u_a1", "label": "Cast 'Mei' into scenes 4,5", "reversible": true }
}
```

### Behavior
1. Resolves character(s), verifies project ownership, validates `scene_ids`
   exist.
2. Appends character name(s) to `Scene.characters` (the existing field) and
   stores per-scene casting metadata (`method`, `role`, `placement_hint`,
   `strength`) in the scene's generation params.
3. `method=auto` resolution: if the character has an S2V embedding → `s2v`; else
   if it has a reference image → `reference_frame` (seeds I2V/FLF2V); else
   `prompt_only` (injects the description text into the visual prompt).
4. `regenerate=now` → credits pre-flight, then enqueues a re-roll of exactly the
   affected scenes (reuses the per-scene regenerate path; preserves neighbours'
   first/last-frame chain so continuity isn't broken).
5. `regenerate=mark_pending` → marks scenes **dirty**; the next `start_generation`
   picks them up. No credits spent now.

### Edge cases
- Character has `consistency_status: "description_only"` and `method` forced to
  `s2v` → returns `error_code: "no_subject_embedding"` with a suggestion to run
  `clone`/reference extraction first; nothing mutated.
- Scene already contains the character → idempotent update of casting params
  (not a duplicate); `note: "already_cast_updated_params"`.
- `strength` ≥ 0.95 with a busy scene prompt → non-fatal `warning:
  "high_strength_may_reduce_scene_adherence"`.
- A scene is mid-generation → casting metadata is applied but `regenerate=now`
  is deferred with `warning: "scene_busy_requeued_after_current_job"`.
- `regenerate=now` but `can_generate=false` → `status: "blocked"`, casting
  metadata **also not** written (atomic: no half-applied change), so the user can
  retry cleanly after upgrading.

### Undo semantics
`undo_token` reverts the casting metadata mutation (removes the character from
`Scene.characters` + restores prior generation params). If `regenerate=now`
already produced new clips, undo **also** restores the previous rendered clips
from version history (each regenerate snapshots the prior clip — same model as
Palmier's "remembers prompt/model/frames per clip", extended to full clip
versions). While the job is still running, `regeneration.job_id` can be cancelled
instead.

### Mapping onto Flow's scene/track model
A scene is a clip on the **video track**. Casting does not add a track or a
clip — it changes **how that clip is generated**. Multi-scene attach is the
agent's lever for **character arcs across the track** (continuity is a property
of the ordered scene sequence, and last-frame conditioning between neighbours is
preserved on re-roll).

### How this beats Palmier
Palmier cannot do this at all — it has no character model and proxies third-party
generators with no subject-consistency primitive. Flow **owns** Wan2.2 S2V/VACE,
so casting is a real conditioning operation with a tunable `strength`, automatic
method selection, and continuity-preserving re-rolls. The `regenerate`
tri-state (`now`/`mark_pending`/`never`) also lets the agent batch casting cheaply
and pay once via `start_generation` — Palmier has no batched-generation notion.

---

## 3. `plan_video` — the autonomous orchestrator

### Purpose
Turn a **topic or a full script** into a complete, editable **shot list** —
ordered scenes (the video track), per-scene visual prompts, camera direction,
duration budget, narration segments, and a casting plan — optionally kicking off
generation. This is Flow's **autonomous-first** signature: Palmier waits to be
told each edit; `plan_video` proposes the entire film from one sentence. It is
the agent-facing wrapper over the existing `writer.py` → `ShotList` pipeline.

### When to call
- Session start when the project is empty and the user gives a topic/brief
  ("make a 60s explainer on how vaccines work").
- "Re-plan this as 90 seconds", "turn this script into scenes", "add 3 more
  scenes about the aftermath" (incremental planning).
- Before `start_generation` on a fresh project.

### Input schema
```jsonc
{
  "type": "object",
  "properties": {
    "topic": {
      "type": "string", "maxLength": 2000,
      "description": "Subject/brief to plan from. Provide topic OR script."
    },
    "script": {
      "type": "string", "maxLength": 20000,
      "description": "A finished narration script to segment into scenes (skips ideation). Mutually exclusive with topic."
    },
    "target_duration_seconds": {
      "type": "integer", "minimum": 5, "maximum": 3600, "default": 60,
      "description": "Total runtime budget in SECONDS. Scenes are sized to fit (see scene_duration_seconds)."
    },
    "scene_duration_seconds": {
      "type": "number", "minimum": 2, "maximum": 8, "default": 5,
      "description": "Target length per scene clip in SECONDS (Wan2.2 sweet spot is 5s). Total/this ≈ scene count."
    },
    "aspect_ratio": {
      "type": "string", "enum": ["9:16", "16:9", "1:1"], "default": "9:16"
    },
    "style": {
      "type": "string", "maxLength": 200,
      "description": "Visual/tonal style applied to every scene prompt (e.g. 'cinematic, warm film grain, shallow depth')."
    },
    "narration": {
      "type": "string", "enum": ["generate", "none", "from_script"], "default": "generate",
      "description": "generate = LLM writes narration; none = silent/visual-only; from_script = use provided script verbatim, segmented per scene."
    },
    "reuse_cast": {
      "type": "array", "items": { "type": "string" },
      "description": "character_ids (from list_characters) the planner should weave in and cast into appropriate scenes."
    },
    "scene_count": {
      "type": "integer", "minimum": 1, "maximum": 600,
      "description": "Optional hard override of scene count; otherwise derived from target/scene duration."
    },
    "mode": {
      "type": "string", "enum": ["replace", "append", "refine"], "default": "replace",
      "description": "replace = new shot list for an empty/cleared project; append = add scenes after existing; refine = revise existing scene prompts/order in place."
    },
    "auto_generate": {
      "type": "boolean", "default": false,
      "description": "If true, immediately enqueue start_generation for all planned scenes (credit-gated). If false, plan only."
    }
  },
  "oneOf": [ { "required": ["topic"] }, { "required": ["script"] } ],
  "additionalProperties": false,
  "examples": [
    { "topic": "the history of the internet", "target_duration_seconds": 60, "style": "retro documentary", "auto_generate": false },
    { "script": "Once, the library held every book…", "narration": "from_script", "reuse_cast": ["ch_mei"], "mode": "replace" }
  ]
}
```

### Output schema
```jsonc
{
  "status": "ok",                         // | "blocked" (only if auto_generate & gate fails) | "error"
  "shot_list": {
    "title": "The Internet: From ARPANET to Everywhere",
    "total_duration_seconds": 60,
    "fps": 24,
    "aspect_ratio": "9:16",
    "narration_full": "In 1969, four computers…",
    "scenes": [
      {
        "scene_id": 0,
        "duration_seconds": 5,
        "duration_frames": 120,
        "visual_prompt": "1969 university lab, reel-to-reel computers, warm tungsten light",
        "camera": "slow dolly in",
        "narration_segment": "In 1969, four computers formed the first network.",
        "characters": [],
        "track_position": 0,            // index on the video track
        "generation_status": "pending" // pending | generating | done | failed
      }
      // …
    ],
    "casting_plan": [
      { "character_id": "ch_mei", "scene_ids": [3, 6], "role": "researcher" }
    ]
  },
  "scene_count": 12,
  "estimated_credits_to_generate": 36,    // if the user later runs start_generation
  "generation": {                          // present only when auto_generate=true
    "job_id": "job_gen_5", "scene_ids": [0,1,2,3,4,5,6,7,8,9,10,11], "status": "queued"
  },
  "credits_gate": { "can_generate": true, "reason": "ok", "estimated_credits": 36, "balance": 50 },
  "undo": { "undo_token": "u_plan_1", "label": "Plan 12-scene video 'The Internet…'", "reversible": true }
}
```

### Behavior
1. **Planning** (no GPU): calls `writer.py` (LLM via configured provider) to
   produce a `ShotList` (`title`, `narration`, `scenes[]`, `characters{}`), then
   normalizes it onto the project's scene/track model and assigns `track_position`
   in order. Pure-text step → **not** credit-gated (LLM tokens only).
2. **Scene sizing:** `scene_count = scene_count ?? round(target_duration /
   scene_duration)`; last scene absorbs rounding remainder so the track total
   matches `target_duration_seconds`.
3. **Casting:** `reuse_cast` characters are matched to scenes the LLM deems
   relevant and emitted as `casting_plan` (the agent can then confirm via
   `attach_character_to_scene`, or planner auto-applies if it placed them).
4. **Narration:** `generate` → LLM writes it; `from_script` → split the provided
   script into per-scene `narration_segment`s aligned to scene boundaries;
   `none` → empty narration, visual-only.
5. **Mode:** `replace` overwrites an empty/cleared timeline; `append` adds scenes
   after the current last; `refine` rewrites prompts/order of existing scenes
   without nuking generated clips already rendered (marks only changed scenes
   dirty).
6. `auto_generate=true` → credits pre-flight for the whole batch, then enqueues
   `start_generation`. If the gate fails, the **plan is still saved** (text is
   free) and `status: "blocked"` flags only the generation step.

### Edge cases
- `replace` on a project that already has rendered clips → returns
  `confirmation_required: true` with a summary ("this discards 8 rendered
  scenes"); the agent must re-call with `mode: "append"`/`"refine"` or an
  explicit `confirm: true` (passed via a follow-up) — protects paid renders.
- `target_duration` not divisible by `scene_duration` → rounds scene count, notes
  `actual_total_seconds` (e.g. 62) vs requested 60 in a `warning`.
- Script far longer than `target_duration` → planner compresses/segments and
  emits `warning: "script_exceeds_budget_trimmed"`, never silently drops content
  without flagging.
- LLM returns malformed plan → retried up to 3× (mirrors pipeline's retry), then
  `error_code: "planning_failed"` (no partial scenes written).
- `scene_count > 600` (≈ 50min at 5s) → rejected with `plan_too_large`; suggests
  chunking.

### Undo semantics
`undo_token` reverts the entire planning mutation as one action: `replace`
restores the prior (empty or previous) timeline; `append` removes the added
scenes; `refine` restores prior prompts/order/clips from version history. If
`auto_generate` already queued a job, undo cancels the job **and** rolls back the
plan atomically.

### Mapping onto Flow's scene/track model
This **is** the track-builder. The output `scenes[]` in order *are* the video
track; `narration_full`/`narration_segment` populate the **audio track**;
`casting_plan` pre-wires subject consistency. `plan_video` is the only tool that
manufactures the whole timeline from nothing — everything else edits it.

### How this beats Palmier
Palmier has **no planner** — it is fundamentally assist-only: a human builds the
timeline and the agent nudges it. `plan_video` inverts the model (Flow's whole
thesis, per the analysis doc's "autonomous-first" framing and the Koyal
competitive note): one topic → a complete, typed, editable shot list with
casting and narration, optionally rendered end-to-end. It is the agentic
embodiment of `python -m flow generate --topic …`, exposed as a tool with rich
modes (`replace`/`append`/`refine`) and a safe credits/confirmation gate.

---

## 4. `set_narration` (+ voice selection)

### Purpose
Author, replace, or clear the spoken **narration on the audio track** — either
for the whole project or a specific scene range — and choose the **voice**
(built-in edge-tts voice, a MisoTTS model voice, or a cloned voice from
`clone_voice`). This is the generation-native, character-aware upgrade of
Palmier's generic `generate_audio` TTS.

### When to call
- "Write narration for the whole video in a calm female voice", "replace scene
  4's line with 'Then everything changed'", "narrate scenes 3–5 in Mei's cloned
  voice", "remove the voiceover from the intro".

### Input schema
```jsonc
{
  "type": "object",
  "properties": {
    "target": {
      "type": "string", "enum": ["project", "scene_range", "scenes"], "default": "project",
      "description": "project = one continuous narration auto-segmented across the track; scene_range = contiguous from/to; scenes = explicit list."
    },
    "scene_ids": {
      "type": "array", "items": { "type": "integer", "minimum": 0 },
      "description": "Required when target=scenes."
    },
    "from_scene_id": { "type": "integer", "minimum": 0, "description": "Required when target=scene_range." },
    "to_scene_id":   { "type": "integer", "minimum": 0, "description": "Required when target=scene_range (inclusive)." },
    "text": {
      "type": "string", "maxLength": 20000,
      "description": "Narration text. For multi-scene targets, use '\\n\\n' to delimit per-scene segments, or omit delimiters to let Flow auto-align to scene durations. Empty string clears narration."
    },
    "voice": {
      "type": "object",
      "description": "Which voice renders the text.",
      "properties": {
        "provider": { "type": "string", "enum": ["edge", "miso", "elevenlabs", "cloned"], "default": "edge" },
        "voice_id": {
          "type": "string",
          "description": "Provider voice id. edge example 'en-US-ChristopherNeural'; cloned example a voice_id from clone_voice; required unless using a character's bound voice."
        },
        "character_id": {
          "type": "string",
          "description": "Use the voice bound to this character (per-character voice). Overrides provider/voice_id if the character has a cloned voice."
        }
      },
      "additionalProperties": false
    },
    "rate": { "type": "number", "minimum": 0.5, "maximum": 2.0, "default": 1.0,
              "description": "Speaking rate multiplier (unitless). 1.0 = normal." },
    "pitch_semitones": { "type": "integer", "minimum": -12, "maximum": 12, "default": 0,
              "description": "Pitch shift in SEMITONES." },
    "fit_to_scene": {
      "type": "string", "enum": ["none", "pad_silence", "adjust_rate", "extend_scene"], "default": "pad_silence",
      "description": "When narration audio length ≠ scene duration: pad_silence pads/trims to fit; adjust_rate nudges speaking rate (±15% max) to fit; extend_scene grows scene_duration_seconds to fit the audio; none leaves mismatch (may overlap)."
    },
    "render": {
      "type": "boolean", "default": true,
      "description": "true = synthesize audio now (TTS; edge is free/not gated, miso/elevenlabs/cloned are gated). false = store text only, render later."
    }
  },
  "additionalProperties": false,
  "examples": [
    { "target": "project", "text": "In 1969…", "voice": { "provider": "edge", "voice_id": "en-US-AriaNeural" } },
    { "target": "scenes", "scene_ids": [3,4,5], "text": "…", "voice": { "character_id": "ch_mei" }, "fit_to_scene": "adjust_rate" },
    { "target": "scene_range", "from_scene_id": 0, "to_scene_id": 0, "text": "", "render": false }
  ]
}
```

### Output schema
```jsonc
{
  "status": "ok",                         // | "blocked" | "error"
  "segments": [
    {
      "scene_id": 3,
      "text": "Then everything changed.",
      "audio_path": "storage/.../narration_003.wav",
      "duration_seconds": 2.1,
      "scene_duration_seconds": 5.0,
      "fit_applied": "pad_silence",
      "voice": { "provider": "cloned", "voice_id": "vc_mei", "character_id": "ch_mei" }
    }
  ],
  "audio_track_updated": true,
  "scenes_extended": [],                   // populated when fit_to_scene=extend_scene
  "credits_gate": { "can_generate": true, "reason": "ok", "estimated_credits": 1, "balance": 39 },
  "undo": { "undo_token": "u_narr_2", "label": "Set narration on scenes 3–5 (Mei voice)", "reversible": true }
}
```

### Behavior
1. Resolves target scenes; splits `text` into per-scene `narration_segment`s
   (explicit `\n\n`, else proportional-to-duration auto-split using sentence
   boundaries).
2. Writes each segment to the scene's `narration_segment` field (the existing
   `Scene` field) — the **audio track** is the parallel narration layer over the
   video track.
3. Voice resolution order: `voice.character_id` (if it has a bound/cloned voice) →
   explicit `provider`+`voice_id` → project default (`TTSConfig.voice`). edge-tts
   is **free** (not gated); `miso`/`cloned`/`elevenlabs` consume credits.
4. `render=true` synthesizes via the configured TTS path
   (`tts_miso.generate_speech` / edge / elevenlabs), measures audio length, and
   applies `fit_to_scene`.
5. Empty `text` clears narration for the target (removes audio segment + clears
   `narration_segment`).

### Edge cases
- `voice.character_id` set but that character has **no** bound voice →
  `error_code: "character_has_no_voice"`, suggests `clone_voice`; nothing
  rendered.
- `adjust_rate` needs > ±15% to fit → applies the 15% cap and returns
  `warning: "fit_incomplete_residual_padding_applied"`.
- `extend_scene` would push total runtime past a hard project cap → falls back to
  `pad_silence` with a `warning`.
- Mixed delimiters vs scene count (3 segments, 4 scenes) → distributes by order,
  last scenes get silence, `warning: "segment_count_lt_scene_count"`.
- `render=true` but cloned/miso gate fails → `status: "blocked"`, **text still
  saved** (so a free re-render with edge, or a later paid render, works); no audio
  written.

### Undo semantics
`undo_token` reverts both the `narration_segment` text changes and the rendered
audio-track artifacts (prior audio restored from version history; cleared
narration restored). Free to undo (no GPU to reclaim).

### Mapping onto Flow's scene/track model
Narration is the **audio track** running parallel to the video track of ordered
scenes. Per-scene `narration_segment`s are what ffmpeg assembly lays under each
scene clip; `fit_to_scene=extend_scene` is the one option that feeds back into the
**video track** (changes `scene_duration_seconds`). Caption generation
(group 02 `add_captions`) can consume these segments for the text track.

### How this beats Palmier
Palmier's `generate_audio` is a generic TTS/music call with **no notion of
narration-per-scene, no character voices, and no fit-to-clip logic**. `set_narration`
is track-aware (segments align to scenes), **character-aware** (`voice.character_id`
→ a per-character cloned voice), and has explicit, typed **fit strategies** so
narration and visuals stay in sync — plus a free path (edge-tts) that never
gates. Flow owns the voice stack (MisoTTS 8B cloning), so a character can *sound*
consistent the same way they *look* consistent.

---

## 5. `clone_voice`

### Purpose
Register a **cloned voice** from a short reference audio sample (one-shot, via
MisoTTS 8B), scoped to the **project** or bound to a **character**, so it can be
reused by `set_narration`. This is the audio analogue of character visual
consistency — Palmier has nothing comparable.

### When to call
- "Clone my voice from this clip", "make the narrator sound like this sample",
  "give Mei this voice", before narrating in a custom/cloned voice.

### Input schema
```jsonc
{
  "type": "object",
  "properties": {
    "name": { "type": "string", "maxLength": 60, "description": "Human label for the voice, e.g. 'Founder VO'." },
    "sample_audio": {
      "type": "string",
      "description": "Reference audio: an uploaded media_id, a project file path, or a base64 data URI. 5–30s of clean single-speaker speech recommended."
    },
    "sample_transcript": {
      "type": "string", "maxLength": 2000,
      "description": "Exact transcript of sample_audio (improves clone fidelity; MisoTTS uses it as context). Strongly recommended."
    },
    "bind_to_character_id": {
      "type": "string",
      "description": "If set, this voice becomes the character's per-character voice (set_narration voice.character_id resolves to it)."
    },
    "scope": {
      "type": "string", "enum": ["project", "account"], "default": "project",
      "description": "project = usable in this video only; account = reusable across all the user's videos (like the cast)."
    },
    "precision": {
      "type": "string", "enum": ["bf16", "int8", "int4"], "default": "int8",
      "description": "MisoTTS inference precision. bf16 = best quality/slowest; int4 = fastest/cheapest. Matches TTSConfig.miso_precision."
    }
  },
  "required": ["name", "sample_audio"],
  "additionalProperties": false,
  "examples": [
    { "name": "Mei VO", "sample_audio": "media_8821", "sample_transcript": "Hello, this is a test of my voice.", "bind_to_character_id": "ch_mei", "scope": "account" }
  ]
}
```

### Output schema
```jsonc
{
  "status": "ok",                         // | "blocked" | "error"
  "voice_id": "vc_mei",
  "name": "Mei VO",
  "scope": "account",
  "bound_character_id": "ch_mei",
  "preview_audio_path": "storage/.../vc_mei_preview.wav",   // short synthesized sample for confirmation
  "ready": true,
  "credits_gate": { "can_generate": true, "reason": "ok", "estimated_credits": 2, "balance": 37 },
  "undo": { "undo_token": "u_voice_1", "label": "Clone voice 'Mei VO'", "reversible": true }
}
```

### Behavior
1. Validates/normalizes the sample (resamples to MisoTTS sample rate, as in
   `tts_miso._generate_local`), warns on multi-speaker/noisy/too-short audio.
2. Builds the one-shot cloning context (sample audio + transcript), synthesizes a
   short **preview** to confirm fidelity, and stores the voice profile keyed by
   `voice_id`.
3. `bind_to_character_id` → records the voice on the character so per-character
   narration resolves automatically.
4. Credit-gated (GPU TTS inference). edge/built-in voices need no cloning, so this
   tool is **only** for custom voices.

### Edge cases
- Sample < 3s or detected multi-speaker → `error_code: "sample_unusable"` with
  the reason; nothing stored.
- `sample_transcript` missing → proceeds but returns `warning:
  "no_transcript_lower_fidelity"`.
- `bind_to_character_id` not found → voice still created (project/account scoped),
  `warning: "character_not_found_binding_skipped"`.
- Duplicate `name` in scope → suffixes/returns existing with `note: "reused_existing_voice"`.

### Undo semantics
`undo_token` deletes the registered voice and removes any character binding it
created. If still synthesizing the preview, the job can be cancelled via `job_id`.

### Mapping onto Flow's scene/track model
A voice is **casting metadata for the audio track** (parallel to a character
being casting metadata for the video track). It does not itself place anything on
the timeline — `set_narration` does, by referencing the `voice_id`.

### How this beats Palmier
Palmier has no voice identity at all. `clone_voice` gives Flow **per-character and
per-project voice consistency** built on its owned MisoTTS 8B stack, with a
quality/cost knob (`precision`), a confirmation preview, and account-scoped reuse
— the auditory twin of subject-consistent characters. This is squarely in Flow's
generation-owned lane (the analysis doc flags Voicebox/voice-cloning as a roadmap
edge); Palmier, proxying third-party TTS, structurally can't match it.

---

## 6. `start_generation` — batch-render all pending scenes

### Purpose
Generate (or re-generate) video clips for scenes that need it, as **one
asynchronous, undoable batch job**, honoring the configured generation mode
(`sequential` / `parallel_flf2v` / `pipelined_flf2v`), scene chaining
(first/last-frame conditioning), and character conditioning. This is the
"press play on the whole film" action — Palmier only generates one clip at a
time.

### When to call
- After `plan_video` (without `auto_generate`) or after a batch of
  `attach_character_to_scene` / `update_scene` edits left scenes **pending/dirty**.
- "Generate everything", "render the scenes I changed", "re-roll scenes 4 and 7".

### Input schema
```jsonc
{
  "type": "object",
  "properties": {
    "selection": {
      "type": "string", "enum": ["pending", "all", "scenes", "failed"], "default": "pending",
      "description": "pending = scenes never rendered or marked dirty; all = force re-render every scene (expensive); scenes = explicit scene_ids; failed = only scenes whose last generation failed."
    },
    "scene_ids": {
      "type": "array", "items": { "type": "integer", "minimum": 0 },
      "description": "Required when selection=scenes."
    },
    "mode": {
      "type": "string", "enum": ["auto", "sequential", "parallel_flf2v", "pipelined_flf2v"], "default": "auto",
      "description": "Generation strategy (mirrors Config.generation_mode). auto = use project config. parallel/pipelined are faster on multi-GPU."
    },
    "resolution": {
      "type": "string", "enum": ["480p", "720p"], "default": "480p",
      "description": "Output resolution (mirrors GPUBackendConfig.resolution). 720p costs more."
    },
    "preserve_chaining": {
      "type": "boolean", "default": true,
      "description": "When re-rolling a subset, keep first/last-frame continuity with un-changed neighbours (re-seed boundaries). false = generate selected scenes independently."
    },
    "max_retries": {
      "type": "integer", "minimum": 0, "maximum": 5, "default": 3,
      "description": "Per-scene validation retries (mirrors generator MAX_RETRIES: black-frame / coherence checks)."
    },
    "priority": {
      "type": "string", "enum": ["normal", "high"], "default": "normal",
      "description": "high may use more GPUs / cost more for faster turnaround."
    }
  },
  "allOf": [
    { "if": { "properties": { "selection": { "const": "scenes" } } },
      "then": { "required": ["scene_ids"] } }
  ],
  "additionalProperties": false,
  "examples": [
    { "selection": "pending", "mode": "auto", "resolution": "480p" },
    { "selection": "scenes", "scene_ids": [4,7], "preserve_chaining": true, "priority": "high" },
    { "selection": "all", "resolution": "720p" }
  ]
}
```

### Output schema
```jsonc
{
  "status": "queued",                     // | "blocked" | "error" | "nothing_to_do"
  "job_id": "job_gen_9",
  "scene_ids": [0,1,2,3,4,5],
  "scene_count": 6,
  "mode_used": "pipelined_flf2v",
  "resolution": "480p",
  "estimated": {
    "credits": 18,
    "seconds_per_scene": 84,             // grounded in benchmarks (~79–84s/clip on A100)
    "wall_clock_seconds_estimate": 520    // accounts for parallel/pipelined overlap
  },
  "progress_channel": "ws://…/jobs/job_gen_9",   // WebSocket for live per-scene progress
  "credits_gate": { "can_generate": true, "reason": "ok", "estimated_credits": 18, "balance": 40 },
  "undo": { "undo_token": "u_gen_9", "label": "Generate 6 scenes", "reversible": true, "cancel_job_id": "job_gen_9" }
}
```

### Behavior
1. Resolves the scene set from `selection` (dirty/pending tracking is maintained
   by every mutating tool above).
2. Credits pre-flight for the **whole batch** (`estimated.credits` =
   per-scene cost × count × resolution/priority multipliers). Refuses cleanly if
   `can_generate=false`.
3. Enqueues an async job on the GPU backend (Modal/RunPod) using the chosen
   `mode`; for `parallel_flf2v`/`pipelined_flf2v` it runs the two-pass keyframe +
   video overlap (per `parallel_generator.py`/`keyframes.py`).
4. `preserve_chaining=true` seeds each selected scene's first frame from the prior
   scene's last frame so a partial re-roll doesn't break continuity on the video
   track.
5. Per-scene **validation + retry** (`max_retries`): black-frame and coherence
   checks (`validation.py`); failed scenes after retries are marked `failed`
   (re-runnable via `selection=failed`).
6. Streams progress on `progress_channel`; the agent can poll a companion
   `get_generation_status(job_id)` (group 04) or surface live updates.

### Edge cases
- `selection=pending` with nothing pending → `status: "nothing_to_do"`,
  `scene_count: 0` (not an error).
- `selection=all` on a large project → returns `confirmation_required: true` with
  cost/time so the agent confirms before spending (protects against accidental
  full re-renders).
- A scene references a character with `consistency_status: "description_only"` →
  generates with `prompt_only` conditioning + per-scene `warning:
  "character_text_only_no_subject_lock"`.
- Backend at capacity → job is `queued` with an `eta_seconds`; never silently
  dropped.
- Mid-job cancel → completed scenes are kept (their clips are valid), the job
  stops; partial result is reported.
- Gate fails → `status: "blocked"`, **no job enqueued**, nothing spent.

### Undo semantics
Two-level (per §0.3): while running, `cancel_job_id` cancels the batch (keeping
already-finished scenes); after completion, `undo_token` restores the **previous
clip versions** for every scene the job replaced (each scene snapshots its prior
rendered clip — extends Palmier's per-clip prompt/model memory to full clip
versioning). Scenes that were `pending` (no prior clip) are reverted to pending.

### Mapping onto Flow's scene/track model
This is the action that turns the **planned/edited video track into actual
rendered clips**. It is the batch wrapper over the existing
`generator.py`/`parallel_generator.py` pipeline, exposed to the agent with
selection semantics (`pending`/`failed`/`scenes`/`all`) and continuity controls.
Narration (audio track) and captions (text track) are composed later by ffmpeg
assembly; `start_generation` is specifically the **video-track render**.

### How this beats Palmier
Palmier's `generate_video` is **per-clip, fire-and-forget**, with no batch, no
selection semantics, no continuity-preserving re-roll, and no project-wide cost
estimate. `start_generation` renders the **entire pending track in one undoable,
cancellable job**, picks the optimal multi-GPU mode, preserves scene chaining on
partial re-rolls, retries on validation failure, and quotes batch cost/time up
front — because Flow owns the Wan2.2 pipeline end-to-end rather than proxying a
third-party generator. It is the operational core of Flow's autonomous thesis:
plan → cast → narrate → **generate it all**.

---

## Summary — why these five (six) stand out

| Capability | Palmier | Flow-native |
|--|--|--|
| Reusable cross-project cast | — | `list_characters` |
| Subject-consistent casting (S2V/VACE, tunable strength) | — | `attach_character_to_scene` |
| Topic/script → full shot list (autonomous) | — | `plan_video` |
| Per-scene, character-aware narration with fit-to-clip | generic TTS only | `set_narration` |
| Per-character / per-project voice cloning | — | `clone_voice` |
| One-shot batch render of the whole track, undoable | per-clip only | `start_generation` |

Common to all: richer JSON Schema (enums, ranges, explicit `*_seconds`/`*_frames`
units, examples), a typed `credits_gate`, `undo_token` (+ job cancel for async),
strict project ownership, and error-as-result for self-correction. These are the
tools that make Flow **autonomous-first and generation-native** rather than an
assist-only NLE copilot.
