"""
Spiritual image post pipeline.
Generates a cosmic quote-card image and posts it to:
  - Instagram (static photo post via instagrapi)
  - YouTube (15-second Short: single image + Hugo TTS narration)
Runs every 6 hours via image_post_cron.yml.
"""
import base64
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
    "you are already what you are seeking",
    "reality is a mirror of your inner state",
    "your thoughts create the universe you live in",
    "the present moment contains everything you need",
    "you are a consciousness having a human experience",
    "manifestation is alignment not effort",
    "what you believe becomes your reality",
    "your vibration speaks louder than your words",
    "the universe responds to your feeling not your thinking",
    "you are the creator of every experience you have",
]

HASHTAGS = (
    "#manifestation #lawofattraction #realityshift #spiritualawakening "
    "#consciousness #raisingvibration #5D #innerguide #quantumshift #abundance"
)

MP_DIR = os.path.join(ROOT_DIR, ".mp")


class ImagePost:
    def generate_quote(self, topic: str) -> str:
        prompt = (
            f"Write ONE deeply profound spiritual quote about: {topic}\n"
            f"Style: YourInnerGuide — calm, wise, ultimate truth. "
            f"Like something Rumi or Lao Tzu would say.\n"
            f"The quote must feel like a revelation — something the reader has always "
            f"felt but never heard said.\n"
            f"Under 120 characters. No attribution. Return ONLY the quote."
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
            "Cosmic spiritual background for a quote card. "
            "Deep space with soft golden and violet light, nebula, sacred geometry. "
            "No text. No faces. Peaceful, divine, awe-inspiring. Square 1:1 format."
        )

        payload = {
            "contents": [{"parts": [{"text": bg_prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "1:1"},
            },
        }

        try:
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
            # Fallback: dark violet gradient
            img = Image.new("RGBA", (SIZE, SIZE), (30, 10, 60, 255))

        draw = ImageDraw.Draw(img)

        # Try to load a bold system font, fallback to default
        font_size = 64
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

        # Wrap text to ~30 chars per line
        wrapped = textwrap.fill(quote, width=28)
        lines = wrapped.split("\n")

        # Measure total text block height
        line_height = font_size + 12
        total_height = line_height * len(lines)
        y_start = (SIZE - total_height) // 2

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_w = bbox[2] - bbox[0]
            x = (SIZE - text_w) // 2
            y = y_start + i * line_height

            # Shadow
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 160))
            # Main text
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

    def make_youtube_short(self, image_path: str, quote: str) -> str:
        """Create a 15-second Short: full-screen image + TTS audio."""
        from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip

        from .Tts import TTS

        wav_path = os.path.join(MP_DIR, f"image_tts_{uuid4().hex[:8]}.wav")
        TTS().synthesize(quote, output_file=wav_path)

        audio_clip = AudioFileClip(wav_path)
        duration = max(audio_clip.duration + 1.0, 15.0)

        # 9:16 for YouTube Shorts (1080×1920)
        img_clip = (
            ImageClip(image_path)
            .set_duration(duration)
            .resize(height=1920)
        )
        # Centre-crop to 1080 wide
        w, h = img_clip.size
        if w > 1080:
            img_clip = img_clip.crop(x_center=w / 2, width=1080)

        video = CompositeVideoClip([img_clip], size=(1080, 1920))
        video = video.set_audio(audio_clip)

        out_path = os.path.join(MP_DIR, f"image_short_{uuid4().hex[:8]}.mp4")
        video.write_videofile(
            out_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        if get_verbose():
            info(f"ImagePost Short: {out_path}")
        return out_path

    def upload_youtube_short(self, video_path: str, quote: str, topic: str):
        """Upload the Short to YouTube via existing upload pipeline."""
        from cache import get_accounts
        from .YouTube import YouTube

        accounts = get_accounts("youtube")
        if not accounts:
            warning("No YouTube account configured — skipping YouTube Short.")
            return

        acc = accounts[0]
        yt = YouTube(
            account_uuid=acc["id"],
            account_nickname=acc.get("nickname", ""),
            fp_profile_path=acc.get("firefox_profile", ""),
            niche="reality shifting vibration manifestation spiritual awakening",
            language="English",
        )

        title = f"{quote[:60]}..." if len(quote) > 60 else quote
        description = (
            f"{quote}\n\n"
            f"✨ {topic.title()}\n\n"
            f"{HASHTAGS}\n\n"
            f"#Shorts"
        )
        tags = [
            "manifestation", "lawofattraction", "realityshift",
            "spiritualawakening", "consciousness", "raisingvibration",
            "shorts", "spiritual",
        ]

        try:
            yt.upload_video(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
            )
            success("YouTube Short (image) uploaded.")
        except Exception as e:
            error(f"YouTube Short upload failed: {e}")

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

        info("Creating YouTube Short...")
        short_path = self.make_youtube_short(image_path, quote)

        info("Uploading YouTube Short...")
        self.upload_youtube_short(short_path, quote, topic)

        success(f"ImagePost done — topic: {topic}")
