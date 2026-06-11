"""Scheduler module — Autonomous daily video generation."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console

from flow.config import Config
from flow.pipeline import Pipeline

console = Console()


class Scheduler:
    """Runs the pipeline on a schedule for autonomous content production."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.pipeline = Pipeline(config)

    def run(self) -> None:
        """Run the scheduler loop."""
        console.print("[bold]Flow Scheduler[/] — Running autonomously")

        topics = self._load_topics()
        for i, topic in enumerate(topics, 1):
            console.print(f"\n[bold]━━━ Video {i}/{len(topics)} ━━━[/]")
            try:
                result = self.pipeline.run(topic=topic, duration=60)
                console.print(f"[green]✓[/] Completed: {result}")
            except Exception as e:
                console.print(f"[red]✗[/] Failed: {e}")
            time.sleep(5)

        console.print("\n[bold green]All topics processed.[/]")

    def _load_topics(self) -> list[str]:
        """Load topics from file or generate them."""
        topics_file = self.config.scheduler.topics_file
        if topics_file and Path(topics_file).exists():
            return [
                line.strip()
                for line in Path(topics_file).read_text().splitlines()
                if line.strip()
            ]

        if self.config.scheduler.auto_generate_topics:
            return self._generate_topics()

        return ["Interesting facts about the ocean"]

    def _generate_topics(self) -> list[str]:
        """Use LLM to generate trending topics."""
        import json

        import httpx

        base_url = self.config.llm.base_url or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.llm.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.llm.model,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Generate 5 engaging short video topics "
                        "that would perform well on TikTok/YouTube"
                        " Shorts. Return ONLY a JSON array of "
                        "strings."
                    ),
                }
            ],
            "temperature": 0.9,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
        # Handle {"topics": [...]} format
        for v in parsed.values():
            if isinstance(v, list):
                return v
        return ["Amazing facts about space"]
