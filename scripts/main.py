"""Daily orchestration entrypoint for Grand Forno social automation."""

from __future__ import annotations

import argparse
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from generate_script import generate
from generate_video import render
from generate_voice import generate as generate_voice
from grand_forno_common import (
    ROOT,
    append_event,
    env_bool,
    read_json,
    select_next_item,
    write_json,
)
from post_instagram import manual_package, post_or_package
from post_youtube import upload as upload_youtube
from update_history import update_history


def attempt_upload(
    name: str,
    function: Callable[[], dict[str, Any]],
    log_path: Path,
) -> dict[str, Any]:
    try:
        result = function()
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


def run(dry_run: bool, allow_fallback: bool) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = ROOT / os.getenv("OUTPUT_DIR", "output")
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    log_path = ROOT / os.getenv("LOG_DIR", "logs") / f"{run_id}.jsonl"
    append_event(
        log_path,
        "run_started",
        run_id=run_id,
        dry_run=dry_run,
        allow_fallback=allow_fallback,
    )

    menu = read_json(ROOT / "data" / "menu_items.json")
    history_path = ROOT / "data" / "post_history.json"
    history = read_json(history_path)
    item = select_next_item(menu, history)
    selected_path = run_dir / "selected_item.json"
    write_json(selected_path, item)
    append_event(log_path, "item_selected", item_id=item["id"], item_name=item["name"])

    content_path = run_dir / "content.json"
    content = generate(item, allow_fallback, history)
    write_json(content_path, content)
    append_event(log_path, "copy_generated", title=content["title"])

    audio_path = run_dir / ("narration.mp3" if os.getenv("VOICE_API_KEY") else "narration.wav")
    generate_voice(content_path, audio_path, allow_fallback)
    append_event(log_path, "voice_generated", path=str(audio_path.relative_to(ROOT)))

    video_path = run_dir / "grand-forno-short.mp4"
    video_metadata = render(content_path, audio_path, video_path, allow_fallback)
    append_event(log_path, "video_generated", **video_metadata)

    manual_dir = run_dir / "instagram-manual"
    if dry_run:
        youtube = {"status": "skipped_dry_run", "url": None}
        instagram = manual_package(
            video_path, content_path, manual_dir, "Dry run: automatic upload skipped"
        )
    else:
        youtube = attempt_upload(
            "youtube", lambda: upload_youtube(video_path, content_path), log_path
        )
        instagram = attempt_upload(
            "instagram",
            lambda: post_or_package(video_path, content_path, manual_dir),
            log_path,
        )

    manifest = {
        "run_id": run_id,
        "dry_run": dry_run,
        "item": {"id": item["id"], "name": item["name"]},
        "content": str(content_path.relative_to(ROOT)),
        "video": str(video_path.relative_to(ROOT)),
        "video_metadata": video_metadata,
        "youtube": youtube,
        "instagram": instagram,
    }
    write_json(run_dir / "manifest.json", manifest)

    if not dry_run:
        history_entry = update_history(
            history_path, content_path, youtube, instagram, run_id
        )
        write_json(ROOT / "logs" / f"{run_id}-result.json", history_entry)
    append_event(log_path, "run_complete", youtube=youtube, instagram=instagram)

    if not dry_run and youtube["status"] == "failed":
        raise RuntimeError("YouTube upload failed; see the committed run log")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Render but do not upload")
    parser.add_argument(
        "--allow-fallback",
        action="store_true",
        help="Allow deterministic copy, local voice, and no-avatar rendering",
    )
    args = parser.parse_args()
    dry_run = args.dry_run or env_bool("DRY_RUN", False)
    allow_fallback = args.allow_fallback or env_bool("ALLOW_GENERATION_FALLBACK", False)
    try:
        manifest = run(dry_run=dry_run, allow_fallback=allow_fallback)
        print(f"Grand Forno run complete: {manifest['run_id']}")
        print(manifest)
    except Exception:
        # GitHub Actions retains this traceback, while JSONL contains structured milestones.
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
