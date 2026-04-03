"""
Dark-theme quote card image post pipeline.
Generates scroll-stopping dark images and posts to:
  - Instagram (static photo post via instagrapi)
  - YouTube Posts tab (Community Post via internal youtubei/v1 API)
Runs every 6 hours via image_post_cron.yml.
"""
import json
import os
import random
import textwrap
from io import BytesIO
from uuid import uuid4

import requests

from config import (
    ROOT_DIR,
    get_nanobanana2_api_base_url,
    get_nanobanana2_api_key,
    get_nanobanana2_model,
    get_verbose,
)
from llm_provider import generate_text
from status import error, info, success, warning

TOPICS = [
    # Dark relationship / psychology
    "people show you who they are in the first 90 days — you choose not to see it",
    "the person who loves you most will hurt you with the truth — the rest lie to keep you",
    "attachment is not love — it is the fear of being alone wearing love's mask",
    "most relationships fail because people fall in love with potential not reality",
    "the one who left taught you more about yourself than the one who stayed",
    "people do not leave relationships — they leave people who stopped making them feel chosen",
    "you cannot heal in the same environment that made you sick",
    "those who gaslight you count on your empathy to silence your instincts",
    "the loudest person in the room is always the most insecure",
    "people treat you how you allow them to — silence is a permission",
    # Spiritual / manifesting
    "you are already what you are seeking",
    "your thoughts create the universe you live in",
    "manifestation is alignment not effort",
    "the universe responds to your feeling not your thinking",
    "you are the creator of every experience you have",
    "what you believe becomes your reality",
    "your vibration speaks louder than your words",
    "reality is a mirror of your inner state",
]

HASHTAGS = (
    "#darkpsychology #relationshiptruth #mindset #consciousnessawakening "
    "#realityshift #lawofattraction #manifestation #spiritualawakening "
    "#shadowwork #innerwork"
)

_DARK_TOPICS = {
    "relationship", "people", "attachment", "leave", "hurt",
    "gaslight", "love", "left", "heal", "silent", "insecure",
    "treat", "permission", "potential",
}

MP_DIR = os.path.join(ROOT_DIR, ".mp")


class ImagePost:

    def _is_dark_topic(self, topic: str) -> bool:
        words = set(topic.lower().split())
        return bool(words & _DARK_TOPICS)

    def generate_quote(self, topic: str) -> str:
        if self._is_dark_topic(topic):
            prompt = (
                f"Write ONE dark, brutally honest truth about: {topic}\n"
                f"Style: dark psychology — short, cuts deep, makes you pause and re-read.\n"
                f"Like something you've always known but never dared to say out loud.\n"
                f"Under 140 characters. No attribution. No hashtags. Return ONLY the quote."
            )
        else:
            prompt = (
                f"Write ONE deeply profound spiritual quote about: {topic}\n"
                f"Style: YourInnerGuide — calm, wise, ultimate truth. "
                f"Like something Rumi or Lao Tzu would say.\n"
                f"The quote must feel like a revelation — something the reader has always "
                f"felt but never heard said.\n"
                f"Under 140 characters. No attribution. Return ONLY the quote."
            )
        quote = generate_text(prompt).strip().strip('"').strip("'")
        if get_verbose():
            info(f"ImagePost quote: {quote}")
        return quote

    def generate_background(self, quote: str) -> bytes:
        api_key = get_nanobanana2_api_key()
        if not api_key:
            error("GEMINI_API_KEY not set — cannot generate background image.")
            return b""

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        endpoint = f"{base_url}/models/{model}:generateContent"

        bg_prompt = (
            "Dark cinematic quote card background. Near-black with deep crimson and dark violet "
            "gradient, dramatic moody lighting, subtle film grain, cinematic atmosphere. "
            "No text. No faces. Intense, powerful, visually striking. Square 1:1 format."
        )

        payload = {
            "contents": [{"parts": [{"text": bg_prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "1:1"},
            },
        }

        try:
            import base64
            r = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            r.raise_for_status()
            body = r.json()
            for candidate in body.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    if not inline_data:
                        continue
                    data = inline_data.get("data")
                    mime = inline_data.get("mimeType") or inline_data.get("mime_type", "")
                    if data and str(mime).startswith("image/"):
                        return base64.b64decode(data)
            warning("Gemini returned no image for background.")
            return b""
        except Exception as e:
            warning(f"Background generation failed: {e}")
            return b""

    def compose_image(self, bg_bytes: bytes, quote: str) -> str:
        from PIL import Image, ImageDraw, ImageFont

        SIZE = 1080

        if bg_bytes:
            img = Image.open(BytesIO(bg_bytes)).convert("RGBA")
            img = img.resize((SIZE, SIZE), Image.LANCZOS)
        else:
            # Dark near-black deep purple fallback
            img = Image.new("RGBA", (SIZE, SIZE), (10, 5, 20, 255))

        draw = ImageDraw.Draw(img)

        # Load bold font, fallback chain
        font_size = 58
        font = None
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            os.path.join(ROOT_DIR, "fonts", "bold_font.ttf"),
        ]
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except Exception:
                    pass
        if font is None:
            font = ImageFont.load_default()

        # Wrap text to ~26 chars per line
        wrapped = textwrap.fill(quote, width=26)
        lines = wrapped.split("\n")

        line_height = font_size + 14
        total_height = line_height * len(lines)
        y_start = (SIZE - total_height) // 2

        # Accent lines above and below text (dark gold)
        accent_color = (192, 160, 50, 220)   # dark gold
        padding = 24
        accent_y_top = y_start - padding
        accent_y_bot = y_start + total_height + padding - 4
        draw.line([(100, accent_y_top), (SIZE - 100, accent_y_top)], fill=accent_color, width=2)
        draw.line([(100, accent_y_bot), (SIZE - 100, accent_y_bot)], fill=accent_color, width=2)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (SIZE - text_w) // 2
            y = y_start + i * line_height

            # Dark red shadow
            draw.text((x + 4, y + 4), line, font=font, fill=(139, 0, 0, 180))
            # White main text
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

        out_path = os.path.join(MP_DIR, f"image_post_{uuid4().hex[:8]}.jpg")
        img.convert("RGB").save(out_path, "JPEG", quality=95)
        if get_verbose():
            info(f"ImagePost composed: {out_path}")
        return out_path

    def post_to_instagram(self, image_path: str, quote: str, topic: str) -> str:
        username = os.environ.get("INSTAGRAM_USERNAME", "").strip()
        password = os.environ.get("INSTAGRAM_PASSWORD", "").strip()
        if not username or not password:
            warning("INSTAGRAM_USERNAME/PASSWORD not set — skipping Instagram photo.")
            return ""

        caption = f"{quote}\n\n✨ {topic.title()}\n\n{HASHTAGS}"

        from .Instagram import Instagram
        try:
            url = Instagram(username, password).upload_photo(image_path, caption)
            return url
        except Exception as e:
            error(f"Instagram photo upload failed: {e}")
            return ""

    def post_youtube_community(self, image_path: str, quote: str, topic: str) -> str:
        """Post to YouTube Posts tab using internal youtubei/v1 API."""
        token_json = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()
        if not token_json:
            warning("YOUTUBE_TOKEN_JSON not set — skipping YouTube community post.")
            return ""

        try:
            from google.auth.transport.requests import Request as GoogleRequest
            from google.oauth2.credentials import Credentials

            SCOPES = [
                "https://www.googleapis.com/auth/youtube",
                "https://www.googleapis.com/auth/youtube.upload",
            ]
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
            access_token = creds.token
        except Exception as e:
            warning(f"YouTube credentials failed: {e}")
            return ""

        auth_header = {"Authorization": f"Bearer {access_token}"}

        # Build post text
        tag = "#" + "".join(w.capitalize() for w in topic.split())[:20]
        text = f"{quote}\n\n{tag} {HASHTAGS}"

        # Step 1: Upload image blob
        image_key = None
        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            r2 = requests.post(
                "https://upload.youtube.com/upload/youtubei/v1/community/create_post_image"
                "?uploadType=media",
                headers={**auth_header, "Content-Type": "image/jpeg"},
                data=img_bytes,
                timeout=60,
            )
            if r2.ok:
                image_key = r2.json().get("key")
                if get_verbose():
                    info(f"YouTube community image uploaded, key: {image_key}")
            else:
                warning(f"YouTube community image upload: {r2.status_code} — falling back to text-only.")
        except Exception as e:
            warning(f"YouTube community image upload failed ({e}), posting text-only.")

        # Step 2: Create community post
        payload = {
            "context": {
                "client": {"clientName": "WEB", "clientVersion": "2.20240101", "hl": "en"}
            },
            "postTextOriginal": text,
        }
        if image_key:
            payload["contentTypeInfo"] = {
                "imagePost": {"images": [{"key": image_key}]}
            }

        try:
            r3 = requests.post(
                "https://www.youtube.com/youtubei/v1/community/create_post",
                headers={**auth_header, "X-Goog-AuthUser": "0", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            if r3.ok:
                post_id = r3.json().get("postId", "")
                url = f"https://www.youtube.com/post/{post_id}" if post_id else "YouTube"
                success(f"YouTube community post published: {url}")
                return url
            else:
                warning(f"YouTube community post failed: {r3.status_code} {r3.text[:200]}")
                return ""
        except Exception as e:
            error(f"YouTube community post exception: {e}")
            return ""

    def run(self, topic: str = None):
        os.makedirs(MP_DIR, exist_ok=True)

        if not topic:
            topic = random.choice(TOPICS)
        info(f"ImagePost topic: {topic}")

        quote = self.generate_quote(topic)
        if not quote:
            error("Quote generation failed.")
            return

        bg_bytes = self.generate_background(quote)
        image_path = self.compose_image(bg_bytes, quote)

        info("Posting to Instagram...")
        self.post_to_instagram(image_path, quote, topic)

        info("Posting to YouTube community...")
        self.post_youtube_community(image_path, quote, topic)

        success(f"ImagePost done — topic: {topic}")
