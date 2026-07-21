"""Create platform-ready Fresh HVN posting packs from a generated Reel."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from grand_forno_common import BRAND_NAME, DIRECT_ORDER_CONTACT, ROOT, read_json, write_json


PLATFORMS = {
    "tiktok": {
        "label": "TikTok",
        "upload_url": "https://www.tiktok.com/upload",
        "signup_url": "https://www.tiktok.com/signup",
        "hashtags": "#FreshHVN #FreshJuice #Smoothies #MumbaiFood #MumbaiDrinks #HealthyDrinks #JuiceLovers #FoodTok #DrinkTok",
    },
    "pinterest": {
        "label": "Pinterest",
        "upload_url": "https://www.pinterest.com/pin-creation-tool/",
        "signup_url": "https://www.pinterest.com/business/create/",
        "hashtags": "#FreshHVN #FreshJuice #Smoothies #HealthyDrinks #MumbaiFood",
    },
    "x": {
        "label": "X",
        "upload_url": "https://x.com/compose/post",
        "signup_url": "https://x.com/i/flow/signup",
        "hashtags": "#FreshHVN #FreshJuice #Smoothies #Mumbai",
    },
    "threads": {
        "label": "Threads",
        "upload_url": "https://www.threads.net/",
        "signup_url": "https://www.threads.net/",
        "hashtags": "#FreshHVN #FreshJuice #Smoothies #Mumbai",
    },
    "facebook": {
        "label": "Facebook Reels",
        "upload_url": "https://business.facebook.com/latest/content",
        "signup_url": "https://www.facebook.com/pages/create/",
        "hashtags": "#FreshHVN #FreshJuice #Smoothies #MumbaiDrinks",
    },
    "whatsapp": {
        "label": "WhatsApp Status",
        "upload_url": "https://web.whatsapp.com/",
        "signup_url": "https://web.whatsapp.com/",
        "hashtags": "#FreshHVN",
    },
}


def short_caption(content: dict, platform: str) -> str:
    item = content["item"]
    base = (
        f"{BRAND_NAME} {item['name']} - {item['price']}.\n"
        f"Fresh juice and smoothies in Mumbai.\n"
        f"Order on {DIRECT_ORDER_CONTACT}."
    )
    if platform == "x":
        return f"{BRAND_NAME} {item['name']} - {item['price']}. Order on {DIRECT_ORDER_CONTACT}. {PLATFORMS[platform]['hashtags']}"
    if platform == "whatsapp":
        return f"{BRAND_NAME} {item['name']} - {item['price']}\nOrder on {DIRECT_ORDER_CONTACT}"
    return f"{base}\n\n{PLATFORMS[platform]['hashtags']}"


def create_pack(video_path: Path, content_path: Path, output_dir: Path) -> dict:
    video_path = video_path.resolve()
    content_path = content_path.resolve()
    output_dir = output_dir.resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if not content_path.exists():
        raise FileNotFoundError(content_path)

    content = read_json(content_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "brand": BRAND_NAME,
        "source_video": str(video_path),
        "source_content": str(content_path),
        "order_phone": DIRECT_ORDER_CONTACT,
        "platforms": {},
    }

    for platform, meta in PLATFORMS.items():
        folder = output_dir / platform
        folder.mkdir(parents=True, exist_ok=True)
        video_copy = folder / f"fresh-hvn-{platform}.mp4"
        shutil.copy2(video_path, video_copy)
        caption = short_caption(content, platform)
        (folder / "caption.txt").write_text(caption + "\n", encoding="utf-8")
        write_json(
            folder / "post.json",
            {
                "platform": platform,
                "label": meta["label"],
                "upload_url": meta["upload_url"],
                "signup_url": meta["signup_url"],
                "video": video_copy.name,
                "caption": caption,
            },
        )
        manifest["platforms"][platform] = {
            "label": meta["label"],
            "folder": str(folder.relative_to(ROOT)),
            "upload_url": meta["upload_url"],
            "signup_url": meta["signup_url"],
        }

    write_json(output_dir / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    manifest = create_pack(Path(args.video), Path(args.content), Path(args.output_dir))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
