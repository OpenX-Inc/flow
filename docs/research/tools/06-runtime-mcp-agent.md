# 06 — Runtime: VPS MCP Server + Agent Loop (the engine that drives all 35+ tools)

**Date:** 2026-06-24
**Status:** 0.3 implementation spec
**Scope:** This is the *runtime* doc. Docs `01`–`05` specify the individual
tools (context, timeline-edit, text, generate, color/FX, media-mgmt,
Flow-specific casting). This doc specifies **what executes them**: the VPS MCP
server that exposes the tools, the nanocode-style agent loop that calls them via
the NVIDIA build endpoint (default model `kimi`), the context-injection
strategy, and the data-model migration that gives the tools something to operate
on.

**Read first (every stage):**
`docs/research/agentic-video-editing-analysis.md`,
`docs/research/agent-tool-loop-nanocode.md`,
`docs/research/palmier-video-tools-catalog.md`.

**Architecture facts this doc binds to:**
1. Backend is Python/FastAPI on a VPS; frontend is Next.js (the Studio workspace
   right-panel chat).
2. **Scenes ARE the timeline.** Ordered scenes = the video track; ffmpeg
   concatenates them into one complete track, with parallel **audio** tracks
   (narration/music via edge-tts/MisoTTS) and **caption** (text) tracks. No
   generic NLE rebuild.
3. Tools are exposed by a **VPS MCP server** and driven by an **in-app agent
   loop** (nanocode pattern) calling the **NVIDIA build API**, default model
   `kimi`, OpenAI-style tool-calling.
4. Generation is Flow-owned: Wan2.2 t2v/i2v + VACE + flf2v on Modal, plus
   characters (subject consistency) and voice cloning.

---

## 0. TL;DR of the runtime design

```
Browser (Next.js Studio, right-panel chat)
   │  POST /agent/chat  (SSE stream back)               ▲ tokens + tool-activity events
   ▼                                                    │
FastAPI app  ─────────────────────────────────────────────────────────────────
   │  AgentSession (per project+user)                   the in-app agent loop
   │   ├─ ContextBuilder ── injects project + cast into system prompt
   │   ├─ NvidiaBuildClient ── /v1/chat/completions, model="kimi", /v1/models
   │   └─ McpToolClient ──── streamable-HTTP MCP client → 127.0.0.1:8765/mcp
   ▼
MCP server (same VPS, loopback 127.0.0.1, bearer-authed)
   │  registers all 35+ tools (handlers from src/flow/tools/*)
   ▼
Flow domain services  → ProjectStore (scenes/tracks/clips/keyframes + undo log)
                      → Generation (OpenX Cloud → Modal: Wan2.2 t2v/i2v/VACE/flf2v)
                      → TTS (edge-tts / MisoTTS voice-clone)
                      → ffmpeg assembly (tracks → final video)
```

Two processes, both on the VPS:
- **`flow-api`** (FastAPI): serves the Studio + hosts the agent loop. It is an
  **MCP client** and an **LLM caller**.
- **`flow-mcp`** (MCP server): loopback-only tool host. It is the **single
  chokepoint** where every tool runs, where auth/ownership/credits are enforced,
  and where the undo log is written.

Why split them (vs. calling handlers in-process)? It mirrors Palmier's
localhost-bound MCP server and gives us the Palmier "for-free" angle: any
external agent (Claude Code / Cursor) pointed at a self-hosted Flow gets the
exact same tool surface, governed by the exact same guards — because the guards
live in the server, not the loop.

---

## (a) The VPS MCP server (`flow-mcp`)

### Stack & binding

- **SDK:** the official Python MCP SDK (`mcp`), `FastMCP` server with the
  **streamable-HTTP** transport (`mcp.server.fastmcp.FastMCP`,
  `transport="streamable-http"`). This is the modern replacement for the older
  SSE transport and matches Palmier's "GET=SSE / POST=JSON-RPC over HTTP" shape.
- **Bind:** `127.0.0.1:8765` **loopback only**, path `/mcp`. Never `0.0.0.0`.
  This is the single most important security property and it is copied directly
  from Palmier (its server is `127.0.0.1`-bound and unreachable from the LAN).
- **Origin/host validation:** reject requests whose `Origin`/`Host` are not in
  an allow-list (`127.0.0.1`, `localhost`) to defend against DNS-rebinding — the
  same validator class Palmier ships.
- **Auth:** a per-process **shared secret** (`FLOW_MCP_TOKEN`, 32-byte random,
  minted at boot, handed to `flow-api` via env/secret file) required on every
  call as `Authorization: Bearer <token>`. Loopback + bearer is defense in
  depth: even a local process can't drive tools without the token.
- **Session identity:** the bearer identifies the *caller process*, not the end
  user. The **acting user + project** travel as **call arguments**
  (`_ctx.actor_user_id`, `_ctx.project_id`) injected by `flow-api` and validated
  per-tool (see guardrails). External agents must supply a scoped token that
  pins `actor_user_id`/`project_id` server-side (token → claims map), so they
  cannot spoof another user's project.

### Tool registration

Tools are **declared once** in a registry and **served twice**: to MCP (for the
loop + external agents) and to the OpenAI tool schema (for kimi). Single source
of truth — no schema drift.

```python
# src/flow/tools/registry.py
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

@dataclass(frozen=True)
class ToolSpec:
    name: str                       # wire-name, e.g. "regenerate_scene"
    description: str                # model-facing, imperative, with "when to call"
    input_schema: dict[str, Any]    # full JSON Schema (enums, ranges, units, examples)
    output_schema: dict[str, Any]   # documented result shape
    handler: Callable[["ToolContext", dict], Awaitable[dict]]
    # governance flags consumed by the runtime:
    mutates: bool = False           # writes domain state → goes in the undo log
    generates: bool = False         # hits the paid pipeline → canGenerate/credits gate
    reads_only: bool = True         # never blocked by the credits gate

REGISTRY: dict[str, ToolSpec] = {}

def tool(**meta):
    def deco(fn):
        REGISTRY[meta["name"]] = ToolSpec(handler=fn, **meta)
        return fn
    return deco
```

```python
# src/flow/mcp_server/app.py
from mcp.server.fastmcp import FastMCP
from flow.tools.registry import REGISTRY
from flow.tools import context, timeline, text, generate, color, media, casting  # noqa: register

mcp = FastMCP("flow", host="127.0.0.1", port=8765)

def _register_all():
    for spec in REGISTRY.values():
        async def _runner(arguments: dict, _spec=spec):
            ctx = ToolContext.from_arguments(arguments)   # pulls _ctx.{token,user,project}
            return await dispatch(_spec, ctx, arguments)  # guards + undo + handler
        mcp.add_tool(
            fn=_runner,
            name=spec.name,
            description=spec.description,
            # FastMCP forwards these to clients verbatim:
            annotations={"inputSchema": spec.input_schema,
                         "outputSchema": spec.output_schema},
        )

_register_all()

def main():
    mcp.settings.streamable_http_path = "/mcp"
    mcp.run(transport="streamable-http")
```

`dispatch()` is the chokepoint (auth → ownership → scope → credits → execute →
undo-log → return). See guardrails in (b).

### Error contract (nanocode's robustness trick, hardened)

Every tool returns a **structured result**, and *errors are values, not
exceptions* — they flow back to the model so it can self-correct (nanocode's key
insight). But unlike nanocode's bare string, we return typed JSON:

```jsonc
// success
{ "ok": true,  "data": { /* tool output schema */ }, "undo_id": "u_8f3a" }
// recoverable (model should retry/adjust)
{ "ok": false, "error": { "code": "scene_not_found", "message": "...", "retryable": true } }
// gated (model must surface to user, not retry)
{ "ok": false, "error": { "code": "credits_exhausted", "message": "...", "gate": "credits" } }
```

`code` is a closed enum per tool (documented in each tool's spec). The loop
serializes this object as the `tool` message content; kimi reads `ok`/`code` and
either adjusts arguments, stops and asks the user, or proceeds.

---

## (b) The agent loop (`flow-api`) — nanocode pattern → NVIDIA build / kimi

### Endpoint exposed to the browser

```
POST /agent/chat
  body: { project_id: str, message: str, session_id?: str }
  resp: text/event-stream (SSE)
        event: token        data: {"text": "..."}            # streamed assistant text
        event: tool_call    data: {"name": "...", "args": {...}, "id": "..."}
        event: tool_result  data: {"id": "...", "ok": true, "summary": "..."}
        event: done         data: {"session_id": "...", "iterations": 3}
        event: error        data: {"code": "...", "message": "..."}
```

The right-panel renders `token` as chat text and `tool_call`/`tool_result` as the
"tool activity" chips (mirrors Palmier's visible tool log).

### NVIDIA build client

- **Base URL:** `https://integrate.api.nvidia.com/v1` (config:
  `[agent].base_url`).
- **Auth:** `Authorization: Bearer $NVIDIA_API_KEY` (an `nvapi-...` key;
  config `[agent].api_key`, never logged).
- **Wire format:** OpenAI-compatible — `POST /v1/chat/completions` with
  `tools=[{type:"function", function:{name, description, parameters}}]`,
  `tool_choice:"auto"`; responses carry `choices[0].message.tool_calls[]` and we
  reply with `role:"tool"` messages keyed by `tool_call_id`. (This is the only
  delta from nanocode, which uses Anthropic `tool_use`/`tool_result` blocks — same
  algorithm, OpenAI field names.)
- **Model:** default **`kimi`** (config `[agent].model = "kimi"`). `kimi` is a
  Flow-side **alias** resolved to the concrete NVIDIA model id at startup by
  listing models and picking the newest Kimi instruct id
  (`moonshotai/kimi-k2-instruct` family). Aliasing keeps the alias stable as
  NVIDIA bumps point versions.
- **Model listing:** `GET /v1/models` populates the `list_models`-style alias
  table and lets the Studio "model" dropdown show what's actually available.

```python
# src/flow/agent/llm.py
import httpx

class NvidiaBuildClient:
    def __init__(self, base_url: str, api_key: str, default_model: str = "kimi"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self._alias: dict[str, str] = {}

    async def resolve_models(self) -> dict[str, str]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{self.base_url}/models",
                            headers={"Authorization": f"Bearer {self.api_key}"})
            r.raise_for_status()
            ids = [m["id"] for m in r.json()["data"]]
        kimi = sorted([i for i in ids if "kimi" in i.lower()])
        self._alias = {"kimi": (kimi[-1] if kimi else "moonshotai/kimi-k2-instruct")}
        return self._alias

    async def chat(self, *, messages, tools, model=None, stream=True):
        model_id = self._alias.get(model or self.default_model, model or self.default_model)
        payload = {"model": model_id, "messages": messages,
                   "tools": tools, "tool_choice": "auto",
                   "temperature": 0.6, "stream": stream}
        # POST /chat/completions; yield SSE deltas (text) + accumulate tool_calls
        ...
```

### The loop (nanocode → OpenAI shape, with Flow guardrails)

```python
# src/flow/agent/loop.py  (the heart — compare nanocode's while-True)
async def run_turn(session, user_message):
    session.messages.append({"role": "user", "content": user_message})
    for iteration in range(session.MAX_ITERATIONS):              # GUARD 1: hard cap
        msg, tool_calls = await session.llm.chat(
            messages=session.messages,
            tools=session.tool_schemas,            # from MCP listTools → OpenAI fn schema
            model=session.model,
        )                                          # streams text tokens to the browser
        session.messages.append(msg)               # assistant turn (may carry tool_calls)
        if not tool_calls:
            return                                  # model answered w/o tools → done
        for call in tool_calls:
            result = await session.mcp.call_tool(   # executes on flow-mcp (loopback)
                call.name,
                {**call.arguments,
                 "_ctx": session.ctx_envelope()},   # actor_user_id, project_id, mcp_token
            )
            session.messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json_dumps(result),      # structured ok/error → self-correct
            })
        # loop again with results appended
    # fell out of the loop:
    session.emit_error("max_iterations_reached",
                       "I made several edits but didn't finish — want me to continue?")
```

### Guardrails Palmier/nanocode lack (all enforced in `dispatch()` on the server, plus loop-level caps)

| Guard | Where | Behavior |
|--|--|--|
| **Max iterations** | loop (`MAX_ITERATIONS`, default 12; configurable) | Prevents runaway tool loops / cost blowups. On hit, stop and ask the user instead of silently looping. |
| **Per-call wall-clock + token budget** | session | Abort a turn exceeding `agent.turn_timeout_s` (default 180) or a token ceiling; emit `error`. |
| **Per-tool auth** | `dispatch()` | Validate the bearer (`FLOW_MCP_TOKEN` or a scoped external token) before anything. No token → `unauthorized`. |
| **Ownership** | `dispatch()` | Resolve `actor_user_id` from the token/claims; assert the row (scene/character/media/track) belongs to that user. Cross-tenant id → `forbidden`. (Palmier has no users; this is net-new.) |
| **Project scoping** | `dispatch()` | Every mutating/read tool is pinned to `_ctx.project_id`; ids referenced in args MUST belong to that project. Agent literally cannot touch another project. |
| **canGenerate / credits gate** | `dispatch()` for `generates=True` tools | Before any Wan2.2/VACE/flf2v/TTS call, check `billing.can_generate(user, est_cost)`. Fail with `{code:"credits_exhausted", gate:"credits"}` or `{code:"signin_required", gate:"auth"}`. Read-only tools are **never** gated (Palmier's exact rule). Estimated cost is computed from the model's per-second price × requested duration (we own the pipeline, so the estimate is real, not a guess). |
| **Idempotency** | `dispatch()` | Mutating calls accept an optional `idempotency_key`; replays return the prior `undo_id` instead of double-applying (protects against loop retries after a stream drop). |
| **Concurrency lock** | `dispatch()` | One in-flight mutation per project (advisory lock). Concurrent agent turns on the same project serialize, so the undo log stays linear. |

### Undo semantics (runtime side)

Every `mutates=True` tool, on success, appends one entry to the project's
**undo log** *before* returning:

```jsonc
{ "undo_id": "u_8f3a", "tool": "reorder_scenes", "project_id": "...",
  "actor": "user_123", "ts": "...",
  "inverse": { "op": "reorder_scenes", "args": { "order": [/* prior order */] } },
  "snapshot_ref": "snap_8f3a" }            // optional blob for non-invertible ops
```

- The `undo` tool (spec'd in `02-timeline-edit`) pops the latest entry **for the
  current agent session+project** and applies its `inverse` (or restores
  `snapshot_ref`). Like Palmier, **one tool call = one undoable action**; a
  single agent turn that made 3 edits = 3 undo entries, popped LIFO.
- Generation tools record the *intent + resulting asset id*; "undo" of a
  completed generation detaches/soft-deletes the produced clip (does not refund
  credits already spent — surfaced clearly to the model/user).
- The log is **server-authoritative** (lives in `ProjectStore`), so external
  agents and the in-app loop share one consistent history.

---

## (c) Injecting full project + character context into the system prompt

Palmier's lesson: `get_timeline` first, always — one call seeds the agent with
the whole project and the ids every other tool needs. We do better: the loop
**pre-injects** a compact, structured snapshot into the **system prompt** at the
start of every turn, so the model starts grounded and spends its first tool call
on *doing*, not *looking*. (`get_project` still exists for re-reads after edits.)

`ContextBuilder.build(project_id, user)` assembles:

```text
SYSTEM (assembled per turn; defaults omitted for token hygiene — Palmier's habit)
────────────────────────────────────────────────────────────────────────────────
You are Flow's video agent. You operate the user's video by calling tools.
Scenes ARE the timeline: ordered scenes = the video track. Audio (narration/
music) and captions are parallel tracks. ffmpeg concatenates scenes into the
final video. Prefer regenerating/reordering scenes over rebuilding a timeline.

## Project  (id=proj_abc)
title: "The History of the Internet"   aspect: 9:16   fps: 30   duration: 58.0s
status: draft        canGenerate: true     credits: 412 (≈ 137s of 480p gen)

## Video track — scenes (in order)         [the timeline]
1. scene_01  0.0–5.0s  model=wan2.2-i2v  cast=[Ada]   "server room, slow push-in"
2. scene_02  5.0–10.0s model=wan2.2-flf2v cast=[Ada]  "ARPANET map glowing"   ⚠ no last_frame
3. scene_03 10.0–14.0s model=wan2.2-t2v   cast=[]      "1969 lab, tracking shot"
... (windowed: first 8 + last 2 if many; mid elided with a count)

## Audio tracks
narration: edge-tts en-US-ChristopherNeural, 11 segments, covers 0–58s
music:     (none)

## Caption track
captions: none

## Cast (characters available)             [Flow-specific, Palmier has none]
- Ada    desc="red-haired engineer, 30s, denim jacket"   ref_image=yes (S2V-ready)
- Newscaster  desc="1960s anchor, grey suit"             ref_image=no  ⚠ generate ref first

## Available models (from /v1/models + Flow model registry)
wan2.2-t2v, wan2.2-i2v, wan2.2-flf2v, wan2.2-vace ; voices: edge(*), miso(clone)

## Rules
- Confirm destructive bulk ops (delete_scene on many, remove_tracks).
- Generation costs credits; check canGenerate before promising output.
- Reference scenes/characters by id. Don't invent ids — call get_project to refresh.
```

Construction details:
- **Source of truth:** `ProjectStore.snapshot(project_id)` + `CharacterBank`
  (`src/flow/characters.py`, already exists) + the resolved model alias table.
- **Token hygiene (Palmier's "defaults omitted"):** identity transform, speed 1,
  opacity 1, full-volume, empty trims are *not* serialized. Only deltas show.
- **Windowing:** for long projects (30-scene films exist in the repo), show
  first N + last M scenes with an elision marker and a total count; the agent
  pulls detail with `get_project`/`inspect_*` on demand.
- **Warnings (⚠):** the builder flags actionable gaps (missing `last_frame` for a
  flf2v scene, a cast member with no reference image) so the model proactively
  fixes them — something Palmier's flat dump never surfaces.
- **Freshness:** rebuilt at the **start of each user turn** and the system
  message is *replaced* (not appended) so stale state never accumulates. Within a
  turn, tool results already reflect mutations, so mid-turn re-injection isn't
  needed; the model re-reads via `get_project` if it wants a clean view.

---

## (d) Data-model migration plan

Today the model is **in-memory Pydantic only** (`src/flow/schemas.py`: `Scene`,
`ShotList`, `GeneratedClip`; characters persist to a JSON manifest via
`CharacterBank`). There is **no project store and no timeline semantics**. The
agentic editor needs: persistent projects, scenes-as-clips with editable props +
keyframes, parallel audio + caption tracks, and an undo log. This migration adds
exactly that — **without** building a generic NLE.

### Target schema (new `src/flow/store/models.py`, SQLModel over SQLite→Postgres)

```python
class Project(SQLModel, table=True):
    id: str            # proj_*
    owner_user_id: str
    title: str
    aspect_ratio: str = "9:16"     # "9:16" | "16:9" | "1:1"
    fps: int = 30                  # PROJECT FPS — the frames⇄seconds anchor
    status: str = "draft"
    created_at: datetime; updated_at: datetime

class Scene(SQLModel, table=True):          # = one CLIP on the video track
    id: str                                  # scene_*
    project_id: str                          # FK, scope key
    order_index: int                         # position on the video track (0-based)
    # --- generation provenance (Palmier's "regenerate in place", richer) ---
    visual_prompt: str
    camera: str = ""
    model: str = "wan2.2-t2v"                # which generator produced/should produce it
    first_frame_path: str | None = None
    last_frame_path: str | None = None       # the chaining handle (flf2v/i2v)
    reference_images: list[str] = []         # JSON; subject conditioning
    prompt_history: list[dict] = []          # JSON; [{prompt,model,ts,clip_path}]
    characters: list[str] = []               # character ids cast in this scene
    clip_path: str | None = None             # rendered scene video
    # --- CLIP PROPERTIES (new; timeline semantics on the scene) ---
    duration_frames: int                     # AUTHORITATIVE length, in PROJECT FPS frames
    source_in_frames: int = 0                # trim head (frames into the generated clip)
    source_out_frames: int | None = None     # trim tail (None = end)
    speed: float = 1.0                       # 0.25–4.0
    opacity: float = 1.0                     # 0.0–1.0
    volume: float = 1.0                      # 0.0–2.0 (scene's own audio, if any)
    transform: dict = {}                     # {scale,x,y,rotation,crop} — omitted when identity
    fade_in_frames: int = 0; fade_out_frames: int = 0
    transition_in: str | None = None         # "crossfade"|"cut"|... (to previous scene)
    generation_status: str = "none"          # none|queued|generating|ready|failed

class Keyframe(SQLModel, table=True):        # animate ONE property of ONE scene
    id: str; scene_id: str
    property: str                            # "opacity"|"transform.scale"|"volume"|...
    at_frame: int                            # PROJECT-FPS frame, relative to scene start
    value: float | dict
    easing: str = "linear"                   # linear|ease_in|ease_out|ease_in_out

class Track(SQLModel, table=True):           # AUDIO + CAPTION lanes (video lane = scenes)
    id: str; project_id: str
    kind: str                                # "audio" | "caption"
    role: str = ""                           # audio: "narration"|"music"|"sfx"; caption: "subtitle"|"title"
    name: str = ""
    muted: bool = False; volume: float = 1.0
    order_index: int = 0                     # stacking order for captions

class TrackItem(SQLModel, table=True):       # a clip on an audio/caption track
    id: str; track_id: str
    start_frame: int; duration_frames: int   # PROJECT-FPS frames
    # audio item:
    media_path: str | None = None            # rendered TTS/music/sfx asset
    tts_voice: str | None = None             # edge voice id OR "miso:clone:<sample>"
    tts_text: str | None = None              # source text (narration segment)
    source_in_frames: int = 0; source_out_frames: int | None = None
    gain: float = 1.0; fade_in_frames: int = 0; fade_out_frames: int = 0
    # caption item:
    text: str | None = None
    style: dict = {}                         # font,size,color,position,stroke — omitted when default

class MediaAsset(SQLModel, table=True):      # library (get_media / import_media / generate_*)
    id: str; project_id: str; owner_user_id: str
    kind: str                                # video|image|audio
    path: str; folder_id: str | None = None
    generation_status: str = "none"
    meta: dict = {}                          # duration, dims, exif, transcript ref

class Folder(SQLModel, table=True):
    id: str; project_id: str; name: str; parent_id: str | None = None

class UndoEntry(SQLModel, table=True):
    id: str                                  # u_*
    project_id: str; session_id: str; actor_user_id: str
    tool: str; inverse: dict; snapshot_ref: str | None = None
    ts: datetime; applied: bool = False      # True once an undo consumes it
```

### Units convention (a Palmier-beating rule, enforced everywhere)

- **Frames are the authoritative unit** for all timeline positions/durations, in
  **project fps** (Palmier mixes frames per its project fps; we make fps explicit
  in every snapshot and schema doc).
- Tool input schemas accept **either** `*_frames` (int) **or** `*_seconds`
  (number); the server converts seconds→frames with `round(seconds * fps)` and
  **echoes both** in outputs. Each tool spec states the unit per field. This kills
  the #1 agent error class (seconds-vs-frames confusion) that loose-typed tools
  invite.

### Mapping the timeline tools onto this model (no NLE engine)

| Tool (from docs 01–05) | Acts on |
|--|--|
| `move_clips` / `reorder_scenes` | rewrite `Scene.order_index` |
| `split_clip` | split one `Scene` into two at a frame (clone provenance, set trims) |
| `ripple_delete_ranges` | trim/remove across `Scene`s + shift later `order_index`/track items |
| `set_clip_properties` | set `Scene` clip props (speed/opacity/volume/transform/trims/fades) |
| `set_keyframes` | insert/replace `Keyframe` rows for a scene+property |
| `add_clips`/`insert_clips` | new `Scene` (or `TrackItem` for audio/caption) at an index/frame |
| `add_texts`/`add_captions` | `Track(kind="caption")` + `TrackItem(text=...)` |
| `set_narration`/`generate_audio` | `Track(kind="audio", role="narration")` + TTS `TrackItem` |
| `regenerate_scene`/`generate_video` | re-run Wan2.2 for a `Scene`, append `prompt_history`, swap `clip_path` |
| `attach_character_to_scene` | add character id to `Scene.characters`, wire S2V/refs |

**Render path is unchanged in spirit:** `postproduction.assemble()` already
concatenates scene clips + overlays narration + subtitles via ffmpeg. The
migration generalizes it to read **Tracks/TrackItems** (multiple audio lanes,
keyframed opacity/transform) instead of the implicit single narration track.
ffmpeg = the "complete track" compositor; no new engine.

### Migration steps (ordered, reversible)

1. **Add `src/flow/store/`** (`models.py`, `db.py` engine/session, `repo.py` CRUD +
   `snapshot()` + `undo_log`). SQLite file (`storage/flow.db`) for self-host;
   `DATABASE_URL` switches to Postgres for the managed cloud. Add `sqlmodel` +
   `alembic` to deps.
2. **Alembic migration `0001_init`**: create all tables above.
3. **Back-compat shim:** keep `flow.schemas.Scene/ShotList` as the *pipeline DTO*;
   add `store.repo.import_shotlist(shot_list) -> Project` so the existing
   topic→video pipeline seeds a Project (each pipeline `Scene` → store `Scene`
   with `duration_frames = duration * fps`, `order_index = id`). Existing
   benchmarks/CLI keep working; the agent edits the persisted Project.
4. **Migration `0002_clip_props_keyframes`**: (folded into init for greenfield;
   listed separately so the plan reads cleanly) scene clip props + `Keyframe`.
5. **Migration `0003_tracks`**: `Track`/`TrackItem`; backfill one
   `audio/narration` track per existing project from `ShotList.narration`
   segments, and (optionally) one `caption` track from the same segments.
6. **Wire `assemble()`** to read Tracks; gate behind a flag (`assembly.v2`) so the
   legacy path stays until parity is verified against the 30-scene film fixture.
7. **Undo log** table + `dispatch()` writes; expose via `undo` tool.

Each step is an independent Alembic revision (downgrade defined) → fully
reversible.

---

## Concrete Python module / endpoint layout (flow repo)

```
src/flow/
  agent/
    __init__.py
    loop.py            # AgentSession + run_turn (the nanocode-style loop)
    llm.py             # NvidiaBuildClient (chat/completions, /v1/models, kimi alias)
    context.py         # ContextBuilder.build(project_id, user) → system prompt
    mcp_client.py      # streamable-HTTP MCP client → 127.0.0.1:8765/mcp (listTools, callTool)
    schema.py          # MCP toolSpec.inputSchema → OpenAI {type:function,...}
    budget.py          # max-iterations, turn timeout, token ceiling
  mcp_server/
    __init__.py
    app.py             # FastMCP("flow"), streamable-http, loopback bind, registers REGISTRY
    dispatch.py        # auth → ownership → scope → credits → idempotency → execute → undo-log
    security.py        # bearer check, origin/host validators, token→claims (external agents)
    context_envelope.py# ToolContext (actor_user_id, project_id, session_id, mcp_token)
  tools/
    registry.py        # ToolSpec + @tool decorator (single source of truth)
    context.py         # get_project, get_media, inspect_media, inspect_timeline,
                       #   get_transcript, search_media, inspect_color, list_folders, list_models
    timeline.py        # add/insert/remove/move clips, set_clip_properties, set_keyframes,
                       #   split_clip, ripple_delete_ranges, sync_audio, undo, remove_tracks, reorder_scenes
    text.py            # add_texts, add_captions
    generate.py        # generate_video, generate_image, generate_audio, upscale_media, import_media
    color.py           # apply_color, apply_effect
    media.py           # create_folder, move_to_folder, rename_media/folder, delete_media/folder
    casting.py         # list_characters, create_character, attach_character_to_scene,
                       #   set_narration, plan_video (orchestrator)
    billing.py         # can_generate(user, est_cost), estimate_cost(model, duration)
  store/
    __init__.py
    models.py          # SQLModel tables (Project/Scene/Keyframe/Track/TrackItem/Media/Folder/UndoEntry)
    db.py              # engine, session factory, DATABASE_URL (sqlite→postgres)
    repo.py            # CRUD, snapshot(project_id), undo_log ops, import_shotlist()
  migrations/          # alembic; 0001_init, 0002_clip_props_keyframes, 0003_tracks
  api/
    __init__.py
    main.py            # FastAPI app factory; mounts routers; starts MCP client on boot
    agent_routes.py    # POST /agent/chat (SSE), GET /agent/models, POST /agent/undo
    project_routes.py  # CRUD for Studio (projects/scenes/tracks/media)  [non-agent UI calls]
    deps.py            # auth (JWT/API key → user), project ownership dependency
```

### HTTP endpoints (FastAPI, served by `flow-api`)

| Method | Path | Purpose |
|--|--|--|
| POST | `/agent/chat` | Drive the agent loop; SSE stream of tokens + tool activity. |
| GET  | `/agent/models` | Resolved model alias table (`kimi` → concrete id) from `/v1/models`. |
| POST | `/agent/undo` | Convenience: pop+apply latest undo for project (also available as a tool). |
| *    | `/projects/*` | Studio CRUD that the UI uses directly (not via the agent). |

### Process / deploy

- `flow-mcp`: `python -m flow.mcp_server.app` → loopback `127.0.0.1:8765`.
- `flow-api`: `uvicorn flow.api.main:app` → reverse-proxied (Caddy/Nginx) with
  the Studio; it holds `FLOW_MCP_TOKEN` + `NVIDIA_API_KEY` as secrets.
- Both in the orchestrator container (`python:3.12-slim` + ffmpeg); `flow-mcp`
  is a sidecar/second process (e.g. supervisord or two compose services sharing
  `storage/`).

### Config additions (`config/config.toml`)

```toml
[agent]
base_url = "https://integrate.api.nvidia.com/v1"
api_key = ""                 # nvapi-... (NVIDIA build)
model = "kimi"               # alias → resolved via /v1/models at boot
max_iterations = 12
turn_timeout_s = 180

[mcp]
host = "127.0.0.1"
port = 8765
path = "/mcp"
# token is minted at boot and shared with flow-api via secret/env (not stored here)

[billing]
enabled = true               # canGenerate / credits gate; false on pure self-host
```

---

## How this runtime beats Palmier (and plain nanocode)

| Dimension | Palmier | nanocode | **Flow 0.3 runtime** |
|--|--|--|--|
| Tool transport | MCP (Swift SDK), loopback | none (direct fns) | **MCP (Python SDK), loopback + bearer + origin validation** — same safety, plus per-user scoped tokens for external agents |
| Loop | (in-app, closed) | while-until-no-tool, errors→string | **same loop, OpenAI/kimi shape, + max-iter, timeout, idempotency, concurrency lock** |
| Multi-tenant | single desktop user | n/a | **per-tool auth + ownership + project scoping** (net-new) |
| Generation | proxies 3rd-party models | n/a | **Flow-owned Wan2.2 t2v/i2v/VACE/flf2v + voice clone, real cost estimates** |
| Credits gate | `canGenerate` boolean | n/a | **canGenerate + per-call cost estimate from owned pipeline pricing** |
| Context | `get_timeline` first | manual | **pre-injected, windowed, warning-annotated project+cast snapshot, refreshed per turn** |
| Undo | one action = one undo | n/a | **server-authoritative undo log, shared by in-app loop + external agents, LIFO per session** |
| Schemas | loose dicts | mini-DSL | **full JSON Schema, frames⇄seconds dual-unit with server conversion + echo** |
| Data model | mature NLE | n/a | **scenes-as-clips + keyframes + audio/caption tracks via reversible Alembic migrations — no NLE rebuild** |

---

## Open questions for downstream tool docs (01–05)

- Exact `code` enums per tool's error contract (this doc fixes the *shape*).
- Whether `plan_video` (orchestrator) is allowed to chain `generate_*` within a
  single turn or must stage scenes and let the user trigger generation (cost UX).
- Caption styling schema defaults (so the context builder knows what to omit).
