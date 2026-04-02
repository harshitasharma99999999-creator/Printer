import os
import re
import json
import time
import requests
from uuid import uuid4

from llm_provider import generate_text
from config import ROOT_DIR, get_groq_api_key, get_verbose, get_nanobanana2_api_key
from status import info, warning, success, error

NICHES = [
    "phone accessories",
    "home gadgets",
    "fitness tools",
    "desk accessories",
    "pet products",
    "kitchen tools",
]


class Dropshipping:
    """
    24/7 free dropshipping automation.
    Sources products from AliExpress (free scraping), creates product showcase videos,
    posts to Instagram/Twitter, and lists on Gumroad.
    Zero upfront cost — Gumroad 10% fee only on sales.
    """

    def __init__(self):
        self.niche = self._pick_niche()
        self.products = []

    def _pick_niche(self) -> str:
        """LLM picks today's trending niche from the rotation list."""
        prompt = (
            f"Pick ONE niche from this list that is most trending right now for online shopping: "
            f"{', '.join(NICHES)}.\n"
            f"Return ONLY the niche name, nothing else."
        )
        result = generate_text(prompt).strip().lower()
        for n in NICHES:
            if n in result:
                return n
        return NICHES[int(time.time()) % len(NICHES)]

    def research_products(self) -> list:
        """
        Scrape AliExpress bestsellers in the chosen niche.
        Returns list of dicts: {title, price, image_url, aliexpress_url}
        """
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        search_query = self.niche.replace(" ", "+")
        url = (
            f"https://www.aliexpress.com/wholesale"
            f"?SearchText={search_query}&SortType=total_tranRanking_desc"
        )

        products = []
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract product data embedded in page JSON (AliExpress embeds mods data)
            scripts = soup.find_all("script")
            raw_json = None
            for s in scripts:
                if s.string and "window._dida_config_" in s.string:
                    raw_json = s.string
                    break

            if raw_json:
                # Extract items array from embedded JSON
                match = re.search(r'"items"\s*:\s*(\[.*?\])\s*[,}]', raw_json, re.DOTALL)
                if match:
                    items = json.loads(match.group(1))
                    for item in items[:6]:
                        title = item.get("title", {}).get("displayTitle", "")
                        price_raw = item.get("prices", {}).get("salePrice", {}).get("minPrice", "0")
                        image = item.get("image", {}).get("imgUrl", "")
                        product_id = item.get("productId", "")
                        if title and product_id:
                            products.append({
                                "title": title,
                                "price": float(str(price_raw).replace(",", "")),
                                "image_url": f"https:{image}" if image.startswith("//") else image,
                                "aliexpress_url": f"https://www.aliexpress.com/item/{product_id}.html",
                            })

            # Fallback: parse visible product cards
            if not products:
                cards = soup.select("a[href*='/item/']")
                seen = set()
                for card in cards[:6]:
                    href = card.get("href", "")
                    m = re.search(r"/item/(\d+)\.html", href)
                    if not m:
                        continue
                    pid = m.group(1)
                    if pid in seen:
                        continue
                    seen.add(pid)
                    title_el = card.find(string=True, recursive=True)
                    title = str(title_el).strip() if title_el else f"Product {pid}"
                    img_el = card.find("img")
                    img_src = img_el.get("src", "") if img_el else ""
                    if img_src.startswith("//"):
                        img_src = "https:" + img_src
                    products.append({
                        "title": title[:120],
                        "price": 0.0,
                        "image_url": img_src,
                        "aliexpress_url": f"https://www.aliexpress.com/item/{pid}.html",
                    })

        except Exception as e:
            if get_verbose():
                warning(f"Dropshipping: AliExpress scrape failed ({e}), using fallback products.")

        # If scraping totally failed, generate fictional product from LLM
        if not products:
            prompt = (
                f"Generate 3 trending {self.niche} products available on AliExpress.\n"
                f"Return a JSON array with fields: title, price (USD float), aliexpress_url (example URL).\n"
                f"Example: [{{'title':'...','price':4.99,'aliexpress_url':'https://www.aliexpress.com/item/123.html'}}]\n"
                f"Return ONLY the JSON array, nothing else."
            )
            try:
                raw = generate_text(prompt).strip()
                raw = re.sub(r"```[a-z]*", "", raw).strip("`").strip()
                llm_products = json.loads(raw)
                for p in llm_products:
                    p.setdefault("image_url", "")
                    products.append(p)
            except Exception as e2:
                if get_verbose():
                    warning(f"Dropshipping: LLM fallback also failed ({e2}).")

        self.products = products[:3]  # process max 3 products per run
        return self.products

    def generate_product_content(self, product: dict) -> dict:
        """
        LLM generates: selling title, description, 5 bullet benefits, markup price.
        Returns updated product dict.
        """
        ali_price = product.get("price", 0) or 0
        # 2-3x markup
        sell_price = round(max(ali_price * 2.5, 9.99), 2)

        prompt = (
            f"You are a high-converting e-commerce copywriter.\n"
            f"Product: {product['title']}\n"
            f"Niche: {self.niche}\n\n"
            f"Return a JSON object with these exact fields:\n"
            f"  title: Compelling product title (under 80 chars, keyword-first)\n"
            f"  description: 2-sentence persuasive product description\n"
            f"  bullets: Array of exactly 5 short benefit bullet points\n"
            f"  price: {sell_price}\n"
            f"  caption: Instagram caption with 5 relevant hashtags (no line breaks)\n"
            f"Return ONLY valid JSON, nothing else."
        )

        try:
            raw = generate_text(prompt).strip()
            raw = re.sub(r"```[a-z]*", "", raw).strip("`").strip()
            content = json.loads(raw)
        except Exception as e:
            if get_verbose():
                warning(f"Dropshipping: content generation failed ({e}), using defaults.")
            content = {
                "title": product["title"][:80],
                "description": f"Premium {self.niche} product. High quality, fast shipping worldwide.",
                "bullets": [
                    "Premium quality materials",
                    "Fast worldwide shipping",
                    "100% satisfaction guarantee",
                    "Lightweight and portable",
                    "Perfect gift idea",
                ],
                "price": sell_price,
                "caption": f"Amazing {self.niche} product! Shop now 🔥 #{self.niche.replace(' ', '')} #aliexpress #deals #shopping #trending",
            }

        product.update(content)
        return product

    def create_product_video(self, product: dict) -> str:
        """
        Generate a 30-second product showcase Short using the existing YouTube pipeline.
        Returns path to mp4.
        """
        from .YouTube import YouTube
        from .Tts import TTS

        subject = (
            f"{product['title']} — {product.get('description', '')} "
            f"Get yours now at {product.get('aliexpress_url', '')}."
        )

        yt = YouTube(
            account_uuid=str(uuid4()),
            account_nickname="dropshipping",
            fp_profile_path="",
            niche=self.niche,
            language="english",
        )
        yt.set_subject(subject)

        tts = TTS()
        path = yt.generate_video(tts)
        if get_verbose():
            info(f"Dropshipping: product video generated at {path}")
        return path

    def post_to_social(self, video_path: str, product: dict) -> None:
        """Post product video to Instagram Reels and Twitter."""
        caption = product.get("caption", f"New {self.niche} deal! #{self.niche.replace(' ','')}")
        link = product.get("aliexpress_url", "")
        tweet_text = f"{product.get('title','')[:100]} — {link} #{self.niche.replace(' ','')} #deals"

        # Instagram
        ig_user = os.environ.get("INSTAGRAM_USERNAME", "").strip()
        ig_pass = os.environ.get("INSTAGRAM_PASSWORD", "").strip()
        if ig_user and ig_pass:
            try:
                from .Instagram import Instagram
                ig = Instagram(ig_user, ig_pass)
                reel_url = ig.upload_reel(video_path, caption)
                if get_verbose():
                    success(f"Dropshipping: Instagram reel posted → {reel_url}")
            except Exception as e:
                if get_verbose():
                    warning(f"Dropshipping: Instagram post failed ({e}).")
        else:
            if get_verbose():
                warning("Dropshipping: INSTAGRAM_USERNAME/PASSWORD not set, skipping Instagram.")

        # Twitter
        tw_key = os.environ.get("TWITTER_API_KEY", "").strip()
        tw_secret = os.environ.get("TWITTER_API_SECRET", "").strip()
        tw_token = os.environ.get("TWITTER_ACCESS_TOKEN", "").strip()
        tw_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "").strip()
        if tw_key and tw_secret and tw_token and tw_token_secret:
            try:
                import tweepy
                client = tweepy.Client(
                    consumer_key=tw_key,
                    consumer_secret=tw_secret,
                    access_token=tw_token,
                    access_token_secret=tw_token_secret,
                )
                client.create_tweet(text=tweet_text[:280])
                if get_verbose():
                    success("Dropshipping: Twitter post sent.")
            except Exception as e:
                if get_verbose():
                    warning(f"Dropshipping: Twitter post failed ({e}).")
        else:
            if get_verbose():
                warning("Dropshipping: Twitter secrets not set, skipping Twitter.")

    def list_on_gumroad(self, product: dict) -> str:
        """
        Create a Gumroad listing for the product (as a digital pre-order / info card).
        Returns the Gumroad product URL.
        """
        access_token = os.environ.get("GUMROAD_ACCESS_TOKEN", "").strip()
        if not access_token:
            if get_verbose():
                warning("Dropshipping: GUMROAD_ACCESS_TOKEN not set, skipping Gumroad.")
            return ""

        base = "https://api.gumroad.com/v2"
        title = product.get("title", "")[:100]
        bullets = "\n".join(f"• {b}" for b in product.get("bullets", []))
        description = (
            f"{product.get('description', '')}\n\n"
            f"What you get:\n{bullets}\n\n"
            f"Source: {product.get('aliexpress_url', '')}"
        )
        price_cents = int(float(product.get("price", 9.99)) * 100)

        try:
            r = requests.post(f"{base}/products", data={
                "access_token": access_token,
                "name": title,
                "price": price_cents,
                "description": description[:2000],
            }, timeout=20)

            if not r.ok:
                if get_verbose():
                    warning(f"Dropshipping: Gumroad create failed: {r.status_code} {r.text[:200]}")
                return ""

            product_data = r.json().get("product", {})
            product_id = product_data.get("id", "")
            product_url = product_data.get("short_url", f"https://app.gumroad.com/products/{product_id}")

            # Publish immediately
            requests.put(f"{base}/products/{product_id}", data={
                "access_token": access_token,
                "published": "true",
            }, timeout=15)

            if get_verbose():
                success(f"Dropshipping: Gumroad listing live → {product_url}")
            return product_url

        except Exception as e:
            if get_verbose():
                warning(f"Dropshipping: Gumroad listing failed ({e}).")
            return ""

    def run(self) -> None:
        """Full dropshipping pipeline: research → content → video → social → Gumroad."""
        if get_verbose():
            info(f"Dropshipping: starting pipeline for niche '{self.niche}'")

        products = self.research_products()
        if not products:
            error("Dropshipping: no products found, aborting.")
            return

        for product in products:
            if get_verbose():
                info(f"Dropshipping: processing product '{product.get('title', '')[:60]}'")

            # Generate copy
            product = self.generate_product_content(product)

            # Create video
            try:
                video_path = self.create_product_video(product)
            except Exception as e:
                if get_verbose():
                    warning(f"Dropshipping: video generation failed ({e}), skipping social post.")
                video_path = None

            # Post to social
            if video_path and os.path.exists(video_path):
                try:
                    self.post_to_social(video_path, product)
                except Exception as e:
                    if get_verbose():
                        warning(f"Dropshipping: social posting failed ({e}).")

            # List on Gumroad
            try:
                gumroad_url = self.list_on_gumroad(product)
                if gumroad_url:
                    product["gumroad_url"] = gumroad_url
            except Exception as e:
                if get_verbose():
                    warning(f"Dropshipping: Gumroad listing failed ({e}).")

            if get_verbose():
                info(f"Dropshipping: product done → {product.get('title', '')[:60]}")

        if get_verbose():
            success(f"Dropshipping: pipeline complete — processed {len(products)} product(s).")
