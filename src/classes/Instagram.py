import json
import os
from pathlib import Path

from status import success, warning
from config import get_verbose


class Instagram:
    """
    Uploads a video as an Instagram Reel using instagrapi (headless, no browser).
    Uses INSTAGRAM_SESSION_JSON env var to persist session across runs.
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._cl = None

    def _get_client(self):
        from instagrapi import Client
        cl = Client()
        cl.delay_range = [2, 5]

        session_json = os.environ.get("INSTAGRAM_SESSION_JSON", "").strip()
        if session_json:
            try:
                cl.load_settings(json.loads(session_json))
                if get_verbose():
                    from status import info
                    info("Instagram: loaded saved session.")
            except Exception as e:
                if get_verbose():
                    warning(f"Instagram: could not load session ({e}), logging in fresh.")

        cl.login(self.username, self.password)
        return cl

    def upload_reel(self, video_path: str, caption: str) -> str:
        """
        Uploads video_path as an Instagram Reel with the given caption.
        Returns the public Reel URL, or empty string on failure.
        """
        cl = self._get_client()
        media = cl.clip_upload(Path(video_path), caption)
        url = f"https://www.instagram.com/reel/{media.code}/"
        if get_verbose():
            success(f"Instagram Reel uploaded: {url}")
        return url
