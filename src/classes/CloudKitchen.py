"""
Grand Forno Cloud Kitchen — Instagram automation.
Posts food images + Reels about healthy meals (salads, fruit bowls) 3× daily.
Every caption includes Swiggy + Zomato ordering links.
"""
import base64
import os
import random
import textwrap
import traceback
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
from status import info, success, warning

SWIGGY  = "https://www.swiggy.com/direct/brand/745335?source=swiggy-direct&subSource=generic"
ZOMATO  = "https://link.zomato.com/xqzv/rshare?id=12604070930563345"

ORDER_BLOCK = (
    f"\n\n🛒 Order now & get it delivered fresh:\n"
    f"🟠 Swiggy → {SWIGGY}\n"
    f"🔴 Zomato → {ZOMATO}"
)

HASHTAGS = (
    "#GrandForno #HealthyFood #CloudKitchen #FreshSalad #FruitBowl "
    "#HealthyEating #CleanEats #EatClean #NutritiousFood #HealthyLifestyle "
    "#SaladBowl #FoodDelivery #FreshFood #WellnessFood #FoodIsMedicine"
)

# (dish_name, post_type)  post_type: "photo" or "reel"
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


class CloudKitchen:

    # ------------------------------------------------------------------ #
    #  Content Generation                                                  #
    # ------------------------------------------------------------------ #

    def generate_caption(self, dish: str) -> str:
        prompt = (
            f"Write an Instagram caption for a cloud kitchen selling '{dish}'.\n\n"
            f"Structure (follow exactly):\n"
            f"Line 1: A bold mouth-watering headline about the dish (use relevant emoji)\n"
            f"Empty line\n"
            f"Lines 2-3: 2-3 sentences about the specific health benefits "
            f"of this dish — name vitamins, minerals, body benefits specifically. "
            f"Make the reader feel they NEED this for their health.\n"
            f"Empty line\n"
            f"Line 4: A warm closing sentence encouraging them to order today.\n\n"
            f"Rules: conversational, warm, max 150 words, no hashtags, no ordering links.\n"
            f"Return ONLY the caption text."
        )
        try:
            caption = generate_text(prompt).strip()
            if get_verbose():
                info(f"CloudKitchen caption for {dish}: {caption[:60]}...")
            return caption
        except Exception as e:
            print(f"[CloudKitchen] Caption generation failed: {e}")
            return f"🥗 Fresh & healthy {dish} — made with love, delivered to your door!"

    def generate_reel_script(self, dish: str) -> str:
        prompt = (
            f"Write a 5-sentence voiceover script for a 20-second Instagram Reel about '{dish}' "
            f"from a healthy cloud kitchen named Grand Forno.\n\n"
            f"Style: warm, enthusiastic, health-coach energy.\n"
            f"Sentence 1: Bold hook about health or this dish.\n"
            f"Sentences 2-3: Specific health benefits with real nutrients/effects.\n"
            f"Sentence 4: How fresh and delicious this dish is.\n"
            f"Sentence 5: Call to action — order via Swiggy or Zomato.\n\n"
            f"No markdown, no bullets, 5 sentences only, spoken word style."
        )
        try:
            script = generate_text(prompt).strip()
            if get_verbose():
                info(f"CloudKitchen reel script for {dish}: {script[:60]}...")
            return script
        except Exception as e:
            print(f"[CloudKitchen] Script generation failed: {e}")
            return (
                f"Your body deserves the best fuel. "
                f"Our {dish} is packed with vitamins, minerals and antioxidants "
                f"that boost your energy and strengthen your immune system. "
                f"Every ingredient is fresh, clean, and carefully chosen for your wellness. "
                f"Order now on Swiggy or Zomato and taste the difference."
            )

    # ------------------------------------------------------------------ #
    #  Image Generation                                                    #
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
            f"Bright, vibrant, appetizing. Shot from above (flat lay) on a clean white marble surface. "
            f"Natural lighting, fresh ingredients visible, restaurant quality. "
            f"Ultra-realistic, mouth-watering, Instagram-worthy. Square 1:1 format. "
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
            print(f"[CloudKitchen] Gemini returned no image for '{dish}'.")
            return b""
        except Exception as e:
            print(f"[CloudKitchen] Food image generation failed: {e}")
            return b""

    def save_food_image(self, img_bytes: bytes, dish: str) -> str:
        from PIL import Image, ImageDraw, ImageFont

        SIZE = 1080

        if img_bytes:
            img = Image.open(BytesIO(img_bytes)).convert("RGB")
            img = img.resize((SIZE, SIZE), Image.LANCZOS)
        else:
            # Branded fallback: warm orange-to-green gradient (food/fresh brand colors)
            img = Image.new("RGB", (SIZE, SIZE))
            draw = ImageDraw.Draw(img)
            for y in range(SIZE):
                ratio = y / SIZE
                r = int(230 * (1 - ratio) + 60 * ratio)
                g = int(120 * (1 - ratio) + 180 * ratio)
                b = int(40 * (1 - ratio) + 60 * ratio)
                draw.line([(0, y), (SIZE, y)], fill=(r, g, b))

            # Add dish name text on fallback
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56
                )
            except Exception:
                font = ImageFont.load_default()

            wrapped = textwrap.fill(dish, width=18)
            lines = wrapped.split("\n")
            line_h = 68
            total_h = line_h * len(lines)
            y0 = (SIZE - total_h) // 2
            for i, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
                x = (SIZE - tw) // 2
                y = y0 + i * line_h
                draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 160))
                draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

        out_path = os.path.join(MP_DIR, f"cloudk_photo_{uuid4().hex[:8]}.jpg")
        img.save(out_path, "JPEG", quality=95)
        if get_verbose():
            info(f"Food image saved: {out_path}")
        return out_path

    # ------------------------------------------------------------------ #
    #  Reel Creation                                                       #
    # ------------------------------------------------------------------ #

    def make_reel(self, dish: str, script: str) -> str:
        """Create a ~20s food Reel: 1 food image repeated + TTS voiceover."""
        from moviepy.editor import (
            AudioFileClip,
            ImageClip,
            concatenate_videoclips,
        )
        from .Tts import TTS

        # Generate image ONCE and reuse — avoids 4× Gemini API calls
        print(f"[CloudKitchen] Generating food image for reel: {dish}")
        img_bytes = self.generate_food_image(dish)
        img_path = self.save_food_image(img_bytes, dish)

        # TTS with fallback to silent reel
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
            print(f"[CloudKitchen] TTS failed: {e} — creating silent reel")

        per_clip = duration / 4
        clips = []
        for _ in range(4):
            clip = ImageClip(img_path).set_duration(per_clip).resize(height=1350)
            w, h = clip.size
            if w > 1080:
                clip = clip.crop(x_center=w / 2, width=1080)
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        if audio:
            video = video.set_audio(audio)

        out_path = os.path.join(MP_DIR, f"cloudk_reel_{uuid4().hex[:8]}.mp4")
        video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        print(f"[CloudKitchen] Reel created: {out_path}")
        return out_path

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
            print("[CloudKitchen] WARNING: CLOUDK_INSTAGRAM_SESSION_JSON not set — will attempt fresh login.")

        from .Instagram import Instagram
        return Instagram(username, password), username

    def post_photo(self, image_path: str, dish: str, caption_body: str) -> str:
        ig, username = self._get_instagram()
        if not ig:
            return ""
        full_caption = f"{caption_body}{ORDER_BLOCK}\n\n{HASHTAGS}"
        try:
            url = ig.upload_photo(image_path, full_caption)
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
        full_caption = f"{caption_body}{ORDER_BLOCK}\n\n{HASHTAGS}"
        try:
            url = ig.upload_reel(video_path, full_caption)
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

            if post_type == "reel":
                script = self.generate_reel_script(dish)
                caption_body = self.generate_caption(dish)
                print("[CloudKitchen] Creating food Reel...")
                reel_path = self.make_reel(dish, script)
                self.post_reel(reel_path, dish, caption_body)
            else:
                caption_body = self.generate_caption(dish)
                print(f"[CloudKitchen] Generating food image for: {dish}")
                img_bytes = self.generate_food_image(dish)
                img_path = self.save_food_image(img_bytes, dish)
                self.post_photo(img_path, dish, caption_body)

            success(f"CloudKitchen run complete: {dish}")
            print(f"[CloudKitchen] Done: {dish}")

        except Exception as e:
            print(f"[CloudKitchen] run() crashed: {e}")
            traceback.print_exc()
