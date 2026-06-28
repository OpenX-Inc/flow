"""Flow MCP server — exposes the tool registry over MCP (streamable HTTP).

Serves the exact same ``tools.registry`` that the in-app agent uses, so any MCP
client (Claude Code, Cursor, Codex) can drive a self-hosted Flow project with the
same 41 tools. Bound to loopback, bearer-authenticated, with DNS-rebinding /
origin protection — the Palmier hardening pattern, on our stack.
"""
