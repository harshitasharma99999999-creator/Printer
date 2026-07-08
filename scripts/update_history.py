"""Append one completed Grand Forno automation run to post history."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from grand_forno_common import read_json, utc_now, write_json


def update_history(
    history_path: Path,
    content_path: Path,
    youtube: dict[str, Any],
    instagram: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    history = read_json(history_path)
    content = read_json(content_path)
    entry = {
        "run_id": run_id,
        "created_at": utc_now(),
        "item_id": content["item"]["id"],
        "item_name": content["item"]["name"],
        "title": content["title"],
        "creative_angle": content.get("creative_angle"),
        "youtube": youtube,
        "instagram": instagram,
    }
    history.setdefault("posts", []).append(entry)
    write_json(history_path, history)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", default="data/post_history.json")
    parser.add_argument("--content", required=True)
    parser.add_argument("--youtube-result", required=True)
    parser.add_argument("--instagram-result", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(
        update_history(
            Path(args.history),
            Path(args.content),
            read_json(Path(args.youtube_result)),
            read_json(Path(args.instagram_result)),
            args.run_id,
        )
    )


if __name__ == "__main__":
    main()
