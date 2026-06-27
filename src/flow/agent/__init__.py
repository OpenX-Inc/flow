"""Flow agent — the in-app loop that drives the tools via an LLM.

Model is served by the NVIDIA build API (OpenAI-compatible), default ``kimi``
(``moonshotai/kimi-k2.6``). The loop is an OpenAI-style tool-calling cycle
(nanocode pattern) that executes tools in-process through the dispatch chokepoint.
"""
