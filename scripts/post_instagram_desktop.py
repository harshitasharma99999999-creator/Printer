"""Publish an Instagram Reel through the logged-in Chrome desktop session.

This is a free fallback for the fresh_hvn account when API posting is not
available. It requires Windows to be logged in/unlocked and Chrome Profile 8 to
remain logged into Instagram as fresh_hvn.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from desktop_automation import click, foreground_window, open_chrome, paste_text


ROOT = Path(__file__).resolve().parents[1]


def read_caption(content_path: Path) -> str:
    return json.loads(content_path.read_text(encoding="utf-8"))["caption"].strip()


def publish_reel(video_path: Path, content_path: Path, *, profile: str, publish: bool) -> None:
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not content_path.exists():
        raise FileNotFoundError(content_path)

    caption = read_caption(content_path)
    open_chrome("https://www.instagram.com/fresh_hvn/", profile)
    foreground_window(("Instagram", "Chrome"))

    # Dismiss Chrome restore bubble if present, then open Create > Post.
    click(1336, 112, delay=0.5)
    click(36, 467, delay=2.5)
    click(44, 519, delay=3)

    # Select From Computer and choose the file in the Windows file picker.
    click(675, 491, delay=2)
    paste_text(str(video_path.resolve()))
    time.sleep(0.3)
    from desktop_automation import send_key

    send_key(0x0D)
    time.sleep(8)

    # First-time reel confirmation, crop, edit, and final caption screen.
    click(677, 563, delay=4)
    click(852, 197, delay=5)
    click(1022, 197, delay=6)

    # Caption and share.
    click(806, 320, delay=0.7)
    paste_text(caption)
    time.sleep(2)
    if publish:
        click(1019, 196, delay=12)
        print("Instagram Share clicked. Check the browser for final confirmation.")
    else:
        print("Instagram Reel prepared. Publish flag was not set.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--profile-directory", default="Profile 8")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    publish_reel(
        Path(args.video),
        Path(args.content),
        profile=args.profile_directory,
        publish=args.publish,
    )


if __name__ == "__main__":
    main()
