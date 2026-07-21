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

CINEMATIC_AD_STYLES = [
    {
        "name": "Fruit Explosion",
        "hook": "A cold Fresh HVN can appears in darkness, then real fruit colour bursts around it",
        "caption_lead": "Real fruit just got cooler. A cinematic Fresh HVN can moment built for chilled cravings and direct orders.",
        "visual_direction": "dark studio, hero 250 ml aluminium can, fruit flying toward the can, liquid splash, condensation, sharp can-opening sound",
    },
    {
        "name": "Ice Drop",
        "hook": "The Fresh HVN can drops into crushed ice and the whole frame turns cold",
        "caption_lead": "Freshness sealed cold. A premium chilled drink shot with ice, droplets, and Fresh HVN energy.",
        "visual_direction": "slow-motion can drop, crushed ice explosion, cold droplets, rotating camera, premium reflections",
    },
    {
        "name": "Gym Recovery",
        "hook": "After the final set, the Fresh HVN can opens with a crisp cold snap",
        "caption_lead": "Your post-workout upgrade: a Fresh HVN drink for gym bags, busy days, and direct orders.",
        "visual_direction": "gym setting, towel and shaker nearby, macro can tab, ingredients shown, no muscle-building claim",
    },
    {
        "name": "Office Refresh",
        "hook": "At 4 PM, a cold Fresh HVN can turns the desk from dull to fresh",
        "caption_lead": "Refresh your 4 PM with Fresh HVN: premium beverage energy for office breaks and group orders.",
        "visual_direction": "modern desk, low-energy lighting shifts brighter after can opens, fruit and ice close-ups",
    },
    {
        "name": "Mumbai Local Campaign",
        "hook": "Mulund gets a colder, cleaner Fresh HVN can moment",
        "caption_lead": "Mumbai, drink fresh. Fresh HVN brings chilled juice and smoothie ads with a premium local feel.",
        "visual_direction": "Mumbai neighbourhood lifestyle, Mulund order focus, can appears naturally in gym, office or college routine",
    },
    {
        "name": "Ingredient Journey",
        "hook": "Fresh ingredients move from cut fruit to a chilled Fresh HVN can",
        "caption_lead": "What you see is what goes in. A clean Fresh HVN ingredient story with premium can-first visuals.",
        "visual_direction": "ingredient cuts, blending motion, liquid pour, can seal, chilled end card",
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
    return CINEMATIC_AD_STYLES[item_post_count(item["id"], history) % len(CINEMATIC_AD_STYLES)]


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
        f"{BRAND_NAME}'s {item['name']} is shown as a premium chilled 250 ml aluminium can with ice, condensation, and {ingredients}. "
        f"Visual direction: {angle['visual_direction']}. "
        f"Menu price stays exactly {item['price']}. "
        f"Order on {DIRECT_ORDER_CONTACT}."
    )
    caption = (
        f"{angle['caption_lead']} "
        f"Try {BRAND_NAME}'s {item['name']} - {benefits}, made for premium chilled beverage moments.\n\n"
        f"{item['serving_size']} serving.\n"
        f"Same menu price as Zomato - {item['price']}.\n"
        f"Best for office orders, gym bags, college breaks, chilled beverage cravings, and repeat drink orders.\n\n"
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
        "cinematic_style": angle["name"],
        "visual_direction": angle["visual_direction"],
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
        f"You write premium cinematic short-form beverage ads for {BRAND_NAME}, a Mumbai fresh juice and smoothie brand. "
        "The ad must feel like a premium canned beverage commercial, not a normal restaurant menu post. "
        "Write on-screen copy for a music-only Reel/Short, roughly 45-65 words. Be concise, bold, modern, and sales-focused. "
        "Usually make the hero object a Fresh HVN 250 ml aluminium can with cold condensation, ice, fresh fruit motion, liquid splash, dramatic lighting, macro can-opening sound, and a premium end card. "
        "Use one concrete sensory detail from the ingredients and one cinematic direction from the selected campaign style. Use only supplied facts. "
        "Avoid robotic phrases, over-polished hype, fake urgency, excessive emojis, and repeated lines. "
        "Never promise cures, guaranteed weight loss, disease prevention, or medical benefits. "
        "Safe phrases include protein-rich, refreshing, fiber-rich, supports digestion, "
        "healthy choice, energy boosting, and made with fresh fruits. "
        "Mention the price exactly as supplied and call it the same menu price as Zomato. "
        "Mention the serving size and one order use case such as office beverages, gym bags, college breaks, party drinks, smoothies, or repeat juice orders. "
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
        "cinematic_campaign_style": angle,
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
            "premium 250 ml aluminium can visual direction",
        ],
        "brand_consistency_rules": [
            "Preserve exact Fresh HVN spelling",
            "Do not invent extra label text",
            "Do not distort can shape",
            "Keep the can as a premium hero object where possible",
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
    content["cinematic_style"] = angle["name"]
    content["visual_direction"] = angle["visual_direction"]
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
