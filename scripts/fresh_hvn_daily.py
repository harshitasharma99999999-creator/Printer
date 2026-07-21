"""Daily Fresh HVN beverage post runner for Instagram Reels and YouTube Shorts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import generate_video
from create_social_post_pack import create_pack
from generate_script import generate
from grand_forno_common import ROOT, read_json, write_json


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


def run_command(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return {
        "status": "complete" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true", help="Publish to Instagram and YouTube.")
    parser.add_argument("--skip-instagram", action="store_true")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--profile-directory", default=os.getenv("CHROME_PROFILE_DIRECTORY", "Profile 8"))
    args = parser.parse_args()

    if not os.getenv("FFMPEG_BINARY") and DEFAULT_FFMPEG.exists():
        os.environ["FFMPEG_BINARY"] = str(DEFAULT_FFMPEG)
        generate_video.FFMPEG = str(DEFAULT_FFMPEG)
    os.environ.setdefault("MUSIC_ONLY_DURATION_SECONDS", "18")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "output" / f"{run_id}-fresh-hvn-daily"
    run_dir.mkdir(parents=True, exist_ok=True)
    history_path = ROOT / "data" / "fresh_hvn_daily_history.json"
    menu = read_json(ROOT / "data" / "menu_items.json")
    history = load_history(history_path)
    item = select_next_beverage(menu, history)

    selected_path = run_dir / "selected_item.json"
    content_path = run_dir / "content.json"
    video_path = run_dir / "fresh-hvn-short.mp4"
    social_pack_dir = run_dir / "social-pack"
    write_json(selected_path, item)
    content = generate(item, allow_fallback=True, history=history)
    write_json(content_path, content)
    video_metadata = generate_video.render(content_path, None, video_path, allow_fallback=True)
    social_pack = create_pack(video_path, content_path, social_pack_dir)

    result: dict[str, Any] = {
        "run_id": run_id,
        "item_id": item["id"],
        "item_name": item["name"],
        "content": str(content_path.relative_to(ROOT)),
        "video": str(video_path.relative_to(ROOT)),
        "video_metadata": video_metadata,
        "social_pack": str(social_pack_dir.relative_to(ROOT)),
        "social_platforms": social_pack["platforms"],
        "instagram": {"status": "skipped"},
        "youtube": {"status": "skipped"},
    }

    if args.publish and not args.skip_instagram:
        result["instagram"] = run_command(
            [
                os.sys.executable,
                "scripts/post_instagram_desktop.py",
                "--video",
                str(video_path),
                "--content",
                str(content_path),
                "--profile-directory",
                args.profile_directory,
                "--publish",
            ]
        )

    if args.publish and not args.skip_youtube:
        result["youtube"] = run_command(
            [
                os.sys.executable,
                "scripts/post_youtube_desktop.py",
                "--video",
                str(video_path),
                "--content",
                str(content_path),
                "--profile-directory",
                args.profile_directory,
                "--publish",
            ]
        )

    history.setdefault("posts", []).append(
        {
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "item_id": item["id"],
            "item_name": item["name"],
            "title": content["title"],
            "instagram_status": result["instagram"]["status"],
            "youtube_status": result["youtube"]["status"],
            "run_id": run_id,
        }
    )
    write_json(history_path, history)
    write_json(run_dir / "manifest.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
