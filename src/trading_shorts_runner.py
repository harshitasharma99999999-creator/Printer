import argparse
import os
import sys

from cache import get_cache_path
from classes.TradingShorts import TRADING_SHORTS_NICHE, TradingShorts
from classes.TradingVoice import TradingVoice
from config import get_groq_api_key, get_ollama_model
from llm_provider import select_model
from status import error, info, success
from utils import preflight_youtube_api


def _use_groq() -> bool:
    return bool(os.environ.get("GROQ_API_KEY") or get_groq_api_key())


def _ensure_llm_selected(model: str | None) -> None:
    if _use_groq():
        return
    resolved = (model or get_ollama_model() or "").strip()
    if not resolved:
        error("No Ollama model configured. Set `ollama_model` in config.json or pass --model.")
        sys.exit(1)
    select_model(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Tradingclub daily YouTube Shorts automation.")
    parser.add_argument("--account-id", default="tradingclub-q7u")
    parser.add_argument("--nickname", default="Tradingclub-q7u")
    parser.add_argument("--language", default="english")
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    os.makedirs(get_cache_path(), exist_ok=True)
    _ensure_llm_selected(args.model)

    youtube = TradingShorts(
        args.account_id,
        args.nickname,
        "",
        TRADING_SHORTS_NICHE,
        args.language,
    )

    preflight_youtube_api(TradingShorts._get_yt_credentials(), verbose=True)
    info("Running Tradingclub Shorts pipeline...")
    youtube.generate_video(TradingVoice())
    ok = youtube.upload_video()
    if not ok:
        error("Tradingclub Shorts upload failed.")
        sys.exit(2)
    success("Tradingclub Short uploaded.")


if __name__ == "__main__":
    main()
