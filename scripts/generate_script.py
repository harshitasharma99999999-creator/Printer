"""Generate safe Fresh HVN script, title, caption, hashtags, and overlays."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import requests

from grand_forno_common import (
    BRAND_NAME,
    DIRECT_ORDER_CONTACT,
    HASHTAGS,
    WHATSAPP_CTA,
    read_json,
    validate_marketing_copy,
    write_json,
)

CREATIVE_ANGLES = [
    {
        "name": "busy-day fresh drink",
        "hook": "Your busy day can still have something chilled, colourful, and fresh",
        "caption_lead": "A fresh drink for busy days when you want something colourful, refreshing, and easy to order directly.",
    },
    {
        "name": "post-workout cooler",
        "hook": "Post-workout or post-office, a chilled drink keeps things fresh without feeling heavy",
        "caption_lead": "A satisfying post-workout or office beverage with fruit, freshness, and clean flavour.",
    },
    {
        "name": "office beverage upgrade",
        "hook": "If the office beverage plan is boring again, send this Fresh HVN drink to the group chat",
        "caption_lead": "Office beverage upgrade: fresh fruits, clean flavour, and drinks people can actually agree on.",
    },
    {
        "name": "cool refreshing craving",
        "hook": "When Mumbai feels too warm, a chilled fruit bowl just makes sense",
        "caption_lead": "For a refreshing craving, keep it simple: chilled fruit, balanced flavour, direct ordering.",
    },
    {
        "name": "simple healthy choice",
        "hook": "Some days, the better choice is just a fresh bowl that tastes good",
        "caption_lead": "A simple fresh choice with real fruit, good texture, and Fresh HVN flavour.",
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


def clean_text(value: Any) -> Any:
    if isinstance(value, str):
        value = value.replace(chr(8212), "-")
        value = value.replace(chr(8211), "-")
        value = value.replace(chr(226) + chr(8364) + chr(8221), "-")
        value = value.replace(chr(226) + chr(8364) + chr(8220), "-")
        replacements = {
            "â€”": "-",
            "â€“": "-",
            "â€˜": "'",
            "â€™": "'",
            "â€œ": '"',
            "â€": '"',
            "â‚¹": "Rs ",
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [clean_text(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_text(item) for key, item in value.items()}
    return value


def fallback_content(item: dict[str, Any], history: dict[str, Any] | None = None) -> dict[str, Any]:
    ingredients = ", ".join(item["ingredients"][:4])
    benefits = ", ".join(item["benefits"])
    angle = choose_creative_angle(item, history)
    script = (
        f"{angle['hook']}, "
        f"{BRAND_NAME}'s {item['name']} brings {ingredients} into one fresh {item['serving_size']} serving. "
        f"It is {benefits}, with {item['protein']} protein, around {item['calories']} calories, and the same menu price as Zomato - {item['price']}. "
        f"Order on {DIRECT_ORDER_CONTACT}."
    )
    caption = (
        f"{angle['caption_lead']} "
        f"Try {BRAND_NAME}'s {item['name']} - {benefits}, made with fresh fruits.\n\n"
        f"{item['serving_size']}, {item['protein']} protein, around {item['calories']} calories.\n"
        f"Same menu price as Zomato - {item['price']}.\n"
        f"Best for office orders, post-workout cravings, chilled beverage breaks, and repeat drink orders.\n\n"
        f"Order directly for quick confirmation and easy custom coordination.\n"
        f"{WHATSAPP_CTA}\n\n{HASHTAGS}"
    )
    return {
        "script": script,
        "title": f"{BRAND_NAME} {item['name']} #Shorts",
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
        f"You write short-form beverage ads for {BRAND_NAME}, a Mumbai fresh juice and smoothie brand. "
        "Use a friendly, natural Indian food-delivery tone that feels like a real food creator "
        "or small restaurant owner speaking, not a generic AI advertisement. Write on-screen copy "
        "for a music-only Reel/Short, roughly 45-65 words. Be concise, warm, and sales-focused. "
        "Make it appealing to health-conscious customers: fresh juices, smoothies, clean flavours, "
        "aluminium juice cans where supplied, protein or fiber where supplied, busy-day convenience, office orders, WhatsApp orders, "
        "direct phone orders, Instagram DMs, and satisfying texture. "
        "Use one concrete sensory detail from the ingredients, such as creamy yogurt, juicy fruit, "
        "crunchy seeds, bright berries, or chilled fresh fruit. Use only supplied facts. "
        "Avoid robotic phrases, over-polished hype, fake urgency, excessive emojis, and repeated lines. "
        "Never promise cures, guaranteed weight loss, disease prevention, or medical benefits. "
        "Safe phrases include protein-rich, refreshing, fiber-rich, supports digestion, "
        "healthy choice, energy boosting, and made with fresh fruits. "
        "Mention the price exactly as supplied and call it the same menu price as Zomato. "
        "Mention the serving size and one order use case such as office beverages, party drinks, smoothies, or repeat juice orders. "
        "The caption MUST NOT mention Zomato ordering, Swiggy ordering, Zomato links, or Swiggy links. "
        "Do not mention platform fees, commissions, aggregator charges, or cutting out delivery apps. "
        "Frame direct ordering as quick confirmation, easy custom coordination, and personal service. "
        "It may say the direct price is the same as Zomato. "
        f"The caption MUST include the exact phrase: Order on {DIRECT_ORDER_CONTACT}. "
        "The caption MUST contain every exact hashtag provided in the input and the exact WhatsApp/call CTA. "
        "The YouTube title must be at most 100 characters and include #Shorts."
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
        "restaurant": BRAND_NAME,
        "youtube": "@fresh_hvn",
        "instagram": "fresh_hvn",
        "menu_item": item,
        "creative_angle": angle,
        "recent_posts_to_avoid_repeating": recent_posts,
        "freshness_rule": (
            "Do not repeat the same hook, title, caption opening, or wording pattern "
            "from recent posts. Keep the item facts the same, but make this post feel newly written."
        ),
        "required_caption_block": f"{WHATSAPP_CTA}\n\n{HASHTAGS}",
        "forbidden_caption_words": ["Order on Zomato", "Order on Swiggy", "Zomato:", "Swiggy:"],
        "must_include_sales_details": [
            "exact price from menu_item.price",
            "same menu price as Zomato",
            "serving_size",
            "protein when available",
            f"Order on {DIRECT_ORDER_CONTACT}",
            "office, party, repeat, or group order use case",
        ],
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
                    "name": "fresh_hvn_post",
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
    content = clean_text(content)
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
