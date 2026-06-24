# nanocode — Agent Tool-Loop Teardown (reference for Flow's agent)

**Date:** 2026-06-24
**Source:** `1rgs/nanocode` (~2.4k stars). Single file `nanocode.py`, 271 lines,
zero deps (stdlib only). **No license declared → all-rights-reserved**, so we
learn the *pattern* and re-implement; we do not copy code.

---

## Why it's the right reference
It is the smallest correct implementation of "an LLM that calls tools in a loop"
— exactly the bridge our Flow agent needs (model ↔ tools), minus all framework
noise. ~120 lines of it is the loop + tool registry; the rest is CLI polish.

## The whole design in 4 pieces

### 1. A tool is just `(description, schema, function)`
```python
TOOLS = {
  "read":  ("Read file with line numbers", {"path":"string","offset":"number?"}, read),
  "edit":  ("Replace old with new",        {"path":"string","old":"string","new":"string","all":"boolean?"}, edit),
  "bash":  ("Run shell command",           {"cmd":"string"}, bash),
  ...
}
```
- Dict keyed by tool name → human description, a **mini type DSL** (`"string"`,
  `"number?"` where trailing `?` = optional), and the Python callable.
- Each tool fn takes one `args: dict`, returns a **string** result.

### 2. Schema generation (DSL → JSON Schema the model understands)
`make_schema()` expands the mini-DSL into JSON-Schema tool defs:
`"number?"` → `{type: integer}` + omitted from `required`; non-`?` → `required`.
This is the only translation layer between "how devs declare tools" and "what
the LLM API expects."

### 3. Safe dispatch
```python
def run_tool(name, args):
    try:    return TOOLS[name][2](args)
    except Exception as err:  return f"error: {err}"
```
Errors become tool-result strings (fed back to the model to self-correct), never
crash the loop. **This is the key robustness trick.**

### 4. The agentic loop (the heart)
```
append user msg
while True:
    resp = call_api(messages, system, tools=make_schema())
    for block in resp.content:
        if block.type == "text":     show it
        if block.type == "tool_use": result = run_tool(name, input)
                                     collect {tool_result, tool_use_id, content}
    append assistant content to messages
    if no tool_results: break          # model answered with no tool call → done
    append tool_results as next user msg  # feed results back, loop again
```
- **Loop until the model stops calling tools.** Every tool call's result is
  appended and the model is re-invoked with full history → multi-step reasoning.
- `tool_use_id` correlates each result to its call (required by the API).
- Conversation = flat `messages` list; assistant tool calls + tool results are
  just message turns.

## API shape (provider-agnostic via one swap)
- `call_api` POSTs `{model, system, messages, tools, max_tokens}` to a single
  endpoint. nanocode swaps **OpenRouter ↔ Anthropic** purely by base URL + auth
  header + model id. **Same trick lets us target the NVIDIA build endpoint.**
- Note: nanocode uses **Anthropic's** tool-call wire format (`content` blocks:
  `tool_use` / `tool_result`). NVIDIA build / kimi are **OpenAI-compatible**
  (`tool_calls` array + `role:"tool"` messages). Same algorithm, different field
  names — our loop targets the OpenAI shape.

---

## What Flow borrows (and what changes)

| nanocode | Flow agent |
|--|--|
| `TOOLS` dict (desc, DSL schema, fn) | same registry, but tool fns call **Flow API / scene store**, exposed via our **VPS MCP server** |
| stdlib tools (read/write/edit/bash/glob/grep) | video tools (list_scenes, regenerate_scene, reorder_scenes, attach_character, start_generation, list_models…) |
| Anthropic `tool_use`/`tool_result` blocks | OpenAI-style `tool_calls` + `role:"tool"` (what kimi/NVIDIA speak) |
| `MODEL` env, OpenRouter/Anthropic | **NVIDIA build endpoint**, default `kimi`, `/v1/models` to list |
| errors → string back to model | keep verbatim — critical for self-correction |
| loop until no tool_use | same; add max-iteration cap + per-tool auth/ownership checks |

### Concrete plan for the loop
1. Tool registry like nanocode's, but each fn is an MCP tool on the VPS (so
   external agents can use the same tools — the Palmier angle).
2. `call_api` → NVIDIA build (`/v1/chat/completions`, OpenAI tool-calling),
   default model `kimi`, model list from `/v1/models`.
3. Loop: send tools+messages → if `tool_calls`, execute via MCP, append each as
   a `role:"tool"` message (`tool_call_id`), re-invoke; else stream final text.
4. Guardrails nanocode lacks but we need: **max iterations**, **auth/ownership**
   on every tool (scenes/characters belong to the user), and **scoped tools**
   (the agent only touches the current project).
5. System prompt carries **full project + character context** (Palmier's
   "full project context" + the user's "orchestrator knows the video and cast").

## Net
nanocode = the loop + tool-registry pattern (provider-agnostic, error-as-string,
loop-until-done). Palmier = the product-as-tools thesis + tool taxonomy + MCP
server. Flow = both, on our VPS, model = kimi via NVIDIA build, tools operate the
scene/character/generation pipeline.
