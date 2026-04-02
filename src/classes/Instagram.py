import json
import os
from pathlib import Path

from status import info, success, warning
from config import get_verbose


class Instagram:
    """
    Uploads a video as an Instagram Reel using instagrapi (headless, no browser).
    Uses INSTAGRAM_SESSION_JSON env var to persist session across runs.
    """

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def _get_client(self):
        from instagrapi import Client
        cl = Client()
        cl.delay_range = [1, 3]

        session_json = os.environ.get("INSTAGRAM_SESSION_JSON", "").strip()
        if session_json:
            try:
                settings = json.loads(session_json)
                cl.set_settings(settings)
                # Verify session is still valid without triggering a new login
                cl.get_timeline_feed()
                if get_verbose():
                    info("Instagram: session reused successfully — no login needed.")
                return cl
            except Exception as e:
                if get_verbose():
                    warning(f"Instagram: saved session invalid/expired ({e}). Falling back to login.")
                # Reset client and try fresh login
                cl = Client()
                cl.delay_range = [1, 3]

        # Fresh login (only reached if no session or session expired)
        try:
            cl.login(self.username, self.password)
            if get_verbose():
                info("Instagram: fresh login successful.")
            return cl
        except Exception as e:
            try:
                from instagrapi.exceptions import ChallengeRequired, BadPassword
                if isinstance(e, ChallengeRequired):
                    warning(
                        "Instagram: challenge required — session expired or login from new IP blocked.\n"
                        "Fix: run  python scripts/gen_instagram_session.py  on your LOCAL machine,\n"
                        "then update the INSTAGRAM_SESSION_JSON GitHub secret with the new value."
                    )
                elif isinstance(e, BadPassword):
                    warning("Instagram: wrong password — check INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD secrets.")
                else:
                    warning(f"Instagram: login failed — {e}")
            except ImportError:
                warning(f"Instagram: login failed — {e}")
            raise

    def upload_reel(self, video_path: str, caption: str) -> str:
        cl = self._get_client()
        media = cl.clip_upload(Path(video_path), caption)
        url = f"https://www.instagram.com/reel/{media.code}/"
        if get_verbose():
            success(f"Instagram Reel uploaded: {url}")
        return url
