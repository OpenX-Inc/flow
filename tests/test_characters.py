"""Tests for character bank."""

import tempfile
from pathlib import Path

from flow.characters import CharacterBank


def test_register_and_get():
    with tempfile.TemporaryDirectory() as tmp:
        bank = CharacterBank(storage_dir=tmp)
        bank.register("hero", "A tall warrior with silver armor")
        ref = bank.get("hero")
        assert ref is not None
        assert ref.name == "hero"
        assert ref.description == "A tall warrior with silver armor"


def test_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        bank = CharacterBank(storage_dir=tmp)
        bank.register("villain", "Dark robed figure")

        # Reload from disk
        bank2 = CharacterBank(storage_dir=tmp)
        ref = bank2.get("villain")
        assert ref is not None
        assert ref.name == "villain"


def test_set_reference_image():
    with tempfile.TemporaryDirectory() as tmp:
        bank = CharacterBank(storage_dir=tmp)
        bank.register("hero", "A warrior")

        # Create a fake image
        img_path = Path(tmp) / "test.png"
        img_path.write_bytes(b"fake image data")

        bank.set_reference_image("hero", str(img_path))
        assert bank.has_reference("hero")


def test_list_characters():
    with tempfile.TemporaryDirectory() as tmp:
        bank = CharacterBank(storage_dir=tmp)
        bank.register("a", "Character A")
        bank.register("b", "Character B")
        assert len(bank.list_characters()) == 2
