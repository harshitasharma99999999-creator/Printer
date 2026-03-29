# RUN THIS N AMOUNT OF TIMES
import sys

from status import *
from cache import get_accounts, get_products
from config import get_verbose
from llm_provider import select_model

def main():
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
    purpose = str(sys.argv[1])
    account_id = str(sys.argv[2])
    model = str(sys.argv[3]) if len(sys.argv) > 3 else None

    if model:
        select_model(model)
    else:
        error("No Ollama model specified. Pass model name as third argument.")
        sys.exit(1)

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
                youtube = YouTube(
                    acc["id"],
                    acc["nickname"],
                    acc["firefox_profile"],
                    acc["niche"],
                    acc["language"]
                )
                youtube.generate_video(tts)
                youtube.upload_video()
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
                    youtube.upload_video()
                    if verbose:
                        success("Uploaded product Short.")
                break
    elif purpose == "longform":
        # argv: cron.py longform <account_id> <model> [niche]
        # model already selected above via argv[3]
        niche = str(sys.argv[4]) if len(sys.argv) > 4 else None

        accounts = get_accounts("youtube")
        if not account_id:
            error("Account UUID cannot be empty.")
            sys.exit(1)

        from classes.LongForm import LongForm, LONG_FORM_NICHES
        for acc in accounts:
            if acc["id"] == account_id:
                if verbose:
                    info("Initializing LongForm...")
                chosen_niche = niche if niche else acc.get("niche", LONG_FORM_NICHES[0])
                lf = LongForm(
                    acc["id"],
                    acc["nickname"],
                    acc["firefox_profile"],
                    chosen_niche,
                    acc.get("language", "English"),
                )
                lf.run()
                if verbose:
                    success("Long-form video uploaded.")
                break
    else:
        error("Invalid Purpose, exiting...")
        sys.exit(1)

if __name__ == "__main__":
    main()
