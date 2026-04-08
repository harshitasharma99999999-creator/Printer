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

    mp_dir = os.path.join(ROOT_DIR, ".mp")
    preferred = os.environ.get("INSTAGRAM_VIDEO_PATH", "").strip()
    stable = os.path.join(mp_dir, "last_short.mp4")
    if preferred and os.path.exists(preferred):
        video_path = preferred
    elif os.path.exists(stable):
        video_path = stable
    else:
        mp4_files = glob.glob(os.path.join(mp_dir, "*.mp4"))
        if not mp4_files:
            warning("No MP4 files found in .mp/ — skipping Instagram upload.")
            sys.exit(0)
        video_path = max(mp4_files, key=os.path.getmtime)
    if get_verbose():
        info(f"Instagram: uploading {video_path}")

    # Build caption from the latest video's subject stored in youtube.json
    caption = "#motivation #mindset #consciousness #shorts #reels #viral #fyp"
    subject = ""
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

    # Append the topic-specific affiliate product link written by YouTube pipeline
    _link_file = os.path.join(mp_dir, "affiliate_link.txt")
    _aff_link = ""
    if os.path.exists(_link_file):
        try:
            with open(_link_file, "r") as _f:
                _aff_link = _f.read().strip()
        except Exception:
            pass
    if not caption_override:
        try:
            from marketing import build_instagram_caption, get_latest_ebook_url

            ebook_url = get_latest_ebook_url(mp_dir)
            caption = build_instagram_caption(
                topic=subject,
                ebook_url=ebook_url,
                affiliate_link=_aff_link,
                include_disclosure=True,
            )
        except Exception:
            if _aff_link:
                caption += f"\n\n🛒 {_aff_link}"
    else:
        # Preserve override caption, but still append affiliate link if caller wants
        if _aff_link:
            caption += f"\n\n🛒 {_aff_link}"

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
