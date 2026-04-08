import os
import re
from datetime import datetime, timezone


def _clean_line(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def get_latest_ebook_url(mp_dir: str) -> str:
    """
    Best-effort: read the last published Gumroad URL saved by the eBook pipeline.
    """
    env_url = os.environ.get("EBOOK_URL", "").strip()
    if env_url:
        return env_url
    return _read_text_file(os.path.join(mp_dir, "last_ebook_url.txt"))


def format_disclosure(*, include_amazon_associate: bool = True) -> str:
    parts = []
    parts.append("Disclosure: links may be affiliate links (at no extra cost to you).")
    if include_amazon_associate:
        parts.append("As an Amazon Associate I earn from qualifying purchases.")
    return " ".join(parts)


def soft_urgency(topic: str) -> str:
    """
    Urgency without fake scarcity. Uses a behavioral nudge: act today or keep paying the cost.
    """
    t = _clean_line(topic)
    if not t:
        return "Start today. Future-you will feel the difference in 7 days."
    return (
        f"If {t} keeps slipping, it’s not a motivation problem — it’s a system problem. "
        "Start today and let the system do the heavy lifting."
    )


def build_value_bullets(topic: str) -> list[str]:
    t = _clean_line(topic)
    base = [
        "A clear step-by-step framework (no fluff)",
        "A 10-minute daily routine you can actually follow",
        "Common traps + the exact fix",
        "A simple checklist to stay consistent",
    ]
    if t:
        base.insert(0, f"A practical system to improve: {t}")
    return base[:5]


def build_instagram_caption(
    *,
    topic: str,
    ebook_url: str = "",
    affiliate_link: str = "",
    include_disclosure: bool = True,
) -> str:
    topic_line = _clean_line(topic)[:120]
    bullets = build_value_bullets(topic_line)
    lines = []
    if topic_line:
        lines.append(topic_line)
        lines.append("")
    lines.append("Quick win:")
    lines.append("Do the next smallest step in 2 minutes — momentum beats motivation.")
    lines.append("")
    lines.append(soft_urgency(topic_line))
    lines.append("")
    if ebook_url:
        lines.append(f"Full guide + checklist: {ebook_url}")
    else:
        lines.append("Full guide + checklist: link in bio.")
    if affiliate_link:
        lines.append(f"Recommended: {affiliate_link}")
    if include_disclosure:
        lines.append("")
        lines.append(format_disclosure(include_amazon_associate=bool(affiliate_link)))
    lines.append("")
    lines.append("#motivation #mindset #selfimprovement #habits #discipline #shorts #reels #fyp")
    return "\n".join(lines).strip()


def build_youtube_description(
    *,
    base_description: str,
    topic: str,
    ebook_url: str = "",
    affiliate_link: str = "",
    include_disclosure: bool = True,
    is_shorts: bool = False,
) -> str:
    lines = []
    bd = (base_description or "").strip()
    if bd:
        lines.append(bd)
    lines.append("")
    lines.append(soft_urgency(topic))
    lines.append("")
    if ebook_url:
        lines.append(f"Full guide + checklist: {ebook_url}")
    if affiliate_link:
        lines.append(f"Recommended: {affiliate_link}")
    if include_disclosure and (ebook_url or affiliate_link):
        lines.append("")
        lines.append(format_disclosure(include_amazon_associate=bool(affiliate_link)))
    if is_shorts:
        lines.append("")
        lines.append("#Shorts #Short")
    return "\n".join(lines).strip()


def build_sales_page_description(topic: str, *, long_description: str) -> str:
    """
    Format a conversion-focused (but not salesy) description for Gumroad/KDP listing.
    """
    t = _clean_line(topic)
    out = []
    if t:
        out.append(f"Topic: {t}")
        out.append("")
    bullets = build_value_bullets(t)
    out.append("Inside you’ll get:")
    for b in bullets:
        out.append(f"- {b}")
    out.append("")
    if long_description:
        out.append("What this helps you do:")
        out.append(_clean_line(long_description))
        out.append("")
    out.append("This is for you if you want a calm, practical system — not hype.")
    out.append("")
    out.append(soft_urgency(t))
    return "\n".join(out).strip()


def utc_today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()

