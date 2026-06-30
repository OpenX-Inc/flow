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

    def upload(self, video_path: Path, shot_list: ShotList,
               video_url: str | None = None) -> None:
        """Upload video to configured platforms.

        ``video_url`` is a public URL for the video — **required** for Instagram
        Reels (the Graph API ingests by URL, not binary) and optional for
        Facebook (falls back to a binary upload when omitted).
        """
        metadata = self._generate_metadata(shot_list)

        for platform in self.config.publish.platforms:
            try:
                if platform == "tiktok":
                    self._upload_tiktok(video_path, metadata)
                elif platform == "youtube":
                    self._upload_youtube(video_path, metadata)
                elif platform == "instagram":
                    self._upload_instagram(video_path, metadata, video_url)
                elif platform == "facebook":
                    self._upload_facebook(video_path, metadata, video_url)
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

    def _caption(self, metadata: dict) -> str:
        """Build a caption from metadata (title + description + hashtags)."""
        parts = [metadata.get("title", ""), metadata.get("description", "")]
        tags = " ".join(f"#{t}" for t in metadata.get("tags", []) if t)
        if tags:
            parts.append(tags)
        return "\n\n".join(p for p in parts if p)[:2200]

    def _upload_instagram(
        self, video_path: Path, metadata: dict, video_url: str | None = None
    ) -> None:
        """Publish an Instagram Reel via the Meta Graph API.

        Three steps: create a REELS media container (by public ``video_url``) →
        poll until processing FINISHED → publish. Needs a long-lived Page access
        token + the linked IG Business account id.
        """
        import time

        p = self.config.publish
        token = p.meta_page_access_token
        ig_id = p.instagram_business_account_id
        if not token or not ig_id:
            console.print(
                "  → Instagram: not configured "
                "(meta_page_access_token + instagram_business_account_id)"
            )
            return
        if not video_url:
            console.print(
                "  → Instagram: Reels require a public video_url — none provided, skipping"
            )
            return

        base = f"https://graph.facebook.com/{p.meta_graph_version}"
        # 1. Create the media container.
        r = httpx.post(
            f"{base}/{ig_id}/media",
            data={
                "media_type": "REELS", "video_url": video_url,
                "caption": self._caption(metadata), "access_token": token,
            },
            timeout=60,
        )
        r.raise_for_status()
        creation_id = r.json()["id"]

        # 2. Poll until the container finishes processing.
        for _ in range(30):
            s = httpx.get(
                f"{base}/{creation_id}",
                params={"fields": "status_code", "access_token": token}, timeout=30,
            )
            s.raise_for_status()
            status = s.json().get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise RuntimeError("Instagram container processing failed")
            time.sleep(5)
        else:
            raise RuntimeError("Instagram container not ready in time")

        # 3. Publish.
        pub = httpx.post(
            f"{base}/{ig_id}/media_publish",
            data={"creation_id": creation_id, "access_token": token}, timeout=60,
        )
        pub.raise_for_status()
        console.print("  ✓ Instagram: published")

    def _upload_facebook(
        self, video_path: Path, metadata: dict, video_url: str | None = None
    ) -> None:
        """Publish a video to a Facebook Page via the Meta Graph API.

        Uses the same Page access token as Instagram. Posts by ``file_url`` when a
        public URL is available, otherwise uploads the local file directly.
        """
        p = self.config.publish
        token = p.meta_page_access_token
        page_id = p.facebook_page_id
        if not token or not page_id:
            console.print(
                "  → Facebook: not configured (meta_page_access_token + facebook_page_id)"
            )
            return

        url = f"https://graph.facebook.com/{p.meta_graph_version}/{page_id}/videos"
        data = {
            "title": metadata.get("title", "")[:255],
            "description": metadata.get("description", "")[:1000],
            "access_token": token,
        }
        if video_url:
            data["file_url"] = video_url
            r = httpx.post(url, data=data, timeout=120)
        else:
            with open(video_path, "rb") as f:
                r = httpx.post(
                    url, data=data,
                    files={"source": ("video.mp4", f, "video/mp4")}, timeout=600,
                )
        r.raise_for_status()
        console.print("  ✓ Facebook: published")
