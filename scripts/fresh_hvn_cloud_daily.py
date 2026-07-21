"""GitHub Actions friendly Fresh HVN beverage daily runner.

Unlike scripts/fresh_hvn_daily.py, this does not use desktop browser clicks. It
renders a music-only Fresh HVN beverage Short/Reel and publishes through API
providers configured in environment variables.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import generate_video
from generate_script import generate
from grand_forno_common import ROOT, append_event, read_json, write_json
from post_instagram import assert_fresh_hvn_target as assert_instagram_target
from post_instagram import post_or_package
from post_youtube import assert_fresh_hvn_target as assert_youtube_target
from post_youtube import upload as upload_youtube


BEVERAGE_TERMS = ("juice", "smoothie", "beverage", "detox", "drink", "can", "shake")
DEFAULT_FFMPEG = (
    Path.home()
    / "AppData"
    / "Local"
    / "Programs"
    / "Python"
    / "Python312"
    / "Lib"
    / "site-packages"
    / "imageio_ffmpeg"
    / "binaries"
    / "ffmpeg-win-x86_64-v7.1.exe"
)


def is_beverage(item: dict[str, Any]) -> bool:
    text = " ".join(
        str(item.get(key, ""))
        for key in ("id", "name", "category", "content_focus", "description")
    ).lower()
    return any(term in text for term in BEVERAGE_TERMS)


def load_history(path: Path) -> dict[str, Any]:
    if path.exists():
        return read_json(path)
    return {"posts": []}


def select_next_beverage(menu: list[dict[str, Any]], history: dict[str, Any]) -> dict[str, Any]:
    beverages = [item for item in menu if is_beverage(item)]
    if not beverages:
        beverages = menu
    recent_ids = [post.get("item_id") for post in history.get("posts", [])[-max(1, len(beverages) - 1):]]
    for item in beverages:
        if item["id"] not in recent_ids:
            return item
    return beverages[0]


def attempt(name: str, fn, log_path: Path) -> dict[str, Any]:
    try:
        result = fn()
        append_event(log_path, f"{name}_complete", result=result)
        return result
    except Exception as error:
        result = {
            "status": "failed",
            "url": None,
            "error": f"{type(error).__name__}: {error}",
        }
        append_event(log_path, f"{name}_failed", result=result)
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "output" / f"{run_id}-fresh-hvn-cloud"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = ROOT / "logs" / f"{run_id}-fresh-hvn-cloud.jsonl"
    history_path = ROOT / "data" / "fresh_hvn_daily_history.json"

    os.environ.setdefault("MUSIC_ONLY_DURATION_SECONDS", "18")
    if not os.getenv("FFMPEG_BINARY") and DEFAULT_FFMPEG.exists():
        os.environ["FFMPEG_BINARY"] = str(DEFAULT_FFMPEG)
        generate_video.FFMPEG = str(DEFAULT_FFMPEG)
    os.environ["UPLOAD_POST_USER"] = "fresh_hvn"
    os.environ["INSTAGRAM_TARGET_HANDLE"] = "fresh_hvn"
    os.environ["YOUTUBE_TARGET_HANDLE"] = "@fresh_hvn"
    assert_youtube_target()
    assert_instagram_target()

    menu = read_json(ROOT / "data" / "menu_items.json")
    history = load_history(history_path)
    item = select_next_beverage(menu, history)
    content_path = run_dir / "content.json"
    selected_path = run_dir / "selected_item.json"
    video_path = run_dir / "fresh-hvn-short.mp4"
    manual_dir = run_dir / "instagram-manual"

    append_event(log_path, "run_started", run_id=run_id, dry_run=args.dry_run)
    write_json(selected_path, item)
    append_event(log_path, "item_selected", item_id=item["id"], item_name=item["name"])

    content = generate(item, allow_fallback=True, history=history)
    write_json(content_path, content)
    append_event(log_path, "copy_generated", title=content["title"])

    video_metadata = generate_video.render(content_path, None, video_path, allow_fallback=True)
    append_event(log_path, "video_generated", **video_metadata)

    if args.dry_run:
        youtube = {"status": "skipped_dry_run", "url": None}
        instagram = {"status": "skipped_dry_run", "url": None}
    else:
        youtube = attempt("youtube", lambda: upload_youtube(video_path, content_path), log_path)
        instagram = attempt(
            "instagram",
            lambda: post_or_package(video_path, content_path, manual_dir),
            log_path,
        )

    manifest = {
        "run_id": run_id,
        "item_id": item["id"],
        "item_name": item["name"],
        "content": str(content_path.relative_to(ROOT)),
        "video": str(video_path.relative_to(ROOT)),
        "video_metadata": video_metadata,
        "youtube": youtube,
        "instagram": instagram,
    }
    write_json(run_dir / "manifest.json", manifest)

    history.setdefault("posts", []).append(
        {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "item_id": item["id"],
            "item_name": item["name"],
            "title": content["title"],
            "youtube": youtube,
            "instagram": instagram,
            "run_id": run_id,
        }
    )
    write_json(history_path, history)
    append_event(log_path, "run_complete", youtube=youtube, instagram=instagram)
    print(json.dumps(manifest, indent=2))

    if not args.dry_run:
        failed = [name for name, value in (("youtube", youtube), ("instagram", instagram)) if value["status"] == "failed"]
        if failed:
            raise RuntimeError(f"Upload failed for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
