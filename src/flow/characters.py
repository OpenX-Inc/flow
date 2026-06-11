"""Character Bank — Maintain character consistency across scenes and videos."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class CharacterRef(BaseModel):
    """A stored character reference with description and image."""

    name: str
    description: str
    reference_image: str | None = None  # path to reference image


class CharacterBank:
    """Manages character references for visual consistency.

    Characters are stored on disk and reused across scenes and videos.
    On first appearance, a reference image is extracted from the generated
    scene. On subsequent appearances, the reference is injected into
    generation via S2V or I2V conditioning.
    """

    def __init__(self, storage_dir: str = "config/characters") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.storage_dir / "manifest.json"
        self._characters: dict[str, CharacterRef] = {}
        self._load()

    def _load(self) -> None:
        """Load character manifest from disk."""
        if self.manifest_path.exists():
            data = json.loads(self.manifest_path.read_text())
            for name, info in data.items():
                self._characters[name] = CharacterRef(**info)

    def _save(self) -> None:
        """Persist character manifest to disk."""
        data = {
            name: ref.model_dump() for name, ref in self._characters.items()
        }
        self.manifest_path.write_text(json.dumps(data, indent=2))

    def get(self, name: str) -> CharacterRef | None:
        """Get a character reference by name."""
        return self._characters.get(name)

    def register(
        self,
        name: str,
        description: str,
        reference_image: str | None = None,
    ) -> CharacterRef:
        """Register a new character or update existing one."""
        ref = CharacterRef(
            name=name,
            description=description,
            reference_image=reference_image,
        )
        self._characters[name] = ref
        self._save()
        return ref

    def set_reference_image(self, name: str, image_path: str) -> None:
        """Set/update the reference image for a character."""
        if name not in self._characters:
            raise KeyError(f"Character '{name}' not found")
        # Copy image to character storage
        src = Path(image_path)
        dst = self.storage_dir / f"{name}_ref{src.suffix}"
        dst.write_bytes(src.read_bytes())
        self._characters[name].reference_image = str(dst)
        self._save()

    def list_characters(self) -> list[CharacterRef]:
        """List all registered characters."""
        return list(self._characters.values())

    def has_reference(self, name: str) -> bool:
        """Check if a character has a reference image."""
        ref = self._characters.get(name)
        if ref is None:
            return False
        return (
            ref.reference_image is not None
            and Path(ref.reference_image).exists()
        )
