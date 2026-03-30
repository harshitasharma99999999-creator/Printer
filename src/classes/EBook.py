import os
import re
import time
import uuid
import requests

from io import BytesIO
from datetime import datetime
from typing import Optional

from status import *
from config import (
    ROOT_DIR, get_verbose, get_headless, get_ebook_author, get_ebook_price,
    get_gumroad_access_token, get_kdp_firefox_profile,
    get_gumroad_firefox_profile, get_kdp_affiliate_link,
    get_kdp_email, get_kdp_password
)
from llm_provider import generate_text

# reportlab
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ebooklib
import ebooklib
from ebooklib import epub


EVERGREEN_TOPICS = [
    "morning routine habits for success",
    "financial freedom for beginners",
    "mindset shifts to achieve your goals",
    "intermittent fasting for weight loss",
    "stoic philosophy for modern life",
    "passive income streams for 2025",
    "anxiety and stress management techniques",
    "manifesting your dream life",
    "productivity hacks for busy people",
    "building confidence and self-esteem",
]

NEWS_BLOCKLIST = (
    "election", "president", "minister", "prime minister",
    "war", "shooting", "killed", "died", "dead", "arrested",
    "bitcoin price", "stock market", "crash", "inflation",
    "hurricane", "earthquake", "flood", "wildfire",
    "trump", "biden", "obama", "putin", "zelensky", "orban",
    "congress", "senate", "parliament", "nato",
    "police", "court", "verdict", "lawsuit", "indicted",
)


class EBook:
    """
    Full eBook pipeline:
    trending topics → LLM content → PDF + EPUB → Gumroad API + KDP Selenium
    """

    def __init__(self) -> None:
        self.topic: str = ""
        self.title: str = ""
        self.subtitle: str = ""
        self.description: str = ""
        self.keywords: list[str] = []
        self.chapters: list[dict] = []   # [{title, body}, ...]
        self.pdf_path: str = ""
        self.epub_path: str = ""
        self.slug: str = ""

    # ------------------------------------------------------------------
    # Step 1: Trending topics
    # ------------------------------------------------------------------

    def get_trending_topics(self) -> list[str]:
        """Fetch trending topics from Google Trends (pytrends) + Reddit."""
        topics = []

        # Google Trends
        try:
            from pytrends.request import TrendReq
            pt = TrendReq(hl="en-US", tz=330, timeout=(5, 15))
            df = pt.today_searches(pn="IN")
            topics.extend(df.tolist()[:5])
            topics = [t for t in topics if not any(kw in t.lower() for kw in NEWS_BLOCKLIST)]
            if get_verbose():
                info(f"Google Trends: {topics[:5]}")
        except Exception as e:
            if get_verbose():
                warning(f"Google Trends failed: {e}")

        # Reddit popular
        try:
            headers = {"User-Agent": "ebook-bot/1.0"}
            r = requests.get(
                "https://www.reddit.com/r/popular/hot.json?limit=15",
                headers=headers, timeout=10
            )
            for post in r.json()["data"]["children"]:
                t = post["data"]["title"]
                t_lower = t.lower()
                # Skip short titles and news/political topics
                if len(t) > 15 and not any(kw in t_lower for kw in NEWS_BLOCKLIST):
                    topics.append(t)
            if get_verbose():
                info(f"Reddit: added {len(topics) - 5} topics")
        except Exception as e:
            if get_verbose():
                warning(f"Reddit failed: {e}")

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in topics:
            key = t.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(t)

        # Backfill with evergreen topics if too few remain after filtering
        if len(unique) < 5:
            for ev in EVERGREEN_TOPICS:
                if ev.lower() not in seen:
                    unique.append(ev)
                    seen.add(ev.lower())
                if len(unique) >= 12:
                    break

        return unique[:12]

    # ------------------------------------------------------------------
    # Step 2: Pick best eBook topic with LLM
    # ------------------------------------------------------------------

    def select_topic(self, topics: list[str]) -> str:
        """Ask LLM to pick the topic most suited for a practical eBook."""
        topic_list = "\n".join(f"{i+1}. {t}" for i, t in enumerate(topics))
        prompt = (
            "From the numbered list below, pick ONE topic that would make a bestselling "
            "practical eBook.\n"
            "Choose a topic about self-improvement, health, money, relationships, "
            "productivity, or mindset — NOT news, politics, or current events.\n"
            "Reply with ONLY the number (e.g. 3).\n\n"
            f"{topic_list}"
        )
        raw = generate_text(prompt).strip()
        # Extract first number from response
        import re as _re
        nums = _re.findall(r'\d+', raw)
        if nums:
            idx = int(nums[0]) - 1
            if 0 <= idx < len(topics):
                chosen = topics[idx]
                # Reject if LLM picked a news/political topic anyway
                if any(kw in chosen.lower() for kw in NEWS_BLOCKLIST):
                    if get_verbose():
                        warning(f"LLM picked news topic ('{chosen}') — falling back to evergreen.")
                    return EVERGREEN_TOPICS[0]
                return chosen
        # Fallback: pick the most "how-to" friendly non-news topic
        for t in topics:
            t_lower = t.lower()
            if any(kw in t_lower for kw in NEWS_BLOCKLIST):
                continue
            if any(w in t_lower for w in ["how", "why", "what", "tips", "best", "produc", "health", "mindset", "financ"]):
                return t
        return EVERGREEN_TOPICS[0]

    # ------------------------------------------------------------------
    # Step 3: Generate full eBook content
    # ------------------------------------------------------------------

    def generate_content(self) -> None:
        """Generate eBook title, description, keywords, and 5 chapters via LLM."""
        if get_verbose():
            info(f"Generating eBook content for: {self.topic}")

        # Title
        title_raw = generate_text(
            f'Write a compelling, specific eBook title for the topic: "{self.topic}". '
            f'Include the main keyword naturally. Make it practical and benefit-focused. '
            f'Return only the title, no quotes, no punctuation at end.'
        ).strip().split("\n")[0]
        self.title = title_raw[:120]

        # Subtitle (for KDP — boosts discoverability)
        subtitle_raw = generate_text(
            f'Write a short subtitle (max 12 words) for the eBook "{self.title}". '
            f'Include 2-3 relevant keywords. Return only the subtitle text.'
        ).strip().split("\n")[0]
        self.subtitle = subtitle_raw[:200]

        # SEO keywords for Amazon (7 keyword phrases)
        kw_raw = generate_text(
            f'List exactly 7 Amazon Kindle search keyword phrases for the eBook "{self.title}". '
            f'Use phrases people actually search (2-4 words each). '
            f'Return one phrase per line, no numbers, no bullets.'
        ).strip()
        self.keywords = [
            re.sub(r'^[\d\-\.\)\s]+', '', l).strip()
            for l in kw_raw.split("\n") if l.strip()
        ][:7]
        if get_verbose():
            info(f"Keywords: {self.keywords}")

        # Description (SEO-rich, 400+ words for KDP ranking)
        self.description = generate_text(
            f'Write a 5-sentence Amazon Kindle book description for "{self.title}". '
            f'Start with a hook. Mention the reader problem it solves. '
            f'List 3 key benefits. End with a call to action. '
            f'Include these keywords naturally: {", ".join(self.keywords[:4])}. '
            f'Return only the description text.'
        ).strip()
        # Append affiliate link to description
        affiliate_link = get_kdp_affiliate_link()
        if affiliate_link:
            self.description += f"\n\nExplore more Kindle eBooks: {affiliate_link}"

        # Chapter outline
        outline_raw = generate_text(
            f'For the eBook "{self.title}", write exactly 5 chapter titles. '
            f'Each title should be practical and specific. '
            f'Return them numbered 1-5, one per line, no extra text.'
        ).strip()

        chapter_titles = []
        for line in outline_raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip leading number/punctuation
            line = re.sub(r'^[\d]+[\.\):\-\s]+', '', line).strip()
            if line:
                chapter_titles.append(line)
            if len(chapter_titles) == 5:
                break

        # Fallback titles
        while len(chapter_titles) < 5:
            chapter_titles.append(f"Chapter {len(chapter_titles) + 1}")

        # Generate each chapter body
        self.chapters = []
        for i, ch_title in enumerate(chapter_titles, 1):
            if get_verbose():
                info(f"  Writing chapter {i}/5: {ch_title}")
            body = generate_text(
                f'Write Chapter {i} of the eBook "{self.title}". '
                f'Chapter title: "{ch_title}". '
                f'Write 600-800 words. Use clear paragraphs. Include practical tips and examples. '
                f'Do not use markdown headers inside the text. Return only the chapter body text.'
            ).strip()
            self.chapters.append({"title": ch_title, "body": body})

        # Create slug for filenames
        self.slug = re.sub(r'[^a-z0-9]+', '-', self.title.lower())[:50].strip('-')
        if get_verbose():
            success(f"Content generated: {self.title} ({len(self.chapters)} chapters)")

    # ------------------------------------------------------------------
    # Step 4a: Format as PDF
    # ------------------------------------------------------------------

    def format_pdf(self) -> str:
        """Generate a formatted PDF using reportlab. Returns file path."""
        mp_dir = os.path.join(ROOT_DIR, ".mp")
        os.makedirs(mp_dir, exist_ok=True)
        path = os.path.join(mp_dir, f"ebook-{self.slug}.pdf")

        doc = SimpleDocTemplate(
            path,
            pagesize=letter,
            rightMargin=inch,
            leftMargin=inch,
            topMargin=inch,
            bottomMargin=inch
        )

        styles = getSampleStyleSheet()
        accent = HexColor("#2C3E50")
        light = HexColor("#7F8C8D")

        title_style = ParagraphStyle(
            "CoverTitle",
            parent=styles["Title"],
            fontSize=28,
            textColor=accent,
            alignment=TA_CENTER,
            spaceAfter=20,
        )
        author_style = ParagraphStyle(
            "Author",
            parent=styles["Normal"],
            fontSize=14,
            textColor=light,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
        ch_title_style = ParagraphStyle(
            "ChTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=accent,
            spaceBefore=20,
            spaceAfter=12,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=11,
            leading=16,
            spaceAfter=8,
        )

        story = []

        # Cover page
        story.append(Spacer(1, 1.5 * inch))
        story.append(Paragraph(self.title, title_style))
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(f"By {get_ebook_author()}", author_style))
        story.append(Spacer(1, 0.2 * inch))
        price_str = f"${get_ebook_price():.2f}"
        story.append(Paragraph(price_str, author_style))
        story.append(PageBreak())

        # Description page
        story.append(Paragraph("About This eBook", ch_title_style))
        for para in self.description.split("\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), body_style))
        story.append(PageBreak())

        # Chapters
        for i, ch in enumerate(self.chapters, 1):
            story.append(Paragraph(f"Chapter {i}: {ch['title']}", ch_title_style))
            story.append(Spacer(1, 0.1 * inch))
            for para in ch["body"].split("\n"):
                if para.strip():
                    story.append(Paragraph(para.strip(), body_style))
            story.append(PageBreak())

        # Final page — affiliate CTA
        affiliate_link = get_kdp_affiliate_link()
        if affiliate_link:
            story.append(Paragraph("Enjoyed This eBook?", ch_title_style))
            story.append(Paragraph(
                "Discover more practical guides and bestselling Kindle eBooks on Amazon:",
                body_style
            ))
            story.append(Paragraph(
                f'<link href="{affiliate_link}">{affiliate_link}</link>',
                body_style
            ))
            story.append(Spacer(1, 0.2 * inch))
            story.append(Paragraph(
                f"By {get_ebook_author()} — Thank you for reading!",
                author_style
            ))

        doc.build(story)
        self.pdf_path = path
        if get_verbose():
            success(f"PDF saved: {path}")
        return path

    # ------------------------------------------------------------------
    # Step 4b: Format as EPUB
    # ------------------------------------------------------------------

    def format_epub(self) -> str:
        """Generate a standard EPUB2 file using ebooklib. Returns file path."""
        mp_dir = os.path.join(ROOT_DIR, ".mp")
        os.makedirs(mp_dir, exist_ok=True)
        path = os.path.join(mp_dir, f"ebook-{self.slug}.epub")

        book = epub.EpubBook()
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(self.title)
        book.set_language("en")
        book.add_author(get_ebook_author())

        css = epub.EpubItem(
            uid="style",
            file_name="style/main.css",
            media_type="text/css",
            content="""
body { font-family: Georgia, serif; font-size: 1em; line-height: 1.6; margin: 2em; }
h1 { color: #2C3E50; font-size: 1.8em; margin-bottom: 0.5em; }
h2 { color: #2C3E50; font-size: 1.4em; margin-top: 1.5em; }
p  { margin-bottom: 0.8em; text-align: justify; }
""".strip()
        )
        book.add_item(css)

        spine = ["nav"]

        # Cover / intro chapter
        intro_html = (
            f"<h1>{self.title}</h1>"
            f"<p><em>By {get_ebook_author()}</em></p>"
            f"<p>{self.description}</p>"
        )
        intro = epub.EpubHtml(title="Introduction", file_name="intro.xhtml", lang="en")
        intro.content = f"<html><body>{intro_html}</body></html>"
        intro.add_item(css)
        book.add_item(intro)
        spine.append(intro)

        toc = [epub.Link("intro.xhtml", "Introduction", "intro")]

        for i, ch in enumerate(self.chapters, 1):
            fname = f"chapter{i}.xhtml"
            paras = "".join(
                f"<p>{p.strip()}</p>" for p in ch["body"].split("\n") if p.strip()
            )
            ch_html = f"<h2>Chapter {i}: {ch['title']}</h2>{paras}"
            item = epub.EpubHtml(
                title=f"Chapter {i}: {ch['title']}",
                file_name=fname,
                lang="en"
            )
            item.content = f"<html><body>{ch_html}</body></html>"
            item.add_item(css)
            book.add_item(item)
            spine.append(item)
            toc.append(epub.Link(fname, f"Chapter {i}: {ch['title']}", f"ch{i}"))

        book.toc = toc
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        epub.write_epub(path, book)
        self.epub_path = path
        if get_verbose():
            success(f"EPUB saved: {path}")
        return path

    # ------------------------------------------------------------------
    # Step 5a: Publish to Gumroad via Selenium
    # ------------------------------------------------------------------

    def publish_to_gumroad(self) -> str:
        """
        Publish PDF to Gumroad via Selenium (Gumroad API v2 is discontinued).
        Uses pre-authenticated Firefox profile. Returns the product URL.
        """
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from webdriver_manager.firefox import GeckoDriverManager

        profile_path = get_gumroad_firefox_profile()
        gumroad_email = os.environ.get("GUMROAD_EMAIL", "").strip()
        gumroad_password = os.environ.get("GUMROAD_PASSWORD", "").strip()

        if not profile_path and not (gumroad_email and gumroad_password):
            warning("gumroad_firefox_profile not set and GUMROAD_EMAIL/GUMROAD_PASSWORD not set — skipping Gumroad.")
            return ""

        if get_verbose():
            info("Opening Gumroad in Firefox...")

        options = Options()
        if profile_path:
            options.profile = profile_path
        if get_headless():
            options.add_argument("--headless")
        driver = webdriver.Firefox(
            service=Service(GeckoDriverManager().install()),
            options=options
        )

        # CI login: if no pre-auth profile, login with email + password
        if not profile_path and gumroad_email:
            try:
                driver.get("https://app.gumroad.com/login")
                time.sleep(4)
                for by, sel in [
                    (By.ID, "email"), (By.NAME, "email"),
                    (By.XPATH, "//input[@type='email']"),
                ]:
                    try:
                        em = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((by, sel)))
                        em.clear(); em.send_keys(gumroad_email); break
                    except Exception:
                        continue
                for by, sel in [
                    (By.ID, "password"), (By.NAME, "password"),
                    (By.XPATH, "//input[@type='password']"),
                ]:
                    try:
                        pw = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((by, sel)))
                        pw.clear(); pw.send_keys(gumroad_password); break
                    except Exception:
                        continue
                for by, sel in [
                    (By.XPATH, "//button[@type='submit']"),
                    (By.XPATH, "//input[@type='submit']"),
                ]:
                    try:
                        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel))).click()
                        break
                    except Exception:
                        continue
                time.sleep(5)
                if get_verbose():
                    info(f"Gumroad login attempted. URL: {driver.current_url}")
            except Exception as _le:
                if get_verbose():
                    warning(f"Gumroad login failed: {_le}")

        wait = WebDriverWait(driver, 30)
        product_url = ""

        def _gumroad_try(selectors, timeout=15):
            for by, sel in selectors:
                try:
                    el = WebDriverWait(driver, timeout).until(
                        EC.element_to_be_clickable((by, sel))
                    )
                    return el
                except Exception:
                    continue
            return None

        def _gumroad_fill(el, text):
            el.click()
            el.send_keys(Keys.CONTROL + "a")
            el.send_keys(Keys.DELETE)
            el.send_keys(text)

        try:
            driver.get("https://app.gumroad.com/products/new")
            time.sleep(5)

            # Product name — Gumroad uses various selectors depending on version
            name_selectors = [
                (By.XPATH, "//input[@placeholder='Name your product']"),
                (By.XPATH, "//input[contains(@placeholder,'Name')]"),
                (By.XPATH, "//input[contains(@placeholder,'name')]"),
                (By.XPATH, "//input[@name='name']"),
                (By.XPATH, "//input[@id='name']"),
                (By.XPATH, "//label[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'name')]/following::input[1]"),
                (By.XPATH, "//input[@type='text'][1]"),
            ]
            name_el = _gumroad_try(name_selectors, timeout=20)
            if name_el:
                _gumroad_fill(name_el, self.title[:100])
                time.sleep(0.5)
            else:
                if get_verbose():
                    warning("Gumroad: product name field not found — taking screenshot")
                    try:
                        import os as _os
                        driver.save_screenshot(_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), ".mp", "gumroad-debug.png"))
                    except Exception:
                        pass

            # Price
            price_selectors = [
                (By.XPATH, "//input[contains(@placeholder,'Price')]"),
                (By.XPATH, "//input[contains(@placeholder,'price')]"),
                (By.XPATH, "//input[@name='price']"),
                (By.XPATH, "//input[@id='price']"),
                (By.XPATH, "//input[@type='number']"),
            ]
            price_el = _gumroad_try(price_selectors, timeout=10)
            if price_el:
                _gumroad_fill(price_el, str(get_ebook_price()))
                time.sleep(0.5)

            # Click "Save and continue" or "Next" to get to content upload page
            save_selectors = [
                (By.XPATH, "//button[contains(text(),'Save and continue')]"),
                (By.XPATH, "//button[contains(text(),'Save')]"),
                (By.XPATH, "//button[contains(text(),'Continue')]"),
                (By.XPATH, "//button[contains(text(),'Next')]"),
                (By.XPATH, "//input[@type='submit']"),
            ]
            btn = _gumroad_try(save_selectors, timeout=10)
            if btn:
                btn.click()
                time.sleep(4)
            else:
                if get_verbose():
                    warning("Gumroad: save button not found")

            # Upload PDF file
            try:
                upload_input = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//input[@type='file']")
                ))
                upload_input.send_keys(self.pdf_path)
                time.sleep(5)
                if get_verbose():
                    info("PDF uploaded to Gumroad.")
            except Exception:
                if get_verbose():
                    warning("File upload field not found — may need manual upload.")

            # Advance from content/upload step → share/publish step
            for _by, _sel in [
                (By.XPATH, "//button[contains(text(),'Save and continue')]"),
                (By.XPATH, "//button[contains(text(),'Continue')]"),
                (By.XPATH, "//button[contains(text(),'Next')]"),
            ]:
                try:
                    _btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((_by, _sel)))
                    _btn.click()
                    time.sleep(4)
                    break
                except Exception:
                    continue

            # Publish — click Publish explicitly (not Save which leaves it as draft)
            _published = False
            for _by, _sel in [
                (By.XPATH, "//button[text()='Publish']"),
                (By.XPATH, "//button[normalize-space()='Publish']"),
                (By.XPATH, "//button[contains(text(),'Publish')]"),
                (By.XPATH, "//input[@type='submit' and contains(@value,'Publish')]"),
                (By.XPATH, "//button[contains(text(),'Done')]"),
            ]:
                try:
                    _pub = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((_by, _sel)))
                    _pub.click()
                    time.sleep(4)
                    _published = True
                    if get_verbose():
                        info("Gumroad: Publish button clicked — product is now live.")
                    break
                except Exception:
                    continue
            if not _published and get_verbose():
                warning("Gumroad: Publish button not found — product may remain as draft.")

            # Grab the product URL from current page
            current = driver.current_url
            if "gumroad.com" in current:
                product_url = current
            if get_verbose():
                success(f"Gumroad product created: {product_url or 'check app.gumroad.com'}")

        except Exception as e:
            if get_verbose():
                warning(f"Gumroad Selenium error: {e}")
        finally:
            time.sleep(2)
            driver.quit()

        return product_url

    # ------------------------------------------------------------------
    # Step 5b: Submit to Amazon KDP via Selenium
    # ------------------------------------------------------------------

    def publish_to_kdp(self) -> None:
        """
        Automate Amazon KDP publishing via Selenium.
        Uses a pre-authenticated Firefox profile for kdp.amazon.com.
        Note: KDP takes 24-72h to review before going live.
        """
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from webdriver_manager.firefox import GeckoDriverManager

        profile_path = get_kdp_firefox_profile()
        kdp_email_cfg = get_kdp_email() or os.environ.get("KDP_EMAIL", "").strip()
        kdp_pass_cfg = get_kdp_password() or os.environ.get("KDP_PASSWORD", "").strip()

        if not profile_path and not (kdp_email_cfg and kdp_pass_cfg):
            warning("kdp_firefox_profile not set and KDP_EMAIL/KDP_PASSWORD not set — skipping KDP.")
            return

        if get_verbose():
            info("Opening KDP in Firefox...")

        options = Options()
        if profile_path:
            options.profile = profile_path
        if get_headless():
            options.add_argument("--headless")

        driver = webdriver.Firefox(
            service=Service(GeckoDriverManager().install()),
            options=options
        )

        def _try_selectors(selectors, timeout=10):
            """Try multiple selectors, return first matching element or None."""
            for by, sel in selectors:
                try:
                    el = WebDriverWait(driver, timeout).until(
                        EC.element_to_be_clickable((by, sel))
                    )
                    return el
                except Exception:
                    continue
            return None

        def _wait_for_url_fragment(fragment, timeout=15):
            """Wait until current URL contains fragment."""
            deadline = time.time() + timeout
            while time.time() < deadline:
                if fragment in driver.current_url:
                    return True
                time.sleep(0.5)
            return False

        def _fill_el(el, text):
            el.click()
            el.send_keys(Keys.CONTROL + "a")
            el.send_keys(Keys.DELETE)
            el.send_keys(text)

        try:
            driver.get("https://kdp.amazon.com/en_US/title-setup/kindle/new/details")
            time.sleep(6)  # wait for React to render

            current_url = driver.current_url
            page_title = driver.title
            if get_verbose():
                info(f"KDP page: {page_title} | {current_url}")

            # Handle Terms of Service agreement page
            if "agreement" in current_url or "agreement" in page_title.lower():
                if get_verbose():
                    info("KDP ToS agreement page — accepting...")
                agree_selectors = [
                    (By.XPATH, "//input[@type='submit']"),
                    (By.XPATH, "//button[contains(text(),'Accept') or contains(text(),'Agree') or contains(text(),'Continue') or contains(text(),'I Accept')]"),
                    (By.XPATH, "//a[contains(text(),'Accept') or contains(text(),'Agree')]"),
                    (By.XPATH, "//input[@name='accept' or @value='Accept']"),
                    (By.XPATH, "//button[@type='submit']"),
                ]
                agree_el = _try_selectors(agree_selectors, timeout=10)
                if agree_el:
                    agree_el.click()
                    time.sleep(4)
                    if get_verbose():
                        info(f"Accepted ToS. Now at: {driver.current_url}")
                # Navigate to new book form after acceptance
                driver.get("https://kdp.amazon.com/en_US/title-setup/kindle/new/details")
                time.sleep(6)
                current_url = driver.current_url
                page_title = driver.title
                if get_verbose():
                    info(f"KDP after ToS: {page_title} | {current_url}")

            # Handle login redirect — auto-login with credentials from config.json
            if "signin" in current_url or "ap/signin" in current_url:
                kdp_email = get_kdp_email()
                kdp_password = get_kdp_password()
                if not kdp_email or not kdp_password:
                    warning("KDP login required. Set kdp_email and kdp_password in config.json.")
                    driver.save_screenshot(os.path.join(ROOT_DIR, ".mp", "kdp-debug.png"))
                    return

                if get_verbose():
                    info("KDP login page — auto-logging in...")

                # Step 1: Email (Amazon may skip this if account is remembered in profile)
                try:
                    email_el = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "ap_email"))
                    )
                    email_el.click()
                    email_el.clear()
                    email_el.send_keys(kdp_email)
                    time.sleep(0.5)
                    for by, sel in [
                        (By.ID, "continue"),
                        (By.XPATH, "//input[@type='submit' and contains(@value,'Continue')]"),
                        (By.XPATH, "//button[contains(text(),'Continue')]"),
                        (By.XPATH, "//input[@type='submit']"),
                    ]:
                        try:
                            btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((by, sel)))
                            btn.click()
                            break
                        except Exception:
                            continue
                    time.sleep(3)
                except Exception:
                    # Amazon remembered the account from Firefox profile — email step skipped
                    if get_verbose():
                        info("KDP: account pre-recognized — skipping email step.")

                # Step 2: Password
                try:
                    pw_el = None
                    for by, sel in [
                        (By.ID, "ap_password"),
                        (By.NAME, "password"),
                        (By.XPATH, "//input[@type='password']"),
                        (By.XPATH, "//input[contains(@id,'password')]"),
                    ]:
                        try:
                            pw_el = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((by, sel)))
                            break
                        except Exception:
                            continue
                    if not pw_el:
                        warning("KDP: password field not found")
                        return
                    pw_el.click()
                    pw_el.clear()
                    pw_el.send_keys(kdp_password)
                    time.sleep(0.5)
                    # Tick "Keep me signed in" so session lasts longer
                    try:
                        keep_signed = driver.find_element(By.NAME, "rememberMe")
                        if not keep_signed.is_selected():
                            driver.execute_script("arguments[0].click();", keep_signed)
                    except Exception:
                        pass
                    for by, sel in [
                        (By.ID, "signInSubmit"),
                        (By.XPATH, "//input[@id='signInSubmit']"),
                        (By.XPATH, "//input[@type='submit' and contains(@value,'Sign in')]"),
                        (By.XPATH, "//button[contains(text(),'Sign in')]"),
                        (By.XPATH, "//input[@type='submit']"),
                    ]:
                        try:
                            sb = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel)))
                            sb.click()
                            break
                        except Exception:
                            continue
                    time.sleep(4)
                except Exception as _le:
                    warning(f"KDP login password step failed: {_le}")
                    driver.save_screenshot(os.path.join(ROOT_DIR, ".mp", "kdp-login-debug.png"))
                    return

                # Step 3: Handle OTP / 2FA if Amazon asks for it
                after_url = driver.current_url
                if any(x in after_url for x in ["ap/mfa", "auth-mfa", "ap/cvf", "verification", "challenge"]):
                    totp_secret = os.environ.get("KDP_TOTP_SECRET", "").strip()
                    if totp_secret:
                        try:
                            import pyotp
                            otp_code = pyotp.TOTP(totp_secret).now()
                            if get_verbose():
                                info(f"KDP: Auto-filling TOTP code...")
                            for by, sel in [
                                (By.ID, "auth-mfa-otpcode"),
                                (By.NAME, "otpCode"),
                                (By.XPATH, "//input[@type='text' and contains(@id,'otp')]"),
                                (By.XPATH, "//input[@type='tel']"),
                                (By.XPATH, "//input[@autocomplete='one-time-code']"),
                                (By.XPATH, "//input[@type='number']"),
                            ]:
                                try:
                                    otp_el = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((by, sel)))
                                    otp_el.clear()
                                    otp_el.send_keys(otp_code)
                                    break
                                except Exception:
                                    continue
                            for by, sel in [
                                (By.ID, "auth-signin-button"),
                                (By.XPATH, "//input[@type='submit']"),
                                (By.XPATH, "//button[@type='submit']"),
                            ]:
                                try:
                                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, sel))).click()
                                    break
                                except Exception:
                                    continue
                            time.sleep(4)
                        except ImportError:
                            warning("KDP: pyotp not installed — cannot auto-fill TOTP. pip install pyotp")
                            return
                    else:
                        warning("KDP: 2FA required but KDP_TOTP_SECRET not set. "
                                "Set it if using authenticator app, or disable 2FA on your Amazon account.")
                        return

                # Check login succeeded
                if "signin" in driver.current_url or "ap/signin" in driver.current_url:
                    warning("KDP login failed — check credentials in config.json.")
                    return

                if get_verbose():
                    info(f"KDP login successful. Navigating to new book form...")

                # Navigate to form after login
                driver.get("https://kdp.amazon.com/en_US/title-setup/kindle/new/details")
                time.sleep(6)
                current_url = driver.current_url
                page_title = driver.title
                if get_verbose():
                    info(f"KDP after login: {page_title} | {current_url}")

            # Book title — try multiple selectors
            title_selectors = [
                (By.ID, "data-title-input"),
                (By.XPATH, "//input[@data-a-input-name='title']"),
                (By.XPATH, "//input[contains(@id,'title') and @type='text']"),
                (By.XPATH, "//label[contains(text(),'Book title') or contains(text(),'Title')]/following::input[1]"),
                (By.XPATH, "//input[contains(@placeholder,'title') or contains(@placeholder,'Title')]"),
            ]
            title_el = _try_selectors(title_selectors, timeout=15)
            if title_el:
                _fill_el(title_el, self.title[:200])
                time.sleep(0.5)
            else:
                driver.save_screenshot(os.path.join(ROOT_DIR, ".mp", "kdp-debug.png"))
                warning("KDP title field not found — saved screenshot to .mp/kdp-debug.png")

            # Subtitle
            subtitle_selectors = [
                (By.ID, "data-subtitle-input"),
                (By.XPATH, "//input[contains(@id,'subtitle')]"),
                (By.XPATH, "//label[contains(text(),'Subtitle')]/following::input[1]"),
                (By.XPATH, "//input[contains(@placeholder,'ubtitle')]"),
            ]
            subtitle_el = _try_selectors(subtitle_selectors, timeout=5)
            if subtitle_el and self.subtitle:
                _fill_el(subtitle_el, self.subtitle[:200])

            # Author first/last name
            # KDP uses indexed IDs: author-first-name-0, author-last-name-0
            parts = get_ebook_author().split(" ", 1)
            first = parts[0]
            last = parts[1] if len(parts) > 1 else "Sharma"
            first_selectors = [
                (By.ID, "author-first-name-0"),
                (By.XPATH, "//input[@id='author-first-name-0']"),
                (By.XPATH, "//input[contains(@id,'author-first-name')]"),
                (By.XPATH, "//input[contains(@name,'author-first-name')]"),
                (By.XPATH, "//label[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'first name')]/following::input[@type='text'][1]"),
            ]
            last_selectors = [
                (By.ID, "author-last-name-0"),
                (By.XPATH, "//input[@id='author-last-name-0']"),
                (By.XPATH, "//input[contains(@id,'author-last-name')]"),
                (By.XPATH, "//input[contains(@name,'author-last-name')]"),
                (By.XPATH, "//label[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'last name')]/following::input[@type='text'][1]"),
            ]
            first_el = _try_selectors(first_selectors, timeout=8)
            if first_el:
                _fill_el(first_el, first)
                if get_verbose():
                    info(f"KDP: author first name filled: {first}")
            else:
                warning("KDP: author first name field not found")
            last_el = _try_selectors(last_selectors, timeout=8)
            if last_el:
                _fill_el(last_el, last)
                if get_verbose():
                    info(f"KDP: author last name filled: {last}")
            else:
                warning("KDP: author last name field not found")

            # Description — KDP uses a contenteditable rich text editor, NOT a textarea
            try:
                # Wait for the contenteditable div inside the description section
                desc_el = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH,
                        "//div[@contenteditable='true' and not(@aria-label='Search')]"
                    ))
                )
                # Click to focus, clear existing content, type description
                desc_el.click()
                time.sleep(0.3)
                desc_el.send_keys(Keys.CONTROL + "a")
                desc_el.send_keys(Keys.DELETE)
                desc_el.send_keys(self.description[:4000])
                time.sleep(0.5)
                if get_verbose():
                    info("KDP: description filled.")
            except Exception as _de:
                if get_verbose():
                    warning(f"KDP: description fill failed ({_de}) — trying JS fallback.")
                try:
                    desc_el = driver.find_element(By.XPATH, "//div[@contenteditable='true']")
                    driver.execute_script(
                        "arguments[0].focus(); arguments[0].textContent = arguments[1];"
                        "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
                        desc_el, self.description[:4000]
                    )
                except Exception:
                    pass

            # SEO Keywords (7 phrases from generate_content)
            kw_list = self.keywords if self.keywords else (self.topic + " guide tips practical how to").split()[:7]
            for i, kw in enumerate(kw_list[:7]):
                kw_selectors = [
                    (By.XPATH, f"(//input[contains(@id,'keyword')])[{i+1}]"),
                    (By.XPATH, f"(//input[@placeholder='Keyword' or contains(@placeholder,'keyword')])[{i+1}]"),
                    (By.XPATH, f"(//input[contains(@name,'keyword')])[{i+1}]"),
                ]
                kw_el = _try_selectors(kw_selectors, timeout=5)
                if kw_el:
                    _fill_el(kw_el, kw)

            # Answer Adult-only question (required before category can be selected)
            # KDP blocks "Save and continue" if this is unanswered
            adult_selectors = [
                (By.XPATH, "//input[@type='radio' and contains(@id,'adult') and (@value='false' or @value='0')]"),
                (By.XPATH, "//input[@type='radio' and contains(@name,'adult') and (@value='false' or @value='0')]"),
                (By.XPATH, "//input[@type='radio' and @name='data-is-adult' and @value='false']"),
                (By.XPATH, "//label[contains(text(),'No') and (contains(@for,'adult') or contains(@for,'Adult'))]/preceding-sibling::input[@type='radio']"),
                (By.XPATH, "//label[contains(@for,'adult') and contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'no')]/preceding-sibling::input"),
            ]
            adult_el = _try_selectors(adult_selectors, timeout=5)
            if adult_el:
                driver.execute_script("arguments[0].click();", adult_el)
                time.sleep(0.5)
                if get_verbose():
                    info("KDP: Adult content answered (No).")
            else:
                if get_verbose():
                    warning("KDP: Adult-only radio not found by standard selectors — trying JS scan.")
                # Fallback: find all radio buttons near text containing "adult"
                try:
                    driver.execute_script("""
                        var radios = document.querySelectorAll('input[type=radio]');
                        for (var r of radios) {
                            var label = document.querySelector('label[for="' + r.id + '"]');
                            var nearby = r.closest('div') ? r.closest('div').textContent : '';
                            if ((nearby.toLowerCase().includes('adult') || (label && label.textContent.toLowerCase().includes('no')))
                                && (r.value === 'false' || r.value === '0' || r.value === 'no')) {
                                r.click(); break;
                            }
                        }
                    """)
                    time.sleep(0.5)
                except Exception:
                    pass

            # Select book category (required — KDP blocks save if no category)
            try:
                cat_btn_selectors = [
                    (By.XPATH, "//button[contains(text(),'Choose categories')]"),
                    (By.XPATH, "//a[contains(text(),'Choose categories')]"),
                    (By.XPATH, "//button[contains(text(),'Add categories')]"),
                    (By.XPATH, "//span[contains(text(),'Choose categories')]"),
                ]
                cat_btn = _try_selectors(cat_btn_selectors, timeout=5)
                if cat_btn:
                    driver.execute_script("arguments[0].click();", cat_btn)
                    time.sleep(3)
                    if get_verbose():
                        info("KDP: category modal opened.")

                    # In the modal: answer adult content question if present
                    modal_adult = _try_selectors([
                        (By.XPATH, "//input[@type='radio' and (@value='false' or @value='0')]"),
                        (By.XPATH, "//label[translate(normalize-space(text()),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='no']/preceding-sibling::input[@type='radio']"),
                    ], timeout=4)
                    if modal_adult:
                        driver.execute_script("arguments[0].click();", modal_adult)
                        time.sleep(1)

                    # Navigate category tree: try "Nonfiction" → "Self-Help", or direct "Self-Help"
                    category_xpaths = [
                        "//span[normalize-space(text())='Nonfiction']",
                        "//li[normalize-space(text())='Nonfiction']",
                        "//div[normalize-space(text())='Nonfiction']",
                        "//span[normalize-space(text())='Self-Help']",
                        "//li[normalize-space(text())='Self-Help']",
                        "//span[normalize-space(text())='Health, Mind & Body']",
                        "//span[normalize-space(text())='Business & Money']",
                    ]
                    for xpath in category_xpaths:
                        try:
                            cat_item = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, xpath))
                            )
                            cat_item.click()
                            time.sleep(1)
                            if get_verbose():
                                info(f"KDP: category item clicked.")
                            break
                        except Exception:
                            continue

                    # Click "Add" button in modal
                    add_btn = _try_selectors([
                        (By.XPATH, "//button[normalize-space(text())='Add']"),
                        (By.XPATH, "//button[contains(text(),'Add')]"),
                        (By.XPATH, "//input[@value='Add category']"),
                        (By.XPATH, "//input[@value='Add']"),
                    ], timeout=5)
                    if add_btn:
                        driver.execute_script("arguments[0].click();", add_btn)
                        time.sleep(1)
                        if get_verbose():
                            info("KDP: category added.")

                    # Close/save the modal
                    close_btn = _try_selectors([
                        (By.XPATH, "//button[normalize-space(text())='Save']"),
                        (By.XPATH, "//button[normalize-space(text())='Done']"),
                        (By.XPATH, "//button[contains(text(),'Close')]"),
                        (By.XPATH, "//button[contains(@aria-label,'Close')]"),
                    ], timeout=3)
                    if close_btn:
                        driver.execute_script("arguments[0].click();", close_btn)
                        time.sleep(1)

            except Exception as _ce:
                if get_verbose():
                    warning(f"KDP category selection skipped: {_ce}")

            time.sleep(1)

            # Save and continue — Details → Content
            save_selectors = [
                (By.XPATH, "//button[contains(@id,'save-and-continue')]"),
                (By.XPATH, "//a[contains(@id,'save-and-continue')]"),
                (By.XPATH, "//button[contains(text(),'Save and continue')]"),
                (By.XPATH, "//button[contains(text(),'Save & Continue')]"),
                (By.XPATH, "//a[contains(text(),'Save and continue')]"),
                (By.XPATH, "//input[@type='submit' and contains(@value,'Save')]"),
                (By.XPATH, "//button[@data-action='save-and-continue']"),
                (By.XPATH, "//span[@id='save-and-continue-announce']"),
            ]
            save_el = _try_selectors(save_selectors, timeout=10)
            if save_el:
                driver.execute_script("arguments[0].scrollIntoView(true);", save_el)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", save_el)
                # Wait for navigation from /details to /content
                if not _wait_for_url_fragment("content", timeout=20):
                    time.sleep(5)
                    # Take screenshot if still on details page
                    if "details" in driver.current_url:
                        try:
                            driver.save_screenshot(os.path.join(ROOT_DIR, ".mp", "kdp-details-blocked.png"))
                        except Exception:
                            pass
                        if get_verbose():
                            warning("KDP: still on details page after Save — check .mp/kdp-details-blocked.png")
                if get_verbose():
                    info(f"KDP navigated to: {driver.current_url}")

            # Content page — upload EPUB
            # KDP renders <input type="file"> as display:none (React UI).
            # Must use presence_of_element_located + JS visibility override.

            # Step 1: click any visible Upload button to initialize KDP's state
            upload_btn_selectors = [
                (By.XPATH, "//button[contains(text(),'Upload manuscript')]"),
                (By.XPATH, "//button[contains(text(),'Upload')]"),
                (By.XPATH, "//button[contains(text(),'Browse')]"),
                (By.XPATH, "//span[contains(text(),'Upload manuscript')]"),
            ]
            upload_btn = _try_selectors(upload_btn_selectors, timeout=8)
            if upload_btn:
                try:
                    upload_btn.click()
                    time.sleep(2)
                    if get_verbose():
                        info("KDP: clicked Upload button, waiting for file input...")
                except Exception:
                    pass

            # Step 2: locate hidden file input and force-show it
            try:
                upload_el = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
                )
                driver.execute_script("arguments[0].style.display = 'block';", upload_el)
                upload_el.send_keys(self.epub_path)
                if get_verbose():
                    info("KDP: EPUB file path sent, waiting for upload processing...")
                time.sleep(15)  # KDP validates the EPUB — needs extra time
                if get_verbose():
                    info("EPUB uploaded to KDP.")
            except Exception as _e:
                warning(f"KDP EPUB upload failed ({_e}) — saving debug screenshot.")
                try:
                    driver.save_screenshot(os.path.join(ROOT_DIR, ".mp", "kdp-content-debug.png"))
                except Exception:
                    pass

            # Save and continue — Content → Pricing
            save_el2 = _try_selectors(save_selectors, timeout=10)
            if save_el2:
                save_el2.click()
                # Wait for navigation from /content to /pricing
                if not _wait_for_url_fragment("pricing", timeout=15):
                    time.sleep(5)
                if get_verbose():
                    info(f"KDP navigated to: {driver.current_url}")

            # Pricing — set price (KDP uses per-territory inputs like price-value-US-)
            price_selectors = [
                (By.XPATH, "//input[contains(@id,'price-value-')]"),
                (By.XPATH, "//input[contains(@id,'price-value')]"),
                (By.XPATH, "//input[contains(@id,'price') and @type='text']"),
                (By.XPATH, "//label[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'list price')]/following::input[1]"),
                (By.XPATH, "//input[@name='price']"),
            ]
            price_el = _try_selectors(price_selectors, timeout=10)
            if price_el:
                _fill_el(price_el, str(get_ebook_price()))
                time.sleep(1)
                if get_verbose():
                    info(f"KDP price set to {get_ebook_price()}")

            # Publish button
            publish_selectors = [
                (By.XPATH, "//button[contains(text(),'Publish Your Kindle eBook')]"),
                (By.XPATH, "//input[@id='submit-button']"),
                (By.XPATH, "//button[contains(text(),'Publish')]"),
                (By.XPATH, "//button[contains(@id,'publish')]"),
                (By.XPATH, "//input[@type='submit' and contains(@value,'Publish')]"),
            ]
            publish_el = _try_selectors(publish_selectors, timeout=10)
            if publish_el:
                publish_el.click()
                time.sleep(3)
                if get_verbose():
                    success("KDP submission sent (review takes 24-72h).")
            else:
                if get_verbose():
                    warning("KDP publish button not found — finish manually at kdp.amazon.com.")

        except Exception as e:
            if get_verbose():
                warning(f"KDP automation error: {e}")
        finally:
            time.sleep(2)
            driver.quit()

    # ------------------------------------------------------------------
    # Main run method
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Run the full pipeline. Returns result dict for cache."""
        info("Fetching trending topics...")
        topics = self.get_trending_topics()

        if not topics:
            topics = ["productivity and time management", "mental wellness", "personal finance basics"]
            warning("No trending topics fetched — using fallback topics.")

        info(f"Found {len(topics)} topics. Asking LLM to pick the best one...")
        for t in topics[:8]:
            print(f"  - {t}")

        self.topic = self.select_topic(topics)
        info(f"Selected topic: {self.topic}")

        self.generate_content()

        info("Formatting PDF...")
        self.format_pdf()

        info("Formatting EPUB...")
        self.format_epub()

        gumroad_url = ""
        _gumroad_ok = get_gumroad_access_token() or os.environ.get("GUMROAD_EMAIL", "").strip()
        if _gumroad_ok:
            gumroad_url = self.publish_to_gumroad()
        else:
            warning("Skipping Gumroad (no access token or GUMROAD_EMAIL). Set gumroad_access_token in config.json.")

        _kdp_ok = get_kdp_firefox_profile() or (get_kdp_email() or os.environ.get("KDP_EMAIL", "").strip())
        if _kdp_ok:
            self.publish_to_kdp()
        else:
            warning("Skipping KDP (no kdp_firefox_profile or KDP_EMAIL). Set kdp_firefox_profile in config.json.")

        result = {
            "id": str(uuid.uuid4()),
            "title": self.title,
            "topic": self.topic,
            "pdf_path": self.pdf_path,
            "epub_path": self.epub_path,
            "gumroad_url": gumroad_url,
            "price": get_ebook_price(),
            "published_at": datetime.utcnow().isoformat(),
        }

        success(f"eBook pipeline complete: {self.title}")
        if gumroad_url:
            success(f"Gumroad: {gumroad_url}")

        return result
