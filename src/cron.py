# RUN THIS N AMOUNT OF TIMES
import argparse
import os
import sys
import random

from status import *
from cache import get_accounts, get_products
from config import get_verbose, get_ollama_model, get_groq_api_key
from llm_provider import select_model

SHORTS_NICHES = [
    "manifestation",
    "law of attraction",
    "abundance mindset",
    "self love and confidence",
    "morning motivation",
    "gratitude and positivity",
    "mindfulness and peace",
    "success habits",
    "stoicism",
    "spiritual awakening",
]

def _use_groq() -> bool:
    return bool(os.environ.get("GROQ_API_KEY") or get_groq_api_key())


def _ensure_llm_selected(model: str | None) -> None:
    if _use_groq():
        return

    resolved = (model or get_ollama_model() or "").strip()
    if not resolved:
        error(
            "No Ollama model configured.\n"
            "- Set `ollama_model` in `config.json`, or\n"
            "- Pass it as an argument: `python src/cron.py <purpose> <account_id> <model>`"
        )
        sys.exit(1)
    select_model(resolved)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scheduled automations (YouTube, LongForm, Twitter, etc.)."
    )
    parser.add_argument(
        "purpose",
        choices=["twitter", "youtube", "afm", "longform", "ebook"],
        help="What automation to run.",
    )
    parser.add_argument("account_id", help="Account UUID (or product id for afm).")
    parser.add_argument(
        "model",
        nargs="?",
        help="Ollama model name (optional if `ollama_model` is set in config.json, or if using Groq).",
    )
    parser.add_argument(
        "niche",
        nargs="?",
        help="Longform niche (only used when purpose=longform).",
    )
    parser.add_argument("--model", dest="model_flag", help="Same as positional model.")
    parser.add_argument("--niche", dest="niche_flag", help="Same as positional niche.")
    return parser.parse_args(argv)


def main() -> None:
    """Main function to post content to Twitter or upload videos to YouTube.

    This function determines its operation based on command-line arguments:
    - If the purpose is "twitter", it initializes a Twitter account and posts a message.
    - If the purpose is "youtube", it initializes a YouTube account, generates a video with TTS, and uploads it.

    Command-line arguments:
        sys.argv[1]: A string indicating the purpose, either "twitter" or "youtube".
        sys.argv[2]: A string representing the account UUID.

    The function also handles verbose output based on user settings and reports success or errors as appropriate.

    Args:
        None. The function uses command-line arguments accessed via sys.argv.

    Returns:
        None. The function performs operations based on the purpose and account UUID and does not return any value."""
    args = _parse_args(sys.argv[1:])
    purpose = str(args.purpose)
    account_id = str(args.account_id)
    model = (args.model_flag or args.model)
    niche = (args.niche_flag or args.niche)

    _ensure_llm_selected(model)

    verbose = get_verbose()

    if purpose == "twitter":
        from classes.Twitter import Twitter
        accounts = get_accounts("twitter")

        if not account_id:
            error("Account UUID cannot be empty.")

        for acc in accounts:
            if acc["id"] == account_id:
                if verbose:
                    info("Initializing Twitter...")
                twitter = Twitter(
                    acc["id"],
                    acc["nickname"],
                    acc["firefox_profile"],
                    acc["topic"]
                )
                twitter.post()
                if verbose:
                    success("Done posting.")
                break
    elif purpose == "youtube":
        from classes.Tts import TTS
        from classes.YouTube import YouTube
        tts = TTS()

        accounts = get_accounts("youtube")

        if not account_id:
            error("Account UUID cannot be empty.")

        for acc in accounts:
            if acc["id"] == account_id:
                if verbose:
                    info("Initializing YouTube...")
                niche = random.choice(SHORTS_NICHES)
                if verbose:
                    info(f"Random niche selected: {niche}")
                youtube = YouTube(
                    acc["id"],
                    acc["nickname"],
                    acc["firefox_profile"],
                    niche,
                    acc["language"]
                )
                youtube.generate_video(tts)
                ok = youtube.upload_video()
                if not ok:
                    error("YouTube upload failed (no video posted).")
                    sys.exit(2)
                if verbose:
                    success("Uploaded Short.")
                break
    elif purpose == "afm":
        from classes.AFM import AffiliateMarketing

        products = get_products()

        for p in products:
            if p["id"] == account_id:
                if verbose:
                    info("Initializing Affiliate Marketing...")
                afm = AffiliateMarketing(p["affiliate_link"])

                yt_accounts = get_accounts("youtube")
                if yt_accounts:
                    yt_account = yt_accounts[0]
                    from classes.Tts import TTS
                    tts = TTS()
                    from classes.YouTube import YouTube
                    youtube = YouTube(
                        yt_account["id"],
                        yt_account["nickname"],
                        yt_account["firefox_profile"],
                        yt_account["niche"],
                        yt_account["language"]
                    )
                    youtube.set_subject(afm.product_title)
                    youtube.generate_video(tts)
                    ok = youtube.upload_video()
                    if not ok:
                        error("AFM YouTube upload failed (no video posted).")
                        sys.exit(2)
                    if verbose:
                        success("Uploaded product Short.")
                break
    elif purpose == "longform":
        accounts = get_accounts("youtube")
        if not account_id:
            error("Account UUID cannot be empty.")
            sys.exit(1)

        from classes.LongForm import LongForm, LONG_FORM_NICHES
        for acc in accounts:
            if acc["id"] == account_id:
                if verbose:
                    info("Initializing LongForm...")
                chosen_niche = niche if niche else random.choice(LONG_FORM_NICHES)
                lf = LongForm(
                    acc["id"],
                    acc["nickname"],
                    acc["firefox_profile"],
                    chosen_niche,
                    acc.get("language", "English"),
                )
                result = lf.run()
                if not result.get("url"):
                    error("Long-form upload failed (no video posted).")
                    sys.exit(2)
                if verbose:
                    success("Long-form video uploaded.")
                break
    elif purpose == "ebook":
        from classes.EBook import EBook
        if verbose:
            info("Initializing EBook pipeline...")
        ebook = EBook()
        ebook.run()
        if verbose:
            success("EBook pipeline complete.")
    else:
        error("Invalid Purpose, exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()
