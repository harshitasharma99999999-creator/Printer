import os
import base64
import requests

from config import get_verbose, get_nanobanana2_api_key, get_nanobanana2_api_base_url, get_nanobanana2_model
from status import info, warning, success


class Pinterest:
    BASE = "https://api.pinterest.com/v5"

    def __init__(self):
        self.token = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()

    def _generate_image_bytes(self, prompt: str) -> bytes:
        """Generate square image via Gemini. Returns raw PNG bytes."""
        api_key = (
            get_nanobanana2_api_key()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        )
        if not api_key:
            return b""

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()

        try:
            r = requests.post(
                f"{base_url}/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseModalities": ["IMAGE"],
                        "imageConfig": {"aspectRatio": "2:3"},
                    },
                },
                timeout=120,
            )
            body = r.json()
            for candidate in body.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        return base64.b64decode(inline["data"])
        except Exception as e:
            if get_verbose():
                warning(f"Pinterest: image generation failed ({e}).")
        return b""

    def _upload_to_catbox(self, image_bytes: bytes) -> str:
        """Upload PNG to catbox.moe (free anonymous CDN). Returns public URL."""
        try:
            r = requests.post(
                "https://catbox.moe/user.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": ("pin.png", image_bytes, "image/png")},
                timeout=30,
            )
            url = r.text.strip()
            if r.ok and url.startswith("http"):
                return url
        except Exception as e:
            if get_verbose():
                warning(f"Pinterest: catbox upload failed ({e}).")
        return ""

    def create_pin(self, title: str, description: str, link: str, image_prompt: str = "") -> str:
        """Create a Pinterest pin. Returns pin URL."""
        if not self.token:
            if get_verbose():
                warning("Pinterest: PINTEREST_ACCESS_TOKEN not set — skipping.")
            return ""

        # Generate and host image
        image_url = ""
        if image_prompt:
            img_bytes = self._generate_image_bytes(image_prompt)
            if img_bytes:
                image_url = self._upload_to_catbox(img_bytes)

        if not image_url:
            # Fallback: dark minimal placeholder
            image_url = "https://picsum.photos/seed/dark/600/900"

        board_id = os.environ.get("PINTEREST_BOARD_ID", "").strip()
        payload = {
            "title": title[:100],
            "description": description[:500],
            "link": link,
            "media_source": {"source_type": "image_url", "url": image_url},
        }
        if board_id:
            payload["board_id"] = board_id

        try:
            r = requests.post(
                f"{self.BASE}/pins",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=30,
            )
            if r.ok:
                pin_id = r.json().get("id", "")
                url = f"https://pinterest.com/pin/{pin_id}/"
                if get_verbose():
                    success(f"Pinterest: pin created → {url}")
                return url
            if get_verbose():
                warning(f"Pinterest: pin failed {r.status_code} {r.text[:200]}")
        except Exception as e:
            if get_verbose():
                warning(f"Pinterest: {e}")
        return ""
