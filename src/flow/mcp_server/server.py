"""The MCP server: registry → MCP tools, dispatched against a resolved project.

Each MCP tool call resolves the target project (``project_id`` arg, else
``FLOW_MCP_PROJECT_ID``), builds a ToolContext, and runs the shared ``dispatch``
chokepoint — so MCP clients get identical behavior (scoping, gate, undo, persist)
to the in-app agent. Transport is streamable HTTP at ``/mcp``.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import mcp.types as mcp_types
import src.flow.tools.all  # noqa: F401 — populate the registry
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from src.flow.store.store import ProjectStore
from src.flow.tools.context import ToolContext, dispatch
from src.flow.tools.registry import REGISTRY
from starlette.applications import Starlette
from starlette.routing import Mount

_store: ProjectStore | None = None
_service: object | None = None


def get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store


def get_service() -> object | None:
    """Lazily build the real GenerationService unless disabled."""
    global _service
    if _service is None and os.environ.get("FLOW_MCP_NO_GENERATION") != "1":
        from src.flow.agent.generation import GenerationService
        _service = GenerationService()
    return _service


def _resolve_project_id(arguments: dict) -> str | None:
    return arguments.get("project_id") or os.environ.get("FLOW_MCP_PROJECT_ID")


def _can_generate() -> bool:
    return os.environ.get("FLOW_MCP_CAN_GENERATE", "1") == "1"


def build_server() -> Server:
    server: Server = Server("flow-mcp")

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(name=t.name, description=t.description,
                           inputSchema=t.input_schema)
            for t in REGISTRY.values()
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list[mcp_types.ContentBlock]:
        def text(payload: dict) -> list[mcp_types.ContentBlock]:
            return [mcp_types.TextContent(type="text", text=json.dumps(payload))]

        if name not in REGISTRY:
            return text({"ok": False, "error": {"code": "unknown_tool",
                                                "message": f"no tool {name!r}"}})
        pid = _resolve_project_id(arguments)
        if not pid:
            return text({"ok": False, "error": {
                "code": "no_project",
                "message": "provide project_id (or set FLOW_MCP_PROJECT_ID)"}})
        store = get_store()
        project = store.load(pid)
        if project is None:
            return text({"ok": False, "error": {"code": "not_found",
                                                "message": f"no project {pid}"}})
        ctx = ToolContext(project=project, store=store, services=get_service(),
                          can_generate=_can_generate())
        return text(dispatch(ctx, name, arguments))

    return server


def create_app() -> Starlette:
    """ASGI app: bearer-auth + DNS-rebinding-protected streamable-HTTP at /mcp."""
    server = build_server()
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=os.environ.get(
            "FLOW_MCP_ALLOWED_HOSTS",
            "127.0.0.1,localhost,127.0.0.1:*,localhost:*",
        ).split(","),
        allowed_origins=os.environ.get(
            "FLOW_MCP_ALLOWED_ORIGINS",
            "http://127.0.0.1:*,http://localhost:*,*",
        ).split(","),
    )
    manager = StreamableHTTPSessionManager(
        app=server, json_response=True, stateless=True, security_settings=security,
    )
    token = os.environ.get("FLOW_MCP_TOKEN", "")

    async def _unauthorized(send) -> None:
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body",
                    "body": b'{"error":"unauthorized"}'})

    async def handle(scope, receive, send) -> None:
        if token:
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            if auth != f"Bearer {token}":
                await _unauthorized(send)
                return
        await manager.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with manager.run():
            yield

    return Starlette(routes=[Mount("/mcp", app=handle)], lifespan=lifespan)


def run(host: str | None = None, port: int | None = None) -> None:
    import uvicorn
    host = host or os.environ.get("FLOW_MCP_HOST", "127.0.0.1")
    port = port or int(os.environ.get("FLOW_MCP_PORT", "8765"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    run()
