import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from status import success, warning, info


def _latest_post(content_dir: Path) -> dict | None:
    files = sorted(content_dir.glob("*.json"), reverse=True)
    newest = None
    newest_key = ""
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        key = str(data.get("published_at") or data.get("generated_utc") or path.name)
        if key > newest_key:
            newest_key = key
            newest = data
    return newest


def _build_tweet(post: dict, article_url: str) -> str:
    title = str(post.get("title", "")).strip()
    summary = str(post.get("summary", "")).strip()
    tags = [str(tag).strip().replace(" ", "") for tag in post.get("tags", []) if str(tag).strip()]
    hashtags = " ".join(f"#{tag}" for tag in tags[:3])

    parts = [title]
    if summary:
        parts.append(summary)
    parts.append(article_url)
    if hashtags:
        parts.append(hashtags)

    tweet = "\n\n".join(part for part in parts if part).strip()
    return tweet[:280]


def main() -> int:
    api_key = os.environ.get("TWITTER_API_KEY", "").strip()
    api_secret = os.environ.get("TWITTER_API_SECRET", "").strip()
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "").strip()
    access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "").strip()
    site_url = os.environ.get("BLOG_SITE_URL", "").strip().rstrip("/")
    content_dir = Path(os.environ.get("BLOG_CONTENT_DIR", "content/ai-crypto").strip())

    if not all([api_key, api_secret, access_token, access_token_secret]):
        warning("Twitter/X credentials missing - skipping article post.")
        return 0
    if not site_url:
        warning("BLOG_SITE_URL missing - skipping article post.")
        return 0
    if not content_dir.exists():
        warning(f"Content directory missing: {content_dir}")
        return 1

    post = _latest_post(content_dir)
    if not post:
        warning("No blog post JSON found to share on X.")
        return 1

    slug = str(post.get("slug", "")).strip()
    if not slug:
        warning("Latest blog post is missing slug.")
        return 1

    article_url = f"{site_url}/blog/{slug}"
    tweet_text = _build_tweet(post, article_url)

    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        resp = client.create_tweet(text=tweet_text)
        tweet_id = ""
        if getattr(resp, "data", None):
            tweet_id = str(resp.data.get("id", "")).strip()
        url = f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "X"
        success(f"Blog article shared on X: {url}")
        info(f"Article URL: {article_url}")
        return 0
    except Exception as exc:
        warning(f"X/Twitter article post failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
