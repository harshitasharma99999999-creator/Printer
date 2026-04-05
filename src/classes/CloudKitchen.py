"""
Grand Forno Cloud Kitchen — Instagram automation.
High-quality food images + Reels with ambient music, 3× daily.

Link strategy: Instagram only makes URLs tappable on Business/Creator accounts.
Switch grand_forno to a Creator account (Profile → Settings → Account → Switch to
Professional Account) and the Swiggy/Zomato URLs in every caption become tappable.
We also keep them in bio as a backup.
"""
import base64
import json
import os
import random
import struct
import subprocess
import textwrap
import traceback
import wave
from io import BytesIO
from math import pi, sin
from uuid import uuid4

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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

# Caption order block — URLs are tappable on Business/Creator accounts
ORDER_BLOCK = (
    "\n\n🛒 Order fresh & get delivery:\n"
    f"🟠 Swiggy → {SWIGGY}\n"
    f"🔴 Zomato → {ZOMATO}"
)

BIO_TEXT = (
    "🥗 Fresh Salads & Fruit Bowls | Cloud Kitchen\n"
    "Order on Swiggy & Zomato ⬇️"
)

HASHTAGS = (
    "#GrandForno #HealthyFood #CloudKitchen #FreshSalad #FruitBowl "
    "#HealthyEating #CleanEats #EatClean #NutritiousFood #HealthyLifestyle "
    "#SaladBowl #FoodDelivery #FreshFood #WellnessFood #FoodIsMedicine "
    "#Salad #FruitBowl #HealthyLiving #OrganicFood #EatHealthy"
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

_BOLD_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_REG_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for p in (_BOLD_FONTS if bold else _REG_FONTS):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _draw_text_centered(draw, text, y, w, font, fill, shadow=(0, 0, 0, 180)):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (w - tw) // 2
    draw.text((x + 2, y + 2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]   # return line height


class CloudKitchen:

    # ------------------------------------------------------------------ #
    #  Content Generation                                                  #
    # ------------------------------------------------------------------ #

    def generate_benefits(self, dish: str) -> list:
        prompt = (
            f"List exactly 3 specific health benefits of eating '{dish}'.\n"
            f"Format: one per line, max 8 words, start with a relevant emoji.\n"
            f"Be specific — name real vitamins, minerals, or body effects.\n"
            f"Example: 💪 Builds muscle with 18g plant protein\n"
            f"Return ONLY the 3 lines."
        )
        try:
            raw = generate_text(prompt).strip()
            lines = [l.strip() for l in raw.split("\n") if l.strip()][:3]
            while len(lines) < 3:
                lines.append("✅ Packed with natural goodness")
            return lines
        except Exception as e:
            print(f"[CloudKitchen] Benefits gen failed: {e}")
            return ["🌿 Rich in vitamins & minerals", "💚 Boosts immunity naturally", "🔥 Energizes your whole day"]

    def generate_caption(self, dish: str, benefits: list) -> str:
        prompt = (
            f"Write a genuine, warm Instagram caption for '{dish}' from Grand Forno cloud kitchen.\n"
            f"Benefits of this dish: {' | '.join(benefits)}\n\n"
            f"Structure:\n"
            f"• Line 1: Bold, mouth-watering headline with food emoji\n"
            f"• (empty line)\n"
            f"• 2-3 sentences: expand on the health benefits in a warm, conversational tone. "
            f"Make the reader crave it AND feel it's good for them.\n"
            f"• (empty line)\n"
            f"• 1 warm closing line.\n\n"
            f"Max 100 words. No hashtags. No ordering links. Only the caption."
        )
        try:
            return generate_text(prompt).strip()
        except Exception as e:
            print(f"[CloudKitchen] Caption failed: {e}")
            return f"🥗 Fresh {dish} — made with love, packed with nature's best nutrients!"

    def generate_reel_script(self, dish: str, benefits: list) -> str:
        prompt = (
            f"Write a 5-sentence spoken voiceover for a 20-second Instagram Reel about '{dish}' "
            f"from Grand Forno, a healthy cloud kitchen.\n"
            f"Benefits: {' | '.join(benefits)}\n\n"
            f"Sentence 1: Powerful hook — a bold truth about eating healthy.\n"
            f"Sentences 2-3: Exciting explanation of these specific benefits.\n"
            f"Sentence 4: How incredibly fresh and delicious this tastes.\n"
            f"Sentence 5: CTA — tap the link in our bio to order on Swiggy or Zomato.\n\n"
            f"Warm, enthusiastic, health-coach energy. Spoken word style. 5 sentences only."
        )
        try:
            return generate_text(prompt).strip()
        except Exception as e:
            print(f"[CloudKitchen] Reel script failed: {e}")
            return (
                f"What you eat is who you become. "
                f"Our {dish} is loaded with nature's most powerful nutrients "
                f"that boost your energy, clear your skin, and strengthen your immune system. "
                f"Every ingredient is hand-picked, farm-fresh, and prepared the same day. "
                f"Tap the link in our bio and order right now on Swiggy or Zomato!"
            )

    # ------------------------------------------------------------------ #
    #  Image Generation                                                    #
    # ------------------------------------------------------------------ #

    def generate_food_image(self, dish: str) -> bytes:
        api_key = get_nanobanana2_api_key()
        if not api_key:
            print("[CloudKitchen] No GEMINI_API_KEY — using fallback image.")
            return b""

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        endpoint = f"{base_url}/models/{model}:generateContent"

        prompt = (
            f"Ultra-realistic professional food photography of a '{dish}'. "
            f"Styled for Instagram — bright natural lighting, vibrant fresh colors, "
            f"appetizing flat-lay on white marble with fresh herbs scattered around. "
            f"Restaurant quality plating, stunning details, mouth-watering. "
            f"Square composition 1:1. No text, no watermarks, no people."
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
                    inline = part.get("inlineData") or part.get("inline_data")
                    if not inline:
                        continue
                    data = inline.get("data")
                    mime = inline.get("mimeType") or inline.get("mime_type", "")
                    if data and str(mime).startswith("image/"):
                        print(f"[CloudKitchen] Gemini image received ({len(data)} chars b64)")
                        return base64.b64decode(data)
            # Log full response for debugging
            print(f"[CloudKitchen] Gemini no image. Response keys: {list(body.keys())}")
            if "candidates" in body and body["candidates"]:
                print(f"[CloudKitchen] First candidate: {str(body['candidates'][0])[:300]}")
            return b""
        except Exception as e:
            print(f"[CloudKitchen] Gemini request failed: {e}")
            return b""

    def _fallback_food_image(self, dish: str, size: int = 1080) -> Image.Image:
        """
        High-quality fallback: deep green-to-white gradient with bokeh circles
        to simulate a professional food background.
        """
        img = Image.new("RGB", (size, size))
        draw = ImageDraw.Draw(img)

        # Rich deep green to light warm cream gradient
        for y in range(size):
            ratio = y / size
            r = int(34  + (245 - 34)  * ratio)
            g = int(85  + (235 - 85)  * ratio)
            b = int(34  + (200 - 34)  * ratio)
            draw.line([(0, y), (size, y)], fill=(r, g, b))

        # Soft bokeh circles (depth-of-field feel)
        import random as _r
        _r.seed(hash(dish) % 9999)
        for _ in range(18):
            cx = _r.randint(0, size)
            cy = _r.randint(0, size)
            rad = _r.randint(30, 120)
            alpha_val = _r.randint(15, 40)
            circle_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            cd = ImageDraw.Draw(circle_layer)
            cd.ellipse([(cx - rad, cy - rad), (cx + rad, cy + rad)],
                       fill=(255, 255, 255, alpha_val))
            img = Image.alpha_composite(img.convert("RGBA"), circle_layer).convert("RGB")

        # Add dish name centered in elegant white
        draw2 = ImageDraw.Draw(img)
        font = _font(72, bold=True)
        wrapped = textwrap.fill(dish, width=16)
        lines = wrapped.split("\n")
        lh = 86
        total = lh * len(lines)
        y0 = (size - total) // 2
        for i, line in enumerate(lines):
            bbox = draw2.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            x = (size - tw) // 2
            y = y0 + i * lh
            draw2.text((x + 4, y + 4), line, font=font, fill=(0, 60, 0, 200))
            draw2.text((x, y), line, font=font, fill=(255, 255, 255, 240))

        return img

    # ------------------------------------------------------------------ #
    #  Image Composition                                                   #
    # ------------------------------------------------------------------ #

    def compose_photo(self, img_bytes: bytes, dish: str, benefits: list) -> str:
        """
        Professional 1080×1080 food post:
        - Full food photo (or premium fallback)
        - Subtle vignette for depth
        - Elegant dark gradient bar at bottom with dish name + benefits
        - Thin green accent line
        - @grand_forno branding
        """
        SIZE = 1080
        BAR_H = 240   # bottom bar height

        if img_bytes:
            bg = Image.open(BytesIO(img_bytes)).convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)
        else:
            bg = self._fallback_food_image(dish, SIZE)

        # Vignette — subtle darkening at edges
        vignette = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        vd = ImageDraw.Draw(vignette)
        for i in range(80):
            alpha = int(120 * (i / 80) ** 2)
            vd.rectangle([(i, i), (SIZE - i, SIZE - i)], outline=(0, 0, 0, alpha))
        bg = Image.alpha_composite(bg.convert("RGBA"), vignette).convert("RGB")

        # Bottom gradient bar (dark, semi-transparent)
        bar_y = SIZE - BAR_H
        bar = Image.new("RGBA", (SIZE, BAR_H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bar)
        for y in range(BAR_H):
            alpha = int(210 * (y / BAR_H) ** 0.4)
            bd.line([(0, y), (SIZE, y)], fill=(10, 30, 10, alpha))

        canvas = bg.convert("RGBA")
        canvas.paste(bar, (0, bar_y), bar)
        draw = ImageDraw.Draw(canvas)

        # Green accent line above bar
        accent_y = bar_y + 6
        draw.line([(40, accent_y), (SIZE - 40, accent_y)], fill=(80, 200, 60, 255), width=3)

        # Dish name
        font_title = _font(54, bold=True)
        name_y = bar_y + 22
        _draw_text_centered(draw, dish.upper(), name_y, SIZE, font_title,
                            fill=(255, 255, 255, 255), shadow=(0, 80, 0, 200))

        # 3 benefit lines
        font_ben = _font(32, bold=False)
        ben_y = name_y + 68
        for benefit in benefits[:3]:
            _draw_text_centered(draw, benefit, ben_y, SIZE, font_ben,
                                fill=(200, 255, 160, 255), shadow=(0, 0, 0, 160))
            ben_y += 42

        # Branding
        font_brand = _font(26, bold=True)
        _draw_text_centered(draw, "📍 @grand_forno", SIZE - 28, SIZE, font_brand,
                            fill=(255, 255, 255, 180), shadow=(0, 0, 0, 0))

        out_path = os.path.join(MP_DIR, f"cloudk_photo_{uuid4().hex[:8]}.jpg")
        canvas.convert("RGB").save(out_path, "JPEG", quality=96)
        print(f"[CloudKitchen] Photo composed: {out_path}")
        return out_path

    # ------------------------------------------------------------------ #
    #  Ambient Music                                                       #
    # ------------------------------------------------------------------ #

    def generate_ambient_music(self, duration: float) -> str:
        """
        Generate a pleasant C-major ambient wellness chord using ffmpeg aevalsrc.
        Sounds like calm health/food content background music.
        No downloads, no copyright issues.
        """
        out_path = os.path.join(MP_DIR, f"ambient_{uuid4().hex[:6]}.wav")
        # C major chord: C3 bass + C4 + E4 + G4 + C5
        # Gentle pulse at 0.4 Hz for that "breathing" feel
        expr = (
            "(0.14*sin(2*PI*261.63*t)"
            "+0.11*sin(2*PI*329.63*t)"
            "+0.09*sin(2*PI*392.00*t)"
            "+0.06*sin(2*PI*523.25*t)"
            "+0.09*sin(2*PI*130.81*t))"
            "*(0.78+0.22*sin(2*PI*0.4*t))"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"aevalsrc={expr}:s=22050:d={int(duration) + 2}",
            "-af", f"afade=t=in:st=0:d=2,afade=t=out:st={int(duration)-1}:d=2",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"[CloudKitchen] Music gen failed: {result.stderr.decode()[:300]}")
            return ""
        print(f"[CloudKitchen] Ambient music generated: {out_path}")
        return out_path

    # ------------------------------------------------------------------ #
    #  Reel Frame Composition                                              #
    # ------------------------------------------------------------------ #

    def _make_reel_frame(self, bg_img: Image.Image, headline: str, subline: str,
                          accent: tuple) -> str:
        """
        Creates a single 1080×1350 reel frame:
        - Blurred food background
        - Central text card (glassmorphism style)
        - Headline + subline with color accent
        """
        W, H = 1080, 1350

        # Resize background to portrait
        bg = bg_img.copy().resize((W, H), Image.LANCZOS)

        # Blur background for depth
        bg_blur = bg.filter(ImageFilter.GaussianBlur(radius=3))

        # Central frosted card
        card_w, card_h = 900, 360
        card_x = (W - card_w) // 2
        card_y = (H - card_h) // 2

        # Crop center region and blur more for glass effect
        region = bg_blur.crop((card_x, card_y, card_x + card_w, card_y + card_h))
        region = region.filter(ImageFilter.GaussianBlur(radius=8))

        # Dark semi-transparent overlay on card
        card_overlay = Image.new("RGBA", (card_w, card_h), (5, 20, 5, 200))
        region_rgba = region.convert("RGBA")
        glass = Image.alpha_composite(region_rgba, card_overlay)

        canvas = bg_blur.convert("RGBA")
        canvas.paste(glass, (card_x, card_y))
        draw = ImageDraw.Draw(canvas)

        # Accent border on card
        draw.rectangle(
            [(card_x, card_y), (card_x + card_w, card_y + card_h)],
            outline=accent + (200,), width=3
        )

        # Headline text
        font_h = _font(58, bold=True)
        font_s = _font(38, bold=False)

        # Wrap headline
        wrapped = textwrap.fill(headline, width=20)
        lines = wrapped.split("\n")
        lh = 68
        total_h = lh * len(lines)
        y0 = card_y + (card_h - total_h - (50 if subline else 0)) // 2

        for i, line in enumerate(lines):
            _draw_text_centered(draw, line, y0 + i * lh, W, font_h,
                                fill=accent + (255,), shadow=(0, 0, 0, 200))

        if subline:
            sub_y = y0 + total_h + 14
            _draw_text_centered(draw, subline, sub_y, W, font_s,
                                fill=(220, 255, 200, 230), shadow=(0, 0, 0, 160))

        # Bottom branding
        font_brand = _font(28, bold=True)
        _draw_text_centered(draw, "@grand_forno", H - 50, W, font_brand,
                            fill=(255, 255, 255, 190), shadow=(0, 0, 0, 0))

        out_path = os.path.join(MP_DIR, f"cloudk_frame_{uuid4().hex[:8]}.jpg")
        canvas.convert("RGB").save(out_path, "JPEG", quality=93)
        return out_path

    # ------------------------------------------------------------------ #
    #  Reel Creation                                                       #
    # ------------------------------------------------------------------ #

    def make_reel(self, dish: str, script: str, benefits: list) -> str:
        """
        Creates a ~22s Reel:
        4 frames × ~5.5s each — each with unique text overlay
        + TTS voiceover mixed with ambient wellness music
        + Ken Burns slow zoom on each clip
        """
        from moviepy.editor import (
            AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips,
        )
        from moviepy.audio.fx.all import audio_loop
        from .Tts import TTS

        print(f"[CloudKitchen] Generating food image for reel: {dish}")
        img_bytes = self.generate_food_image(dish)
        if img_bytes:
            bg = Image.open(BytesIO(img_bytes)).convert("RGB")
        else:
            bg = self._fallback_food_image(dish, 1080)

        # 4 frames: intro → benefit 1 → benefit 2 → order CTA
        frames_def = [
            (dish.upper(),   "Fresh from Grand Forno 🥗",          (80, 220, 80)),
            (benefits[0],    "Eat right. Feel amazing. 💚",         (255, 220, 60)),
            (benefits[1] if len(benefits) > 1 else benefits[0],
                             "Zero compromise on quality. ✨",       (60, 200, 255)),
            ("Order Now 🛒", "Tap link in bio → Swiggy / Zomato",  (255, 130, 60)),
        ]
        frame_paths = []
        for headline, sub, color in frames_def:
            fp = self._make_reel_frame(bg, headline, sub, color)
            frame_paths.append(fp)

        # TTS
        wav_path = os.path.join(MP_DIR, f"cloudk_tts_{uuid4().hex[:8]}.wav")
        tts_audio = None
        duration = 22.0
        try:
            print("[CloudKitchen] Synthesizing TTS...")
            TTS().synthesize(script, output_file=wav_path)
            tts_audio = AudioFileClip(wav_path)
            duration = max(tts_audio.duration + 1.0, 20.0)
            print(f"[CloudKitchen] TTS done: {duration:.1f}s")
        except Exception as e:
            print(f"[CloudKitchen] TTS failed: {e} — silent reel")

        # Ambient music
        music_path = self.generate_ambient_music(duration)

        per_clip = duration / 4
        clips = []
        for fp in frame_paths:
            clip = ImageClip(fp).set_duration(per_clip)
            # Ken Burns: slow zoom in (2% over clip duration)
            clip = clip.resize(lambda t, d=per_clip: 1.0 + 0.02 * (t / d))
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")

        # Mix TTS + ambient music
        audio_tracks = []
        if tts_audio:
            audio_tracks.append(tts_audio)
        if music_path and os.path.exists(music_path):
            try:
                music = AudioFileClip(music_path).volumex(0.22)
                if music.duration < duration:
                    music = audio_loop(music, duration=duration)
                else:
                    music = music.subclip(0, duration)
                audio_tracks.append(music)
            except Exception as e:
                print(f"[CloudKitchen] Music mix failed: {e}")

        if audio_tracks:
            mixed = CompositeAudioClip(audio_tracks) if len(audio_tracks) > 1 else audio_tracks[0]
            video = video.set_audio(mixed)

        out_path = os.path.join(MP_DIR, f"cloudk_reel_{uuid4().hex[:8]}.mp4")
        video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        print(f"[CloudKitchen] Reel created: {out_path}")
        return out_path

    # ------------------------------------------------------------------ #
    #  Bio Update                                                          #
    # ------------------------------------------------------------------ #

    def update_bio(self, cl):
        try:
            cl.account_edit(biography=BIO_TEXT, external_url=SWIGGY)
            print("[CloudKitchen] Bio updated.")
        except Exception as e:
            print(f"[CloudKitchen] Bio update failed (non-critical): {e}")

    # ------------------------------------------------------------------ #
    #  Instagram Posting                                                   #
    # ------------------------------------------------------------------ #

    def _get_client(self):
        username = os.environ.get("CLOUDK_INSTAGRAM_USERNAME", "").strip()
        password = os.environ.get("CLOUDK_INSTAGRAM_PASSWORD", "").strip()
        if not username or not password:
            print("[CloudKitchen] CLOUDK_INSTAGRAM_USERNAME/PASSWORD not set.")
            return None

        session_json = os.environ.get("CLOUDK_INSTAGRAM_SESSION_JSON", "").strip()
        if session_json:
            os.environ["INSTAGRAM_SESSION_JSON"] = session_json

        from .Instagram import Instagram
        ig = Instagram(username, password)
        return ig._get_client()

    def post_photo(self, image_path: str, dish: str, caption_body: str) -> str:
        from pathlib import Path
        cl = self._get_client()
        if not cl:
            return ""
        self.update_bio(cl)
        caption = f"{caption_body}{ORDER_BLOCK}\n\n{HASHTAGS}"
        try:
            media = cl.photo_upload(Path(image_path), caption)
            url = f"https://www.instagram.com/p/{media.code}/"
            success(f"Grand Forno photo posted: {url}")
            print(f"[CloudKitchen] Photo posted: {url}")
            return url
        except Exception as e:
            print(f"[CloudKitchen] Photo post FAILED: {e}")
            traceback.print_exc()
            return ""

    def post_reel(self, video_path: str, dish: str, caption_body: str) -> str:
        from pathlib import Path
        cl = self._get_client()
        if not cl:
            return ""
        self.update_bio(cl)
        caption = f"{caption_body}{ORDER_BLOCK}\n\n{HASHTAGS}"
        try:
            media = cl.clip_upload(Path(video_path), caption)
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
                reel_path = self.make_reel(dish, script, benefits)
                self.post_reel(reel_path, dish, caption_body)
            else:
                caption_body = self.generate_caption(dish, benefits)
                img_bytes = self.generate_food_image(dish)
                img_path = self.compose_photo(img_bytes, dish, benefits)
                self.post_photo(img_path, dish, caption_body)

            success(f"CloudKitchen done: {dish}")

        except Exception as e:
            print(f"[CloudKitchen] run() crashed: {e}")
            traceback.print_exc()
