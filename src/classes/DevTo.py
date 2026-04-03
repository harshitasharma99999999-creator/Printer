import os
import requests

from config import get_verbose
from status import warning, success


class DevTo:
    """
    Dev.to API — publishes articles to dev.to.
    Free. Articles rank on Google and dev.to has a creator monetization program.
    API key: dev.to → Settings → Extensions → DEV Community API Keys → Generate
    """

    BASE = "https://dev.to/api"

    def __init__(self):
        self.api_key = os.environ.get("DEVTO_API_KEY", "").strip()

    def post_article(self, title: str, content_markdown: str, tags: list = None) -> str:
        """Publish article to Dev.to. Returns URL."""
        if not self.api_key:
            if get_verbose():
                warning("Dev.to: DEVTO_API_KEY not set — skipping.")
            return ""

        r = requests.post(
            f"{self.BASE}/articles",
            headers={
                "api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json={
                "article": {
                    "title": title,
                    "body_markdown": content_markdown,
                    "published": True,
                    "tags": tags or ["psychology", "selfimprovement", "mindset", "philosophy"],
                }
            },
            timeout=30,
        )

        if r.status_code in (200, 201):
            url = r.json().get("url", "")
            if get_verbose():
                success(f"Dev.to: article published → {url}")
            return url

        if get_verbose():
            warning(f"Dev.to: post failed {r.status_code} {r.text[:200]}")
        return ""
