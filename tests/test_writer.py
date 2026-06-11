"""Tests for the Writer module."""

import json

from flow.schemas import ShotList
from flow.writer import Writer


def test_parse_response():
    """Test parsing a valid LLM response into ShotList."""
    from flow.config import Config

    config = Config()
    writer = Writer(config)

    sample_response = json.dumps({
        "title": "Test Video",
        "narration": "This is a test narration.",
        "scenes": [
            {
                "id": 1,
                "duration": 5,
                "visual_prompt": "A sunset over the ocean",
                "camera": "slow pan right",
                "narration_segment": "This is a test.",
                "characters": [],
            }
        ],
        "characters": {},
    })

    result = writer._parse_response(sample_response)
    assert isinstance(result, ShotList)
    assert result.title == "Test Video"
    assert len(result.scenes) == 1
    assert result.scenes[0].visual_prompt == "A sunset over the ocean"
