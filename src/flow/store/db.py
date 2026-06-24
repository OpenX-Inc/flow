"""Database engine + session for the agent store.

SQLite by default (file at ``~/.flow/flow.db`` — no server, self-host friendly);
set ``FLOW_DATABASE_URL`` (e.g. ``postgresql+psycopg://...``) for the managed
product. One small ``projects`` table holds each project as a JSON document plus
queryable ``user_id``/``revision`` columns — real transactions and concurrency,
consistent with the rest of the platform, without rewriting the tool layer.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine


class ProjectRow(SQLModel, table=True):
    __tablename__ = "projects"

    project_id: str = Field(primary_key=True)
    user_id: str = Field(default="local", index=True)
    revision: int = Field(default=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    doc: str = ""  # JSON-serialized Project aggregate


def _default_url() -> str:
    db_path = Path(os.path.expanduser("~/.flow/flow.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


def make_engine(url: str | None = None):
    url = url or os.environ.get("FLOW_DATABASE_URL") or _default_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session(engine) -> Session:
    return Session(engine)
