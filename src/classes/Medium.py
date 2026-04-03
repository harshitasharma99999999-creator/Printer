import os
import requests

from config import get_verbose
from status import info, warning, success


class Medium:
    BASE = "https://api.medium.com/v1"

    def __init__(self):
        self.token = os.environ.get("MEDIUM_INTEGRATION_TOKEN", "").strip()

    def _get_user_id(self) -> str:
        r = requests.get(
            f"{self.BASE}/me",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10,
        )
        if r.ok:
            return r.json().get("data", {}).get("id", "")
        if get_verbose():
            warning(f"Medium: could not get user ID ({r.status_code}).")
        return ""

    def post_article(self, title: str, content_html: str, tags: list = None) -> str:
        """Publish article to Medium. Returns published URL."""
        if not self.token:
            if get_verbose():
                warning("Medium: MEDIUM_INTEGRATION_TOKEN not set — skipping.")
            return ""

        user_id = self._get_user_id()
        if not user_id:
            return ""

        r = requests.post(
            f"{self.BASE}/users/{user_id}/posts",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json={
                "title": title,
                "contentFormat": "html",
                "content": content_html,
                "tags": tags or ["psychology", "self-improvement", "mindset", "philosophy"],
                "publishStatus": "public",
            },
            timeout=30,
        )

        if r.ok:
            url = r.json().get("data", {}).get("url", "")
            if get_verbose():
                success(f"Medium: article published → {url}")
            return url

        if get_verbose():
            warning(f"Medium: post failed {r.status_code} {r.text[:200]}")
        return ""
