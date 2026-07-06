"""Shared helpers for the Grand Forno social automation."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

ZOMATO_URL = "https://zomato.onelink.me/xqzv/w36rgxfb"
SWIGGY_URL = "https://www.swiggy.com/menu/1308871?source=sharing"
HASHTAGS = (
    "#GrandForno #FruitSalad #HealthyFood #HealthyBowl #Zomato #Swiggy "
    "#MumbaiFood #CloudKitchen #ProteinBowl #FreshFruits"
)
UNSAFE_CLAIMS = (
    "cure",
    "cures",
    "guaranteed weight loss",
    "medical benefit",
    "treats",
    "prevents disease",
)


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def validate_marketing_copy(content: dict[str, Any]) -> None:
    combined = " ".join(str(value) for value in content.values()).lower()
    found = [claim for claim in UNSAFE_CLAIMS if claim in combined]
    if found:
        raise ValueError(f"Unsafe marketing claim(s) generated: {', '.join(found)}")

    caption = str(content.get("caption", ""))
    required = [ZOMATO_URL, SWIGGY_URL, *HASHTAGS.split()]
    missing = [value for value in required if value not in caption]
    if missing:
        raise ValueError(f"Caption is missing required content: {', '.join(missing)}")


def select_next_item(menu: list[dict[str, Any]], history: dict[str, Any]) -> dict[str, Any]:
    """Choose the least recently used item, preserving menu order for ties."""
    last_used: dict[str, str] = {}
    for post in history.get("posts", []):
        youtube_ok = post.get("youtube", {}).get("status") == "uploaded"
        instagram_ok = post.get("instagram", {}).get("status") == "uploaded"
        if not (youtube_ok or instagram_ok):
            continue
        item_id = post.get("item_id")
        created_at = post.get("created_at", "")
        if item_id and created_at > last_used.get(item_id, ""):
            last_used[item_id] = created_at
    return min(menu, key=lambda item: (last_used.get(item["id"], ""), menu.index(item)))


def require_env(*names: str) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def append_event(log_path: Path, event: str, **fields: Any) -> None:
    entry = {"timestamp": utc_now(), "event": event, **fields}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
