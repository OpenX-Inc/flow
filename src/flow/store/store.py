"""ProjectStore — DB-backed persistence (SQLModel; SQLite default, Postgres via env).

Stores each Project aggregate as a JSON document in the ``projects`` table with
queryable ``user_id``/``revision`` columns. Same small interface the tools rely
on (save/load/list/delete), now with transactions, safe concurrency, and a
Postgres path — replacing the earlier JSON-file store.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import select

from flow.store.db import ProjectRow, get_session, make_engine
from flow.store.project import Project


class ProjectStore:
    def __init__(self, engine=None, url: str | None = None) -> None:
        self.engine = engine or make_engine(url)

    def save(self, project: Project, user_id: str = "local") -> None:
        with get_session(self.engine) as s:
            row = s.get(ProjectRow, project.project_id)
            doc = project.model_dump_json()
            if row is None:
                row = ProjectRow(project_id=project.project_id, user_id=user_id)
            row.user_id = user_id
            row.revision = project.revision
            row.updated_at = datetime.now(UTC)
            row.doc = doc
            s.add(row)
            s.commit()

    def load(self, project_id: str) -> Project | None:
        with get_session(self.engine) as s:
            row = s.get(ProjectRow, project_id)
            return Project.model_validate_json(row.doc) if row else None

    def list_projects(self, user_id: str | None = None) -> list[str]:
        with get_session(self.engine) as s:
            stmt = select(ProjectRow.project_id)
            if user_id is not None:
                stmt = stmt.where(ProjectRow.user_id == user_id)
            return sorted(s.exec(stmt).all())

    def delete(self, project_id: str) -> bool:
        with get_session(self.engine) as s:
            row = s.get(ProjectRow, project_id)
            if row is None:
                return False
            s.delete(row)
            s.commit()
            return True
