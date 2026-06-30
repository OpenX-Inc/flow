"""Tests for the in-app agent: token-streaming loop + the create_character tool."""

import json

import flow.tools.all  # noqa: F401 — register all tools
from flow.agent.loop import Agent
from flow.store.project import Project
from flow.store.store import ProjectStore
from flow.tools.context import ToolContext, dispatch


def make_ctx() -> ToolContext:
    store = ProjectStore(url="sqlite://")  # in-memory
    project = Project(title="Test")
    store.save(project)
    return ToolContext(project=project, store=store)


class FakeClient:
    """Scripted streaming client. Each turn is (content_chunks, tool_calls)."""

    def __init__(self, turns: list[tuple[list[str], list[dict] | None]]) -> None:
        self.turns = list(turns)
        self.calls = 0

    def chat_stream(self, messages, tools=None, **kw):
        chunks, tool_calls = self.turns[self.calls]
        self.calls += 1
        for ch in chunks:
            yield {"type": "content", "text": ch}
        msg: dict = {"role": "assistant", "content": "".join(chunks)}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        yield {"type": "final", "message": msg}


def _tool_call(name: str, args: dict, cid: str = "call_1") -> dict:
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


# --- create_character tool ---

def test_create_character_adds_to_cast():
    ctx = make_ctx()
    res = dispatch(ctx, "create_character", {"name": "hero", "description": "a knight"})
    assert res["ok"] is True
    assert "hero" in ctx.project.characters
    assert ctx.project.characters["hero"].description == "a knight"


def test_create_character_rejects_duplicate():
    ctx = make_ctx()
    dispatch(ctx, "create_character", {"name": "hero", "description": "a knight"})
    res = dispatch(ctx, "create_character", {"name": "hero", "description": "other"})
    assert res["ok"] is False
    assert res["error"]["code"] == "exists"


def test_create_then_attach_character():
    ctx = make_ctx()
    dispatch(ctx, "create_character", {"name": "hero", "description": "a knight"})
    dispatch(ctx, "plan_video", {"scenes": [{"prompt": "opening shot"}]})
    scene_id = ctx.project.ordered_clips()[0].clip_id
    res = dispatch(ctx, "attach_character_to_scene",
                   {"scene_id": scene_id, "character_name": "hero"})
    assert res["ok"] is True
    assert "hero" in ctx.project.get_clip(scene_id).characters


# --- streaming agent loop ---

def test_run_stream_emits_tokens_then_reply():
    ctx = make_ctx()
    agent = Agent(FakeClient([(["Hel", "lo!"], None)]), ctx)
    events = list(agent.run_stream("hi"))
    assert [e["type"] for e in events] == ["token", "token", "reply"]
    assert events[0]["content"] == "Hel"
    assert events[-1]["content"] == "Hello!"


def test_run_stream_executes_tool_then_replies():
    ctx = make_ctx()
    turns = [
        ([], [_tool_call("create_character", {"name": "hero", "description": "knight"})]),
        (["done"], None),
    ]
    agent = Agent(FakeClient(turns), ctx)
    events = list(agent.run_stream("make a hero"))
    types = [e["type"] for e in events]

    assert "tool_start" in types and "tool_result" in types
    assert types.index("tool_start") < types.index("tool_result")
    assert types[-1] == "reply"

    start = next(e for e in events if e["type"] == "tool_start")
    assert start["tool"] == "create_character"
    res = next(e for e in events if e["type"] == "tool_result")
    assert res["result"]["ok"] is True
    # the tool really ran against the project
    assert "hero" in ctx.project.characters
    assert events[-1]["content"] == "done"


def test_run_collects_stream():
    ctx = make_ctx()
    turns = [
        ([], [_tool_call("create_character", {"name": "hero", "description": "knight"})]),
        (["all ", "set"], None),
    ]
    out = Agent(FakeClient(turns), ctx).run("make a hero")
    assert out["reply"] == "all set"
    assert len(out["tool_calls"]) == 1
    assert out["tool_calls"][0]["tool"] == "create_character"
