"""Generate safe Grand Forno script, title, caption, hashtags, and overlays."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

from grand_forno_common import (
    HASHTAGS,
    SWIGGY_URL,
    ZOMATO_URL,
    read_json,
    validate_marketing_copy,
    write_json,
)

CREATIVE_ANGLES = [
    {
        "name": "busy-day light meal",
        "hook": "If you want something fresh without making it feel like a heavy meal",
        "caption_lead": "Fresh fruit, clean flavours, and a bowl that feels good for busy days.",
    },
    {
        "name": "post-workout fresh bowl",
        "hook": "After a workout or a long workday, this is the kind of bowl that still feels light",
        "caption_lead": "A fresh, satisfying bowl for days when you want flavour without going heavy.",
    },
    {
        "name": "office snack upgrade",
        "hook": "If your usual snack feels boring, this fruit bowl is an easy upgrade",
        "caption_lead": "Upgrade your snack break with fresh fruit, clean flavours, and a colourful bowl.",
    },
    {
        "name": "cool refreshing craving",
        "hook": "When you want something chilled, colourful, and refreshing",
        "caption_lead": "For a refreshing craving, keep it simple: fresh fruit, balanced flavours, easy ordering.",
    },
    {
        "name": "simple healthy choice",
        "hook": "Some days, a simple fresh bowl is exactly what you need",
        "caption_lead": "A simple healthy choice with fresh fruit, good texture, and Grand Forno flavour.",
    },
]


def item_post_count(item_id: str, history: dict[str, Any] | None) -> int:
    if not history:
        return 0
    return sum(
        1
        for post in history.get("posts", [])
        if post.get("item_id") == item_id
        and (
            post.get("youtube", {}).get("status") == "uploaded"
            or post.get("instagram", {}).get("status") == "uploaded"
        )
    )


def choose_creative_angle(item: dict[str, Any], history: dict[str, Any] | None) -> dict[str, str]:
    return CREATIVE_ANGLES[item_post_count(item["id"], history) % len(CREATIVE_ANGLES)]


def fallback_content(item: dict[str, Any], history: dict[str, Any] | None = None) -> dict[str, Any]:
    ingredients = ", ".join(item["ingredients"][:4])
    benefits = ", ".join(item["benefits"])
    angle = choose_creative_angle(item, history)
    script = (
        f"{angle['hook']}, "
        f"Grand Forno's {item['name']} is a lovely pick. "
        f"You get {ingredients}, packed neatly into a colourful {item['serving_size']} bowl. "
        f"It is {benefits}, with {item['protein']} protein and around {item['calories']} calories. "
        f"Simple, refreshing, and easy to order on Zomato or Swiggy."
    )
    caption = (
        f"{angle['caption_lead']} "
        f"Try Grand Forno's {item['name']} — {benefits}, made with fresh fruits.\n\n"
        f"Order Grand Forno on Zomato:\n{ZOMATO_URL}\n\n"
        f"Order on Swiggy:\n{SWIGGY_URL}\n\n{HASHTAGS}"
    )
    return {
        "script": script,
        "title": f"{item['name']} at Grand Forno #Shorts",
        "caption": caption,
        "hashtags": HASHTAGS.split(),
        "benefit_overlays": item["benefits"][:3],
        "creative_angle": angle["name"],
    }


def generate_with_openai(item: dict[str, Any], history: dict[str, Any] | None = None) -> dict[str, Any]:
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["script", "title", "caption", "hashtags", "benefit_overlays"],
        "properties": {
            "script": {"type": "string"},
            "title": {"type": "string"},
            "caption": {"type": "string"},
            "hashtags": {"type": "array", "items": {"type": "string"}},
            "benefit_overlays": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 3,
            },
        },
    }
    instructions = (
        "You write short-form food ads for Grand Forno, a Mumbai cloud kitchen. "
        "Use a friendly, natural Indian food-delivery tone that feels like a real food creator "
        "or small restaurant owner speaking, not a generic AI advertisement. Write narration "
        "for 20-30 seconds, roughly 60-82 words. Be concise, warm, and sales-focused. "
        "Make it appealing to health-conscious customers: fresh fruit, light meal, clean flavours, "
        "protein or fiber where supplied, busy-day convenience, and satisfying texture. "
        "Use one concrete sensory detail from the ingredients, such as creamy yogurt, juicy fruit, "
        "crunchy seeds, bright berries, or chilled fresh fruit. Use only supplied facts. "
        "Avoid robotic phrases, over-polished hype, fake urgency, excessive emojis, and repeated lines. "
        "Never promise cures, guaranteed weight loss, disease prevention, or medical benefits. "
        "Safe phrases include protein-rich, refreshing, fiber-rich, supports digestion, "
        "healthy choice, energy boosting, and made with fresh fruits. "
        "The caption MUST contain the two exact order labels, URLs, and every exact hashtag "
        "provided in the input. The YouTube title must be at most 100 characters and include #Shorts."
    )
    recent_posts = []
    if history:
        recent_posts = [
            {
                "item_id": post.get("item_id"),
                "title": post.get("title"),
                "creative_angle": post.get("creative_angle"),
            }
            for post in history.get("posts", [])[-12:]
        ]
    angle = choose_creative_angle(item, history)
    prompt = {
        "restaurant": "Grand Forno",
        "youtube": "@fornogrand",
        "instagram": "grand_forno",
        "menu_item": item,
        "creative_angle": angle,
        "recent_posts_to_avoid_repeating": recent_posts,
        "freshness_rule": (
            "Do not repeat the same hook, title, caption opening, or wording pattern "
            "from recent posts. Keep the item facts the same, but make this post feel newly written."
        ),
        "required_caption_block": (
            f"Order Grand Forno on Zomato:\n{ZOMATO_URL}\n\n"
            f"Order on Swiggy:\n{SWIGGY_URL}\n\n{HASHTAGS}"
        ),
    }
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "instructions": instructions,
            "input": json.dumps(prompt, ensure_ascii=False),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "grand_forno_post",
                    "strict": True,
                    "schema": schema,
                }
            },
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    output_text = payload.get("output_text")
    if not output_text:
        chunks = []
        for output in payload.get("output", []):
            for part in output.get("content", []):
                if part.get("type") == "output_text":
                    chunks.append(part.get("text", ""))
        output_text = "".join(chunks)
    if not output_text:
        raise RuntimeError("OpenAI returned no output text")
    content = json.loads(output_text)
    content["creative_angle"] = angle["name"]
    return content


def generate(
    item: dict[str, Any],
    allow_fallback: bool,
    history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if os.getenv("OPENAI_API_KEY"):
        try:
            content = generate_with_openai(item, history)
        except Exception:
            if not allow_fallback:
                raise
            content = fallback_content(item, history)
            content["generation_warning"] = "OpenAI failed; deterministic copy fallback used."
    elif allow_fallback:
        content = fallback_content(item, history)
        content["generation_warning"] = "OPENAI_API_KEY absent; deterministic copy fallback used."
    else:
        raise RuntimeError("OPENAI_API_KEY is required when fallback mode is disabled")
    content["item"] = item
    validate_marketing_copy(content)
    return content


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", required=True, help="Path to selected menu item JSON")
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-fallback", action="store_true")
    args = parser.parse_args()
    item = read_json(Path(args.item))
    write_json(Path(args.output), generate(item, args.allow_fallback))


if __name__ == "__main__":
    main()
