"""
Content Distributor — runs every 8 hours independently.

Generates fresh psychology/mindset content and auto-publishes to:
  1. Dev.to (Google SEO + creator monetization program)
  2. Beehiiv Newsletter (ad network pays per subscriber)
  3. Spotify Podcast via GitHub Releases + RSS (monetize at 100 listeners/ep)
  4. Pinterest Affiliate Pins (buyer-intent traffic → affiliate commissions)
  5. Reddit (affiliate commissions from viral comments)
  6. Hashnode (Google SEO traffic → affiliate clicks)
  7. WhatsApp Broadcast (highest open-rate channel)
  Weekly (Monday):   Gumroad Printable PDF ($2.99 passive sale)
  Monthly (1st):     Gumroad Course PDF ($19.97 passive sale)
"""
import os
import re
import sys
import random
from datetime import datetime
from urllib.parse import urlparse, parse_qs, quote_plus

sys.path.insert(0, os.path.dirname(__file__))

from llm_provider import generate_text
from config import ROOT_DIR, get_verbose, get_affiliate_link
from status import info, warning, success, error
from classes.DevTo import DevTo
from classes.Newsletter import Newsletter
from classes.Podcast import Podcast
from classes.Pinterest import Pinterest
from classes.WhatsApp import WhatsApp
from classes.Hashnode import Hashnode
from classes.Printables import Printables
from classes.Course import Course
from classes.Tts import TTS

NICHE = "Carl Jung psychology empath shadow work spiritual awakening dark wisdom"

SUBREDDITS = ["Jung", "psychology", "selfimprovement", "shadowwork",
               "spirituality", "consciousness", "philosophy"]


# ─── Content Generation ───────────────────────────────────────────────────────

def pick_topic() -> str:
    prompt = (
        f"Generate ONE compelling article/video topic in this niche: {NICHE}\n"
        f"Style: philosophical, psychological, dark wisdom, uncomfortable truth.\n"
        f"Format: a punchy phrase under 80 characters. Examples:\n"
        f"- 'Why Most People Never Heal: The Shadow They Refuse to Face'\n"
        f"- 'The Hidden Cost of Being Too Nice: A Jungian Warning'\n"
        f"- 'What Happens to Your Mind When You Stop Seeking Approval'\n"
        f"Return ONLY the topic. Nothing else."
    )
    topic = generate_text(prompt).strip().strip('"').strip("'")
    return topic or "The Shadow Self: What You Refuse to See Will Control You"


def get_affiliate_link_for_topic(topic: str) -> str:
    """Build a topic-specific Amazon affiliate link (same logic as YouTube.py)."""
    base = get_affiliate_link() or ""
    tag = parse_qs(urlparse(base).query).get("tag", ["harshita000-21"])[0]

    kw_prompt = (
        f"Extract 2-3 Amazon search keywords for: {topic}\n"
        f"Think: what book or product would a reader of this article want to buy?\n"
        f"Return ONLY a short search phrase (e.g. 'shadow work journal'). Nothing else."
    )
    try:
        keywords = generate_text(kw_prompt).strip().strip('"').strip("'")
    except Exception:
        keywords = ""

    if not keywords:
        return base or f"https://www.amazon.in/s?k=psychology+books&tag={tag}"

    encoded = quote_plus(keywords)
    search_url = f"https://www.amazon.in/s?k={encoded}&tag={tag}"

    # Try to find a specific product ASIN
    try:
        import requests as _req
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        r = _req.get(search_url, headers=headers, timeout=12)
        asins = re.findall(r"/dp/([A-Z0-9]{10})", r.text)
        if asins:
            return f"https://www.amazon.in/dp/{asins[0]}?tag={tag}"
    except Exception:
        pass

    return search_url


def generate_content(topic: str) -> dict:
    """Generate all content variants from a single topic."""

    # Long-form article (Medium + Hashnode)
    article = generate_text(
        f"Write a deep, philosophical 700-word article about: {topic}\n"
        f"Tone: authoritative, commanding male voice. Speak directly to 'you'.\n"
        f"Structure: scroll-stopping hook → 3 Jungian psychological insights → devastating truth → action-forcing close.\n"
        f"Use YOU and YOUR constantly. Commands only — never suggestions.\n"
        f"NO markdown headers. Flowing paragraphs only."
    ).strip()

    # Newsletter (Beehiiv)
    newsletter = generate_text(
        f"Write a punchy weekly newsletter about: {topic}\n"
        f"Sections (use these exact labels):\n"
        f"THIS WEEK'S TRUTH: 1 shocking sentence.\n"
        f"THE INSIGHT: 2 paragraphs of deep psychological truth.\n"
        f"YOUR CHALLENGE: 1 specific action for this week.\n"
        f"CLOSING: 1 haunting sentence they can't unhear.\n"
        f"Tone: direct, commanding. Under 280 words total."
    ).strip()

    # Reddit post
    reddit_body = generate_text(
        f"Write a Reddit post sharing a personal realization about: {topic}\n"
        f"Tone: genuine, first-person, universal. NOT preachy.\n"
        f"Length: 200 words. End with 1 question to spark discussion.\n"
        f"No self-promotion whatsoever."
    ).strip()

    # Pinterest description
    pin_desc = generate_text(
        f"Write a 2-sentence Pinterest pin description for: {topic}\n"
        f"Make it keyword-rich for Pinterest SEO. Include 3 relevant hashtags.\n"
        f"Under 150 characters total."
    ).strip()

    # WhatsApp broadcast (ultra-short)
    wa_msg = generate_text(
        f"Write a 3-sentence WhatsApp broadcast about: {topic}\n"
        f"Sentence 1: shocking insight. Sentence 2: the raw truth. Sentence 3: call to action.\n"
        f"Under 200 characters total. No hashtags."
    ).strip()

    # Podcast script (conversational, 3 minutes ~= 450 words)
    podcast_script = generate_text(
        f"Write a 450-word podcast script about: {topic}\n"
        f"Tone: deep, commanding, intimate — like a wise elder speaking truth.\n"
        f"Structure: hook → insight 1 → insight 2 → insight 3 → powerful close.\n"
        f"Use YOU constantly. Commands only. Conversational, not academic."
    ).strip()

    return {
        "article": article,
        "newsletter": newsletter,
        "reddit": reddit_body,
        "pin_desc": pin_desc,
        "whatsapp": wa_msg,
        "podcast": podcast_script,
    }


# ─── Format Helpers ───────────────────────────────────────────────────────────

def to_html(topic: str, article: str, affiliate_link: str) -> str:
    paragraphs = "".join(
        f"<p>{p.strip()}</p>\n" for p in article.split("\n") if p.strip()
    )
    return (
        f"<h1>{topic}</h1>\n"
        f"{paragraphs}"
        f"<hr>\n"
        f'<p><strong>Recommended for your journey → </strong>'
        f'<a href="{affiliate_link}">{affiliate_link}</a></p>\n'
    )


def to_markdown(topic: str, article: str, affiliate_link: str) -> str:
    return (
        f"# {topic}\n\n"
        f"{article}\n\n"
        f"---\n\n"
        f"**Recommended for your journey →** [{affiliate_link}]({affiliate_link})\n"
    )


def to_newsletter_html(newsletter: str, affiliate_link: str) -> str:
    paragraphs = "".join(
        f"<p>{p.strip()}</p>\n" for p in newsletter.split("\n") if p.strip()
    )
    return (
        f"{paragraphs}"
        f'<p style="margin-top:24px;">'
        f'<a href="{affiliate_link}" style="background:#1a1a2e;color:#c4a44d;'
        f'padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:bold;">'
        f'Get it here →</a></p>\n'
    )


# ─── Platform Runners ─────────────────────────────────────────────────────────

def run_reddit(topic: str, body: str, affiliate_link: str) -> None:
    import praw
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    username = os.environ.get("REDDIT_USERNAME", "").strip()
    password = os.environ.get("REDDIT_PASSWORD", "").strip()

    if not all([client_id, client_secret, username, password]):
        if get_verbose():
            warning("Reddit: credentials not set — skipping.")
        return

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent=f"MoneyPrinterV2:distributor:1.0 (by /u/{username})",
        )
        subreddit_name = random.choice(SUBREDDITS)
        full_body = f"{body}\n\n---\n*If this resonated → {affiliate_link}*"
        post = reddit.subreddit(subreddit_name).submit(
            title=topic[:300], selftext=full_body
        )
        if get_verbose():
            success(f"Reddit: post live → https://reddit.com{post.permalink}")
    except Exception as e:
        if get_verbose():
            warning(f"Reddit: {e}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    now = datetime.utcnow()
    if get_verbose():
        info(f"Distributor: starting at {now.strftime('%Y-%m-%d %H:%M UTC')}")

    os.makedirs(os.path.join(ROOT_DIR, ".mp"), exist_ok=True)

    # 1. Pick topic
    topic = pick_topic()
    if get_verbose():
        info(f"Distributor: topic → '{topic}'")

    # 2. Affiliate link for this topic
    affiliate_link = get_affiliate_link_for_topic(topic)
    if get_verbose():
        info(f"Distributor: affiliate link → {affiliate_link}")

    # 3. Generate all content variants
    content = generate_content(topic)

    html_article = to_html(topic, content["article"], affiliate_link)
    md_article = to_markdown(topic, content["article"], affiliate_link)
    newsletter_html = to_newsletter_html(content["newsletter"], affiliate_link)

    # 4. Dev.to
    try:
        DevTo().post_article(
            title=topic,
            content_markdown=md_article,
            tags=["psychology", "selfimprovement", "mindset", "philosophy"],
        )
    except Exception as e:
        if get_verbose():
            warning(f"Dev.to: {e}")

    # 5. Beehiiv Newsletter
    try:
        Newsletter().send(subject=topic, content_html=newsletter_html)
    except Exception as e:
        if get_verbose():
            warning(f"Beehiiv: {e}")

    # 6. Podcast episode (TTS → MP3 → GitHub Release → RSS)
    try:
        tts = TTS()
        wav_path = tts.synthesize(content["podcast"])
        Podcast().add_episode(title=topic, script=content["podcast"][:500], wav_path=wav_path)
    except Exception as e:
        if get_verbose():
            warning(f"Podcast: {e}")

    # 7. Pinterest pin
    try:
        image_prompt = (
            f"Minimalist dark motivational quote card for Pinterest. "
            f"Deep dark background with elegant gold typography. "
            f"One powerful short sentence about: {topic}. "
            f"No faces. No clutter. Portrait 2:3 format."
        )
        Pinterest().create_pin(
            title=topic,
            description=content["pin_desc"],
            link=affiliate_link,
            image_prompt=image_prompt,
        )
    except Exception as e:
        if get_verbose():
            warning(f"Pinterest: {e}")

    # 8. Reddit
    try:
        run_reddit(topic, content["reddit"], affiliate_link)
    except Exception as e:
        if get_verbose():
            warning(f"Reddit: {e}")

    # 9. Hashnode
    try:
        Hashnode().post_article(title=topic, content_markdown=md_article)
    except Exception as e:
        if get_verbose():
            warning(f"Hashnode: {e}")

    # 10. WhatsApp broadcast
    try:
        wa_message = f"{content['whatsapp']}\n\n{affiliate_link}"
        sent = WhatsApp().broadcast(wa_message)
        if get_verbose() and sent:
            success(f"WhatsApp: sent to {sent} recipients.")
    except Exception as e:
        if get_verbose():
            warning(f"WhatsApp: {e}")

    # 11. Weekly printable (every Monday)
    if now.weekday() == 0:
        try:
            if get_verbose():
                info("Distributor: Monday → creating weekly Gumroad printable")
            Printables().run(topic)
        except Exception as e:
            if get_verbose():
                warning(f"Printables: {e}")

    # 12. Monthly course (1st of every month)
    if now.day == 1:
        try:
            if get_verbose():
                info("Distributor: 1st of month → creating Gumroad course")
            Course().run(topic)
        except Exception as e:
            if get_verbose():
                warning(f"Course: {e}")

    if get_verbose():
        success("Distributor: all platforms done.")


if __name__ == "__main__":
    main()
