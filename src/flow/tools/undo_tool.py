"""Undo tool — pop the last edit and restore its pre-state snapshot.

Not itself a mutating tool (it must not push a new undo entry); it restores the
collections from the popped entry and persists directly.
"""

from __future__ import annotations

from src.flow.schemas import Character
from src.flow.store.media import Folder, MediaAsset
from src.flow.store.models import Clip
from src.flow.store.tracks import Track
from src.flow.tools import result
from src.flow.tools.context import ToolContext
from src.flow.tools.registry import tool


@tool("undo", "Revert the most recent timeline edit (create/update/delete/reorder/"
      "split/properties). Returns what was undone.",
      {"project_id": "string?"})
def undo(ctx: ToolContext, args: dict) -> dict:
    p = ctx.project
    if not p.undo_stack:
        return result.error("nothing_to_undo", "the undo stack is empty")
    entry = p.undo_stack.pop()
    before = entry.before
    p.clips = [Clip.model_validate(d) for d in before.get("clips", [])]
    p.tracks = [Track.model_validate(d) for d in before.get("tracks", [])]
    p.media = [MediaAsset.model_validate(d) for d in before.get("media", [])]
    p.folders = [Folder.model_validate(d) for d in before.get("folders", [])]
    p.characters = {
        k: Character.model_validate(v) for k, v in before.get("characters", {}).items()
    }
    p.touch()
    ctx.store.save(p)
    return result.ok(undone=entry.tool, summary=f"undid {entry.summary}")
