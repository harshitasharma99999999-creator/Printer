import re
import base64
import json
import time
import os
import subprocess
import requests

from utils import *
from cache import *
from .Tts import TTS
from llm_provider import generate_text
from config import *
from status import *
from uuid import uuid4
from constants import *
from typing import List
from moviepy.editor import *
from moviepy.config import change_settings
from moviepy.video.fx.crop import crop as mpy_crop
from termcolor import colored
from moviepy.video.tools.subtitles import SubtitlesClip
from datetime import datetime


class YouTube:
    """
    Class for YouTube Automation.

    Steps to create a YouTube Short:
    1. Generate a topic [DONE]
    2. Generate a script [DONE]
    3. Generate metadata (Title, Description, Tags) [DONE]
    4. Generate AI Image Prompts [DONE]
    4. Generate Images based on generated Prompts [DONE]
    5. Convert Text-to-Speech [DONE]
    6. Show images each for n seconds, n: Duration of TTS / Amount of images [DONE]
    7. Combine Concatenated Images with the Text-to-Speech [DONE]
    """

    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
    ) -> None:
        """
        Constructor for YouTube Class.

        Args:
            account_uuid (str): The unique identifier for the YouTube account.
            account_nickname (str): The nickname for the YouTube account.
            fp_profile_path (str): Path to the firefox profile that is logged into the specificed YouTube Account.
            niche (str): The niche of the provided YouTube Channel.
            language (str): The language of the Automation.

        Returns:
            None
        """
        self._account_uuid: str = account_uuid
        self._account_nickname: str = account_nickname
        self._fp_profile_path: str = fp_profile_path
        self._niche: str = niche
        self._language: str = language

        self.images = []
        os.environ["IMAGEMAGICK_BINARY"] = get_imagemagick_path()
        change_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})

    def set_subject(self, subject: str) -> None:
        """Override topic generation with a specific subject (e.g. product name)."""
        self.subject = subject

    def _is_psychology_channel(self) -> bool:
        niche = (self.niche or "").lower()
        return "psychology" in niche or "behavior" in niche or "dark truth" in niche

    def _is_manifestation_channel(self) -> bool:
        niche = (self.niche or "").lower()
        nickname = (self._account_nickname or "").lower()
        return (
            "manifestation" in niche
            or "law of attraction" in niche
            or "spiritual" in niche
            or "consciousness" in niche
            or "universe" in nickname
        )

    def _is_finance_channel(self) -> bool:
        niche = (self.niche or "").lower()
        finance_terms = [
            "stock",
            "stock market",
            "stockmarket",
            "forex",
            "crypto",
            "trading",
            "investing",
            "finance",
            "market facts",
            "bitcoin",
        ]
        return any(term in niche for term in finance_terms)

    def _is_cryptohub_channel(self) -> bool:
        nickname = (self._account_nickname or "").lower()
        account_uuid = (self._account_uuid or "").lower()
        niche = (self.niche or "").lower()
        return (
            "cryptohub" in nickname
            or "cryptohub" in account_uuid
            or "crypto hub" in niche
            or "cryptohub" in niche
        )

    def _get_brand_logo_path(self) -> str:
        if self._is_cryptohub_channel():
            logo_path = os.path.join(ROOT_DIR, "assets", "channel_branding", "cryptohub_logo.png")
            if os.path.exists(logo_path):
                return logo_path
        return ""

    def _is_music_only_channel(self) -> bool:
        nickname = (self._account_nickname or "").lower()
        account_uuid = (self._account_uuid or "").lower()
        return (
            self._is_cryptohub_channel()
            or self._is_psychology_channel()
            or self._is_manifestation_channel()
            or "moneymarkettt" in nickname
            or "moneymarkettt" in account_uuid
        )

    @property
    def niche(self) -> str:
        """
        Getter Method for the niche.

        Returns:
            niche (str): The niche
        """
        return self._niche

    @property
    def language(self) -> str:
        """
        Getter Method for the language to use.

        Returns:
            language (str): The language
        """
        return self._language

    def generate_response(self, prompt: str, model_name: str = None) -> str:
        """
        Generates an LLM Response based on a prompt and the user-provided model.

        Args:
            prompt (str): The prompt to use in the text generation.

        Returns:
            response (str): The generated AI Repsonse.
        """
        return generate_text(prompt, model_name=model_name)

    def generate_topic(self) -> str:
        """
        Generates a topic based on the YouTube Channel niche.

        Returns:
            topic (str): The generated topic.
        """
        if self._is_psychology_channel():
            completion = self.generate_response(
                f"""Generate a compelling YouTube Shorts topic about: {self.niche}
Style: real human psychology, dark truths, emotional patterns, hidden motives, self-deception, power, attachment, attraction, insecurity, status, respect, and manipulation.
Use formats like:
- "The Dark Truth About Why People Pull Away"
- "What Silence Really Means In Human Psychology"
- "Why People Respect You Less When You Do This"
- "The Brutal Psychology Of Attention And Validation"
- "What Insecurity Makes People Hide"
- "The Dark Side Of People Pleasing"
- "Why Some People Only Value You After Losing You"
Return ONLY the video topic as one sentence. Nothing else."""
            )
            if not completion:
                error("Failed to generate Topic.")
            self.subject = completion
            return completion
        if self._is_cryptohub_channel():
            completion = self.generate_response(
                f"""Generate a compelling YouTube Shorts topic about: {self.niche}
Style: premium crypto facts and crypto market insights for the CryptoHub brand.
Use formats like:
- "The Bitcoin Fact Most People Miss"
- "The Crypto Signal Smart Traders Watch"
- "Why Ethereum Moves Before Altcoins"
- "The Hidden Truth Behind This Crypto Rally"
- "What Most Beginners Never Notice In Crypto"
- "The On-Chain Clue That Changes Everything"
- "The Crypto Psychology Behind Panic Selling"
Rules:
- Focus only on crypto, bitcoin, ethereum, altcoins, blockchain, on-chain data, market structure, or trader psychology
- Make it sharp, premium, curiosity-driven, and factual
- Return ONLY the video topic as one sentence
- No emojis, no numbering, nothing else"""
            )
            if not completion:
                error("Failed to generate Topic.")
            self.subject = completion
            return completion
        if self._is_finance_channel():
            completion = self.generate_response(
                f"""Generate a compelling YouTube Shorts topic about: {self.niche}
Style: fast, cool, educational market facts about stocks, forex, crypto, macro moves, trader psychology, money history, and surprising chart facts.
Use formats like:
- "The Stock Market Fact Most Beginners Never Learn"
- "The Forex Truth Hidden In One Number"
- "This Crypto Fact Sounds Fake But It Is Real"
- "Why Traders Watch This One Market Signal"
- "The Weird History Behind A Market Crash"
- "What Most People Get Wrong About Bitcoin"
- "The Fastest Way To Understand Market Volatility"
Rules:
- Make it sound factual, punchy, and curiosity-driven
- Focus on one cool fact, one surprising pattern, or one powerful market insight
- Return ONLY the video topic as one sentence
- No emojis, no numbering, nothing else"""
            )
            if not completion:
                error("Failed to generate Topic.")
            self.subject = completion
            return completion
        completion = self.generate_response(
            f"""Generate a compelling YouTube Shorts topic about: {self.niche}
Style: like the channel "YourInnerGuide" — deep, guiding, truth-revealing. The video must feel like a personal spiritual guide is speaking directly to the viewer, revealing an ultimate truth that changes how they see reality.
Use formats like:
- "You Are Not Who You Think You Are — The Truth About Your Consciousness"
- "The Reality You See Is Not Real — Here Is What Actually Is"
- "You Came Here To Shift Reality — This Is How You Do It"
- "The Universe Has Been Trying To Tell You This Your Entire Life"
- "You Are Already Living In Multiple Realities — Here Is The Proof"
- "This Is The ONLY Truth You Need To Shift Your Reality Forever"
- "Stop Trying To Manifest — Do This Instead And Watch Everything Change"
Return ONLY the video topic as one sentence. Nothing else."""
        )

        if not completion:
            error("Failed to generate Topic.")

        self.subject = completion

        return completion

    def generate_script(self) -> str:
        """
        Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.

        Returns:
            script (str): The script of the video.
        """
        sentence_length = get_script_sentence_length()
        if self._is_psychology_channel():
            prompt = f"""You are a sharp human psychology storyteller.
Write a script of exactly {sentence_length} sentences about the subject below.

Tone:
- Direct, emotionally intelligent, and insight-heavy
- Focus on real human behavior and uncomfortable truths
- Make the viewer feel understood, exposed, and more aware
- FIRST SENTENCE must hit with a dark but accurate truth that stops attention immediately
- Each sentence should reveal a deeper layer of motive, insecurity, desire, attachment, fear, or self-deception
- End with a strong insight that helps the viewer read people and themselves more clearly

Rules:
- Exactly {sentence_length} sentences
- NO markdown, NO titles, NO bullet points
- NO filler, NO intro phrases like "in this video"
- Spoken words only
- Use YOU and PEOPLE naturally
- Stay grounded in psychology, behavior, emotional patterns, and dark truths
- Language: {self.language}

Subject: {self.subject}"""
            completion = self.generate_response(prompt)
            completion = re.sub(r"\*", "", completion)
            if not completion:
                error("The generated script is empty.")
                return
            if len(completion) > 5000:
                if get_verbose():
                    warning("Generated Script is too long. Retrying...")
                return self.generate_script()
            self.script = completion
            return completion
        if self._is_cryptohub_channel():
            prompt = f"""You are CryptoHub's sharp crypto educator creating a viral YouTube Short.
Write a script of exactly {sentence_length} sentences about the subject below.

Tone:
- Premium, confident, and intelligent
- Sounds like a strong crypto analyst, not a hype influencer
- FIRST SENTENCE must stop attention with a surprising crypto fact, pattern, or truth
- Keep each sentence short, visual, and easy to follow
- Focus on bitcoin, ethereum, altcoins, blockchain, on-chain behavior, or crypto market psychology
- End with a strong insight that makes the viewer feel more informed about crypto

Rules:
- Exactly {sentence_length} sentences
- NO markdown, NO titles, NO bullet points
- NO filler like "in this video"
- Spoken words only
- No profit promises, no financial advice wording
- Keep it factual, exciting, and clean
- Language: {self.language}

Subject: {self.subject}"""
            completion = self.generate_response(prompt)
            completion = re.sub(r"\*", "", completion)
            if not completion:
                error("The generated script is empty.")
                return
            if len(completion) > 5000:
                if get_verbose():
                    warning("Generated Script is too long. Retrying...")
                return self.generate_script()
            self.script = completion
            return completion
        if self._is_finance_channel():
            prompt = f"""You are a sharp financial educator creating a viral YouTube Short.
Write a script of exactly {sentence_length} sentences about the subject below.

Tone:
- Fast, clear, and surprisingly insightful
- Sounds like a cool market fact expert, not a boring textbook
- FIRST SENTENCE must stop attention immediately with a surprising market truth or stat
- Keep each sentence compact, useful, and easy to follow
- Explain one fact, pattern, lesson, or historical insight about stocks, forex, or crypto
- End with a strong takeaway that makes the viewer feel smarter about markets

Rules:
- Exactly {sentence_length} sentences
- NO markdown, NO titles, NO bullet points
- NO filler like "in this video"
- Spoken words only
- Keep it educational, factual, and engaging
- No promises of profit, no financial advice wording
- Language: {self.language}

Subject: {self.subject}"""
            completion = self.generate_response(prompt)
            completion = re.sub(r"\*", "", completion)
            if not completion:
                error("The generated script is empty.")
                return
            if len(completion) > 5000:
                if get_verbose():
                    warning("Generated Script is too long. Retrying...")
                return self.generate_script()
            self.script = completion
            return completion
        prompt = f"""You are a deeply wise spiritual guide — calm, certain, and profound. Your words carry the weight of ultimate truth. You are like "YourInnerGuide" on YouTube.
Write a script of exactly {sentence_length} sentences about the subject below.

Tone:
- DEEPLY GUIDING — like a wise teacher who knows the truth of consciousness and reality
- Calm yet powerful — every sentence lands like a revelation the viewer has been waiting to hear
- Speak directly to "you" as if you are their inner voice finally speaking out loud
- FIRST SENTENCE must reveal an ultimate truth that immediately makes the viewer stop everything
- Each sentence deepens the truth — like descending deeper into the real nature of existence
- End with a guiding declaration that empowers them to shift their reality right now

Rules:
- Exactly {sentence_length} sentences
- NO markdown, NO titles, NO bullet points
- NO "welcome to" or "in this video" — START with the ultimate truth
- Spoken words only — wise, certain, spiritual, timeless
- Mix short truth bombs with longer profound guiding sentences
- Use YOU and YOUR constantly — speak as their inner guide, their higher self
- Reveal truths about: consciousness, reality, who they truly are, why they are here, how reality works
- Language: {self.language}

Subject: {self.subject}"""
        completion = self.generate_response(prompt)

        # Apply regex to remove *
        completion = re.sub(r"\*", "", completion)

        if not completion:
            error("The generated script is empty.")
            return

        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script()

        self.script = completion

        return completion

    def _get_product_affiliate_link(self) -> str:
        """
        Finds an exact Amazon product matching the video topic and returns a direct
        affiliate link (/dp/ASIN?tag=...). Falls back to a topic-relevant search URL.
        """
        import requests as _req
        import re as _re
        from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs, quote_plus as _qp

        base = get_affiliate_link()
        # Extract affiliate tag from the configured URL
        tag = _parse_qs(_urlparse(base).query).get("tag", ["harshita000-21"])[0]

        # LLM extracts 2-3 product keywords from the video subject
        kw_prompt = (
            f"Extract 2-3 Amazon product search keywords from this YouTube video topic. "
            f"Think: what physical or digital product would someone watching this video want to buy? "
            f"Return ONLY a short search phrase (e.g. 'meditation cushion', 'journal notebook'), nothing else.\n"
            f"Topic: {self.subject}"
        )
        try:
            keywords = generate_text(kw_prompt).strip().strip('"').strip("'")
        except Exception:
            keywords = ""

        if not keywords:
            return base  # fallback to static config link

        keywords = re.sub(r"[\r\n\t]+", " ", keywords)
        keywords = re.sub(r"^\s*[-*]+\s*", "", keywords)
        keywords = re.sub(r"\s{2,}", " ", keywords).strip()

        encoded = _qp(keywords)
        search_url = f"https://www.amazon.in/s?k={encoded}&tag={tag}"

        # Scrape first product ASIN from Amazon search results
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-IN,en;q=0.9",
            }
            r = _req.get(search_url, headers=headers, timeout=12)
            asins = _re.findall(r"/dp/([A-Z0-9]{10})", r.text)
            if asins:
                asin = asins[0]
                product_url = f"https://www.amazon.in/dp/{asin}?tag={tag}"
                if get_verbose():
                    info(f"Affiliate product link: {product_url} (keywords: {keywords})")
                return product_url
        except Exception as e:
            if get_verbose():
                warning(f"Amazon ASIN scrape failed ({e}), using search URL.")

        # Still topic-relevant — far better than a generic category page
        if get_verbose():
            info(f"Affiliate search link: {search_url}")
        return search_url

    @staticmethod
    def _sanitize_youtube_text(text: str, *, limit: int, multiline: bool = False) -> str:
        if not text:
            return ""

        cleaned = str(text).replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", cleaned)

        if multiline:
            cleaned = "\n".join(line.strip() for line in cleaned.split("\n"))
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        else:
            cleaned = re.sub(r"\s+", " ", cleaned)

        return cleaned.strip()[:limit]

    def generate_metadata(self) -> dict:
        """
        Generates Video metadata for the to-be-uploaded YouTube Short (Title, Description, Tags).

        Returns:
            metadata (dict): The generated metadata.
        """
        if self._is_psychology_channel():
            title = self.generate_response(
                f"""Generate a YouTube video title for the following subject.
Style: human psychology channel focused on dark truths, behavior patterns, and emotional insight.
Use formats like:
"The Dark Truth About X", "Why People X", "What X Really Means", "The Brutal Psychology Of X"
Include 2-3 hashtags like #Psychology #HumanBehavior #DarkPsychology
SEO:
- naturally include one strong searchable phrase like human psychology, dark psychology, relationships, body language, emotional intelligence, or attachment style
- make it broad-audience friendly and curiosity-driven
Only return the title. Under 100 characters.
Subject: {self.subject}"""
            )

            if len(title) > 100:
                if get_verbose():
                    warning("Generated Title is too long. Retrying...")
                return self.generate_metadata()

            description = self.generate_response(
                f"Please generate a YouTube Video Description for the following script: {self.script}. "
                f"Tone: calm, confident, insightful, and psychologically sharp. No hype. No markdown. "
                f"Only return the description, nothing else."
            )

            tags_response = self.generate_response(
                f"Generate 10-15 relevant YouTube tags for a video about: {self.subject}. "
                f"Return ONLY a comma-separated list of tags, nothing else. "
                f"Tags should be short (1-3 words), relevant to psychology, human behavior, and emotional truth."
            )

            tags = [tag.strip() for tag in tags_response.split(',') if tag.strip()]
            broad_tags = [
                "human psychology",
                "dark psychology",
                "human behavior",
                "body language",
                "emotional intelligence",
                "relationships",
                "relationship psychology",
                "attachment style",
                "female psychology",
                "male psychology",
                "self awareness",
                "psychology facts",
                "mindset",
                "shorts",
            ]
            for tag in broad_tags:
                if tag.lower() not in {t.lower() for t in tags}:
                    tags.append(tag)
            tags = tags[:15]

            subject_line = self._sanitize_youtube_text(self.subject, limit=120, multiline=False)
            summary_line = self._sanitize_youtube_text(description, limit=220, multiline=False)
            if not summary_line:
                summary_line = "Dark truths about human behavior, emotional patterns, and self-awareness."

            description = (
                f"{subject_line}\n\n"
                f"{summary_line}\n\n"
                "#Shorts #Psychology #HumanBehavior #DarkPsychology #RelationshipAdvice"
            )

            self.metadata = {"title": title, "description": description, "tags": tags}
            return self.metadata
        if self._is_cryptohub_channel():
            title = self.generate_response(
                f"""Generate a YouTube Shorts title for the following subject.
Style: premium CryptoHub channel focused on bitcoin, crypto facts, market psychology, and sharp insights.
Use formats like:
"The Bitcoin Truth Nobody Sees", "This Crypto Signal Matters", "Why Ethereum Moves First", "The Hidden Crypto Pattern"
Include 2-3 hashtags like #Crypto #Bitcoin #Ethereum
SEO:
- naturally include one strong searchable keyword like Bitcoin, Ethereum, crypto market, altcoins, blockchain, or crypto trading
- make it curiosity-driven and broad-audience friendly
Only return the title. Under 100 characters.
Subject: {self.subject}"""
            )

            if len(title) > 100:
                if get_verbose():
                    warning("Generated Title is too long. Retrying...")
                return self.generate_metadata()

            description = self.generate_response(
                f"Please generate a YouTube Video Description for the following script: {self.script}. "
                f"Tone: premium, clear, confident, crypto-smart. No hype. No markdown. "
                f"Only return the description, nothing else."
            )

            tags_response = self.generate_response(
                f"Generate 10-15 relevant YouTube tags for a video about: {self.subject}. "
                f"Return ONLY a comma-separated list of tags, nothing else. "
                f"Tags should be short, search-friendly, and relevant to crypto, bitcoin, ethereum, altcoins, blockchain, and market insights."
            )

            tags = [tag.strip() for tag in tags_response.split(',') if tag.strip()]
            broad_tags = [
                "crypto",
                "bitcoin",
                "ethereum",
                "altcoins",
                "blockchain",
                "crypto news",
                "crypto facts",
                "crypto shorts",
                "bitcoin news",
                "ethereum news",
                "crypto market",
                "crypto trading",
                "on chain",
                "market psychology",
                "shorts",
            ]
            for tag in broad_tags:
                if tag.lower() not in {t.lower() for t in tags}:
                    tags.append(tag)
            tags = tags[:15]

            subject_line = self._sanitize_youtube_text(self.subject, limit=120, multiline=False)
            summary_line = self._sanitize_youtube_text(description, limit=220, multiline=False)
            if not summary_line:
                summary_line = "Sharp crypto facts and premium market insights about bitcoin, ethereum, altcoins, and blockchain behavior."

            description = (
                f"{subject_line}\n\n"
                f"{summary_line}\n\n"
                "#Shorts #Crypto #Bitcoin #Ethereum #CryptoNews"
            )

            self.metadata = {"title": title, "description": description, "tags": tags}
            return self.metadata
        if self._is_finance_channel():
            title = self.generate_response(
                f"""Generate a YouTube Shorts title for the following subject.
Style: finance facts channel focused on cool stock market, forex, and crypto insights.
Use formats like:
"The Market Fact Nobody Tells You", "This Crypto Truth Is Wild", "Why Traders Watch This", "The Hidden Forex Rule"
Include 2-3 hashtags like #StockMarket #Forex #Crypto
SEO:
- naturally include a searchable keyword like stock market, forex, bitcoin, trading, investing, market crash, volatility, or market psychology
- make it broad-audience friendly and curiosity-driven
Only return the title. Under 100 characters.
Subject: {self.subject}"""
            )

            if len(title) > 100:
                if get_verbose():
                    warning("Generated Title is too long. Retrying...")
                return self.generate_metadata()

            description = self.generate_response(
                f"Please generate a YouTube Video Description for the following script: {self.script}. "
                f"Tone: confident, clear, educational, and market-smart. No hype. No markdown. "
                f"Only return the description, nothing else."
            )

            tags_response = self.generate_response(
                f"Generate 10-15 relevant YouTube tags for a video about: {self.subject}. "
                f"Return ONLY a comma-separated list of tags, nothing else. "
                f"Tags should be short, search-friendly, and relevant to stock market, forex, trading, investing, and crypto facts."
            )

            tags = [tag.strip() for tag in tags_response.split(',') if tag.strip()]
            broad_tags = [
                "stock market",
                "forex",
                "crypto",
                "trading",
                "investing",
                "market facts",
                "finance",
                "bitcoin",
                "money",
                "stock market facts",
                "market psychology",
                "forex trading",
                "crypto trading",
                "investing for beginners",
                "shorts",
            ]
            for tag in broad_tags:
                if tag.lower() not in {t.lower() for t in tags}:
                    tags.append(tag)
            tags = tags[:15]

            subject_line = self._sanitize_youtube_text(self.subject, limit=120, multiline=False)
            summary_line = self._sanitize_youtube_text(description, limit=220, multiline=False)
            if not summary_line:
                summary_line = "Cool facts and sharp lessons about stocks, forex, crypto, and how markets really move."

            description = (
                f"{subject_line}\n\n"
                f"{summary_line}\n\n"
                "#Shorts #StockMarket #Forex #Crypto #TradingTips"
            )

            self.metadata = {"title": title, "description": description, "tags": tags}
            return self.metadata
        title = self.generate_response(
            f"""Generate a YouTube video title for the following subject.
Style: Jung Thoughts channel — use formats like:
"What X Really Becomes", "X's Uncomfortable Truth", "The Hidden Truth About X", "Why X – A Warning"
Include 2-3 hashtags like #Psychology #JungThoughts #Spirituality
SEO:
- naturally include one strong searchable keyword like manifestation, law of attraction, spiritual awakening, consciousness, self concept, or reality shifting
- make it broad-audience friendly and curiosity-driven
Only return the title. Under 100 characters.
Subject: {self.subject}"""
        )

        if len(title) > 100:
            if get_verbose():
                warning("Generated Title is too long. Retrying...")
            return self.generate_metadata()

        description = self.generate_response(
            f"Please generate a YouTube Video Description for the following script: {self.script}. "
            f"Tone: calm, confident, helpful. No hype. No markdown. "
            f"Only return the description, nothing else."
        )

        # Generate relevant tags based on the subject
        tags_response = self.generate_response(
            f"Generate 10-15 relevant YouTube tags for a video about: {self.subject}. "
            f"Return ONLY a comma-separated list of tags, nothing else. "
            f"Tags should be short (1-3 words), relevant to the topic, and optimized for search."
        )
        
        # Parse tags from response
        tags = [tag.strip() for tag in tags_response.split(',') if tag.strip()]
        broad_tags = [
            "manifestation",
            "law of attraction",
            "spiritual awakening",
            "mindset",
            "motivation",
            "self improvement",
            "consciousness",
            "reality shifting",
            "self concept",
            "subconscious mind",
            "affirmations",
            "manifestation techniques",
            "healing",
            "energy",
            "shorts",
        ]
        for tag in broad_tags:
            if tag.lower() not in {t.lower() for t in tags}:
                tags.append(tag)
        tags = tags[:15]  # YouTube allows max 15 tags
        
        affiliate_link = self._get_product_affiliate_link()
        if affiliate_link:
            description += f"\n\n🛒 Recommended → {affiliate_link}"
            # Write for Instagram runner to pick up in the same CI run
            try:
                with open(os.path.join(ROOT_DIR, ".mp", "affiliate_link.txt"), "w") as _f:
                    _f.write(affiliate_link)
            except Exception:
                pass

        # Add non-salesy CTA for the matching eBook (if available)
        try:
            from marketing import build_youtube_description, get_latest_ebook_url

            mp_dir = os.path.join(ROOT_DIR, ".mp")
            ebook_url = get_latest_ebook_url(mp_dir)
            description = build_youtube_description(
                base_description=description,
                topic=self.subject,
                ebook_url=ebook_url,
                affiliate_link=affiliate_link,
                include_disclosure=True,
                is_shorts=True,
            )
        except Exception:
            pass

        # #Shorts tag is required for YouTube to classify vertical videos as Shorts
        broad_hashtags = "#Shorts #Manifestation #LawOfAttraction #SpiritualAwakening #Mindset"
        if "#Shorts" not in description and "#shorts" not in description:
            description += f"\n\n{broad_hashtags}"
        elif "#Manifestation" not in description and "#manifestation" not in description:
            description += "\n#Manifestation #LawOfAttraction #SpiritualAwakening #Mindset"

        self.metadata = {"title": title, "description": description, "tags": tags}

        return self.metadata

    def generate_prompts(self, _retries: int = 0) -> List[str]:
        """
        Generates AI Image Prompts based on the provided Video Script.

        Returns:
            image_prompts (List[str]): Generated List of image prompts.
        """
        n_prompts = 5

        if self._is_psychology_channel():
            prompt = f"""Generate exactly {n_prompts} cinematic image prompts for a YouTube Short about human psychology.
Each image must feel emotionally intense, realistic, and symbolic of hidden motives, emotional distance, power, insecurity, overthinking, attachment, or self-deception.
Style: hyper-realistic psychology visuals, dramatic lighting, expressive faces, tense body language, reflective mirrors, isolation, urban night scenes, subtle symbolism.
DO NOT generate gore, monsters, or fantasy. Keep it realistic, human, and emotionally sharp.
Return ONLY a JSON array of {n_prompts} strings, nothing else.

Subject: {self.subject}"""

            completion = (
                str(self.generate_response(prompt))
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            image_prompts = []

            try:
                parsed = json.loads(completion)
                if isinstance(parsed, list):
                    image_prompts = [str(p) for p in parsed if p]
                elif isinstance(parsed, dict) and "image_prompts" in parsed:
                    image_prompts = parsed["image_prompts"]
            except Exception:
                r = re.compile(r"\[.*?\]", re.DOTALL)
                match = r.search(completion)
                if match:
                    try:
                        image_prompts = json.loads(match.group())
                    except Exception:
                        pass

            if not image_prompts:
                if _retries < 3:
                    if get_verbose():
                        warning("Failed to parse image prompts. Retrying...")
                    return self.generate_prompts(_retries=_retries + 1)
                if get_verbose():
                    warning("Using fallback image prompts.")
                image_prompts = [
                    f"close-up of a person's face hiding emotion behind a calm expression, dramatic cinematic lighting, realistic human psychology theme, {self.subject}",
                    f"person sitting alone at night overthinking text messages, city lights blurred in background, emotionally tense, realistic, {self.subject}",
                    f"mirror reflection showing inner conflict and self-deception, cinematic realism, powerful body language, {self.subject}",
                    f"two people standing close but emotionally distant, subtle tension, dark neutral palette, realistic relationship psychology, {self.subject}",
                    f"extreme close-up of eyes revealing fear, desire, and insecurity, dramatic portrait photography, {self.subject}",
                ]

            image_prompts = image_prompts[:n_prompts]
            self.image_prompts = image_prompts

            if get_verbose():
                info(f" => Generated Image Prompts: {image_prompts}")
            success(f"Generated {len(image_prompts)} Image Prompts.")
            return image_prompts

        if self._is_cryptohub_channel():
            prompt = f"""Generate exactly {n_prompts} cinematic image prompts for a YouTube Short about crypto markets.
Each image must feel premium, futuristic, and branded for a black, gold, and silver crypto channel, showing bitcoin, ethereum, candlestick charts, blockchain signals, digital market dashboards, and high-end macro tension.
Style: luxury crypto visuals, deep black background, gold highlights, silver accents, dramatic lighting, glossy screens, coins, on-chain data, market motion, and premium contrast.
DO NOT generate fantasy art, cartoons, or text-heavy images.
Return ONLY a JSON array of {n_prompts} strings, nothing else.

Subject: {self.subject}"""

            completion = (
                str(self.generate_response(prompt))
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            image_prompts = []

            try:
                parsed = json.loads(completion)
                if isinstance(parsed, list):
                    image_prompts = [str(p) for p in parsed if p]
                elif isinstance(parsed, dict) and "image_prompts" in parsed:
                    image_prompts = parsed["image_prompts"]
            except Exception:
                r = re.compile(r"\[.*?\]", re.DOTALL)
                match = r.search(completion)
                if match:
                    try:
                        image_prompts = json.loads(match.group())
                    except Exception:
                        pass

            if not image_prompts:
                if _retries < 3:
                    if get_verbose():
                        warning("Failed to parse image prompts. Retrying...")
                    return self.generate_prompts(_retries=_retries + 1)
                if get_verbose():
                    warning("Using fallback image prompts.")
                image_prompts = [
                    f"premium black and gold bitcoin coin floating over a glossy dark trading screen with silver reflections, cinematic crypto branding, {self.subject}",
                    f"luxury ethereum chart dashboard with deep black background and gold signal lines, futuristic crypto analysis, {self.subject}",
                    f"close-up of candlestick charts, bitcoin, and blockchain nodes in black gold and silver theme, premium contrast, {self.subject}",
                    f"futuristic crypto trader desk with glowing market monitors in black, gold, and silver palette, dramatic finance lighting, {self.subject}",
                    f"macro crypto market skyline with digital coins, circuit patterns, and gold highlights on a black background, branded premium crypto mood, {self.subject}",
                ]

            image_prompts = image_prompts[:n_prompts]
            self.image_prompts = image_prompts

            if get_verbose():
                info(f" => Generated Image Prompts: {image_prompts}")
            success(f"Generated {len(image_prompts)} Image Prompts.")

            return image_prompts

        if self._is_finance_channel():
            prompt = f"""Generate exactly {n_prompts} cinematic image prompts for a YouTube Short about financial markets.
Each image must feel modern, premium, and scroll-stopping, showing the energy of stocks, forex, crypto, charts, trading floors, glowing tickers, global money flows, and macro movement.
Style: strict black and white finance visuals, monochrome cinematic contrast, dramatic lighting, deep shadows, glossy screens, chart reflections, city skylines, trading desks, coins, candlesticks, world maps, motion and tension.
DO NOT generate fantasy art, cartoons, or unreadable text-heavy images.
Return ONLY a JSON array of {n_prompts} strings, nothing else.

Subject: {self.subject}"""

            completion = (
                str(self.generate_response(prompt))
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            image_prompts = []

            try:
                parsed = json.loads(completion)
                if isinstance(parsed, list):
                    image_prompts = [str(p) for p in parsed if p]
                elif isinstance(parsed, dict) and "image_prompts" in parsed:
                    image_prompts = parsed["image_prompts"]
            except Exception:
                r = re.compile(r"\[.*?\]", re.DOTALL)
                match = r.search(completion)
                if match:
                    try:
                        image_prompts = json.loads(match.group())
                    except Exception:
                        pass

            if not image_prompts:
                if _retries < 3:
                    if get_verbose():
                        warning("Failed to parse image prompts. Retrying...")
                    return self.generate_prompts(_retries=_retries + 1)
                if get_verbose():
                    warning("Using fallback image prompts.")
                image_prompts = [
                    f"strict black and white stock market screens with monochrome candlesticks and dramatic trading floor mood, {self.subject}",
                    f"black and white bitcoin and forex charts reflected on a trader's face in a dark modern office, cinematic finance lighting, {self.subject}",
                    f"monochrome global market map with currency lines, stock tickers, and moving data streams, premium macro finance visual, {self.subject}",
                    f"black and white close-up of hands analyzing multiple trading charts on monitors, high tension, realistic investing scene, {self.subject}",
                    f"black and white city skyline at night blended with crypto coins, market graphs, and bullish-bearish tension, cinematic, {self.subject}",
                ]

            image_prompts = image_prompts[:n_prompts]
            self.image_prompts = image_prompts

            if get_verbose():
                info(f" => Generated Image Prompts: {image_prompts}")
            success(f"Generated {len(image_prompts)} Image Prompts.")

            return image_prompts

        prompt = f"""Generate exactly {n_prompts} deeply spiritual and cinematic image prompts for a YouTube Short about consciousness, reality shifting, and inner truth.
Each image must feel like a visual gateway into a higher dimension — breathtaking, otherworldly, and deeply meaningful.
Style: hyper-realistic spiritual photography — soft divine light, cosmic infinity, the feeling of awakening, sacred and timeless.
Use: a lone meditating human bathed in divine golden light, infinite starfields with a silhouette, cosmic doorways opening, the universe inside a human chest, eyes reflecting galaxies, light pouring from hands, ancient temples dissolving into stars.
DO NOT use dark or scary imagery. Only divine, awe-inspiring, deeply peaceful yet powerful visuals.
Return ONLY a JSON array of {n_prompts} strings, nothing else.

Subject: {self.subject}"""

        completion = (
            str(self.generate_response(prompt))
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        image_prompts = []

        try:
            parsed = json.loads(completion)
            if isinstance(parsed, list):
                image_prompts = [str(p) for p in parsed if p]
            elif isinstance(parsed, dict) and "image_prompts" in parsed:
                image_prompts = parsed["image_prompts"]
        except Exception:
            # Try to extract [...] substring
            r = re.compile(r"\[.*?\]", re.DOTALL)
            match = r.search(completion)
            if match:
                try:
                    image_prompts = json.loads(match.group())
                except Exception:
                    pass

        if not image_prompts:
            if _retries < 3:
                if get_verbose():
                    warning("Failed to parse image prompts. Retrying...")
                return self.generate_prompts(_retries=_retries + 1)
            # Fallback: scroll-stopping cinematic prompts
            if get_verbose():
                warning("Using fallback image prompts.")
            image_prompts = [
                f"lone human silhouette sitting in deep meditation on a mountaintop, vast cosmos above, divine golden light pouring down from infinite stars, {self.subject}, 8k cinematic spiritual",
                f"a human figure dissolving into pure white light, the universe expanding from within their chest, reality shifting, awe-inspiring, {self.subject}, hyper-realistic divine",
                f"ancient cosmic doorway opening in the sky above a still lake, perfect reflection, soft golden light streaming through, invitation to higher reality, {self.subject}, cinematic 8k",
                f"extreme close-up of a human eye reflecting an entire galaxy, stars and nebulas inside the iris, the universe looking back, {self.subject}, ultra-detailed spiritual 8k",
                f"human hands open and glowing, streams of soft golden light flowing upward into the cosmos, infinite giving and receiving, {self.subject}, divine cinematic composition",
            ]

        image_prompts = image_prompts[:n_prompts]
        self.image_prompts = image_prompts

        if get_verbose():
            info(f" => Generated Image Prompts: {image_prompts}")
        success(f"Generated {len(image_prompts)} Image Prompts.")

        return image_prompts

    def _generate_finance_music(self, duration: float) -> str:
        out_path = os.path.join(ROOT_DIR, ".mp", f"finance_ambient_{uuid4().hex[:6]}.wav")
        expr = (
            "(0.16*sin(2*PI*48.00*t)"
            "+0.10*sin(2*PI*96.00*t)"
            "+0.08*sin(2*PI*192.00*t)"
            "+0.05*sin(2*PI*288.00*t)"
            "+0.03*sin(2*PI*384.00*t)"
            "+0.025*sin(2*PI*768.00*t)*(0.45+0.55*sin(2*PI*3.4*t))"
            "+0.02*sin(2*PI*1536.00*t)*(0.35+0.65*sin(2*PI*6.8*t)))"
            "*(0.72+0.28*sin(2*PI*0.48*t))"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"aevalsrc={expr}:s=22050:d={int(duration) + 2}",
            "-af",
            (
                "highpass=f=40,"
                "lowpass=f=5400,"
                "acompressor=threshold=-18dB:ratio=2.5:attack=20:release=180,"
                "aecho=0.75:0.68:42:0.18,"
                "treble=g=4:f=2800:w=0.7,"
                "afade=t=in:st=0:d=0.8,"
                f"afade=t=out:st={max(0, int(duration) - 1)}:d=2"
            ),
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            if get_verbose():
                warning(
                    "Finance ambient music generation failed: "
                    f"{result.stderr.decode(errors='ignore')[:300]}"
                )
            return ""
        if get_verbose():
            info(f"Generated finance ambient music: {out_path}")
        return out_path

    def _generate_psychology_music(self, duration: float) -> str:
        out_path = os.path.join(ROOT_DIR, ".mp", f"psychology_ambient_{uuid4().hex[:6]}.wav")
        expr = (
            "(0.12*sin(2*PI*82.41*t)"
            "+0.08*sin(2*PI*164.81*t)"
            "+0.05*sin(2*PI*246.94*t)"
            "+0.03*sin(2*PI*329.63*t)*(0.5+0.5*sin(2*PI*0.8*t)))"
            "*(0.78+0.22*sin(2*PI*0.27*t))"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"aevalsrc={expr}:s=22050:d={int(duration) + 2}",
            "-af",
            (
                "highpass=f=45,"
                "lowpass=f=3600,"
                "aecho=0.8:0.72:48:0.22,"
                "acompressor=threshold=-20dB:ratio=2.2:attack=25:release=220,"
                "afade=t=in:st=0:d=0.8,"
                f"afade=t=out:st={max(0, int(duration) - 1)}:d=2"
            ),
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            if get_verbose():
                warning(
                    "Psychology ambient music generation failed: "
                    f"{result.stderr.decode(errors='ignore')[:300]}"
                )
            return ""
        if get_verbose():
            info(f"Generated psychology ambient music: {out_path}")
        return out_path

    def _generate_manifestation_music(self, duration: float) -> str:
        out_path = os.path.join(ROOT_DIR, ".mp", f"manifestation_ambient_{uuid4().hex[:6]}.wav")
        expr = (
            "(0.11*sin(2*PI*174.61*t)"
            "+0.08*sin(2*PI*261.63*t)"
            "+0.06*sin(2*PI*392.00*t)"
            "+0.04*sin(2*PI*523.25*t)*(0.55+0.45*sin(2*PI*0.6*t)))"
            "*(0.82+0.18*sin(2*PI*0.18*t))"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"aevalsrc={expr}:s=22050:d={int(duration) + 2}",
            "-af",
            (
                "highpass=f=35,"
                "lowpass=f=4200,"
                "aecho=0.82:0.75:60:0.24,"
                "acompressor=threshold=-22dB:ratio=2.0:attack=20:release=260,"
                "afade=t=in:st=0:d=1.2,"
                f"afade=t=out:st={max(0, int(duration) - 1)}:d=2"
            ),
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            if get_verbose():
                warning(
                    "Manifestation ambient music generation failed: "
                    f"{result.stderr.decode(errors='ignore')[:300]}"
                )
            return ""
        if get_verbose():
            info(f"Generated manifestation ambient music: {out_path}")
        return out_path

    def _build_subtitle_generator(self):
        if self._is_cryptohub_channel():
            subtitle_color = "#FFD54A"
            subtitle_stroke = 6
            subtitle_fontsize = 88
        else:
            subtitle_color = "#FFFFFF" if self._is_finance_channel() else "#FFFF00"
            subtitle_stroke = 7 if self._is_finance_channel() else 5
            subtitle_fontsize = 92 if self._is_finance_channel() else 100

        return lambda txt: TextClip(
            txt,
            font=os.path.join(get_fonts_dir(), get_font()),
            fontsize=subtitle_fontsize,
            color=subtitle_color,
            stroke_color="black",
            stroke_width=subtitle_stroke,
            size=(960, 1720),
            align="center",
            method="caption",
        )

    def _build_finance_headline_clip(self, duration: float):
        headline = self._sanitize_youtube_text(
            getattr(self, "subject", ""),
            limit=110,
            multiline=False,
        ).upper()
        if not headline:
            return None

        headline = headline.replace(" - ", "\n").replace(" — ", "\n")
        if len(headline) > 46 and "\n" not in headline:
            words = headline.split()
            midpoint = max(1, len(words) // 2)
            headline = " ".join(words[:midpoint]) + "\n" + " ".join(words[midpoint:])

        return (
            TextClip(
                headline,
                font=os.path.join(get_fonts_dir(), get_font()),
                fontsize=70 if self._is_cryptohub_channel() else 74,
                color="#FFD54A" if self._is_cryptohub_channel() else "#FFFFFF",
                stroke_color="black",
                stroke_width=3,
                bg_color="#000000",
                kerning=2,
                size=(960, 210),
                align="center",
                method="caption",
            )
            .set_position(("center", 90))
            .set_duration(duration)
            .crossfadein(0.2)
        )

    def _build_brand_logo_clip(self, duration: float):
        logo_path = self._get_brand_logo_path()
        if not logo_path:
            return None
        try:
            clip = (
                ImageClip(logo_path)
                .set_duration(duration)
                .resize(width=260)
                .set_opacity(0.95)
                .set_position(("right", "bottom"))
                .margin(right=36, bottom=52, opacity=0)
            )
            return clip
        except Exception as exc:
            if get_verbose():
                warning(f"Failed to add brand logo overlay: {exc}")
            return None

    def _split_script_segments(self) -> List[str]:
        raw = re.split(r"(?<=[.!?])\s+", str(getattr(self, "script", "") or "").strip())
        segments = []
        for item in raw:
            cleaned = re.sub(r"\s+", " ", item).strip(" .")
            if not cleaned:
                continue
            words = cleaned.split()
            if len(words) > 9:
                midpoint = max(4, len(words) // 2)
                segments.append(" ".join(words[:midpoint]))
                segments.append(" ".join(words[midpoint:]))
            else:
                segments.append(cleaned)
        return segments or [self._sanitize_youtube_text(getattr(self, "subject", ""), limit=90, multiline=False)]

    def _estimate_music_only_duration(self, segments: List[str]) -> float:
        count = max(1, len(segments))
        return float(max(12, min(24, int(round(count * 2.8)))))

    def _build_music_only_text_overlays(self, duration: float):
        segments = self._split_script_segments()
        per_segment = duration / max(1, len(segments))
        clips = []

        for idx, segment in enumerate(segments):
            color = "#FFD54A" if self._is_cryptohub_channel() else "#FFFFFF"
            bg_color = "#000000" if self._is_cryptohub_channel() else None
            clip = (
                TextClip(
                    segment.upper() if self._is_cryptohub_channel() else segment,
                    font=os.path.join(get_fonts_dir(), get_font()),
                    fontsize=84 if self._is_cryptohub_channel() else 88,
                    color=color,
                    stroke_color="black",
                    stroke_width=5,
                    kerning=1 if self._is_cryptohub_channel() else 0,
                    bg_color=bg_color,
                    size=(940, 320),
                    align="center",
                    method="caption",
                )
                .set_start(idx * per_segment)
                .set_duration(per_segment + 0.15)
                .set_position(("center", 1290 if self._is_cryptohub_channel() else 1230))
                .crossfadein(0.12)
            )
            clips.append(clip)

        return clips

    def _persist_image(self, image_bytes: bytes, provider_label: str) -> str:
        """
        Writes generated image bytes to a PNG file in .mp.

        Args:
            image_bytes (bytes): Image payload
            provider_label (str): Label for logging

        Returns:
            path (str): Absolute image path
        """
        image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".png")

        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        if get_verbose():
            info(f' => Wrote image from {provider_label} to "{image_path}"')

        self.images.append(image_path)
        return image_path

    def generate_image_nanobanana2(self, prompt: str) -> str:
        """
        Generates an AI Image using Nano Banana 2 API (Gemini image API).

        Args:
            prompt (str): Prompt for image generation

        Returns:
            path (str): The path to the generated image.
        """
        print(f"Generating Image using Nano Banana 2 API: {prompt}")

        api_key = get_nanobanana2_api_key()
        if not api_key:
            error("nanobanana2_api_key is not configured.")
            return None

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        aspect_ratio = get_nanobanana2_aspect_ratio()

        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }

        try:
            response = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            body = response.json()

            candidates = body.get("candidates", [])
            for candidate in candidates:
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    if not inline_data:
                        continue
                    data = inline_data.get("data")
                    mime_type = inline_data.get("mimeType") or inline_data.get("mime_type", "")
                    if data and str(mime_type).startswith("image/"):
                        image_bytes = base64.b64decode(data)
                        return self._persist_image(image_bytes, "Nano Banana 2 API")

            if get_verbose():
                warning(f"Nano Banana 2 did not return an image payload. Response: {body}")
            return None
        except Exception as e:
            if get_verbose():
                warning(f"Failed to generate image with Nano Banana 2 API: {str(e)}")
            return None

    def generate_image_free(self, prompt: str) -> str:
        import hashlib
        print(f"Generating Image using Picsum (free): {prompt}")
        seed = hashlib.md5(prompt.encode()).hexdigest()[:8]
        url = f"https://picsum.photos/seed/{seed}/1080/1920"
        try:
            response = requests.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return self._persist_image(response.content, "Picsum")
        except Exception as e:
            if get_verbose():
                warning(f"Failed to generate image with Picsum: {str(e)}")
            return None

    def generate_image(self, prompt: str) -> str:
        """
        Generates an AI Image based on the given prompt.
        Tries Nano Banana 2 (Gemini) API first, falls back to Picsum if not configured.

        Args:
            prompt (str): Reference for image generation

        Returns:
            path (str): The path to the generated image.
        """
        # Try AI generation first if API key is configured
        api_key = get_nanobanana2_api_key()
        if api_key:
            result = self.generate_image_nanobanana2(prompt)
            if result:
                return result
            if get_verbose():
                warning("AI image generation failed, falling back to Picsum")
        
        # Fallback to Picsum
        return self.generate_image_free(prompt)

    def generate_script_to_speech(self, tts_instance: TTS) -> str:
        """
        Converts the generated script into Speech using KittenTTS and returns the path to the wav file.

        Args:
            tts_instance (tts): Instance of TTS Class.

        Returns:
            path_to_wav (str): Path to generated audio (WAV Format).
        """
        path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".wav")

        # Clean script, remove every character that is not a word character, a space, a period, a question mark, or an exclamation mark.
        self.script = re.sub(r"[^\w\s.?!]", "", self.script)

        tts_instance.synthesize(self.script, path)

        self.tts_path = path

        if get_verbose():
            info(f' => Wrote TTS to "{path}"')

        return path

    def add_video(self, video: dict) -> None:
        """
        Adds a video to the cache.

        Args:
            video (dict): The video to add

        Returns:
            None
        """
        cache = get_youtube_cache_path()

        if not os.path.exists(cache):
            with open(cache, "w", encoding="utf-8") as file:
                json.dump({"accounts": []}, file, indent=4)

        with open(cache, "r", encoding="utf-8") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json.get("accounts", [])
            found = False
            for account in accounts:
                if account["id"] == self._account_uuid:
                    account.setdefault("videos", []).append(video)
                    found = True
                    break

            if not found:
                accounts.append(
                    {
                        "id": self._account_uuid,
                        "nickname": self._account_nickname,
                        "firefox_profile": self._fp_profile_path,
                        "niche": self._niche,
                        "language": self._language,
                        "videos": [video],
                    }
                )
                previous_json["accounts"] = accounts

            # Commit changes
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(previous_json, f, indent=4)

    def generate_subtitles(self, audio_path: str) -> str:
        """
        Generates subtitles for the audio using the configured STT provider.

        Args:
            audio_path (str): The path to the audio file.

        Returns:
            path (str): The path to the generated SRT File.
        """
        provider = str(get_stt_provider() or "local_whisper").lower()

        if provider == "local_whisper":
            return self.generate_subtitles_local_whisper(audio_path)

        if provider == "third_party_assemblyai":
            return self.generate_subtitles_assemblyai(audio_path)

        warning(f"Unknown stt_provider '{provider}'. Falling back to local_whisper.")
        return self.generate_subtitles_local_whisper(audio_path)

    def generate_subtitles_assemblyai(self, audio_path: str) -> str:
        """
        Generates subtitles using AssemblyAI.

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        try:
            import assemblyai as aai
        except ImportError as exc:
            raise RuntimeError(
                "AssemblyAI subtitles require the 'assemblyai' package to be installed."
            ) from exc

        aai.settings.api_key = get_assemblyai_api_key()
        config = aai.TranscriptionConfig()
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)
        subtitles = transcript.export_subtitles_srt()

        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")

        with open(srt_path, "w") as file:
            file.write(subtitles)

        return srt_path

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Formats a timestamp in seconds to SRT format.

        Args:
            seconds (float): Seconds

        Returns:
            ts (str): HH:MM:SS,mmm
        """
        total_millis = max(0, int(round(seconds * 1000)))
        hours = total_millis // 3600000
        minutes = (total_millis % 3600000) // 60000
        secs = (total_millis % 60000) // 1000
        millis = total_millis % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_subtitles_local_whisper(self, audio_path: str) -> str:
        """
        Generates subtitles using local Whisper (faster-whisper).

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            error(
                "Local STT selected but 'faster-whisper' is not installed. "
                "Install it or switch stt_provider to third_party_assemblyai."
            )
            raise

        model = WhisperModel(
            get_whisper_model(),
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        segments, _ = model.transcribe(audio_path, vad_filter=True)

        lines = []
        for idx, segment in enumerate(segments, start=1):
            start = self._format_srt_timestamp(segment.start)
            end = self._format_srt_timestamp(segment.end)
            text = str(segment.text).strip()

            if not text:
                continue

            lines.append(str(idx))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        subtitles = "\n".join(lines)
        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
        with open(srt_path, "w", encoding="utf-8") as file:
            file.write(subtitles)

        return srt_path

    def combine(self) -> str:
        """
        Combines everything into the final video.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        combined_image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")
        threads = get_threads()
        music_only = self._is_music_only_channel()
        tts_clip = None if music_only else AudioFileClip(self.tts_path)
        max_duration = self._estimate_music_only_duration(self._split_script_segments()) if music_only else tts_clip.duration
        req_dur = max_duration / len(self.images)

        generator = self._build_subtitle_generator()

        print(colored("[+] Combining images...", "blue"))

        clips = []
        tot_dur = 0
        # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
        while tot_dur < max_duration:
            for image_path in self.images:
                clip = ImageClip(image_path)
                clip.duration = req_dur
                clip = clip.set_fps(30)

                # Not all images are same size,
                # so we need to resize them
                if round((clip.w / clip.h), 4) < 0.5625:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1080x1920")
                    clip = mpy_crop(
                        clip,
                        width=clip.w,
                        height=round(clip.w / 0.5625),
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                else:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1920x1080")
                    clip = mpy_crop(
                        clip,
                        width=round(0.5625 * clip.h),
                        height=clip.h,
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                clip = clip.resize((1080, 1920))

                if self._is_cryptohub_channel():
                    clip = clip.fx(vfx.lum_contrast, lum=-6, contrast=22, contrast_thr=118)
                    clip = clip.fadein(0.12).fadeout(0.12)
                elif self._is_finance_channel():
                    clip = clip.fx(vfx.blackwhite)
                    clip = clip.fx(vfx.lum_contrast, lum=0, contrast=28, contrast_thr=110)
                    clip = clip.fadein(0.15).fadeout(0.15)

                # FX (Fade In)
                # clip = clip.fadein(2)

                clips.append(clip)
                tot_dur += clip.duration

        final_clip = concatenate_videoclips(clips)
        final_clip = final_clip.set_fps(30)
        random_song = choose_random_song()
        generated_music = ""
        if not random_song:
            if self._is_cryptohub_channel() or self._is_finance_channel():
                generated_music = self._generate_finance_music(max_duration)
            elif self._is_psychology_channel():
                generated_music = self._generate_psychology_music(max_duration)
            elif self._is_manifestation_channel():
                generated_music = self._generate_manifestation_music(max_duration)

        subtitles = None
        if not music_only:
            try:
                subtitles_path = self.generate_subtitles(self.tts_path)
                equalize_subtitles(subtitles_path, 10)
                subtitles = SubtitlesClip(subtitles_path, generator)
                subtitles.set_pos(("center", "center"))
            except Exception as e:
                warning(f"Failed to generate subtitles, continuing without subtitles: {e}")

        music_path = random_song or generated_music
        if music_only:
            if music_path:
                music_clip = AudioFileClip(music_path).set_fps(44100)
                if music_clip.duration < max_duration:
                    music_clip = afx.audio_loop(music_clip, duration=max_duration)
                else:
                    music_clip = music_clip.subclip(0, max_duration)
                comp_audio = music_clip.fx(afx.volumex, 0.22 if random_song else 0.20)
            else:
                comp_audio = AudioClip(lambda t: 0, duration=max_duration, fps=44100)
        elif music_path:
            random_song_clip = AudioFileClip(music_path).set_fps(44100)
            random_song_clip = random_song_clip.fx(afx.volumex, 0.1 if random_song else 0.16)
            comp_audio = CompositeAudioClip([tts_clip.set_fps(44100), random_song_clip])
        else:
            comp_audio = tts_clip.set_fps(44100)

        final_clip = final_clip.set_audio(comp_audio)
        final_clip = final_clip.set_duration(max_duration)

        if subtitles is not None:
            subtitles = subtitles.set_position(("center", "center"))

        if self._is_finance_channel() or self._is_cryptohub_channel():
            overlays = [final_clip]
            if self._is_cryptohub_channel():
                overlays.append(
                    ColorClip(size=(1080, 1920), color=(0, 0, 0))
                    .set_opacity(0.12)
                    .set_duration(max_duration)
                )
            headline_clip = self._build_finance_headline_clip(max_duration)
            if headline_clip is not None:
                overlays.append(headline_clip)
            brand_logo = self._build_brand_logo_clip(max_duration)
            if brand_logo is not None:
                overlays.append(brand_logo)
            if music_only:
                overlays.extend(self._build_music_only_text_overlays(max_duration))
            if subtitles is not None:
                overlays.append(subtitles)
            final_clip = CompositeVideoClip(overlays, size=(1080, 1920))
        elif subtitles is not None:
            final_clip = CompositeVideoClip([final_clip, subtitles])

        final_clip.write_videofile(combined_image_path, threads=threads)

        success(f'Wrote Video to "{combined_image_path}"')

        # Stable path for downstream automations (Instagram, artifacts, etc.)
        try:
            stable_path = os.path.join(ROOT_DIR, ".mp", "last_short.mp4")
            try:
                if os.path.exists(stable_path):
                    os.remove(stable_path)
            except Exception:
                pass
            # Copy rather than rename so the random UUID file remains for debugging.
            import shutil

            shutil.copyfile(combined_image_path, stable_path)
            with open(os.path.join(ROOT_DIR, ".mp", "last_short_path.txt"), "w", encoding="utf-8") as f:
                f.write(os.path.abspath(stable_path))
            if get_verbose():
                info(f"Saved stable short path: {stable_path}")
        except Exception as _se:
            if get_verbose():
                warning(f"Failed to write stable short marker file: {_se}")

        return combined_image_path

    def generate_video(self, tts_instance: TTS) -> str:
        """
        Generates a YouTube Short based on the provided niche and language.

        Args:
            tts_instance (TTS): Instance of TTS Class.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        try:
            # Generate the Topic (skip if subject already set via set_subject())
            if not hasattr(self, 'subject') or not self.subject:
                self.generate_topic()

            # Fail fast if YouTube token is invalid/missing upload scope, so we don't waste time rendering.
            try:
                from utils import preflight_youtube_api

                creds = self._get_yt_credentials()
                preflight_youtube_api(creds, verbose=get_verbose())
            except Exception as e:
                # Keep error concise for GitHub Actions logs.
                raise RuntimeError(str(e)) from e

            # Generate the Script
            self.generate_script()

            # Optional: auto-generate + publish a companion eBook (Gumroad) for this video.
            # This runs BEFORE metadata so the Gumroad link can be injected into the description.
            auto_ebook = str(os.environ.get("YOUTUBE_AUTO_EBOOK", "")).strip().lower() in ("1", "true", "yes")
            if auto_ebook:
                require_ebook = str(os.environ.get("YOUTUBE_REQUIRE_EBOOK", "true")).strip().lower() in ("1", "true", "yes")
                from config import get_gumroad_access_token
                from classes.EBook import EBook

                gumroad_ok = bool(
                    (os.environ.get("GUMROAD_ACCESS_TOKEN", "").strip())
                    or (os.environ.get("GUMROAD_SESSION_JSON", "").strip())
                    or (
                        os.environ.get("GUMROAD_EMAIL", "").strip()
                        and os.environ.get("GUMROAD_PASSWORD", "").strip()
                    )
                    or (get_gumroad_access_token() or "").strip()
                )
                if not gumroad_ok:
                    msg = (
                        "YOUTUBE_AUTO_EBOOK is enabled but no Gumroad credentials were found. "
                        "Set `GUMROAD_ACCESS_TOKEN` (recommended) or `GUMROAD_SESSION_JSON` "
                        "or `GUMROAD_EMAIL`+`GUMROAD_PASSWORD`."
                    )
                    if require_ebook:
                        raise RuntimeError(msg)
                    warning(msg)
                    auto_ebook = False

            if auto_ebook:
                keys = ["EBOOK_TOPIC", "EBOOK_CONTEXT", "EBOOK_SKIP_KDP", "EBOOK_SKIP_PRINT"]
                prev = {k: os.environ.get(k) for k in keys}
                try:
                    os.environ["EBOOK_TOPIC"] = self.subject
                    os.environ["EBOOK_CONTEXT"] = (self.script or "")[:5000]
                    os.environ.setdefault("EBOOK_SKIP_KDP", "1")
                    os.environ.setdefault("EBOOK_SKIP_PRINT", "1")

                    eb = EBook()
                    result = eb.run()
                    if not result.get("gumroad_url"):
                        msg = "Companion eBook publish failed (no Gumroad URL). Check `.mp/gumroad_*` debug files and your Gumroad token/settings."
                        if require_ebook:
                            raise RuntimeError(msg)
                        warning(msg)
                finally:
                    for k, v in prev.items():
                        if v is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = v

            # Generate the Metadata
            self.generate_metadata()

            # Generate the Image Prompts
            self.generate_prompts()

            # Generate the Images
            for prompt in self.image_prompts:
                self.generate_image(prompt)

            # Generate TTS for voice-led channels only. CryptoHub and MoneyMarkettt
            # are intentionally rendered as text + music Shorts.
            if not self._is_music_only_channel():
                self.generate_script_to_speech(tts_instance)

            # Combine everything
            path = self.combine()

            if get_verbose():
                info(f" => Generated Video: {path}")

            self.video_path = os.path.abspath(path)

            return path
            
        except Exception as e:
            error(f"Video generation failed: {e}")
            if get_verbose():
                import traceback
                traceback.print_exc()
            raise

    @staticmethod
    def _get_yt_credentials():
        import json
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        required_scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        token_json = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()

        token_info = None
        if token_json:
            token_info = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_info)
        else:
            token_path = os.path.join(ROOT_DIR, "token.json")
            if not os.path.exists(token_path):
                raise FileNotFoundError(
                    "token.json not found. Run scripts/setup_youtube_auth.py first."
                )
            with open(token_path, "r", encoding="utf-8") as f:
                token_info = json.loads(f.read())
            creds = Credentials.from_authorized_user_file(token_path)

        if not getattr(creds, "scopes", None) and isinstance(token_info, dict):
            raw_scopes = token_info.get("scopes") or token_info.get("scope")
            if isinstance(raw_scopes, str):
                creds.scopes = [s for s in raw_scopes.split() if s]
            elif isinstance(raw_scopes, list):
                creds.scopes = [str(s) for s in raw_scopes if str(s).strip()]

        # Ensure scopes are set
        if not getattr(creds, "scopes", None):
            creds.scopes = required_scopes

        if creds.expired and creds.refresh_token:
            try:
                if get_verbose():
                    info("Refreshing YouTube OAuth token...")
                creds.refresh(Request())
            except Exception as refresh_error:
                if get_verbose():
                    warning(f"Token refresh failed: {refresh_error}")

        return creds

    def upload_video(self) -> bool:
        """
        Uploads the video to YouTube via Data API v3.

        Returns:
            success (bool): Whether the upload was successful or not.
        """
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
        from utils import format_youtube_http_error

        try:
            if not getattr(self, "video_path", None):
                raise RuntimeError("No rendered video found. Run generate_video() before upload.")
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Rendered video not found: {self.video_path}")
            if not getattr(self, "metadata", None):
                if not getattr(self, "subject", None):
                    raise RuntimeError("Video subject is missing, so metadata cannot be generated.")
                if not getattr(self, "script", None):
                    self.script = getattr(self, "subject", "")
                self.generate_metadata()

            creds = self._get_yt_credentials()
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
            verbose = get_verbose()
            title = self._sanitize_youtube_text(
                self.metadata.get("title", self.subject),
                limit=100,
                multiline=False,
            )
            description = self._sanitize_youtube_text(
                self.metadata.get("description", ""),
                limit=5000,
                multiline=True,
            )

            body = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": self.metadata.get("tags", []),
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": get_is_for_kids(),
                },
            }

            media = MediaFileUpload(self.video_path, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            if verbose:
                info("Uploading Short to YouTube...")
            response = run_youtube_resumable_upload(
                request,
                verbose=verbose,
                label="Short",
            )

            video_id = response["id"]
            url = build_url(video_id)
            self.uploaded_video_url = url

            if verbose:
                success(f"Short uploaded: {url}")

            self.add_video(
                {
                    "subject": self.subject,
                    "title": title,
                    "description": description,
                    "url": url,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            return True

        except HttpError as e:
            warning(format_youtube_http_error(e))
            if get_verbose():
                import traceback
                traceback.print_exc()
            return False
        except Exception as e:
            import traceback
            warning(f"Short upload error: {e}")
            traceback.print_exc()
            return False

    def get_videos(self) -> List[dict]:
        """
        Gets the uploaded videos from the YouTube Channel.

        Returns:
            videos (List[dict]): The uploaded videos.
        """
        cache_path = get_youtube_cache_path()
        if not os.path.exists(cache_path):
            # Create the cache file
            with open(cache_path, "w", encoding="utf-8") as file:
                json.dump({"accounts": []}, file, indent=4)
            return []

        videos = []
        # Read the cache file
        with open(cache_path, "r", encoding="utf-8") as file:
            previous_json = json.loads(file.read())
            # Find our account
            accounts = previous_json.get("accounts", [])
            for account in accounts:
                if account["id"] == self._account_uuid:
                    videos = account.get("videos", [])

        return videos
