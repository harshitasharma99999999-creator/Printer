import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from config import ROOT_DIR, get_verbose
from llm_provider import generate_text
from status import info, success, warning
from classes.DevTo import DevTo
from classes.Medium import Medium
from classes.Hashnode import Hashnode


NICHE = os.environ.get(
    "BLOG_NICHE",
    "artificial intelligence crypto blockchain web3 bitcoin ethereum ai agents "
    "trading automation onchain data defi market psychology productivity"
).strip()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "ai-crypto-blog"


def pick_topic() -> str:
    prompt = (
        f"Generate ONE timely-feeling evergreen blog topic in this niche: {NICHE}\n"
        "The topic must blend AI and crypto naturally.\n"
        "Good examples:\n"
        "- How AI Agents Are Changing Crypto Research for Retail Investors\n"
        "- What AI Can Actually Do for Crypto Traders in 2026\n"
        "- The Dark Side of AI Hype in Web3\n"
        "Return ONLY the title. No quotes, no bullets, no explanation."
    )
    topic = generate_text(prompt).strip().strip('"').strip("'")
    return topic or "How AI Agents Are Changing Crypto Research"


def build_article(topic: str) -> str:
    prompt = (
        f"Write a high-quality 900 to 1200 word blog article titled: {topic}\n"
        "Audience: curious readers, founders, retail investors, and builders.\n"
        "Goals:\n"
        "- explain the idea clearly\n"
        "- stay practical, credible, and readable\n"
        "- avoid fake certainty and avoid price predictions\n"
        "- include concrete examples and real-world use cases\n"
        "- end with a balanced conclusion and one practical takeaway\n"
        "Style:\n"
        "- crisp, modern, human\n"
        "- paragraphs with short subheads\n"
        "- markdown is allowed\n"
        "- no emojis\n"
        "- no disclaimers about being an AI\n"
        "- no mention of word count\n"
    )
    return generate_text(prompt).strip()


def build_summary(topic: str) -> str:
    prompt = (
        f"Write a 2-sentence SEO summary for this article: {topic}\n"
        "Make it natural, specific, and useful. No hashtags."
    )
    summary = generate_text(prompt).strip()
    return summary or topic


def build_tags(topic: str) -> list[str]:
    prompt = (
        f"Return 4 short lowercase tags for a blog post about: {topic}\n"
        "Must be relevant to AI and crypto.\n"
        "Return ONLY a comma-separated list like: ai, crypto, blockchain, web3"
    )
    raw = generate_text(prompt).strip().lower()
    tags = []
    for item in raw.split(","):
        tag = re.sub(r"[^a-z0-9-]", "", item.strip().replace(" ", "-"))
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:4] or ["ai", "crypto", "blockchain", "web3"]


def to_html(topic: str, article_markdown: str) -> str:
    lines = []
    for line in article_markdown.splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("### "):
            lines.append(f"<h3>{text[4:].strip()}</h3>")
        elif text.startswith("## "):
            lines.append(f"<h2>{text[3:].strip()}</h2>")
        elif text.startswith("# "):
            lines.append(f"<h1>{text[2:].strip()}</h1>")
        elif text.startswith("- "):
            lines.append(f"<p>• {text[2:].strip()}</p>")
        else:
            lines.append(f"<p>{text}</p>")
    body = "\n".join(lines).strip()
    if "<h1>" not in body:
        body = f"<h1>{topic}</h1>\n{body}"
    return body


def save_outputs(topic: str, summary: str, tags: list[str], article_markdown: str) -> dict:
    mp_dir = os.path.join(ROOT_DIR, ".mp")
    os.makedirs(mp_dir, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _slugify(topic)
    md_path = os.path.join(mp_dir, f"{stamp}_{slug}.md")
    meta_path = os.path.join(mp_dir, f"{stamp}_{slug}.txt")
    latest_md = os.path.join(mp_dir, "last_ai_crypto_blog.md")
    latest_meta = os.path.join(mp_dir, "last_ai_crypto_blog.txt")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(article_markdown)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(article_markdown)

    meta = [
        f"Title: {topic}",
        f"Summary: {summary}",
        f"Tags: {', '.join(tags)}",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
    ]
    meta_text = "\n".join(meta)
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(meta_text)
    with open(latest_meta, "w", encoding="utf-8") as f:
        f.write(meta_text)

    return {
        "markdown": md_path,
        "meta": meta_path,
    }


def publish(topic: str, summary: str, tags: list[str], article_markdown: str) -> dict:
    html = to_html(topic, article_markdown)
    markdown = f"{summary}\n\n{article_markdown}".strip()

    results = {"devto": "", "medium": "", "hashnode": ""}

    try:
        results["devto"] = DevTo().post_article(title=topic, content_markdown=markdown, tags=tags)
    except Exception as e:
        if get_verbose():
            warning(f"Dev.to publish failed: {e}")

    try:
        results["medium"] = Medium().post_article(title=topic, content_html=html, tags=tags)
    except Exception as e:
        if get_verbose():
            warning(f"Medium publish failed: {e}")

    try:
        hashnode_tags = [{"name": t.replace("-", " ").title(), "slug": t} for t in tags]
        results["hashnode"] = Hashnode().post_article(
            title=topic,
            content_markdown=markdown,
            tags=hashnode_tags,
        )
    except Exception as e:
        if get_verbose():
            warning(f"Hashnode publish failed: {e}")

    return results


def main() -> None:
    if get_verbose():
        info("AI + Crypto blog automation starting...")

    topic = pick_topic()
    summary = build_summary(topic)
    tags = build_tags(topic)
    article_markdown = build_article(topic)

    saved = save_outputs(topic, summary, tags, article_markdown)
    results = publish(topic, summary, tags, article_markdown)

    if get_verbose():
        info(f"Topic: {topic}")
        info(f"Saved markdown: {saved['markdown']}")
        info(f"Tags: {', '.join(tags)}")

    published_count = sum(1 for url in results.values() if url)
    if published_count:
        success(f"AI + Crypto blog published on {published_count} platform(s).")
        for platform, url in results.items():
            if url:
                success(f"{platform}: {url}")
    else:
        warning(
            "No blog platform published successfully. "
            "Content was still generated and saved in .mp."
        )


if __name__ == "__main__":
    main()
