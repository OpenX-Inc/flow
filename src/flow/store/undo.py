"""Undo log — server-authoritative LIFO of reversible edits.

Every mutating tool pushes an UndoEntry capturing what's needed to revert
(a ``before`` snapshot of the affected entities). The ``undo`` tool pops and
restores. Generation side-effects (paid output) are never destroyed by undo —
they detach, not delete (the asset stays in the library).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from src.flow.store.models import new_id


class UndoEntry(BaseModel):
    op_id: str = Field(default_factory=lambda: new_id("op"))
    tool: str  # tool name that produced the edit
    summary: str = ""  # human-readable description
    # Snapshot needed to revert. Store-defined shape, e.g.
    # {"clips": [...], "tracks": [...], "media": [...]} of pre-edit entities.
    before: dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
