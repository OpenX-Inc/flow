"""Import this module to register all tools into the registry.

The MCP server and the agent loop both ``import src.flow.tools.all`` so the
``REGISTRY`` is fully populated before they read schemas.
"""

from __future__ import annotations

from src.flow.tools import (  # noqa: F401  (import for registration side-effects)
    analysis_read,
    color_tools,
    context_read,
    flow_native,
    generate,
    media_mgmt,
    text_tools,
    timeline_advanced,
    timeline_edit,
    undo_tool,
)
from src.flow.tools.registry import REGISTRY


def loaded_tool_names() -> list[str]:
    return sorted(REGISTRY.keys())
