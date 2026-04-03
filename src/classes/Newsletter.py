import os
import requests

from config import get_verbose
from status import warning, success


class Newsletter:
    """Beehiiv email newsletter integration."""

    BASE = "https://api.beehiiv.com/v2"

    def __init__(self):
        self.api_key = os.environ.get("BEEHIIV_API_KEY", "").strip()
        self.pub_id = os.environ.get("BEEHIIV_PUBLICATION_ID", "").strip()

    def send(self, subject: str, content_html: str) -> str:
        """Create and send a newsletter post. Returns URL."""
        if not self.api_key or not self.pub_id:
            if get_verbose():
                warning("Newsletter: BEEHIIV_API_KEY or BEEHIIV_PUBLICATION_ID not set — skipping.")
            return ""

        r = requests.post(
            f"{self.BASE}/publications/{self.pub_id}/posts",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "subject": subject,
                "content": {
                    "free": {
                        "web": {"html": content_html},
                        "email": {"html": content_html},
                    }
                },
                "status": "confirmed",
            },
            timeout=30,
        )

        if r.status_code in (200, 201):
            data = r.json().get("data", {})
            url = data.get("web_url", "")
            if get_verbose():
                success(f"Newsletter: Beehiiv post sent → {url}")
            return url

        if get_verbose():
            warning(f"Newsletter: Beehiiv failed {r.status_code} {r.text[:200]}")
        return ""
