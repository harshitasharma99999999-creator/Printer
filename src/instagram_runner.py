"""
Uploads the most recently generated Short (.mp4 in .mp/) to Instagram as a Reel.
Called after the Shorts pipeline completes in shorts_cron.yml.
"""
import glob
import json
import os
import sys

from config import ROOT_DIR, get_verbose
from status import error, info, warning, success


def main():
    username = os.environ.get("INSTAGRAM_USERNAME", "").strip()
    password = os.environ.get("INSTAGRAM_PASSWORD", "").strip()

    if not username or not password:
        warning("INSTAGRAM_USERNAME or INSTAGRAM_PASSWORD not set — skipping Instagram upload.")
        sys.exit(0)

    # Find the most recently modified MP4 in .mp/
    mp_dir = os.path.join(ROOT_DIR, ".mp")
    mp4_files = glob.glob(os.path.join(mp_dir, "*.mp4"))
    if not mp4_files:
        warning("No MP4 files found in .mp/ — skipping Instagram upload.")
        sys.exit(0)

    video_path = max(mp4_files, key=os.path.getmtime)
    if get_verbose():
        info(f"Instagram: uploading {video_path}")

    # Build caption from the latest video's subject stored in youtube.json
    caption = "#motivation #mindset #consciousness #shorts #reels #viral #fyp"
    try:
        yt_json = os.path.join(mp_dir, "youtube.json")
        with open(yt_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        accounts = data.get("accounts", [])
        if accounts:
            videos = accounts[0].get("videos", [])
            if videos:
                subject = videos[-1].get("subject", "")
                if subject:
                    caption = (
                        f"{subject}\n\n"
                        "#motivation #mindset #consciousness #shorts #reels #viral #fyp"
                    )
    except Exception:
        pass

    # Allow workflow to override caption (e.g. AFM uses a product-specific caption)
    caption_override = os.environ.get("INSTAGRAM_CAPTION", "").strip()
    if caption_override:
        caption = caption_override

    from classes.Instagram import Instagram
    ig = Instagram(username, password)
    try:
        url = ig.upload_reel(video_path, caption)
        success(f"Reel live at: {url}")
    except Exception as e:
        error(f"Instagram upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
