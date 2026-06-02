import argparse
import os
import sys

from cache import get_cache_path
from classes.TradingEducation import TRADING_EDUCATION_NICHE, TradingEducation
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
    parser = argparse.ArgumentParser(description="Run Tradingclub long-form education automation.")
    parser.add_argument("--account-id", default="tradingclub-q7u")
    parser.add_argument("--nickname", default="Tradingclub-q7u")
    parser.add_argument("--language", default="english")
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    os.makedirs(get_cache_path(), exist_ok=True)
    _ensure_llm_selected(args.model)

    trading = TradingEducation(
        args.account_id,
        args.nickname,
        "",
        TRADING_EDUCATION_NICHE,
        args.language,
    )

    preflight_youtube_api(TradingEducation._get_yt_credentials(), verbose=True)
    info("Running Tradingclub long-form education pipeline...")
    result = trading.run()
    if not result.get("url"):
        error("Tradingclub long-form upload failed.")
        sys.exit(2)
    success(f"Tradingclub long-form uploaded: {result['url']}")


if __name__ == "__main__":
    main()
