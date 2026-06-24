# Agentic Video Editing — Landscape & Architecture Analysis

**Date:** 2026-06-24
**Purpose:** Decide how to build Flow's agentic editing layer (the right-side
"video agent"). Anchored on the most-cited YC reference point — **Palmier Pro** —
plus the surrounding open-source landscape.

---

## TL;DR / Verdict

Palmier Pro (YC S24) validates the thesis we're betting on, but its
implementation is **architecturally different** from Flow:

- **Right call?** The *pattern* — yes, strongly. "An agent **operates** the
  product via tools, instead of a chatbot suggesting things in a sidebar" — is
  the correct, fundable bet. Palmier has ~3.5k GitHub stars and was used to cut
  15+ YC launch videos.
- **Borrow the code?** No. Palmier is **Swift / native macOS (Tahoe-only)** and
  drives editing through an **MCP server consumed by external coding agents**
  (Claude Code, Cursor, Codex). Flow is a **web platform** (Next.js + FastAPI)
  whose users are creators in a browser, not developers in Claude Code.
- **Too much?** A full multi-track NLE timeline is out of scope for us. Flow's
  primitive is the **scene**, not a track. We borrow the *concepts*, not the NLE.

**Decision: build a web-native, in-app agent that calls our own Flow API as
tools, with full project + character context. "Palmier pattern, our stack."**

---

## What Palmier Pro Is (the reference)

- **Company:** Palmier, YC Summer 2024. 2-person SF team (Marcos Rico Peng,
  ex-LinkedIn infra; Harrison Tin, ex-Microsoft). Pivoted from "AI that
  understands any codebase" → video. Public launch mid-June 2026.
- **Product:** Swift-native macOS NLE (Premiere-like: media library, preview,
  multi-track timeline). Requires macOS 26 (Tahoe), Apple Silicon only.
- **License:** GPLv3. Repo `github.com/palmier-io/palmier-pro` (~3,500 stars,
  ~291 forks). Open: editor + MCP server + in-app agent chat. Closed: the
  generative-AI processing pipeline (the paid part).
- **Pricing:** Editor + MCP free, no account. Generation credits: Pro $29/mo
  (5,000), Max $69/mo (12,000). Models: Seedance, Kling, Veo 3.1, Nano Banana
  Pro, Grok Imagine.
- **Export:** MP4 (H.264/265, ProRes) + NLE XML for Premiere/DaVinci (not a
  one-way door).

### The three ideas that make it notable
1. **AI generation is a timeline primitive, not an import.** You generate on the
   timeline; regeneration happens in place. No "download → reimport → lose
   context" loop, no `final_v3_actually_final.mp4` folder.
2. **Every clip remembers how it was made** — prompt, model, first/last frame,
   reference images stay attached to the clip, so you can re-run or tweak from
   there.
3. **The agent operates the editor.** A local MCP server (`127.0.0.1:19789/mcp`)
   exposes the editor as tools. An external agent (Claude Code/Desktop, Codex,
   Cursor) connects and: reads the timeline, adds clips, trims, splits, reorders,
   generates by prompt, regenerates clips, queries project state — **with full
   project context** (what's on each track, durations, the prompt behind each
   clip).

> "Instead of bolting an AI assistant onto a product, you expose the product
> itself as a tool an agent can drive." — the load-bearing insight.

---

## Why we can't just adopt it

| Dimension | Palmier Pro | OpenX Flow |
|--|--|--|
| Platform | Native macOS app (Tahoe only) | Web (Next.js) + FastAPI |
| Language | Swift | TS / Python |
| Agent model | **External** coding agent via MCP | **In-app** web agent for creators |
| User | Founders/marketers in Claude Code | Creators in a browser |
| Editing unit | Multi-track NLE timeline | Scene list (script → scenes) |
| Generation | Calls 3rd-party model APIs (Kling/Veo…) | Our own Wan 2.2 / VACE on Modal |

The MCP-for-external-agents model assumes the user already runs Claude Code on a
Mac. Our creator opens a browser tab. So the *delivery mechanism* is wrong for
us even though the *pattern* is right.

---

## What we borrow (pattern, not code)

1. **Agent operates the product.** Flow's right-side agent is an LLM loop that
   **calls real tools** against our Flow API — not a chat box that gives advice.
   Tools (first cut): `list_scenes`, `get_project`, `create_scene`,
   `regenerate_scene(prompt, model, refs)`, `reorder_scenes`, `update_narration`,
   `list_characters`, `attach_character_to_scene`, `start_generation`.
2. **Scene carries its generation metadata.** Extend the Scene model to keep
   `prompt`, `model`, `first/last frame`, and `reference_images` so a scene can
   be **regenerated in place** (and the agent can reason about it). Mirrors
   Palmier's "clip remembers how it was made."
3. **Full project + character context.** The agent is given the project's scenes
   (prompt/duration/status) and the user's character library, so it edits
   coherently — directly satisfies "the orchestrator should have context of the
   video being produced and even characters."
4. **Generation as an in-place primitive.** For us the primitive is the *scene*:
   generate / regenerate happens on the scene, never as an external import.

## What we explicitly do NOT build (avoid "too much")
- No multi-track NLE timeline, no frame-accurate trim/split UI. Scene-grid +
  per-scene regenerate is the right scope for v1.
- No MCP server / external-agent integration (revisit later as a *power-user*
  add-on — see OpenCut below — but it is not the creator path).
- No Swift / desktop anything.

---

## Surrounding landscape (for context)

- **OpenCut** (open-source web NLE) is *adding* an MCP server + headless/scripting
  mode + multi-platform — signal that "editor as agent-drivable tool" is becoming
  table stakes. If we ever want a power-user scripting surface, this is the
  closer architectural cousin (web, not Swift).
- **HKUDS/VideoAgent** — academic "all-in-one agentic framework for video
  understanding, editing, remaking." Good reference for tool decomposition.
- **Cardboard (YC)** — agentic video editor for growth/marketing teams (closed).
- **Koyal (YC 2026)** — "agentic AI filmmaking: script/audio → personalized
  stories." This is the closest to Flow's *autonomous generation* thesis (vs.
  Palmier's *assisted editing*). Worth tracking as a direct competitor.
- **Voicebox** (open source, 31k stars) — voice cloning + TTS + MCP. Relevant to
  our voice-cloning roadmap.

---

## Implication for Flow's architecture

Flow already separates: orchestrator (writer/planner) → generator (Wan on Modal)
→ assembly → publish. The agent layer slots in as a **controller** over the
orchestrator + scene store:

```
Creator (browser, right-side agent panel)
        │  natural language
        ▼
  Agent loop (LLM: NVIDIA build API, default `kimi`; lists models from endpoint)
        │  tool calls (JSON)
        ▼
  Flow API tools  ── scenes / characters / generation (full project context)
        │
        ▼
  OpenX Cloud → Modal GPU (Wan 2.2 / VACE) + narration (edge-tts / MisoTTS)
```

Next research step: the agent **tool-calling loop** itself (ReAct-style: model
emits tool calls, we execute, feed results back). Reference the `nanocode` repo
for a minimal, dependency-light tool-use loop to borrow from, then implement
against the NVIDIA build endpoint with model-listing and `kimi` as default.
