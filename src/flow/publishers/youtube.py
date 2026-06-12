"""YouTube Shorts uploader via Data API v3 (resumable upload)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

TOKEN_FILE = Path("config/.youtube_token.json")


def upload_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    client_id: str,
    client_secret: str,
    category_id: str = "22",  # People & Blogs
) -> str:
    """Upload a video to YouTube using resumable upload.

    Returns the video ID on success.
    """
    access_token = _get_access_token(client_id, client_secret)

    # Step 1: Initiate resumable upload
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    init_resp = httpx.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
        },
        json=metadata,
        timeout=30,
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]

    # Step 2: Upload video binary
    with open(video_path, "rb") as f:
        upload_resp = httpx.put(
            upload_url,
            content=f.read(),
            headers={"Content-Type": "video/mp4"},
            timeout=600,
        )
        upload_resp.raise_for_status()

    video_id = upload_resp.json().get("id", "")
    return video_id


def _get_access_token(client_id: str, client_secret: str) -> str:
    """Get a valid access token, refreshing if needed."""
    if TOKEN_FILE.exists():
        token_data = json.loads(TOKEN_FILE.read_text())
        refresh_token = token_data.get("refresh_token")
        if refresh_token:
            return _refresh_token(client_id, client_secret, refresh_token)

    raise RuntimeError(
        "No YouTube token found. Run the OAuth flow first:\n"
        "  python -m flow.publishers.youtube_auth"
    )


def _refresh_token(
    client_id: str, client_secret: str, refresh_token: str
) -> str:
    """Refresh an expired access token."""
    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    # Persist updated token
    token_data = {"refresh_token": refresh_token}
    if TOKEN_FILE.exists():
        token_data = json.loads(TOKEN_FILE.read_text())
    token_data["access_token"] = data["access_token"]
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))

    return data["access_token"]
