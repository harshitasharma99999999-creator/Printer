"""Publish an Instagram Reel or create a complete manual-post fallback package.

Supported providers:
- Official Meta Graph API (recommended and safest)
- Upload-Post API (official third-party OAuth-based connector)
- instagrapi private API fallback (risky; may trigger checkpoints/account locks)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import uuid
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
        "provider": "meta_graph",
        "media_id": media_id,
        "url": permalink_response.json().get("permalink"),
    }


def publish_private_api(video_path: Path, content_path: Path) -> dict[str, Any]:
    """Upload a Reel through instagrapi.

    This is intentionally isolated from the official Graph API path because it
    uses Instagram's private mobile API. Use only when the business owner has
    accepted the operational risk.
    """

    try:
        from instagrapi import Client
        from instagrapi.exceptions import BadPassword, ChallengeRequired, LoginRequired
    except ImportError as error:
        raise RuntimeError(
            "instagrapi is not installed. Run: pip install -r requirements-grand-forno.txt"
        ) from error

    username = os.getenv("INSTAGRAM_USERNAME", "").strip()
    password = os.getenv("INSTAGRAM_PASSWORD", "").strip()
    session_json = os.getenv("INSTAGRAM_SESSION_JSON", "").strip()
    content = read_json(content_path)

    if not session_json and (not username or not password):
        raise RuntimeError(
            "INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD are required when "
            "INSTAGRAM_SESSION_JSON is unavailable"
        )

    client = Client()
    client.delay_range = [2, 5]

    if session_json:
        try:
            client.set_settings(json.loads(session_json))
            client.get_timeline_feed()
        except Exception:
            if not username or not password:
                raise RuntimeError(
                    "INSTAGRAM_SESSION_JSON is invalid/expired, and username/password "
                    "were not provided for refresh"
                )
            client = Client()
            client.delay_range = [2, 5]
            client.set_settings(json.loads(session_json))
            client.login(username, password)
    else:
        try:
            client.login(username, password)
        except ChallengeRequired as error:
            raise RuntimeError(
                "Instagram challenge/checkpoint required. Run scripts/gen_instagram_session.py "
                "locally, complete the verification, then save INSTAGRAM_SESSION_JSON as a "
                "GitHub secret."
            ) from error
        except BadPassword as error:
            raise RuntimeError("Instagram password rejected") from error
        except LoginRequired as error:
            raise RuntimeError("Instagram login required but failed") from error

    media = client.clip_upload(video_path, content["caption"])
    code = getattr(media, "code", None)
    media_id = getattr(media, "id", None) or getattr(media, "pk", None)
    return {
        "status": "uploaded",
        "provider": "instagrapi_private_api",
        "media_id": str(media_id) if media_id else None,
        "url": f"https://www.instagram.com/reel/{code}/" if code else None,
    }


def _upload_post_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Upload-Post API responses across sync and async shapes."""

    results = payload.get("results")
    instagram = None
    if isinstance(results, dict):
        instagram = results.get("instagram")
    elif isinstance(results, list):
        for platform_result in results:
            if not isinstance(platform_result, dict):
                continue
            if str(platform_result.get("platform", "")).lower() == "instagram":
                instagram = platform_result
                break

    if isinstance(instagram, dict):
        success = instagram.get("success")
        raw_status = str(instagram.get("status") or instagram.get("message") or "").lower()
        if success is False and raw_status not in {"queued", "processing", "pending", "submitted"}:
            raise RuntimeError(f"Upload-Post Instagram upload failed: {instagram}")
        url = (
            instagram.get("url")
            or instagram.get("post_url")
            or instagram.get("permalink")
            or instagram.get("share_url")
        )
        return {
            "status": "uploaded" if url or success else "submitted",
            "provider": "upload_post",
            "media_id": instagram.get("id") or instagram.get("post_id"),
            "url": url,
            "raw_status": instagram.get("status") or instagram.get("message"),
        }

    if payload.get("success") is False:
        raise RuntimeError(f"Upload-Post upload failed: {payload}")

    url = payload.get("url") or payload.get("post_url") or payload.get("permalink")
    return {
        "status": "uploaded" if url else "submitted",
        "provider": "upload_post",
        "media_id": payload.get("id") or payload.get("post_id"),
        "url": url,
        "request_id": payload.get("request_id"),
    }


def _poll_upload_post_status(
    api_base: str, api_key: str, request_id: str
) -> dict[str, Any] | None:
    deadline = time.monotonic() + int(os.getenv("UPLOAD_POST_POLL_SECONDS", "600"))
    headers = {"Authorization": f"Apikey {api_key}"}
    while time.monotonic() < deadline:
        response = requests.get(
            f"{api_base}/uploadposts/status",
            params={"request_id": request_id},
            headers=headers,
            timeout=60,
        )
        if response.status_code == 404:
            time.sleep(15)
            continue
        response.raise_for_status()
        payload = response.json()
        normalized = _upload_post_result(payload)
        status_text = str(
            normalized.get("raw_status") or payload.get("status") or normalized["status"]
        ).lower()
        if normalized.get("url") or status_text in {"uploaded", "published", "success", "complete", "completed"}:
            return normalized
        if status_text in {"failed", "error", "rejected"}:
            raise RuntimeError(f"Upload-Post async upload failed: {payload}")
        time.sleep(15)
    return None


def publish_upload_post(video_path: Path, content_path: Path) -> dict[str, Any]:
    """Upload an Instagram Reel via Upload-Post's OAuth-based API."""

    api_key = os.getenv("UPLOAD_POST_API_KEY", "").strip()
    user = os.getenv("UPLOAD_POST_USER", "").strip()
    api_base = os.getenv("UPLOAD_POST_API_BASE", "https://api.upload-post.com/api").rstrip("/")
    async_upload = os.getenv("UPLOAD_POST_ASYNC", "true").lower() != "false"
    request_id = os.getenv("UPLOAD_POST_REQUEST_ID", "").strip() or str(uuid.uuid4())
    content = read_json(content_path)

    if not api_key:
        raise RuntimeError("UPLOAD_POST_API_KEY is required")
    if not user:
        raise RuntimeError("UPLOAD_POST_USER is required")

    caption = content["caption"]
    headers = {"Authorization": f"Apikey {api_key}"}
    data: list[tuple[str, str]] = [
        ("user", user),
        ("platform[]", "instagram"),
        ("title", caption),
        ("instagram_title", caption),
        ("media_type", "REELS"),
        ("share_to_feed", "true"),
        ("async_upload", "true" if async_upload else "false"),
        ("request_id", request_id),
    ]

    with video_path.open("rb") as handle:
        response = requests.post(
            f"{api_base}/upload",
            headers=headers,
            data=data,
            files={"video": (video_path.name, handle, "video/mp4")},
            timeout=600,
        )
    if response.status_code >= 400:
        raise RuntimeError(
            "Upload-Post upload request failed "
            f"with HTTP {response.status_code}: {response.text[:1000]}"
        )
    payload = response.json()
    result = _upload_post_result(payload)
    result["request_id"] = result.get("request_id") or request_id

    if async_upload and not result.get("url"):
        polled = _poll_upload_post_status(api_base, api_key, request_id)
        if polled:
            polled["request_id"] = request_id
            return polled

    return result


def post_or_package(
    video_path: Path, content_path: Path, manual_dir: Path
) -> dict[str, Any]:
    if os.getenv("INSTAGRAM_MODE", "auto").lower() == "manual":
        return manual_package(video_path, content_path, manual_dir, "INSTAGRAM_MODE=manual")

    provider = os.getenv("INSTAGRAM_PROVIDER", "").strip().lower()
    if not provider:
        if os.getenv("INSTAGRAM_ACCESS_TOKEN") and os.getenv("INSTAGRAM_ACCOUNT_ID"):
            provider = "meta_graph"
        elif (
            os.getenv("INSTAGRAM_SESSION_JSON")
            or (os.getenv("INSTAGRAM_USERNAME") and os.getenv("INSTAGRAM_PASSWORD"))
        ):
            provider = "instagrapi"

    if provider in {"instagrapi", "private", "private_api"}:
        try:
            return publish_private_api(video_path, content_path)
        except Exception as error:
            return manual_package(
                video_path,
                content_path,
                manual_dir,
                f"Instagram private API auto-publish failed: {type(error).__name__}: {error}",
            )

    if provider in {"upload_post", "upload-post", "uploadpost"}:
        try:
            return publish_upload_post(video_path, content_path)
        except Exception as error:
            return manual_package(
                video_path,
                content_path,
                manual_dir,
                f"Upload-Post Instagram auto-publish failed: {type(error).__name__}: {error}",
            )

    if provider in {"meta_graph", "graph", "official"}:
        if not os.getenv("INSTAGRAM_ACCESS_TOKEN") or not os.getenv("INSTAGRAM_ACCOUNT_ID"):
            return manual_package(
                video_path, content_path, manual_dir, "Instagram Graph credentials are unavailable"
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

    if not provider:
        return manual_package(
            video_path, content_path, manual_dir, "Instagram credentials are unavailable"
        )

    return manual_package(
        video_path, content_path, manual_dir, f"Unsupported INSTAGRAM_PROVIDER={provider}"
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
