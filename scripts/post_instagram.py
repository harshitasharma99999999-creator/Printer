"""Publish an Instagram Reel or create a complete manual-post fallback package."""

from __future__ import annotations

import argparse
import os
import shutil
import time
from pathlib import Path
from typing import Any

import requests

from grand_forno_common import read_json, write_json


def manual_package(
    video_path: Path, content_path: Path, manual_dir: Path, reason: str
) -> dict[str, Any]:
    manual_dir.mkdir(parents=True, exist_ok=True)
    video_copy = manual_dir / "grand-forno-reel.mp4"
    shutil.copy2(video_path, video_copy)
    content = read_json(content_path)
    (manual_dir / "caption.txt").write_text(content["caption"] + "\n", encoding="utf-8")
    (manual_dir / "title.txt").write_text(content["title"] + "\n", encoding="utf-8")
    write_json(
        manual_dir / "manual-post.json",
        {
            "reason": reason,
            "instagram_account": "grand_forno",
            "video": video_copy.name,
            "caption": "caption.txt",
        },
    )
    return {
        "status": "manual_required",
        "reason": reason,
        "package": str(manual_dir),
        "url": None,
    }


def wait_for_container(container_id: str, token: str, version: str) -> None:
    deadline = time.monotonic() + 10 * 60
    while time.monotonic() < deadline:
        response = requests.get(
            f"https://graph.facebook.com/{version}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram container failed: {data}")
        time.sleep(10)
    raise TimeoutError("Instagram media container was not ready after 10 minutes")


def publish(video_path: Path, content_path: Path) -> dict[str, Any]:
    token = os.environ["INSTAGRAM_ACCESS_TOKEN"]
    account_id = os.environ["INSTAGRAM_ACCOUNT_ID"]
    version = os.getenv("INSTAGRAM_GRAPH_VERSION", "v23.0")
    content = read_json(content_path)

    create = requests.post(
        f"https://graph.facebook.com/{version}/{account_id}/media",
        data={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": content["caption"],
            "share_to_feed": "true",
            "access_token": token,
        },
        timeout=90,
    )
    create.raise_for_status()
    create_payload = create.json()
    container_id = create_payload["id"]
    upload_uri = create_payload["uri"]

    with video_path.open("rb") as handle:
        upload_response = requests.post(
            upload_uri,
            headers={
                "Authorization": f"OAuth {token}",
                "file_offset": "0",
                "Content-Type": "application/octet-stream",
            },
            data=handle,
            timeout=300,
        )
    upload_response.raise_for_status()
    wait_for_container(container_id, token, version)

    publish_response = requests.post(
        f"https://graph.facebook.com/{version}/{account_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=90,
    )
    publish_response.raise_for_status()
    media_id = publish_response.json()["id"]
    permalink_response = requests.get(
        f"https://graph.facebook.com/{version}/{media_id}",
        params={"fields": "permalink", "access_token": token},
        timeout=60,
    )
    permalink_response.raise_for_status()
    return {
        "status": "uploaded",
        "media_id": media_id,
        "url": permalink_response.json().get("permalink"),
    }


def post_or_package(
    video_path: Path, content_path: Path, manual_dir: Path
) -> dict[str, Any]:
    if os.getenv("INSTAGRAM_MODE", "auto").lower() == "manual":
        return manual_package(video_path, content_path, manual_dir, "INSTAGRAM_MODE=manual")
    if not os.getenv("INSTAGRAM_ACCESS_TOKEN") or not os.getenv("INSTAGRAM_ACCOUNT_ID"):
        return manual_package(
            video_path, content_path, manual_dir, "Instagram credentials are unavailable"
        )
    try:
        return publish(video_path, content_path)
    except Exception as error:
        return manual_package(
            video_path,
            content_path,
            manual_dir,
            f"Instagram auto-publish failed: {type(error).__name__}: {error}",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--manual-dir", required=True)
    args = parser.parse_args()
    print(post_or_package(Path(args.video), Path(args.content), Path(args.manual_dir)))


if __name__ == "__main__":
    main()
