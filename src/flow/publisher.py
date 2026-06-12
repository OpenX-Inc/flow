"""Publisher module — Auto-upload to TikTok, YouTube, Instagram."""

from __future__ import annotations

from pathlib import Path

import httpx
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
        metadata = self._generate_metadata(shot_list)

        for platform in self.config.publish.platforms:
            try:
                if platform == "tiktok":
                    self._upload_tiktok(video_path, metadata)
                elif platform == "youtube":
                    self._upload_youtube(video_path, metadata)
                elif platform == "instagram":
                    self._upload_instagram(video_path, metadata)
                else:
                    console.print(f"  ⚠ Unknown platform: {platform}")
            except Exception as e:
                console.print(f"  ✗ {platform}: {e}")

    def _generate_metadata(self, shot_list: ShotList) -> dict:
        """Generate upload metadata from shot list."""
        return {
            "title": shot_list.title,
            "description": shot_list.narration[:500],
            "tags": [],
        }

    def _upload_tiktok(
        self, video_path: Path, metadata: dict
    ) -> None:
        """Upload to TikTok via Content Posting API.

        Requires OAuth access token configured in config.
        Flow: init upload → upload video → publish.
        """
        token = self.config.publish.tiktok_access_token
        if not token:
            console.print("  → TikTok: no access token configured")
            return

        # Step 1: Initialize upload
        init_resp = httpx.post(
            "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "post_info": {
                    "title": metadata["title"][:150],
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": video_path.stat().st_size,
                },
            },
        )
        init_resp.raise_for_status()
        upload_url = init_resp.json()["data"]["upload_url"]

        # Step 2: Upload video binary
        with open(video_path, "rb") as f:
            upload_resp = httpx.put(
                upload_url,
                content=f.read(),
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": (
                        f"bytes 0-{video_path.stat().st_size - 1}"
                        f"/{video_path.stat().st_size}"
                    ),
                },
            )
            upload_resp.raise_for_status()

        console.print("  ✓ TikTok: uploaded")

    def _upload_youtube(
        self, video_path: Path, metadata: dict
    ) -> None:
        """Upload to YouTube Shorts via Data API v3.

        Requires OAuth credentials configured.
        Videos ≤60s and 9:16 are auto-detected as Shorts.
        Uses resumable upload protocol.
        """
        from flow.publishers.youtube import upload_to_youtube

        client_id = self.config.publish.youtube_client_id
        client_secret = self.config.publish.youtube_client_secret
        if not client_id or not client_secret:
            console.print("  → YouTube: no credentials configured")
            return

        upload_to_youtube(
            video_path=video_path,
            title=metadata["title"],
            description=metadata["description"],
            client_id=client_id,
            client_secret=client_secret,
        )
        console.print("  ✓ YouTube: uploaded")

    def _upload_instagram(
        self, video_path: Path, metadata: dict
    ) -> None:
        """Upload to Instagram Reels via Graph API.

        Requires Facebook Business account + app review.
        Two-step: create media container → publish.
        """
        console.print("  → Instagram: not yet implemented")
