"""
Uploads the most recently generated Short (.mp4 in .mp/) to X/Twitter as a native video tweet.
Uses Twitter API credentials from environment variables.
"""
import glob
import json
import os
import sys

from config import ROOT_DIR, get_verbose
from status import error, info, success, warning


def _resolve_video_path(mp_dir: str) -> str:
    preferred = os.environ.get("TWITTER_VIDEO_PATH", "").strip()
    stable = os.path.join(mp_dir, "last_short.mp4")

    if preferred and os.path.exists(preferred):
        return preferred
    if os.path.exists(stable):
        return stable

    mp4_files = glob.glob(os.path.join(mp_dir, "*.mp4"))
    if not mp4_files:
        return ""
    return max(mp4_files, key=os.path.getmtime)


def _build_tweet_text(mp_dir: str) -> str:
    override = os.environ.get("TWITTER_TEXT", "").strip()
    if override:
        return override[:280]

    subject = ""
    title = ""
    try:
        yt_json = os.path.join(mp_dir, "youtube.json")
        with open(yt_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        accounts = data.get("accounts", [])
        if accounts:
            videos = accounts[0].get("videos", [])
            if videos:
                latest = videos[-1]
                subject = str(latest.get("subject", "")).strip()
                title = str(latest.get("title", "")).strip()
    except Exception:
        pass

    ebook_url = ""
    ebook_file = os.path.join(mp_dir, "last_ebook_url.txt")
    if os.path.exists(ebook_file):
        try:
            with open(ebook_file, "r", encoding="utf-8") as f:
                ebook_url = f.read().strip()
        except Exception:
            pass

    affiliate_link = ""
    affiliate_file = os.path.join(mp_dir, "affiliate_link.txt")
    if os.path.exists(affiliate_file):
        try:
            with open(affiliate_file, "r", encoding="utf-8") as f:
                affiliate_link = f.read().strip()
        except Exception:
            pass

    base = title or subject or "New short"
    parts = [base]
    if ebook_url:
        parts.append(f"Read more: {ebook_url}")
    if affiliate_link:
        parts.append(f"Recommended: {affiliate_link}")
    parts.append("#shorts #motivation #mindset")

    tweet = "\n\n".join(part for part in parts if part).strip()
    return tweet[:280]


def main() -> None:
    api_key = os.environ.get("TWITTER_API_KEY", "").strip()
    api_secret = os.environ.get("TWITTER_API_SECRET", "").strip()
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "").strip()
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "").strip()

    if not all([api_key, api_secret, access_token, access_secret]):
        warning("Twitter secrets missing - skipping X upload.")
        sys.exit(0)

    mp_dir = os.path.join(ROOT_DIR, ".mp")
    video_path = _resolve_video_path(mp_dir)
    if not video_path:
        warning("No MP4 files found in .mp/ - skipping X upload.")
        sys.exit(0)

    tweet_text = _build_tweet_text(mp_dir)

    if get_verbose():
        info(f"X: uploading {video_path}")

    try:
        import tweepy

        auth = tweepy.OAuth1UserHandler(
            api_key,
            api_secret,
            access_token,
            access_secret,
        )
        api = tweepy.API(auth)
        media = api.media_upload(
            filename=video_path,
            chunked=True,
            media_category="tweet_video",
        )

        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
        )
        resp = client.create_tweet(
            text=tweet_text,
            media_ids=[media.media_id_string],
        )
        tweet_id = ""
        if getattr(resp, "data", None):
            tweet_id = str(resp.data.get("id", "")).strip()
        url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "X"
        success(f"X post live at: {url}")
    except Exception as e:
        error(f"X upload failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
