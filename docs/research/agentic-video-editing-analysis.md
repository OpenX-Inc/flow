# Agentic Video Editing — Landscape, Palmier Deep-Dive & Flow Architecture

**Date:** 2026-06-24
**Purpose:** Decide how to build Flow's agentic editing layer (the right-side
"video agent"). Anchored on a code-level teardown of the YC reference point
**Palmier Pro**, plus the surrounding open-source landscape.

---

## TL;DR / Verdict

- **The thesis is right and proven:** an agent should **operate the product
  through tools** (not chat in a sidebar). Palmier Pro (YC S24, ~3.5k stars)
  validates it and uses **MCP** to do it.
- **We borrow the pattern, not the code.** Palmier is **Swift / native macOS 26
  only** and **GPLv3** — unusable in our Linux VPS pipeline and incompatible with
  our MIT repo / proprietary cloud. We re-implement the pattern in our stack.
- **MCP is the right fit for us** (correcting an earlier take): the Flow OSS
  backend runs on a **VPS**, so we run an **MCP server on that VPS** exposing our
  video tools. Our in-app agent's model (via **NVIDIA build API, default
  `kimi`**) consumes those tools — and, for free, so can any external agent
  (Claude Code/Cursor) pointed at a self-hosted Flow.
- **Scope guard:** we do **not** build a multi-track NLE. Flow's primitive is the
  **scene**. Borrow the tool taxonomy, not the timeline UI.

---

## Palmier Pro — code-level teardown (cloned `palmier-io/palmier-pro`)

| Fact | Finding |
|--|--|
| Language | **Swift 6.2** (326 `.swift` files) — native Apple app |
| Platform | `Package.swift` → `platforms: [.macOS(.v26)]` — **macOS 26 Tahoe only**, Apple Silicon |
| License | **GPLv3** (strong copyleft) |
| Backend | **Convex** + **Clerk** auth (`convex-swift`, `clerk-ios`, `clerk-convex-swift`) |
| GPU/video | **Metal** CI kernels (`MetalCIKernelPlugin`), CoreImage/AVFoundation |
| Agent stack | official **MCP Swift SDK** (`modelcontextprotocol/swift-sdk`) |
| Other deps | Sparkle (mac updater), sentry-cocoa, swift-transformers, Lottie |

### Why it's macOS-only (and unusable for us)
Hard-pinned to macOS 26 and built on Apple-exclusive frameworks — Metal,
`Network.framework` (`NWListener`), SwiftUI/AppKit, CoreImage — none of which
exist on Linux/Windows. It is a desktop NLE, not a server component. Our backend
is a Linux VPS; there is nothing to run there.

### What GPLv3 means for us
GPLv3 is viral copyleft: redistributing a derivative obligates the **whole work**
to be GPLv3 + source-available. Our `flow` repo is **MIT** and the managed cloud
is proprietary, so **we cannot copy any of this code in**. Reading it to learn
patterns is fine (architecture/ideas aren't copyrighted); copying code is not.
Moot anyway since it's Swift/macOS.

### How Palmier wires the agent (the part worth stealing — as a pattern)
- A tiny **MCP server over streamable HTTP**, bound to **`127.0.0.1` loopback
  only** (never reachable from the LAN), endpoint `/mcp`, GET=SSE / POST=JSON-RPC,
  with origin/content-type/protocol validators and an OAuth well-known resource.
- The model connects, lists tools, calls them; the editor executes against the
  live project. **Full project context** (clips, tracks, durations, the prompt
  behind each clip) is available to the agent.

### Palmier's tool taxonomy (~35 tools) — our reference menu
```
Read/inspect : getTimeline, inspectTimeline, getMedia, inspectMedia, searchMedia,
               getTranscript, inspectColor, listFolders, listModels
Edit timeline: addClips, insertClips, removeClips, removeTracks, moveClips,
               setClipProperties, setKeyframes, splitClip, rippleDeleteRanges,
               syncAudio, undo
Text         : addTexts, addCaptions
Generate     : generateVideo, generateImage, generateAudio, upscaleMedia, importMedia
Effects      : applyColor, applyEffect
Media mgmt   : createFolder, moveToFolder, renameMedia, renameFolder,
               deleteMedia, deleteFolder
```

---

## Flow's design — "Palmier pattern, our stack"

Flow backend runs on a VPS, so the agent + MCP server live **server-side**. The
web right-panel is a thin chat UI streaming to/from the server-side agent.

```
Creator (browser right-panel, thin chat UI)
        │  natural language  ▲ streamed tokens / tool activity
        ▼                    │
  Agent loop (server, VPS)  ── MCP client + LLM caller (nanocode-style loop)
        │  list/call tools          │  chat w/ tool schemas
        ▼                           ▼
  MCP server (VPS, loopback)   NVIDIA build API  (default model: kimi; /v1/models to list)
        │  executes tools
        ▼
  Flow API / scene store  →  OpenX Cloud → Modal GPU (Wan 2.2 / VACE) + narration
        (full project + character context)
```

### Key technical note
Kimi (like all LLMs) speaks **OpenAI-style function calling**, not MCP natively.
So the **agent loop is the bridge**: it's an MCP *client* (reads tool schemas
from our MCP server, executes calls) **and** an LLM *caller* (hands those schemas
to kimi via NVIDIA build, receives `tool_calls`, executes, feeds results back,
repeats). This is exactly what Claude Code does internally and what we borrow
from **nanocode**.

### Our tool set (scene-based mapping of Palmier's taxonomy + characters)
```
Context  : get_project, list_scenes, list_characters, list_models
Scenes   : create_scene, update_scene(prompt/duration/narration),
           regenerate_scene(prompt, model, refs), reorder_scenes, delete_scene
Generate : start_generation, generate_image (keyframe/reference)
Casting  : attach_character_to_scene, create_character
Publish  : (later) export, publish_to_platform
```

### Borrow from Palmier's data model
Every Palmier clip remembers prompt + model + first/last frame + reference
images, enabling **regenerate in place**. Extend Flow's `Scene` to carry the
same (`model`, `first/last_frame`, `reference_images`, prompt history) so the
agent can reason about and re-roll a scene.

### Scope guard (avoid "too much")
- No multi-track NLE timeline / frame-accurate trim UI. Scene-grid + per-scene
  regenerate is v1.
- MCP server is loopback/authenticated on the VPS (mirror Palmier's localhost
  binding + origin validation) — don't expose it to the internet unauthenticated.

---

## Surrounding landscape
- **OpenCut** (open-source **web** NLE) is adding MCP + headless/scripting — the
  closest architectural cousin if we ever want a power-user scripting surface
  (web, not Swift).
- **HKUDS/VideoAgent** — academic all-in-one agentic video framework; good for
  tool decomposition ideas.
- **Koyal (YC 2026)** — "script/audio → personalized stories"; closest to Flow's
  *autonomous generation* thesis (vs Palmier's *assisted editing*). Track as a
  direct competitor.
- **Cardboard (YC)** — agentic editor for marketing teams (closed).
- **Voicebox** (OSS, 31k stars) — voice cloning + TTS + MCP; relevant to our
  voice roadmap.

## Next research step
Teardown of **nanocode**'s tool-calling loop (how it defines custom tools and
runs the model↔tool cycle with minimal deps), then implement the Flow agent loop
against the NVIDIA build endpoint (model listing + `kimi` default), backed by our
VPS MCP server.
