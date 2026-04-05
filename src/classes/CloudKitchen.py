"""
Grand Forno Cloud Kitchen — Instagram automation.
Posts food images + Reels about healthy meals (salads, fruit bowls) 3× daily.

Links in bio strategy: Instagram captions never support clickable links.
We auto-update the bio + website link on every run so followers can tap bio link to order.
"""
import base64
import os
import random
import textwrap
import traceback
from io import BytesIO
from uuid import uuid4

import requests
from PIL import Image, ImageDraw, ImageFont

from config import (
    ROOT_DIR,
    get_nanobanana2_api_base_url,
    get_nanobanana2_api_key,
    get_nanobanana2_model,
    get_verbose,
)
from llm_provider import generate_text
from status import info, success, warning

SWIGGY = "https://www.swiggy.com/direct/brand/745335?source=swiggy-direct&subSource=generic"
ZOMATO = "https://link.zomato.com/xqzv/rshare?id=12604070930563345"

BIO_TEXT = (
    "🥗 Healthy Cloud Kitchen | Fresh Salads & Fruit Bowls\n"
    f"🟠 Swiggy: {SWIGGY}\n"
    f"🔴 Zomato: {ZOMATO}"
)

CAPTION_ORDER = "🔗 Tap the link in our bio to order fresh ⬆️"

HASHTAGS = (
    "#GrandForno #HealthyFood #CloudKitchen #FreshSalad #FruitBowl "
    "#HealthyEating #CleanEats #EatClean #NutritiousFood #HealthyLifestyle "
    "#SaladBowl #FoodDelivery #FreshFood #WellnessFood #FoodIsMedicine"
)

MENU_ITEMS = [
    ("Greek Salad Bowl", "photo"),
    ("Rainbow Fruit Bowl", "photo"),
    ("Quinoa Power Salad", "photo"),
    ("Tropical Fruit Bowl", "reel"),
    ("Caesar Salad", "photo"),
    ("Watermelon Mint Cooler Bowl", "photo"),
    ("Grilled Veggie Salad", "reel"),
    ("Antioxidant Berry Bowl", "photo"),
    ("Avocado Green Salad", "photo"),
    ("Mango Papaya Fruit Bowl", "reel"),
    ("Spinach Chickpea Salad", "photo"),
    ("Dragon Fruit Acai Bowl", "photo"),
    ("Mediterranean Salad", "reel"),
    ("Kiwi Strawberry Fruit Bowl", "photo"),
    ("Detox Green Salad", "photo"),
    ("Protein Power Salad", "reel"),
]

MP_DIR = os.path.join(ROOT_DIR, ".mp")

# Font paths available on Ubuntu CI
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_FONT_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    paths = _FONT_PATHS if bold else _FONT_REGULAR_PATHS
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


class CloudKitchen:

    # ------------------------------------------------------------------ #
    #  Content Generation                                                  #
    # ------------------------------------------------------------------ #

    def generate_benefits(self, dish: str) -> list:
        """Returns 3 short health benefit strings for the dish."""
        prompt = (
            f"List exactly 3 specific health benefits of eating '{dish}'.\n"
            f"Format: one benefit per line, max 7 words each, start with a relevant emoji.\n"
            f"Be specific — name real vitamins, minerals, or body effects.\n"
            f"Example:\n"
            f"💪 Builds muscle with 18g protein\n"
            f"🧠 Boosts brain with Omega-3\n"
            f"🔥 Burns fat with zero bad carbs\n"
            f"Return ONLY the 3 lines, nothing else."
        )
        try:
            raw = generate_text(prompt).strip()
            lines = [l.strip() for l in raw.split("\n") if l.strip()][:3]
            while len(lines) < 3:
                lines.append("✅ Nutritious & delicious")
            return lines
        except Exception as e:
            print(f"[CloudKitchen] Benefits generation failed: {e}")
            return ["🌿 100% fresh ingredients", "💚 Rich in vitamins & minerals", "🔥 Boosts energy naturally"]

    def generate_caption(self, dish: str, benefits: list) -> str:
        benefits_text = "\n".join(benefits)
        prompt = (
            f"Write an Instagram caption for a cloud kitchen selling '{dish}'.\n\n"
            f"Known benefits of this dish:\n{benefits_text}\n\n"
            f"Structure:\n"
            f"Line 1: Bold mouth-watering headline with emoji\n"
            f"(empty line)\n"
            f"Lines 2-4: Expand on the benefits in warm conversational tone — "
            f"make the reader feel they NEED this for their health today.\n"
            f"(empty line)\n"
            f"Line 5: Warm closing line.\n\n"
            f"Max 120 words. No hashtags. No ordering links. Return ONLY the caption."
        )
        try:
            return generate_text(prompt).strip()
        except Exception as e:
            print(f"[CloudKitchen] Caption failed: {e}")
            return f"🥗 Fresh {dish} — packed with nutrients, made fresh daily for you!"

    def generate_reel_script(self, dish: str, benefits: list) -> str:
        benefits_text = " | ".join(benefits)
        prompt = (
            f"Write a 5-sentence voiceover script for a 20-second Instagram Reel about '{dish}'.\n"
            f"Known benefits: {benefits_text}\n\n"
            f"Sentence 1: Powerful hook — one bold truth about healthy eating.\n"
            f"Sentence 2-3: Explain the benefits of this specific dish in an exciting way.\n"
            f"Sentence 4: Describe how fresh and delicious it tastes.\n"
            f"Sentence 5: CTA — order now on Swiggy or Zomato via link in bio.\n\n"
            f"Spoken word style, enthusiastic, health-coach energy. No bullets. 5 sentences only."
        )
        try:
            return generate_text(prompt).strip()
        except Exception as e:
            print(f"[CloudKitchen] Reel script failed: {e}")
            return (
                f"Your body is a temple — feed it right. "
                f"Our {dish} is loaded with vitamins and antioxidants that energize you from within. "
                f"Every bite fights inflammation and keeps you feeling light and alive. "
                f"Made fresh every day with the finest ingredients — you can taste the difference. "
                f"Order right now via the link in our bio on Swiggy or Zomato!"
            )

    # ------------------------------------------------------------------ #
    #  Image Generation & Composition                                      #
    # ------------------------------------------------------------------ #

    def generate_food_image(self, dish: str) -> bytes:
        api_key = get_nanobanana2_api_key()
        if not api_key:
            print("[CloudKitchen] GEMINI_API_KEY not set — using fallback image.")
            return b""

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        endpoint = f"{base_url}/models/{model}:generateContent"

        prompt = (
            f"Professional food photography of '{dish}'. "
            f"Bright, vibrant, appetizing. Flat lay on clean white marble. "
            f"Natural lighting, fresh ingredients visible, restaurant quality. "
            f"Ultra-realistic, mouth-watering, Instagram-worthy. Square 1:1. "
            f"No text, no watermarks, no people."
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
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
            for candidate in r.json().get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if not inline:
                        continue
                    data = inline.get("data")
                    mime = inline.get("mimeType") or inline.get("mime_type", "")
                    if data and str(mime).startswith("image/"):
                        return base64.b64decode(data)
            print(f"[CloudKitchen] Gemini returned no image for '{dish}'.")
            return b""
        except Exception as e:
            print(f"[CloudKitchen] Food image generation failed: {e}")
            return b""

    def compose_photo(self, img_bytes: bytes, dish: str, benefits: list) -> str:
        """
        Creates a scroll-stopping 1080×1080 image:
        - Food photo as background
        - Semi-transparent dark bar at top with dish name
        - Semi-transparent dark bar at bottom with 3 benefit bullets
        """
        SIZE = 1080

        if img_bytes:
            bg = Image.open(BytesIO(img_bytes)).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
        else:
            # Warm orange-green gradient fallback
            bg = Image.new("RGBA", (SIZE, SIZE))
            draw_bg = ImageDraw.Draw(bg)
            for y in range(SIZE):
                ratio = y / SIZE
                r = int(230 * (1 - ratio) + 40 * ratio)
                g = int(100 * (1 - ratio) + 180 * ratio)
                b_val = 30
                draw_bg.line([(0, y), (SIZE, y)], fill=(r, g, b_val, 255))

        overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # ── Top bar: dish name ──────────────────────────────────────────
        top_h = 130
        draw.rectangle([(0, 0), (SIZE, top_h)], fill=(0, 0, 0, 180))

        font_title = _load_font(58, bold=True)
        title = dish.upper()
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
        tx = (SIZE - tw) // 2
        ty = (top_h - (bbox[3] - bbox[1])) // 2
        # Shadow
        draw.text((tx + 3, ty + 3), title, font=font_title, fill=(0, 0, 0, 200))
        # Text — fresh green
        draw.text((tx, ty), title, font=font_title, fill=(120, 220, 80, 255))

        # ── Bottom bar: 3 benefits ──────────────────────────────────────
        bot_h = 200
        bot_y = SIZE - bot_h
        draw.rectangle([(0, bot_y), (SIZE, SIZE)], fill=(0, 0, 0, 185))

        font_ben = _load_font(40, bold=False)
        line_h = 56
        total_text_h = line_h * len(benefits)
        start_y = bot_y + (bot_h - total_text_h) // 2

        for i, benefit in enumerate(benefits[:3]):
            bbox2 = draw.textbbox((0, 0), benefit, font=font_ben)
            bw = bbox2[2] - bbox2[0]
            bx = (SIZE - bw) // 2
            by = start_y + i * line_h
            draw.text((bx + 2, by + 2), benefit, font=font_ben, fill=(0, 0, 0, 160))
            draw.text((bx, by), benefit, font=font_ben, fill=(255, 255, 255, 255))

        # ── Grand Forno branding (bottom right) ────────────────────────
        font_brand = _load_font(28, bold=True)
        brand = "@grand_forno"
        bbox3 = draw.textbbox((0, 0), brand, font=font_brand)
        bx = SIZE - (bbox3[2] - bbox3[0]) - 20
        by_brand = SIZE - 30
        draw.text((bx, by_brand), brand, font=font_brand, fill=(255, 255, 255, 160))

        final = Image.alpha_composite(bg, overlay).convert("RGB")
        out_path = os.path.join(MP_DIR, f"cloudk_photo_{uuid4().hex[:8]}.jpg")
        final.save(out_path, "JPEG", quality=95)
        if get_verbose():
            info(f"Food photo composed: {out_path}")
        print(f"[CloudKitchen] Photo composed: {out_path}")
        return out_path

    def _compose_reel_frame(self, bg: Image.Image, headline: str, subtext: str = "",
                             text_color=(255, 255, 255, 255), accent_color=(120, 220, 80, 255)) -> str:
        """Bake text onto a 1080×1350 frame and return the saved path."""
        SIZE_W, SIZE_H = 1080, 1350
        frame = bg.copy().resize((SIZE_W, SIZE_H), Image.LANCZOS)
        # Dark overlay for readability
        overlay = Image.new("RGBA", (SIZE_W, SIZE_H), (0, 0, 0, 100))
        frame = Image.alpha_composite(frame.convert("RGBA"), overlay)

        draw = ImageDraw.Draw(frame)
        font_h = _load_font(62, bold=True)
        font_s = _load_font(42, bold=False)

        # Headline centered vertically
        mid_y = SIZE_H // 2
        wrapped = textwrap.fill(headline, width=22)
        lines = wrapped.split("\n")
        line_h = 74
        total_h = line_h * len(lines)
        y0 = mid_y - total_h // 2 - (50 if subtext else 0)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_h)
            tw = bbox[2] - bbox[0]
            x = (SIZE_W - tw) // 2
            y = y0 + i * line_h
            draw.text((x + 3, y + 3), line, font=font_h, fill=(0, 0, 0, 200))
            draw.text((x, y), line, font=font_h, fill=accent_color)

        if subtext:
            bbox2 = draw.textbbox((0, 0), subtext, font=font_s)
            sw = bbox2[2] - bbox2[0]
            sx = (SIZE_W - sw) // 2
            sy = y0 + total_h + 20
            draw.text((sx, sy), subtext, font=font_s, fill=text_color)

        # Brand watermark
        font_brand = _load_font(30, bold=True)
        brand = "@grand_forno"
        bbox3 = draw.textbbox((0, 0), brand, font=font_brand)
        bx = SIZE_W - (bbox3[2] - bbox3[0]) - 20
        draw.text((bx, SIZE_H - 50), brand, font=font_brand, fill=(255, 255, 255, 180))

        out_path = os.path.join(MP_DIR, f"cloudk_frame_{uuid4().hex[:8]}.jpg")
        frame.convert("RGB").save(out_path, "JPEG", quality=92)
        return out_path

    # ------------------------------------------------------------------ #
    #  Reel Creation                                                       #
    # ------------------------------------------------------------------ #

    def make_reel(self, dish: str, script: str, benefits: list) -> str:
        """
        Creates a ~20s Reel with 4 visual frames:
          Frame 1: Dish name (intro)
          Frame 2: Benefit 1
          Frame 3: Benefit 2
          Frame 4: Order CTA
        Each frame has text baked in via PIL so it's readable without sound.
        """
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips
        from .Tts import TTS

        print(f"[CloudKitchen] Generating food image for reel: {dish}")
        img_bytes = self.generate_food_image(dish)
        if img_bytes:
            bg = Image.open(BytesIO(img_bytes)).convert("RGBA")
        else:
            bg = Image.new("RGBA", (1080, 1350), (40, 120, 40, 255))

        # 4 frames with different text
        frame_defs = [
            (dish.upper(), "Fresh from Grand Forno 🥗", (120, 220, 80, 255)),
            (benefits[0] if benefits else "✅ Packed with nutrients", "Eat well. Feel great.", (255, 220, 80, 255)),
            (benefits[1] if len(benefits) > 1 else "💚 100% fresh ingredients", "Zero compromise on quality.", (80, 200, 255, 255)),
            ("Order Now 🛒", "Swiggy & Zomato — link in bio ⬆️", (255, 120, 80, 255)),
        ]

        frame_paths = []
        for headline, sub, color in frame_defs:
            fp = self._compose_reel_frame(bg, headline, sub, accent_color=color)
            frame_paths.append(fp)

        # TTS
        wav_path = os.path.join(MP_DIR, f"cloudk_tts_{uuid4().hex[:8]}.wav")
        audio = None
        duration = 20.0
        try:
            print("[CloudKitchen] Synthesizing TTS...")
            TTS().synthesize(script, output_file=wav_path)
            audio = AudioFileClip(wav_path)
            duration = max(audio.duration + 0.5, 18.0)
            print(f"[CloudKitchen] TTS done, duration: {duration:.1f}s")
        except Exception as e:
            print(f"[CloudKitchen] TTS failed: {e} — silent reel")

        per_clip = duration / 4
        clips = []
        for fp in frame_paths:
            clip = ImageClip(fp).set_duration(per_clip)
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        if audio:
            video = video.set_audio(audio)

        out_path = os.path.join(MP_DIR, f"cloudk_reel_{uuid4().hex[:8]}.mp4")
        video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        print(f"[CloudKitchen] Reel created: {out_path}")
        return out_path

    # ------------------------------------------------------------------ #
    #  Bio Update (makes links accessible — Instagram captions can't      #
    #  have clickable links, so we put them in the bio instead)           #
    # ------------------------------------------------------------------ #

    def update_bio(self, ig_client):
        """Update grand_forno bio with both ordering links so followers can tap them."""
        try:
            ig_client.account_edit(
                biography=BIO_TEXT,
                external_url=SWIGGY,   # sets the clickable website link in profile
            )
            print("[CloudKitchen] Bio updated with Swiggy + Zomato links.")
        except Exception as e:
            print(f"[CloudKitchen] Bio update failed (non-critical): {e}")

    # ------------------------------------------------------------------ #
    #  Instagram Posting                                                   #
    # ------------------------------------------------------------------ #

    def _get_instagram(self):
        username = os.environ.get("CLOUDK_INSTAGRAM_USERNAME", "").strip()
        password = os.environ.get("CLOUDK_INSTAGRAM_PASSWORD", "").strip()
        if not username or not password:
            print("[CloudKitchen] CLOUDK_INSTAGRAM_USERNAME/PASSWORD not set — skipping.")
            return None, None

        session_json = os.environ.get("CLOUDK_INSTAGRAM_SESSION_JSON", "").strip()
        if session_json:
            os.environ["INSTAGRAM_SESSION_JSON"] = session_json
            print("[CloudKitchen] Instagram session JSON loaded.")
        else:
            print("[CloudKitchen] WARNING: CLOUDK_INSTAGRAM_SESSION_JSON not set.")

        from .Instagram import Instagram
        return Instagram(username, password), username

    def post_photo(self, image_path: str, dish: str, caption_body: str) -> str:
        ig, username = self._get_instagram()
        if not ig:
            return ""
        cl = ig._get_client()

        # Update bio with ordering links on every run
        self.update_bio(cl)

        full_caption = f"{caption_body}\n\n{CAPTION_ORDER}\n\n{HASHTAGS}"
        try:
            from pathlib import Path
            media = cl.photo_upload(Path(image_path), full_caption)
            url = f"https://www.instagram.com/p/{media.code}/"
            success(f"Grand Forno photo posted: {url}")
            print(f"[CloudKitchen] Photo posted: {url}")
            return url
        except Exception as e:
            print(f"[CloudKitchen] Photo post FAILED: {e}")
            traceback.print_exc()
            return ""

    def post_reel(self, video_path: str, dish: str, caption_body: str) -> str:
        ig, username = self._get_instagram()
        if not ig:
            return ""
        cl = ig._get_client()

        # Update bio with ordering links on every run
        self.update_bio(cl)

        full_caption = f"{caption_body}\n\n{CAPTION_ORDER}\n\n{HASHTAGS}"
        try:
            from pathlib import Path
            media = cl.clip_upload(Path(video_path), full_caption)
            url = f"https://www.instagram.com/reel/{media.code}/"
            success(f"Grand Forno reel posted: {url}")
            print(f"[CloudKitchen] Reel posted: {url}")
            return url
        except Exception as e:
            print(f"[CloudKitchen] Reel post FAILED: {e}")
            traceback.print_exc()
            return ""

    # ------------------------------------------------------------------ #
    #  Main runner                                                         #
    # ------------------------------------------------------------------ #

    def run(self, dish: str = None, post_type: str = None):
        os.makedirs(MP_DIR, exist_ok=True)
        try:
            if not dish:
                item = random.choice(MENU_ITEMS)
                dish, post_type = item[0], item[1]
            print(f"[CloudKitchen] Starting: {dish} ({post_type})")

            benefits = self.generate_benefits(dish)
            print(f"[CloudKitchen] Benefits: {benefits}")

            if post_type == "reel":
                script = self.generate_reel_script(dish, benefits)
                caption_body = self.generate_caption(dish, benefits)
                print("[CloudKitchen] Creating Reel...")
                reel_path = self.make_reel(dish, script, benefits)
                self.post_reel(reel_path, dish, caption_body)
            else:
                caption_body = self.generate_caption(dish, benefits)
                print(f"[CloudKitchen] Generating food image: {dish}")
                img_bytes = self.generate_food_image(dish)
                img_path = self.compose_photo(img_bytes, dish, benefits)
                self.post_photo(img_path, dish, caption_body)

            success(f"CloudKitchen run complete: {dish}")
            print(f"[CloudKitchen] Done: {dish}")

        except Exception as e:
            print(f"[CloudKitchen] run() crashed: {e}")
            traceback.print_exc()
