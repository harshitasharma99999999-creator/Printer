"""Generate reusable Fresh HVN cinematic ad assets.

The daily GitHub runner cannot depend on paid image/video tools, so these
assets are generated locally with Pillow and reused by FFmpeg. They give each
Short/Reel a cinematic campaign setting while preserving exact Fresh HVN text
through controlled overlays.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from grand_forno_common import BRAND_NAME, ROOT

WIDTH = 1080
HEIGHT = 1920
ASSET_DIR = ROOT / "assets" / "cinematic"
BACKGROUND_DIR = ASSET_DIR / "backgrounds"
CAN_PATH = ASSET_DIR / "fresh-hvn-can-transparent.png"


STYLE_COLORS = {
    "fruit-explosion": {
        "top": (20, 10, 18),
        "bottom": (25, 52, 33),
        "accent": (235, 32, 45),
        "accent2": (41, 171, 90),
        "liquid": (229, 42, 54),
    },
    "ice-drop": {
        "top": (5, 18, 32),
        "bottom": (12, 68, 96),
        "accent": (139, 223, 255),
        "accent2": (224, 248, 255),
        "liquid": (55, 169, 230),
    },
    "fruit-vortex": {
        "top": (18, 14, 38),
        "bottom": (28, 78, 52),
        "accent": (250, 120, 45),
        "accent2": (232, 52, 83),
        "liquid": (250, 169, 42),
    },
    "gym-recovery": {
        "top": (14, 15, 18),
        "bottom": (34, 42, 34),
        "accent": (142, 220, 112),
        "accent2": (232, 232, 214),
        "liquid": (102, 184, 84),
    },
    "office-refresh": {
        "top": (16, 22, 28),
        "bottom": (31, 73, 61),
        "accent": (255, 214, 74),
        "accent2": (71, 185, 147),
        "liquid": (255, 184, 66),
    },
    "mumbai-local-campaign": {
        "top": (17, 23, 32),
        "bottom": (40, 64, 58),
        "accent": (255, 196, 68),
        "accent2": (62, 174, 119),
        "liquid": (244, 116, 54),
    },
    "ingredient-journey": {
        "top": (18, 22, 20),
        "bottom": (34, 76, 48),
        "accent": (255, 96, 80),
        "accent2": (87, 204, 109),
        "liquid": (235, 63, 72),
    },
}

ALIASES = {
    "fruit explosion": "fruit-explosion",
    "ice drop": "ice-drop",
    "fruit flies together to form the can": "fruit-vortex",
    "fruit vortex": "fruit-vortex",
    "gym recovery": "gym-recovery",
    "office refresh": "office-refresh",
    "mumbai local campaign": "mumbai-local-campaign",
    "ingredient journey": "ingredient-journey",
}


def style_slug(style: str | None) -> str:
    raw = (style or "fruit-explosion").strip().lower()
    if raw in ALIASES:
        return ALIASES[raw]
    cleaned = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return cleaned if cleaned in STYLE_COLORS else "fruit-explosion"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        ROOT / "fonts" / "bold_font.ttf",
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def vertical_gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), top)
    pixels = image.load()
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(WIDTH):
            pixels[x, y] = color
    return image.convert("RGBA")


def add_radial_light(image: Image.Image, center: tuple[int, int], color: tuple[int, int, int], radius: int) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = center
    for step in range(radius, 0, -18):
        alpha = int(105 * (step / radius) ** 2)
        draw.ellipse((cx - step, cy - step, cx + step, cy + step), fill=(*color, alpha))
    image.alpha_composite(overlay.filter(ImageFilter.GaussianBlur(32)))


def add_fruit_particles(draw: ImageDraw.ImageDraw, palette: dict[str, tuple[int, int, int]], seed: int) -> None:
    rng = random.Random(seed)
    fruit_colors = [
        palette["accent"],
        palette["accent2"],
        palette["liquid"],
        (248, 238, 106),
        (248, 248, 232),
    ]
    for _ in range(150):
        angle = rng.uniform(0, math.tau)
        distance = rng.uniform(170, 640)
        x = int(WIDTH / 2 + math.cos(angle) * distance * rng.uniform(0.6, 1.05))
        y = int(720 + math.sin(angle) * distance * rng.uniform(0.55, 1.15))
        size = rng.randint(8, 34)
        color = rng.choice(fruit_colors)
        draw.ellipse((x - size, y - size, x + size, y + size), fill=(*color, rng.randint(120, 220)))
        if rng.random() > 0.55:
            draw.arc(
                (x - size * 2, y - size, x + size * 2, y + size),
                start=rng.randint(0, 120),
                end=rng.randint(190, 330),
                fill=(*color, 160),
                width=3,
            )


def add_ice_shards(draw: ImageDraw.ImageDraw, palette: dict[str, tuple[int, int, int]], seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(90):
        x = rng.randint(-80, WIDTH + 80)
        y = rng.randint(250, HEIGHT - 120)
        length = rng.randint(35, 130)
        points = [
            (x, y),
            (x + rng.randint(-22, 22), y + length),
            (x + rng.randint(18, 70), y + rng.randint(20, length)),
        ]
        draw.polygon(points, fill=(*palette["accent2"], rng.randint(42, 118)))
        draw.line(points + [points[0]], fill=(*palette["accent"], 150), width=2)


def add_gym_silhouette(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((0, 1260, WIDTH, HEIGHT), fill=(8, 11, 10, 155))
    draw.line((145, 1020, 935, 1020), fill=(210, 220, 190, 125), width=14)
    draw.ellipse((452, 710, 628, 886), fill=(16, 18, 18, 190))
    draw.rounded_rectangle((410, 870, 670, 1245), radius=65, fill=(14, 16, 16, 205))
    draw.line((265, 1110, 815, 1110), fill=(18, 20, 20, 210), width=48)
    draw.ellipse((205, 1038, 300, 1133), fill=(18, 20, 20, 230))
    draw.ellipse((780, 1038, 875, 1133), fill=(18, 20, 20, 230))


def add_motion_streaks(draw: ImageDraw.ImageDraw, palette: dict[str, tuple[int, int, int]], seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(60):
        x = rng.randint(-200, WIDTH + 120)
        y = rng.randint(160, HEIGHT - 220)
        length = rng.randint(160, 460)
        color = rng.choice([palette["accent"], palette["accent2"], palette["liquid"]])
        draw.line((x, y, x + length, y + rng.randint(-60, 60)), fill=(*color, rng.randint(45, 105)), width=rng.randint(3, 9))


def create_background(slug: str) -> Image.Image:
    palette = STYLE_COLORS[slug]
    image = vertical_gradient(palette["top"], palette["bottom"])
    add_radial_light(image, (WIDTH // 2, 700), palette["accent"], 560)
    add_radial_light(image, (WIDTH // 2, 1280), palette["accent2"], 420)
    draw = ImageDraw.Draw(image, "RGBA")

    if slug == "ice-drop":
        add_ice_shards(draw, palette, 12)
        add_motion_streaks(draw, palette, 13)
    elif slug == "gym-recovery":
        add_motion_streaks(draw, palette, 22)
        add_gym_silhouette(draw)
    elif slug in {"fruit-vortex", "ingredient-journey"}:
        add_motion_streaks(draw, palette, 31)
        add_fruit_particles(draw, palette, 32)
    else:
        add_fruit_particles(draw, palette, 42)
        add_motion_streaks(draw, palette, 43)

    for y in range(0, HEIGHT, 14):
        alpha = 26 if y % 28 == 0 else 0
        draw.rectangle((0, y, WIDTH, y + 1), fill=(255, 255, 255, alpha))

    vignette = Image.new("RGBA", image.size, (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for radius in range(980, 100, -28):
        alpha = int(62 * (1 - radius / 980))
        vdraw.ellipse((WIDTH / 2 - radius, 880 - radius, WIDTH / 2 + radius, 880 + radius), outline=(0, 0, 0, alpha), width=34)
    image.alpha_composite(vignette.filter(ImageFilter.GaussianBlur(26)))
    return image.convert("RGB")


def create_can() -> Image.Image:
    image = Image.new("RGBA", (520, 980), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")
    body = (110, 110, 420, 895)
    draw.rounded_rectangle((132, 118, 398, 875), radius=86, fill=(238, 245, 238, 255), outline=(210, 226, 210, 255), width=5)
    draw.ellipse((132, 91, 398, 162), fill=(218, 229, 220, 255), outline=(248, 255, 248, 255), width=4)
    draw.ellipse((132, 837, 398, 908), fill=(176, 191, 181, 245), outline=(238, 248, 238, 255), width=4)
    draw.rounded_rectangle(body, radius=80, outline=(255, 255, 255, 90), width=10)
    draw.rectangle((166, 175, 210, 825), fill=(255, 255, 255, 92))
    draw.rectangle((332, 175, 368, 825), fill=(110, 142, 116, 42))
    draw.ellipse((230, 278, 290, 338), fill=(38, 132, 60, 255))
    draw.line((260, 335, 260, 408), fill=(31, 100, 45, 255), width=7)
    draw.arc((192, 300, 330, 438), start=202, end=340, fill=(31, 100, 45, 255), width=5)
    title_font = font(52)
    small_font = font(29)
    tiny_font = font(22)
    for idx, text in enumerate(["F R E S H", "H V N"]):
        bbox = draw.textbbox((0, 0), text, font=title_font)
        draw.text(((520 - (bbox[2] - bbox[0])) / 2, 450 + idx * 72), text, font=title_font, fill=(45, 88, 54, 255))
    tagline = "JUICE + SMOOTHIES"
    bbox = draw.textbbox((0, 0), tagline, font=small_font)
    draw.text(((520 - (bbox[2] - bbox[0])) / 2, 610), tagline, font=small_font, fill=(87, 122, 82, 255))
    size = "250 ML"
    bbox = draw.textbbox((0, 0), size, font=tiny_font)
    draw.text(((520 - (bbox[2] - bbox[0])) / 2, 690), size, font=tiny_font, fill=(88, 92, 88, 235))
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse((84, 878, 436, 952), fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))
    shadow.alpha_composite(image)
    return shadow


def ensure_cinematic_assets() -> dict[str, Path | dict[str, Path]]:
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    if not CAN_PATH.exists():
        create_can().save(CAN_PATH)
    backgrounds: dict[str, Path] = {}
    for slug in STYLE_COLORS:
        path = BACKGROUND_DIR / f"{slug}.png"
        if not path.exists():
            create_background(slug).save(path, quality=95)
        backgrounds[slug] = path
    return {"can": CAN_PATH, "backgrounds": backgrounds}


if __name__ == "__main__":
    assets = ensure_cinematic_assets()
    print(assets)
