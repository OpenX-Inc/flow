"""Flow agent HTTP API — the surface the web frontend talks to.

- POST /agent/chat   : stream the agent's tool activity + reply over SSE
- GET  /agent/models : available models + the default (kimi)
- POST /agent/undo   : undo the last edit on a project

The blocking agent loop runs in a worker thread feeding an asyncio queue so SSE
streaming never blocks the event loop.
"""
