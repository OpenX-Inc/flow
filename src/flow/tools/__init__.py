"""Flow agent tools — the registry the MCP server and agent loop both consume.

One source of truth: every tool is declared once with ``@tool`` and a compact
param DSL; the registry renders it to JSON Schema and wraps that for either MCP
(``inputSchema``) or OpenAI-style function calling (``parameters``) so the two
surfaces never drift.
"""
