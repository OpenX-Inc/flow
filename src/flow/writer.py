"""Writer module — LLM-powered script and shot list generation."""

from __future__ import annotations

import json

import httpx

from flow.config import Config
from flow.schemas import Character, Scene, ShotList

SYSTEM_PROMPT = """\
You are a video scriptwriter. Given a topic and target duration, \
generate a structured shot list for an AI video generation pipeline.

Output ONLY valid JSON matching this schema:
{
  "title": "Video title",
  "narration": "Full narration text read aloud over the video",
  "scenes": [
    {
      "id": 1,
      "duration": 5,
      "visual_prompt": "Detailed visual description for AI video gen.",
      "camera": "Camera movement (e.g., slow dolly forward, wide shot)",
      "narration_segment": "The portion of narration for this scene",
      "characters": ["character_name"]
    }
  ],
  "characters": {
    "character_name": {
      "description": "Detailed physical appearance for consistency"
    }
  }
}

Rules:
- Each scene is exactly 5 seconds of video
- Number of scenes = duration / 5
- Visual prompts must be highly detailed and cinematic
- Include camera direction for each scene
- Narration should be engaging and match the visual pacing
- Character descriptions must be detailed for visual consistency
"""


class Writer:
    """Generates structured shot lists from topics using an LLM."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.llm = config.llm

    def generate(self, topic: str, duration: int = 60) -> ShotList:
        """Generate a shot list from a topic."""
        scene_count = duration // 5
        user_prompt = (
            f"Create a video about: {topic}\n"
            f"Target duration: {duration} seconds "
            f"({scene_count} scenes of 5 seconds each)\n"
            f"Aspect ratio: {self.config.aspect_ratio}"
        )

        response = self._call_llm(user_prompt)
        return self._parse_response(response)

    def _call_llm(self, user_prompt: str) -> str:
        """Call the LLM API and return the response text."""
        base_url = self.llm.base_url or _default_base_url(self.llm.provider)
        url = f"{base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.llm.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.llm.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=120) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> ShotList:
        """Parse LLM JSON response into a ShotList."""
        raw = json.loads(response)
        scenes = [Scene(**s) for s in raw.get("scenes", [])]
        characters = {
            k: Character(**v) for k, v in raw.get("characters", {}).items()
        }
        return ShotList(
            title=raw.get("title", "Untitled"),
            narration=raw.get("narration", ""),
            scenes=scenes,
            characters=characters,
        )


def _default_base_url(provider: str) -> str:
    """Return default base URL for known providers."""
    urls = {
        "openai": "https://api.openai.com/v1",
        "deepseek": "https://api.deepseek.com",
        "ollama": "http://localhost:11434/v1",
    }
    return urls.get(provider, "https://api.openai.com/v1")
