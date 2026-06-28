"""FastAPI app exposing the agent: /agent/chat (SSE), /agent/models, /agent/undo."""

from __future__ import annotations

import asyncio
import json
import os
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from flow.agent.loop import Agent
from flow.agent.nvidia import NvidiaClient
from flow.config import Config, load_config
from flow.store.store import ProjectStore
from flow.tools.context import ToolContext, dispatch

app = FastAPI(title="Flow Agent API", version="0.3.0")

_store: ProjectStore | None = None
_config: Config | None = None


def get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config(os.environ.get("FLOW_CONFIG", "config/config.toml"))
    return _config


def _client() -> NvidiaClient:
    cfg = get_config().agent
    return NvidiaClient(api_key=cfg.api_key or None, base_url=cfg.base_url, model=cfg.model)


def _make_agent(project_id: str) -> Agent:
    project = get_store().load(project_id)
    if project is None:
        raise HTTPException(404, f"no project {project_id}")
    cfg = get_config()
    service = None
    if os.environ.get("FLOW_NO_GENERATION") != "1":
        from flow.agent.generation import GenerationService
        service = GenerationService()
    ctx = ToolContext(project=project, store=get_store(), services=service,
                      can_generate=cfg.billing.can_generate)
    return Agent(_client(), ctx, max_iterations=cfg.agent.max_iterations)


class ChatRequest(BaseModel):
    project_id: str
    message: str
    history: list[dict] = []


class UndoRequest(BaseModel):
    project_id: str


@app.get("/agent/models")
def models() -> dict:
    cfg = get_config().agent
    try:
        ids = _client().list_models()
    except Exception:  # noqa: BLE001 — degrade gracefully if the endpoint is unreachable
        ids = []
    return {"default": cfg.model, "resolved": NvidiaClient(model=cfg.model).model,
            "models": ids}


@app.post("/agent/undo")
def undo(req: UndoRequest) -> dict:
    agent = _make_agent(req.project_id)
    return dispatch(agent.ctx, "undo", {})


@app.post("/agent/chat")
async def chat(req: ChatRequest):
    agent = _make_agent(req.project_id)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    sentinel = object()

    def producer() -> None:
        try:
            for ev in agent.run_stream(req.message, req.history):
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as err:  # noqa: BLE001 — surface as an SSE error event
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "message": str(err)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    threading.Thread(target=producer, daemon=True).start()

    async def event_stream():
        while True:
            ev = await queue.get()
            if ev is sentinel:
                break
            yield {"data": json.dumps(ev)}

    return EventSourceResponse(event_stream())


def run(host: str | None = None, port: int | None = None) -> None:
    import uvicorn
    uvicorn.run(app, host=host or os.environ.get("FLOW_API_HOST", "127.0.0.1"),
                port=port or int(os.environ.get("FLOW_API_PORT", "8770")))


if __name__ == "__main__":
    run()
