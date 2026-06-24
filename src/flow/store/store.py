"""ProjectStore — JSON-file persistence for projects.

Dependency-light store fit for self-hosting: each project is one JSON file
under ``base_dir``. Writes are atomic (tmp file + rename). The interface is
deliberately small so a SQLModel/Postgres backend can replace it later without
touching the tools.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from src.flow.store.project import Project


class ProjectStore:
    def __init__(self, base_dir: str | Path = "~/.flow/projects") -> None:
        self.base_dir = Path(os.path.expanduser(str(base_dir)))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        return self.base_dir / f"{project_id}.json"

    def save(self, project: Project) -> None:
        """Atomically persist a project (tmp file + rename)."""
        path = self._path(project.project_id)
        data = project.model_dump_json(indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.base_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(data)
            os.replace(tmp, path)  # atomic on POSIX
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load(self, project_id: str) -> Project | None:
        path = self._path(project_id)
        if not path.exists():
            return None
        return Project.model_validate_json(path.read_text())

    def list_projects(self) -> list[str]:
        return sorted(p.stem for p in self.base_dir.glob("*.json"))

    def delete(self, project_id: str) -> bool:
        path = self._path(project_id)
        if path.exists():
            path.unlink()
            return True
        return False
