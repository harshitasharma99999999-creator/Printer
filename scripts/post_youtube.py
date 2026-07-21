"""Upload the rendered video with YouTube Data API videos.insert."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from grand_forno_common import read_json, require_env

TARGET_YOUTUBE_HANDLE = "@fresh_hvn"


def assert_fresh_hvn_target() -> None:
    expected = os.getenv("YOUTUBE_TARGET_HANDLE", TARGET_YOUTUBE_HANDLE).strip()
    if not expected.startswith("@"):
        expected = f"@{expected}"
    if expected.lower() != TARGET_YOUTUBE_HANDLE:
        raise RuntimeError(
            f"YOUTUBE_TARGET_HANDLE must be {TARGET_YOUTUBE_HANDLE}, got {expected}"
        )


def upload(video_path: Path, content_path: Path) -> dict[str, Any]:
    assert_fresh_hvn_target()
    require_env("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
    content = read_json(content_path)
    credentials = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    body = {
        "snippet": {
            "title": content["title"][:100],
            "description": content["caption"],
            "tags": [tag.lstrip("#") for tag in content["hashtags"]],
            "categoryId": "26",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": os.getenv("YOUTUBE_PRIVACY_STATUS", "public"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(
            str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        ),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    return {
        "status": "uploaded",
        "video_id": video_id,
        "url": f"https://www.youtube.com/shorts/{video_id}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--content", required=True)
    args = parser.parse_args()
    print(upload(Path(args.video), Path(args.content)))


if __name__ == "__main__":
    main()
