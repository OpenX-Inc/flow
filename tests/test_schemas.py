"""Tests for schema validation."""

from flow.schemas import Character, GeneratedClip, Scene, ShotList


def test_scene_defaults():
    scene = Scene(id=1, visual_prompt="test")
    assert scene.duration == 5
    assert scene.camera == ""
    assert scene.characters == []


def test_shot_list():
    shot_list = ShotList(
        title="Test",
        narration="Hello world",
        scenes=[Scene(id=1, visual_prompt="test")],
        characters={"hero": Character(description="A brave warrior")},
    )
    assert len(shot_list.scenes) == 1
    assert "hero" in shot_list.characters


def test_generated_clip():
    clip = GeneratedClip(scene_id=1, path="/tmp/test.mp4", duration=5.0)
    assert clip.last_frame_path is None
