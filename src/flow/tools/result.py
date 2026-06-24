"""Tool result envelope — errors and gates are *values*, never exceptions.

Every tool returns one of these dicts. Feeding structured failures back to the
model (instead of raising) lets it self-correct (nanocode's insight, hardened
with typed codes). The gate result is how generation tools decline cleanly when
the user can't generate yet (not signed in / out of credits) — the agent then
explains it rather than crashing.
"""

from __future__ import annotations

from typing import Any


def ok(**fields: Any) -> dict:
    """Success envelope: ``{"ok": True, ...fields}``."""
    return {"ok": True, **fields}


def error(code: str, message: str, hint: str = "") -> dict:
    """Recoverable error the model can react to (e.g. ``not_found``, ``invalid``)."""
    err: dict[str, Any] = {"code": code, "message": message}
    if hint:
        err["hint"] = hint
    return {"ok": False, "error": err}


def gate(reason: str, *, estimated_credits: float = 0.0, action: str = "") -> dict:
    """canGenerate/credits gate — a generation tool declining cleanly."""
    g: dict[str, Any] = {"reason": reason}
    if estimated_credits:
        g["estimated_credits"] = estimated_credits
    if action:
        g["action"] = action  # e.g. "sign_in", "subscribe", "add_credits"
    return {"ok": False, "gate": g}
