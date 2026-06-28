"""Tool registry: ``@tool`` decorator, param DSL → JSON Schema, OpenAI/MCP wrappers.

Param DSL (richer than nanocode's, to "beat Palmier"): each param is either a
shorthand string or a full dict spec.

  shorthand: ``"string"``, ``"integer"``, ``"number"``, ``"boolean"`` — append
             ``?`` to make optional (e.g. ``"integer?"``).
  full dict: {"type": "string"|"integer"|"number"|"boolean"|"array"|"object",
              "items": <param-spec>,      # for arrays
              "enum": [...],
              "minimum"/"maximum": n,      # numeric ranges
              "description": str,
              "optional": bool,            # default False
              "default": any,
              "examples": [...]}

A tool callable has signature ``fn(ctx, args: dict) -> dict`` and returns a
result envelope (see ``result.py``). ``mutating`` tools record undo; ``generates``
tools are subject to the canGenerate/credits gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

_SCALARS = {"string", "integer", "number", "boolean", "object"}


def _spec_to_schema(spec: Any) -> dict:
    """Convert one param spec (shorthand string or dict) to JSON Schema."""
    if isinstance(spec, str):
        base = spec[:-1] if spec.endswith("?") else spec
        if base not in _SCALARS:
            raise ValueError(f"unknown shorthand type: {spec!r}")
        return {"type": base}

    if not isinstance(spec, dict) or "type" not in spec:
        raise ValueError(f"invalid param spec: {spec!r}")

    schema: dict[str, Any] = {"type": spec["type"]}
    for key in ("enum", "minimum", "maximum", "description", "default", "examples"):
        if key in spec:
            schema[key] = spec[key]
    if spec["type"] == "array":
        items = spec.get("items", "string")
        schema["items"] = _spec_to_schema(items)
    return schema


def _is_optional(spec: Any) -> bool:
    if isinstance(spec, str):
        return spec.endswith("?")
    return bool(spec.get("optional", False)) or "default" in spec


def build_input_schema(params: dict[str, Any]) -> dict:
    """Build a JSON-Schema object from the param DSL."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, spec in params.items():
        properties[name] = _spec_to_schema(spec)
        if not _is_optional(spec):
            required.append(name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


@dataclass
class ToolSpec:
    name: str
    description: str
    params: dict[str, Any]
    fn: Callable[[Any, dict], dict]
    mutating: bool = False
    generates: bool = False  # subject to canGenerate/credits gate
    input_schema: dict = field(default_factory=dict)

    def openai_schema(self) -> dict:
        """OpenAI-style function-calling tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def mcp_schema(self) -> dict:
        """MCP tool definition."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


REGISTRY: dict[str, ToolSpec] = {}


def tool(
    name: str,
    description: str,
    params: dict[str, Any] | None = None,
    *,
    mutating: bool = False,
    generates: bool = False,
) -> Callable:
    """Register a tool. The decorated fn is ``fn(ctx, args) -> result dict``."""
    params = params or {}

    def decorator(fn: Callable[[Any, dict], dict]) -> Callable[[Any, dict], dict]:
        if name in REGISTRY:
            raise ValueError(f"duplicate tool name: {name}")
        REGISTRY[name] = ToolSpec(
            name=name,
            description=description,
            params=params,
            fn=fn,
            mutating=mutating,
            generates=generates,
            input_schema=build_input_schema(params),
        )
        return fn

    return decorator


def openai_schemas() -> list[dict]:
    return [t.openai_schema() for t in REGISTRY.values()]


def mcp_schemas() -> list[dict]:
    return [t.mcp_schema() for t in REGISTRY.values()]
