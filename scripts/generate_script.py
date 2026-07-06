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
    ROOT,
    SWIGGY_URL,
    ZOMATO_URL,
    read_json,
    validate_marketing_copy,
    write_json,
)


def fallback_content(item: dict[str, Any]) -> dict[str, Any]:
    ingredients = ", ".join(item["ingredients"][:4])
    benefits = ", ".join(item["benefits"])
    script = (
        f"Looking for a fresh and satisfying bowl? Try Grand Forno's {item['name']}. "
        f"It brings together {ingredients}, with a delicious premium finish. "
        f"It is {benefits}, and made for busy Mumbai days. "
        f"You get a {item['serving_size']} serving with {item['protein']} of protein "
        f"for {item['price']}. Order Grand Forno now on Zomato or Swiggy!"
    )
    caption = (
        f"Fresh, colourful and ready when you are. Try Grand Forno's {item['name']} — "
        f"{benefits} and made with fresh fruits. 🍓🥭\n\n"
        f"Order Grand Forno on Zomato:\n{ZOMATO_URL}\n\n"
        f"Order on Swiggy:\n{SWIGGY_URL}\n\n{HASHTAGS}"
    )
    return {
        "script": script,
        "title": f"{item['name']} at Grand Forno 🥭 #Shorts",
        "caption": caption,
        "hashtags": HASHTAGS.split(),
        "benefit_overlays": item["benefits"][:3],
    }


def generate_with_openai(item: dict[str, Any]) -> dict[str, Any]:
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
        "Use a friendly, natural Indian food-delivery tone. Write narration for 20-30 seconds, "
        "roughly 65-85 words. Be concise and sales-focused. Use only supplied facts. "
        "Never promise cures, guaranteed weight loss, disease prevention, or medical benefits. "
        "Safe phrases include protein-rich, refreshing, fiber-rich, supports digestion, "
        "healthy choice, energy boosting, and made with fresh fruits. "
        "The caption MUST contain the two exact order labels, URLs, and every exact hashtag "
        "provided in the input. The YouTube title must be at most 100 characters and include #Shorts."
    )
    prompt = {
        "restaurant": "Grand Forno",
        "youtube": "@fornogrand",
        "instagram": "grand_forno",
        "menu_item": item,
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
    return json.loads(output_text)


def generate(item: dict[str, Any], allow_fallback: bool) -> dict[str, Any]:
    if os.getenv("OPENAI_API_KEY"):
        try:
            content = generate_with_openai(item)
        except Exception:
            if not allow_fallback:
                raise
            content = fallback_content(item)
            content["generation_warning"] = "OpenAI failed; deterministic copy fallback used."
    elif allow_fallback:
        content = fallback_content(item)
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
