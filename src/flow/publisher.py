"""Publisher module — Auto-upload to TikTok, YouTube, Instagram."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from flow.config import Config
from flow.schemas import ShotList

console = Console()


class Publisher:
    """Publishes generated videos to social platforms."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def upload(self, video_path: Path, shot_list: ShotList) -> None:
        """Upload video to configured platforms."""
        for platform in self.config.publish.platforms:
            try:
                if platform == "tiktok":
                    self._upload_tiktok(video_path, shot_list)
                elif platform == "youtube":
                    self._upload_youtube(video_path, shot_list)
                elif platform == "instagram":
                    self._upload_instagram(video_path, shot_list)
                else:
                    console.print(f"  ⚠ Unknown platform: {platform}")
            except Exception as e:
                console.print(f"  ✗ Failed to upload to {platform}: {e}")

    def _upload_tiktok(self, video_path: Path, shot_list: ShotList) -> None:
        """Upload to TikTok via Content Posting API."""
        # TODO: Implement TikTok OAuth + upload
        console.print("  → TikTok upload: not yet implemented")

    def _upload_youtube(self, video_path: Path, shot_list: ShotList) -> None:
        """Upload to YouTube Shorts via Data API v3."""
        # TODO: Implement YouTube OAuth + videos.insert
        console.print("  → YouTube upload: not yet implemented")

    def _upload_instagram(self, video_path: Path, shot_list: ShotList) -> None:
        """Upload to Instagram Reels via Graph API."""
        # TODO: Implement Instagram Graph API upload
        console.print("  → Instagram upload: not yet implemented")
