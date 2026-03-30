import json
import os
import re
import shutil
import subprocess
import tempfile

import requests

from config import ROOT_DIR, get_verbose
from llm_provider import generate_text
from status import error, info, success, warning

RESEARCH_SUBREDDITS = [
    "SaaS", "microsaas", "entrepreneur", "startups",
    "productivity", "nocode", "Entrepreneur", "indiehackers",
]

DEMAND_KEYWORDS = [
    "looking for", "i wish", "is there a tool", "does anyone know",
    "app that can", "tool that", "i need a way", "how do i automate",
    "would pay for", "would love a tool", "can't find", "anyone built",
]


class WebAppBuilder:
    def __init__(self):
        self.template_dir = os.path.join(ROOT_DIR, "webapp_template")

    def research_niche(self) -> list:
        posts = []
        headers = {"User-Agent": "Mozilla/5.0 (compatible; WebAppBot/1.0)"}

        for sub in RESEARCH_SUBREDDITS:
            try:
                url = f"https://www.reddit.com/r/{sub}/new.json?limit=100"
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code != 200:
                    continue
                for child in r.json()["data"]["children"]:
                    p = child["data"]
                    text = (p["title"] + " " + p.get("selftext", "")).lower()
                    if any(kw in text for kw in DEMAND_KEYWORDS):
                        posts.append({
                            "title": p["title"],
                            "body": p.get("selftext", "")[:300],
                            "subreddit": sub,
                            "upvotes": p.get("score", 0),
                            "permalink": p.get("permalink", ""),
                        })
            except Exception as e:
                if get_verbose():
                    warning(f"Reddit scrape failed for r/{sub}: {e}")

        posts.sort(key=lambda x: x["upvotes"], reverse=True)
        if get_verbose():
            info(f"Found {len(posts)} demand signals from Reddit")
        return posts[:20]

    def generate_config(self, demand_posts: list) -> dict:
        posts_text = "\n".join(
            f'- [r/{p["subreddit"]}] {p["title"]}' for p in demand_posts[:15]
        )

        prompt = f"""You are a startup founder analyzing Reddit posts to find the best SaaS opportunity.

Reddit demand signals (people asking for tools/apps):
{posts_text}

Pick the SINGLE BEST niche and design a simple SaaS MVP landing page.
Return ONLY a valid JSON object, no markdown, no explanation:
{{
  "app_name": "2-3 word product name",
  "app_slug": "lowercase-hyphenated",
  "tagline": "One punchy value proposition under 10 words",
  "description": "What the app does in 2 sentences. Be specific about the problem it solves.",
  "features": [
    {{"name": "Feature One", "desc": "Short benefit statement, 1 sentence"}},
    {{"name": "Feature Two", "desc": "Short benefit statement, 1 sentence"}},
    {{"name": "Feature Three", "desc": "Short benefit statement, 1 sentence"}}
  ],
  "price_monthly": 9,
  "price_yearly": 79,
  "target_subreddit": "best subreddit to post launch announcement",
  "reddit_post_title": "Show HN style launch post title",
  "reddit_post_body": "2-3 paragraph post: describe the problem, the solution, and invite feedback. Include a call to action."
}}"""

        response = generate_text(prompt)
        response = response.replace("```json", "").replace("```", "").strip()

        try:
            config = json.loads(response)
        except Exception:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if match:
                config = json.loads(match.group())
            else:
                raise ValueError(f"Could not parse LLM config: {response[:300]}")

        # Sanitize app_slug and append today's date so daily runs don't collide
        from datetime import datetime
        slug = re.sub(r"[^a-z0-9-]", "-", config["app_slug"].lower())
        slug = re.sub(r"-+", "-", slug).strip("-")[:32]
        slug = slug or "my-saas-app"
        date_suffix = datetime.now().strftime("%m%d")
        config["app_slug"] = f"{slug}-{date_suffix}"

        if get_verbose():
            info(f"App config: {config['app_name']} — {config['tagline']}")
        return config

    def build_app(self, config: dict) -> str:
        work_dir = os.path.join(tempfile.gettempdir(), f"webapp-{config['app_slug']}")
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        shutil.copytree(self.template_dir, work_dir)

        features = config.get("features", [])
        while len(features) < 3:
            features.append({"name": "Feature", "desc": "Coming soon"})

        replacements = {
            "__APP_NAME__": config["app_name"],
            "__APP_SLUG__": config["app_slug"],
            "__TAGLINE__": config["tagline"],
            "__DESCRIPTION__": config["description"],
            "__FEATURE_1_NAME__": features[0]["name"],
            "__FEATURE_1_DESC__": features[0]["desc"],
            "__FEATURE_2_NAME__": features[1]["name"],
            "__FEATURE_2_DESC__": features[1]["desc"],
            "__FEATURE_3_NAME__": features[2]["name"],
            "__FEATURE_3_DESC__": features[2]["desc"],
            "__PRICE_MONTHLY__": str(int(config.get("price_monthly", 9))),
            "__PRICE_YEARLY__": str(int(config.get("price_yearly", 79))),
        }

        for root, _, files in os.walk(work_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    for placeholder, value in replacements.items():
                        content = content.replace(placeholder, value)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
                except (UnicodeDecodeError, PermissionError):
                    pass

        if get_verbose():
            info(f"App built at {work_dir}")
        return work_dir

    def set_vercel_env_vars(self, project_slug: str, env_vars: dict):
        token = os.environ.get("VERCEL_TOKEN", "")
        if not token:
            return

        for key, value in env_vars.items():
            if not value:
                continue
            try:
                r = requests.post(
                    f"https://api.vercel.com/v10/projects/{project_slug}/env",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "key": key,
                        "value": value,
                        "type": "encrypted",
                        "target": ["production", "preview"],
                    },
                    timeout=15,
                )
                if get_verbose():
                    info(f"Set Vercel env {key}: {r.status_code}")
            except Exception as e:
                warning(f"Failed to set Vercel env {key}: {e}")

    def deploy(self, app_dir: str, config: dict) -> str:
        vercel_token = os.environ.get("VERCEL_TOKEN", "")
        if not vercel_token:
            raise ValueError("VERCEL_TOKEN env var not set")

        slug = config["app_slug"]

        cmd = [
            "vercel",
            "--token", vercel_token,
            "--yes",
            "--prod",
            "--name", slug,
        ]

        if get_verbose():
            info(f"Deploying {config['app_name']} to Vercel...")

        result = subprocess.run(
            cmd,
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )

        output = result.stdout + result.stderr
        if get_verbose():
            print(output[-3000:])

        match = re.search(r"https://[\w.-]+\.vercel\.app", output)
        deploy_url = match.group() if match else None

        if result.returncode != 0 and not deploy_url:
            raise RuntimeError(f"Vercel deploy failed:\n{output[-1000:]}")

        # Set env vars via Vercel API so they persist for all future deployments
        dodo_api_key = os.environ.get("DODO_API_KEY", "")
        dodo_product_id = os.environ.get("DODO_PRODUCT_ID", "")
        base_url = deploy_url or f"https://{slug}.vercel.app"

        self.set_vercel_env_vars(slug, {
            "DODO_API_KEY": dodo_api_key,
            "DODO_PRODUCT_ID": dodo_product_id,
            "NEXT_PUBLIC_BASE_URL": base_url,
        })

        success(f"Deployed to {base_url}")
        return base_url

    def print_marketing_plan(self, config: dict, url: str):
        print("\n" + "=" * 60)
        print("MARKETING PLAN — POST THIS AFTER LAUNCH")
        print("=" * 60)
        print(f"\n   Target: r/{config.get('target_subreddit', 'entrepreneur')}")
        print(f"   URL: {url}")
        print(f"\n TITLE:\n{config.get('reddit_post_title', '')}")
        print(f"\n BODY:\n{config.get('reddit_post_body', '')}")
        print(f"\n   Direct app link: {url}")
        print("=" * 60 + "\n")

    def run(self):
        if get_verbose():
            info("=== WebApp Builder starting ===")

        demand_posts = self.research_niche()
        if not demand_posts:
            warning("No Reddit demand signals found, using fallback topic.")
            demand_posts = [{
                "title": "I wish there was a simple tool to automate repetitive tasks",
                "subreddit": "SaaS", "upvotes": 0, "body": "",
            }]

        config = self.generate_config(demand_posts)
        app_dir = self.build_app(config)
        url = self.deploy(app_dir, config)
        self.print_marketing_plan(config, url)

        success(f"Done! App live at: {url}")
        return url
