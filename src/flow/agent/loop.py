"""The agent loop — kimi drives the Flow tools (nanocode pattern, OpenAI shape).

A turn appends the user message, then loops: ask the model with the tool schemas,
execute any tool_calls through ``dispatch`` (which enforces scoping/gate/undo),
feed results back as ``role:"tool"`` messages, and repeat until the model answers
with no tool call. A max-iteration cap is the safety net.
"""

from __future__ import annotations

import json

import src.flow.tools.all  # noqa: F401 — register all tools
from src.flow.agent.nvidia import NvidiaClient
from src.flow.tools.context import ToolContext, dispatch
from src.flow.tools.registry import openai_schemas

SYSTEM_RULES = (
    "You are Flow's in-app video agent. You operate the user's video project by "
    "calling tools — never claim an edit you did not make via a tool. Scenes are "
    "the video track; ordered scenes assemble (ffmpeg) into the final video, with "
    "audio (narration/music) and caption tracks alongside. Call get_project first "
    "if you need current state. Prefer plan_video to lay out a video, "
    "generate_video/start_generation to render, and the edit tools to refine. Be "
    "concise."
)


def build_system_prompt(ctx: ToolContext) -> str:
    p = ctx.project
    scenes = "; ".join(
        f"{c.clip_id}:{(c.visual_prompt or 'empty')[:40]} [{c.status.value}]"
        for c in p.ordered_clips()
    ) or "(no scenes yet)"
    cast = ", ".join(p.characters.keys()) or "(none)"
    return (
        f"{SYSTEM_RULES}\n\n"
        f"PROJECT {p.project_id} '{p.title}' — {p.fps}fps {p.width}x{p.height}, "
        f"rev {p.revision}, can_generate={ctx.can_generate}.\n"
        f"SCENES: {scenes}\nCAST: {cast}"
    )


class Agent:
    def __init__(self, client: NvidiaClient, ctx: ToolContext,
                 max_iterations: int = 12) -> None:
        self.client = client
        self.ctx = ctx
        self.max_iterations = max_iterations

    def run(self, user_message: str, history: list[dict] | None = None) -> dict:
        """Run one user turn to completion. Returns reply + trace."""
        messages: list[dict] = [{"role": "system", "content": build_system_prompt(self.ctx)}]
        messages += history or []
        messages.append({"role": "user", "content": user_message})

        tools = openai_schemas()
        calls_made: list[dict] = []

        for _ in range(self.max_iterations):
            resp = self.client.chat(messages, tools=tools)
            msg = resp["choices"][0]["message"]
            messages.append(msg)

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return {"reply": msg.get("content", ""), "tool_calls": calls_made,
                        "messages": messages}

            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                res = dispatch(self.ctx, name, args)
                calls_made.append({"tool": name, "args": args, "result": res})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(res),
                })

        return {"reply": "(stopped: max tool iterations reached)",
                "tool_calls": calls_made, "messages": messages}
