"""Tool execution context + dispatch chokepoint.

All tool calls go through ``dispatch`` so the guardrails Palmier/nanocode lack
are enforced in one place: project scoping, the canGenerate/credits gate,
required-arg validation, error-as-value catching, and automatic undo capture +
persistence for mutating tools.
"""

from __future__ import annotations

from dataclasses import dataclass

from flow.store.project import Project
from flow.store.store import ProjectStore
from flow.store.undo import UndoEntry
from flow.tools import result
from flow.tools.registry import REGISTRY


@dataclass
class ToolContext:
    project: Project
    store: ProjectStore
    user_id: str = "local"
    can_generate: bool = True  # plan/credits gate
    services: object | None = None  # generation/tts services (wired later)


def _snapshot(project: Project) -> dict:
    """Pre-edit snapshot of the mutable collections, for undo."""
    return {
        "clips": [c.model_dump() for c in project.clips],
        "tracks": [t.model_dump() for t in project.tracks],
        "media": [m.model_dump() for m in project.media],
        "folders": [f.model_dump() for f in project.folders],
        "characters": {k: v.model_dump() for k, v in project.characters.items()},
    }


def dispatch(ctx: ToolContext, name: str, args: dict) -> dict:
    """Execute a tool by name with all guardrails applied."""
    spec = REGISTRY.get(name)
    if spec is None:
        return result.error("unknown_tool", f"no tool named {name!r}")

    # Project scoping: a tool may only touch the context's project.
    pid = args.get("project_id")
    if pid is not None and pid != ctx.project.project_id:
        return result.error(
            "out_of_scope",
            "project_id does not match the active project",
            hint="omit project_id or use the active project",
        )

    # Required-arg validation from the generated schema.
    for req in spec.input_schema.get("required", []):
        if req not in args:
            return result.error("missing_arg", f"required argument missing: {req}")

    # Credits/plan gate for generation tools.
    if spec.generates and not ctx.can_generate:
        return result.gate(
            "generation requires an active plan with credits",
            action="subscribe",
        )

    # Capture undo state before a mutating call.
    before = _snapshot(ctx.project) if spec.mutating else None

    try:
        res = spec.fn(ctx, args)
    except Exception as err:  # noqa: BLE001 — surface as recoverable value
        return result.error("tool_error", f"{type(err).__name__}: {err}")

    # On a successful mutation: record undo, bump revision, persist.
    if spec.mutating and res.get("ok"):
        ctx.project.undo_stack.append(
            UndoEntry(tool=name, summary=res.get("summary", name), before=before or {})
        )
        ctx.project.touch()
        ctx.store.save(ctx.project)

    return res
