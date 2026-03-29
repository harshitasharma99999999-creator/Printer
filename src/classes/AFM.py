import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from typing import Any

from status import *
from config import *
from constants import *
from llm_provider import generate_text


class AffiliateMarketing:
    """
    Handles affiliate marketing — scrapes Amazon product info and generates pitch content.
    Uses requests (no browser) for scraping to avoid Firefox profile lock issues.
    """

    def __init__(
        self,
        affiliate_link: str,
        fp_profile_path: str = None,
        twitter_account_uuid: str = None,
        account_nickname: str = None,
        topic: str = None,
    ) -> None:
        self.affiliate_link: str = affiliate_link

        parsed_link = urlparse(self.affiliate_link)
        if parsed_link.scheme not in ["http", "https"] or not parsed_link.netloc:
            raise ValueError(
                f"Affiliate link is invalid. Expected a full URL, got: {self.affiliate_link}"
            )

        self.account_uuid: str = twitter_account_uuid
        self.account_nickname: str = account_nickname
        self.topic: str = topic

        self.scrape_product_information()

    def scrape_product_information(self) -> None:
        """
        Scrapes product info using requests + BeautifulSoup.
        Handles category/browse pages by finding a specific product link.
        No browser required — avoids Firefox profile lock issues entirely.
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        try:
            r = requests.get(self.affiliate_link, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            # Find product links on category/browse pages
            product_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/dp/" in href and href.startswith("/"):
                    clean = "https://www.amazon.in" + href.split("?")[0]
                    if clean not in product_links:
                        product_links.append(clean)

            if product_links:
                chosen_url = random.choice(product_links[:10])
                chosen_url += "?tag=harshita000-21"
                self.affiliate_link = chosen_url
                if get_verbose():
                    info(f" => Picked product: {chosen_url}")
                r = requests.get(chosen_url, headers=headers, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")

            title_el = soup.find(id="productTitle")
            self.product_title: str = title_el.get_text().strip() if title_el else "Wellness & Self-Care Product"
            self.features: Any = []

            if get_verbose():
                info(f"Product Title: {self.product_title}")

        except Exception as e:
            if get_verbose():
                warning(f"Failed to scrape product: {e}")
            self.product_title = "Wellness & Self-Care Product"
            self.features = []

    def generate_response(self, prompt: str) -> str:
        return generate_text(prompt)

    def generate_pitch(self) -> str:
        """Generates a concise Twitter-friendly pitch with hashtags."""
        pitch_text = self.generate_response(
            f'Write a single punchy Twitter post (under 200 characters) promoting this Amazon product. '
            f'Include 2-3 relevant hashtags. Return only the tweet text, nothing else.\n'
            f'Product: "{self.product_title}"'
        )
        pitch = pitch_text.strip() + "\n" + self.affiliate_link
        self.pitch: str = pitch
        return pitch

    def quit(self) -> None:
        pass  # No browser to close
