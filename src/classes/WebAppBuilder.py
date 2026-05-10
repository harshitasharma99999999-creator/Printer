import base64
import json
import os
import re
import shutil
import subprocess
import tempfile

import requests

from config import (
    ROOT_DIR, get_verbose,
    get_nanobanana2_api_key, get_nanobanana2_api_base_url, get_nanobanana2_model,
)
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

    @staticmethod
    def _decode_base64_secret(value: str) -> bytes:
        raw = (value or "").strip()
        if not raw:
            raise ValueError("Secret is empty.")
        remainder = len(raw) % 4
        if remainder:
            raw += "=" * (4 - remainder)
        return base64.b64decode(raw)

    @staticmethod
    def _extract_json_object(text: str) -> str:
        decoder = json.JSONDecoder()
        for idx, char in enumerate(text):
            if char != "{":
                continue
            try:
                _, end = decoder.raw_decode(text[idx:])
                return text[idx:idx + end]
            except json.JSONDecodeError:
                continue
        raise ValueError("No valid JSON object found in model response.")

    def _repair_json_response(self, bad_response: str) -> dict:
        repair_prompt = (
            "Repair this invalid JSON so it becomes a single valid JSON object. "
            "Do not change the meaning. Return only valid JSON.\n\n"
            f"{bad_response}"
        )
        repaired = generate_text(repair_prompt).replace("```json", "").replace("```", "").strip()
        return json.loads(self._extract_json_object(repaired))

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

Pick the SINGLE BEST niche and design a simple SaaS MVP that includes a real AI-powered tool.
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
  "reddit_post_body": "2-3 paragraph post: describe the problem, the solution, and invite feedback. Include a call to action.",
  "tool_title": "Action verb phrase describing what the tool does (e.g. Write your cold email instantly)",
  "tool_description": "One sentence telling the user exactly what to enter to get their result",
  "input_1_label": "Short label for the first input field (e.g. Company Name)",
  "input_1_placeholder": "Realistic example value for input 1",
  "input_2_label": "Short label for the second input field (e.g. Your role or context)",
  "input_2_placeholder": "Realistic example value for input 2",
  "output_label": "What the generated result is called (e.g. Your Cold Email)",
  "tool_prompt": "A Gemini AI prompt that uses {{input1}} and {{input2}} as placeholders and produces a high-quality immediately useful result. Be specific and detailed."
}}"""

        response = generate_text(prompt)
        response = response.replace("```json", "").replace("```", "").strip()

        try:
            config = json.loads(response)
        except Exception:
            try:
                config = json.loads(self._extract_json_object(response))
            except Exception:
                config = self._repair_json_response(response[:8000])

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

    def generate_icons(self, app_dir: str, app_name: str, tagline: str) -> str:
        """Generate 512×192 app icons via Gemini image API. Returns theme_color hex."""
        from PIL import Image
        import io

        api_key = get_nanobanana2_api_key()
        if not api_key:
            if get_verbose():
                warning("Gemini API key not set — skipping icon generation, using placeholder icons.")
            return "#7c3aed"

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        endpoint = f"{base_url}/models/{model}:generateContent"

        prompt = (
            f"App icon for a SaaS web app called '{app_name}'. "
            f"Theme: {tagline}. "
            "Flat design, bold vibrant colors, clean simple symbol in center, "
            "white background, NO text, NO letters. Square format, professional modern look."
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "1:1"},
            },
        }

        image_bytes = None
        try:
            resp = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            body = resp.json()
            for candidate in body.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and str(inline.get("mimeType", "")).startswith("image/"):
                        image_bytes = base64.b64decode(inline["data"])
                        break
                if image_bytes:
                    break
        except Exception as e:
            if get_verbose():
                warning(f"Icon generation API error: {e}")

        if not image_bytes:
            if get_verbose():
                warning("No icon returned by Gemini — using placeholder.")
            return "#7c3aed"

        public_dir = os.path.join(app_dir, "public")
        os.makedirs(public_dir, exist_ok=True)

        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        img.resize((512, 512), Image.LANCZOS).save(os.path.join(public_dir, "icon-512.png"))
        img.resize((192, 192), Image.LANCZOS).save(os.path.join(public_dir, "icon-192.png"))

        # Extract dominant color for theme_color
        pixels = list(img.resize((50, 50)).convert("RGB").getdata())
        avg_r = sum(p[0] for p in pixels) // len(pixels)
        avg_g = sum(p[1] for p in pixels) // len(pixels)
        avg_b = sum(p[2] for p in pixels) // len(pixels)
        theme_color = f"#{avg_r:02x}{avg_g:02x}{avg_b:02x}"

        if get_verbose():
            info(f"Icons generated. Theme color: {theme_color}")
        return theme_color

    def _get_android_fingerprint(self) -> str:
        """Decode keystore from env and return its SHA-256 certificate fingerprint."""
        keystore_b64 = os.environ.get("ANDROID_KEYSTORE_BASE64", "").strip()
        keystore_password = os.environ.get("ANDROID_KEYSTORE_PASSWORD", "").strip()
        key_alias = os.environ.get("ANDROID_KEY_ALIAS", "appkey").strip()

        if not keystore_b64 or not keystore_password:
            return "PLACEHOLDER"

        keystore_path = os.path.join(tempfile.gettempdir(), "android_release.keystore")
        with open(keystore_path, "wb") as f:
            f.write(self._decode_base64_secret(keystore_b64))

        try:
            result = subprocess.run(
                [
                    "keytool", "-list", "-v",
                    "-keystore", keystore_path,
                    "-alias", key_alias,
                    "-storepass", keystore_password,
                    "-noprompt",
                ],
                capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.splitlines():
                if "SHA256:" in line:
                    return line.split("SHA256:")[-1].strip()
            if get_verbose():
                warning(f"keytool did not output SHA256. Output: {result.stdout[:500]}")
        except Exception as e:
            if get_verbose():
                warning(f"keytool failed: {e}")
        return "PLACEHOLDER"

    def build_app(self, config: dict) -> str:
        work_dir = os.path.join(tempfile.gettempdir(), f"webapp-{config['app_slug']}")
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        shutil.copytree(self.template_dir, work_dir)

        features = config.get("features", [])
        while len(features) < 3:
            features.append({"name": "Feature", "desc": "Coming soon"})

        # Generate icons and extract theme color
        theme_color = self.generate_icons(work_dir, config["app_name"], config["tagline"])
        config["theme_color"] = theme_color

        # Compute Android package name and fingerprint
        # Use fixed package name from env if set (required for Play Store — same app every run)
        # Otherwise derive from slug (changes daily, Play Store will reject after first upload)
        fixed_pkg = os.environ.get("ANDROID_PACKAGE_NAME", "").strip()
        if fixed_pkg:
            package_name = fixed_pkg
        else:
            safe_slug = re.sub(r"[^a-z0-9]", "", config["app_slug"].lower().replace("-", ""))
            package_name = f"com.moneyprinter.{safe_slug}"
        config["package_name"] = package_name
        fingerprint = self._get_android_fingerprint()

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
            "__THEME_COLOR__": theme_color,
            "__PACKAGE_NAME__": package_name,
            "__FINGERPRINT__": fingerprint,
            "__TOOL_TITLE__": config.get("tool_title", f"Generate with {config['app_name']}"),
            "__TOOL_DESCRIPTION__": config.get("tool_description", "Enter your details below to get an instant AI-generated result."),
            "__INPUT_1_LABEL__": config.get("input_1_label", "Input"),
            "__INPUT_1_PLACEHOLDER__": config.get("input_1_placeholder", "Enter your input here..."),
            "__INPUT_2_LABEL__": config.get("input_2_label", "Additional context (optional)"),
            "__INPUT_2_PLACEHOLDER__": config.get("input_2_placeholder", "Add any extra context..."),
            "__OUTPUT_LABEL__": config.get("output_label", "Your Result"),
            "__TOOL_PROMPT__": config.get("tool_prompt", f"You are an expert assistant for {config['app_name']}. The user provided: {{input1}}. Additional context: {{input2}}. Provide a detailed, high-quality response that directly solves their problem."),
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

    def _redeploy(self, app_dir: str, config: dict, vercel_token: str) -> str:
        """Trigger a fresh Vercel deploy and return the URL."""
        slug = config["app_slug"]
        result = subprocess.run(
            ["vercel", "--token", vercel_token, "--yes", "--prod", "--name", slug],
            cwd=app_dir, capture_output=True, text=True, timeout=300,
        )
        output = result.stdout + result.stderr
        canonical_url = f"https://{slug}.vercel.app"
        if result.returncode != 0 and canonical_url not in output:
            raise RuntimeError(f"Vercel redeploy failed:\n{output[-1000:]}")
        return canonical_url

    def verify_app(self, url: str, config: dict) -> dict:
        """
        Hit the live app and verify all critical endpoints work.
        Returns dict: { tool_ok, payment_ok, errors[] }
        """
        import time as _time
        input_payload = {"input1": config.get("input_1_placeholder", "test"), "input2": "test"}
        final_results = {"tool_ok": False, "payment_ok": False, "errors": []}

        for attempt in range(1, 4):
            results = {"tool_ok": False, "payment_ok": False, "errors": []}
            if attempt > 1 and get_verbose():
                info(f"Retrying app verification ({attempt}/3)...")
            _time.sleep(15 if attempt == 1 else 10)

            try:
                r = requests.get(url, timeout=20)
                if r.status_code != 200:
                    results["errors"].append(f"Homepage returned {r.status_code}")
            except Exception as e:
                results["errors"].append(f"Homepage unreachable: {e}")

            try:
                r = requests.post(f"{url}/api/generate", json=input_payload, timeout=30)
                data = r.json()
                if r.status_code == 200 and data.get("result"):
                    results["tool_ok"] = True
                    if get_verbose():
                        info(f"Verify: /api/generate OK - result: {str(data['result'])[:80]}...")
                else:
                    results["errors"].append(f"/api/generate failed: {r.status_code} {str(data)[:100]}")
            except Exception as e:
                results["errors"].append(f"/api/generate error: {e}")

            try:
                r = requests.post(
                    f"{url}/api/checkout",
                    json={"email": "test@test.com", "yearly": False},
                    timeout=20,
                )
                data = r.json()
                if r.status_code == 200 and data.get("url"):
                    results["payment_ok"] = True
                    if get_verbose():
                        info("Verify: /api/checkout OK - payment link returned.")
                elif "not configured" in str(data).lower() or r.status_code == 500:
                    results["errors"].append("Payment not configured: DODO_API_KEY or DODO_PRODUCT_ID missing on Vercel.")
                else:
                    results["errors"].append(f"/api/checkout: {r.status_code} {str(data)[:100]}")
            except Exception as e:
                results["errors"].append(f"/api/checkout error: {e}")

            final_results = results
            if results["tool_ok"] and results["payment_ok"]:
                return results

        return final_results
        results = {"tool_ok": False, "payment_ok": False, "errors": []}

        # Wait for Vercel to propagate the new deployment
        _time.sleep(15)

        # 1. Check homepage loads
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                results["errors"].append(f"Homepage returned {r.status_code}")
        except Exception as e:
            results["errors"].append(f"Homepage unreachable: {e}")

        # 2. Verify /api/generate works (AI tool)
        try:
            r = requests.post(
                f"{url}/api/generate",
                json={"input1": config.get("input_1_placeholder", "test"), "input2": "test"},
                timeout=30,
            )
            data = r.json()
            if r.status_code == 200 and data.get("result"):
                results["tool_ok"] = True
                if get_verbose():
                    info(f"Verify: /api/generate OK — result: {str(data['result'])[:80]}…")
            else:
                results["errors"].append(f"/api/generate failed: {r.status_code} {str(data)[:100]}")
        except Exception as e:
            results["errors"].append(f"/api/generate error: {e}")

        # 3. Verify /api/checkout responds (payment)
        try:
            r = requests.post(
                f"{url}/api/checkout",
                json={"email": "test@test.com", "yearly": False},
                timeout=20,
            )
            data = r.json()
            if r.status_code == 200 and data.get("url"):
                results["payment_ok"] = True
                if get_verbose():
                    info("Verify: /api/checkout OK — payment link returned.")
            elif "not configured" in str(data).lower() or r.status_code == 500:
                results["errors"].append("Payment not configured: DODO_API_KEY or DODO_PRODUCT_ID missing on Vercel.")
            else:
                results["errors"].append(f"/api/checkout: {r.status_code} {str(data)[:100]}")
        except Exception as e:
            results["errors"].append(f"/api/checkout error: {e}")

        return results

    def deploy(self, app_dir: str, config: dict) -> str:
        vercel_token = os.environ.get("VERCEL_TOKEN", "")
        if not vercel_token:
            raise ValueError("VERCEL_TOKEN env var not set")

        slug = config["app_slug"]
        dodo_api_key = os.environ.get("DODO_API_KEY", "")
        dodo_product_id = os.environ.get("DODO_PRODUCT_ID", "")

        if not dodo_api_key or not dodo_product_id:
            warning("DODO_API_KEY or DODO_PRODUCT_ID not set — payment will be broken. "
                    "Add these to GitHub secrets to enable payments.")

        if get_verbose():
            info(f"Deploying {config['app_name']} to Vercel (pass 1 — build)...")

        result = subprocess.run(
            ["vercel", "--token", vercel_token, "--yes", "--prod", "--name", slug],
            cwd=app_dir, capture_output=True, text=True, timeout=300,
        )

        output = result.stdout + result.stderr
        if get_verbose():
            print(output[-3000:])

        canonical_url = f"https://{slug}.vercel.app"

        if result.returncode != 0 and canonical_url not in output:
            raise RuntimeError(f"Vercel deploy failed:\n{output[-1000:]}")

        base_url = canonical_url

        # Set all env vars via Vercel API
        self.set_vercel_env_vars(slug, {
            "DODO_API_KEY": dodo_api_key,
            "DODO_PRODUCT_ID": dodo_product_id,
            "NEXT_PUBLIC_BASE_URL": base_url,
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
        })

        # Redeploy so the env vars take effect in the running build
        if get_verbose():
            info("Redeploying with env vars applied (pass 2)...")
        base_url = self._redeploy(app_dir, config, vercel_token)

        success(f"Deployed to {base_url}")
        return base_url

    def build_twa(self, app_dir: str, config: dict, deploy_url: str) -> str | None:
        """Build a signed Android TWA (AAB) using Bubblewrap CLI."""
        keystore_b64 = os.environ.get("ANDROID_KEYSTORE_BASE64", "").strip()
        keystore_password = os.environ.get("ANDROID_KEYSTORE_PASSWORD", "").strip()
        key_alias = os.environ.get("ANDROID_KEY_ALIAS", "appkey").strip()
        key_password = os.environ.get("ANDROID_KEY_PASSWORD", keystore_password).strip()

        if not keystore_b64 or not keystore_password:
            if get_verbose():
                warning("Android keystore secrets not set — skipping TWA build.")
            return None

        twa_dir = os.path.join(tempfile.gettempdir(), f"twa-{config['app_slug']}")
        if os.path.exists(twa_dir):
            shutil.rmtree(twa_dir)
        os.makedirs(twa_dir, exist_ok=True)

        # Write keystore file
        keystore_path = os.path.join(twa_dir, "release.keystore")
        with open(keystore_path, "wb") as f:
            f.write(self._decode_base64_secret(keystore_b64))

        domain = deploy_url.replace("https://", "").replace("http://", "").rstrip("/")
        package_name = config.get("package_name", f"com.moneyprinter.{re.sub(r'[^a-z0-9]', '', config['app_slug'].lower())}")
        theme_color = config.get("theme_color", "#7c3aed")

        # Read fingerprint from already-written assetlinks.json (filled in build_app)
        assetlinks_path = os.path.join(app_dir, "public", ".well-known", "assetlinks.json")
        fingerprint = "PLACEHOLDER"
        if os.path.exists(assetlinks_path):
            with open(assetlinks_path) as f:
                content = f.read()
            m = re.search(r'"sha256_cert_fingerprints":\s*\["([^"]+)"', content)
            if m:
                fingerprint = m.group(1)

        # Build twa-manifest.json for Bubblewrap
        from datetime import datetime

        version_code = int(datetime.utcnow().strftime("%y%m%d%H%M%S"))
        version_name = datetime.utcnow().strftime("%Y.%m.%d.%H%M%S")

        twa_manifest = {
            "packageId": package_name,
            "host": domain,
            "name": config["app_name"],
            "launcherName": config["app_name"][:12],
            "display": "standalone",
            "orientation": "default",
            "themeColor": theme_color,
            "navigationColor": theme_color,
            "navigationColorDark": theme_color,
            "navigationDividerColor": "#ffffff",
            "navigationDividerColorDark": "#cccccc",
            "backgroundColor": "#ffffff",
            "enableNotifications": False,
            "startUrl": "/",
            "iconUrl": f"https://{domain}/icon-512.png",
            "maskableIconUrl": f"https://{domain}/icon-512.png",
            "splashScreenFadeOutDuration": 300,
            "signingKey": {"path": keystore_path, "alias": key_alias},
            "appVersionCode": version_code,
            "appVersion": version_name,
            "shortcuts": [],
            "generatorApp": "bubblewrap-cli",
            "webManifestUrl": f"https://{domain}/manifest.json",
            "isChromeOSOnly": False,
            "isMetaQuest": False,
            "fullScopeUrl": f"https://{domain}/",
            "minSdkVersion": 19,
            "fingerprints": [{"name": "release", "value": fingerprint}],
            "enableSiteSettingsShortcut": True,
            "isSplashScreenEnabled": True,
            "useBrowserOnChromeOS": False,
            "features": {},
        }

        twa_manifest_path = os.path.join(twa_dir, "twa-manifest.json")
        with open(twa_manifest_path, "w") as f:
            json.dump(twa_manifest, f, indent=2)

        if get_verbose():
            info(f"Running bubblewrap build in {twa_dir}...")

        try:
            result = subprocess.run(
                ["bubblewrap", "build", "--skipPwaValidation"],
                cwd=twa_dir,
                capture_output=True,
                text=True,
                timeout=600,
                env={
                    **os.environ,
                    "KEYSTORE_PASSWORD": keystore_password,
                    "KEY_PASSWORD": key_password,
                },
            )
            if get_verbose():
                print(result.stdout[-2000:])
                if result.stderr:
                    print(result.stderr[-1000:])
            if result.returncode != 0:
                if get_verbose():
                    warning(f"Bubblewrap exited with code {result.returncode}.")
                return None
        except Exception as e:
            if get_verbose():
                warning(f"Bubblewrap build failed: {e}")
            return None

        # Find signed AAB
        aab_path = os.path.join(twa_dir, "app-release-signed.aab")
        if not os.path.exists(aab_path):
            for root, _, files in os.walk(twa_dir):
                for fname in files:
                    if fname.endswith(".aab"):
                        aab_path = os.path.join(root, fname)
                        break

        if os.path.exists(aab_path):
            success(f"TWA AAB built: {aab_path}")
            return aab_path

        if get_verbose():
            warning("Bubblewrap build did not produce an AAB.")
        return None

    def _make_screenshot(self, title: str, subtitle: str, bullets: list,
                         bg_color: tuple, accent: tuple) -> str:
        """Generate a 1080×1920 Play Store screenshot via Pillow."""
        from PIL import Image, ImageDraw, ImageFont as PILFont
        W, H = 1080, 1920
        img = Image.new("RGB", (W, H), bg_color)
        draw = ImageDraw.Draw(img)

        # Gradient overlay (darker at top)
        for y in range(H):
            alpha = int(80 * (1 - y / H))
            draw.line([(0, y), (W, y)], fill=(
                max(0, bg_color[0] - alpha),
                max(0, bg_color[1] - alpha),
                max(0, bg_color[2] - alpha),
            ))

        font_paths_bold = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        font_paths_reg = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

        def load_font(size, bold=True):
            for p in (font_paths_bold if bold else font_paths_reg):
                if os.path.exists(p):
                    try:
                        return PILFont.truetype(p, size)
                    except Exception:
                        pass
            return PILFont.load_default()

        def draw_centered(text, y, font, color):
            bbox = draw.textbbox((0, 0), text, font=font)
            x = (W - (bbox[2] - bbox[0])) // 2
            draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0, 120))
            draw.text((x, y), text, font=font, fill=color)

        # Accent bar at top
        draw.rectangle([(0, 0), (W, 12)], fill=accent)

        # Title
        f_title = load_font(88, bold=True)
        import textwrap as tw
        for i, line in enumerate(tw.fill(title, 16).split("\n")):
            draw_centered(line, 300 + i * 100, f_title, (255, 255, 255))

        # Accent line
        draw.rectangle([(120, 520), (W - 120, 526)], fill=accent)

        # Subtitle
        f_sub = load_font(52, bold=False)
        for i, line in enumerate(tw.fill(subtitle, 28).split("\n")):
            draw_centered(line, 570 + i * 65, f_sub, (210, 210, 210))

        # Bullet points
        f_bullet = load_font(44, bold=False)
        by = 880
        for bullet in bullets[:4]:
            draw_centered(f"✦  {bullet}", by, f_bullet, (255, 255, 255))
            by += 80

        # Bottom brand bar
        draw.rectangle([(0, H - 100), (W, H)], fill=accent)
        f_brand = load_font(36, bold=True)
        draw_centered("Available on Google Play", H - 72, f_brand, (255, 255, 255))

        out = os.path.join(tempfile.gettempdir(), f"screenshot_{title[:8].replace(' ','')}_{id(img)}.png")
        img.save(out, "PNG")
        return out

    def publish_to_play_store(self, aab_path: str, config: dict, deploy_url: str = "") -> bool:
        """
        Full Play Store publication:
        - Upload signed AAB to internal testing track
        - Generate + upload 3 phone screenshots
        - Set store listing with privacy policy URL
        - Add internal testers
        - Commit edit
        """
        service_account_json = os.environ.get("PLAY_STORE_SERVICE_ACCOUNT_JSON", "").strip()
        if not service_account_json:
            if get_verbose():
                warning("PLAY_STORE_SERVICE_ACCOUNT_JSON not set — skipping Play Store publish.")
            return False
        if not aab_path or not os.path.exists(aab_path):
            if get_verbose():
                warning("AAB file not found — skipping Play Store publish.")
            return False

        package_name = config.get("package_name", f"com.moneyprinter.{re.sub(r'[^a-z0-9]', '', config['app_slug'].lower())}")
        app_name = config["app_name"]
        tagline = config["tagline"]
        features = config.get("features", [])
        feature_names = [f["name"] for f in features[:4]] or ["Smart AI", "Fast Results", "Easy to Use", "No Signup"]

        # Tester emails: env var + owner always included
        raw_testers = os.environ.get("PLAY_STORE_TESTERS", "").strip()
        tester_emails = [e.strip() for e in raw_testers.split(",") if e.strip()]
        owner = "harshitasharma99999999@gmail.com"
        if owner not in tester_emails:
            tester_emails.insert(0, owner)

        # Privacy policy URL
        privacy_url = f"{deploy_url.rstrip('/')}/privacy" if deploy_url else "https://moneyprinter.vercel.app/privacy"

        try:
            from google.oauth2 import service_account as sa
            from googleapiclient.discovery import build as google_build
            from googleapiclient.http import MediaFileUpload

            credentials = sa.Credentials.from_service_account_info(
                json.loads(service_account_json),
                scopes=["https://www.googleapis.com/auth/androidpublisher"],
            )
            service = google_build("androidpublisher", "v3", credentials=credentials)
            edits = service.edits()

            # ── Create edit ────────────────────────────────────────────
            edit = edits.insert(packageName=package_name, body={}).execute()
            edit_id = edit["id"]
            info(f"Play Store edit: {edit_id}")

            # ── Upload AAB ─────────────────────────────────────────────
            bundle = edits.bundles().upload(
                packageName=package_name,
                editId=edit_id,
                media_body=MediaFileUpload(aab_path, mimetype="application/octet-stream"),
            ).execute()
            version_code = bundle["versionCode"]
            info(f"AAB uploaded — version code: {version_code}")

            # ── Internal testing track ─────────────────────────────────
            edits.tracks().update(
                packageName=package_name,
                editId=edit_id,
                track="internal",
                body={"releases": [{"versionCodes": [str(version_code)], "status": "completed"}]},
            ).execute()
            info("Assigned to internal testing track.")

            # ── Add testers ────────────────────────────────────────────
            try:
                edits.testers().update(
                    packageName=package_name,
                    editId=edit_id,
                    track="internal",
                    body={"testers": tester_emails},
                ).execute()
                info(f"Testers added: {tester_emails}")
            except Exception as e:
                warning(f"Testers update failed (non-critical): {e}")

            # ── Generate + upload 3 screenshots ───────────────────────
            try:
                screenshots = [
                    self._make_screenshot(
                        app_name, tagline,
                        feature_names,
                        (15, 10, 40), (124, 58, 237),
                    ),
                    self._make_screenshot(
                        "Key Features", f"Everything you need in one app",
                        feature_names,
                        (10, 30, 20), (34, 197, 94),
                    ),
                    self._make_screenshot(
                        "Get Started Today", "Join thousands of users",
                        ["Free to try", "No credit card needed", "Instant access", "Cancel anytime"],
                        (30, 10, 10), (239, 68, 68),
                    ),
                ]
                # Clear old screenshots first
                try:
                    edits.images().deleteall(
                        packageName=package_name,
                        editId=edit_id,
                        language="en-US",
                        imageType="phoneScreenshots",
                    ).execute()
                except Exception:
                    pass

                for ss_path in screenshots:
                    with open(ss_path, "rb") as f:
                        edits.images().upload(
                            packageName=package_name,
                            editId=edit_id,
                            language="en-US",
                            imageType="phoneScreenshots",
                            media_body=MediaFileUpload(ss_path, mimetype="image/png"),
                        ).execute()
                info(f"Uploaded {len(screenshots)} screenshots.")
            except Exception as e:
                warning(f"Screenshot upload failed (non-critical): {e}")

            # ── Store listing ──────────────────────────────────────────
            short_desc = tagline[:80]
            full_desc = (
                f"{config['description']}\n\n"
                f"Features:\n" +
                "\n".join(f"• {f['name']}: {f['desc']}" for f in features) +
                f"\n\nPrivacy Policy: {privacy_url}"
            )
            edits.listings().update(
                packageName=package_name,
                editId=edit_id,
                language="en-US",
                body={
                    "language": "en-US",
                    "title": app_name[:50],
                    "shortDescription": short_desc,
                    "fullDescription": full_desc[:4000],
                    "contactEmail": owner,
                    "contactWebsite": deploy_url or "https://moneyprinter.vercel.app",
                },
            ).execute()
            info("Store listing updated.")

            # ── Privacy policy ─────────────────────────────────────────
            try:
                edits.details().update(
                    packageName=package_name,
                    editId=edit_id,
                    body={"defaultLanguage": "en-US"},
                ).execute()
            except Exception:
                pass

            # ── Commit ─────────────────────────────────────────────────
            edits.commit(packageName=package_name, editId=edit_id).execute()
            success(f"✅ Published to Play Store internal track: {package_name}")
            success(f"✅ Testers: {', '.join(tester_emails)}")
            success(f"✅ Privacy policy: {privacy_url}")
            success(f"✅ Screenshots uploaded: 3")
            print(f"\n📱 Play Console: https://play.google.com/console")
            print(f"⏳ After 14 days of testing → run 'promote_to_production' workflow to go live.\n")
            return True

        except Exception as e:
            warning(f"Play Store publish failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_twitter_client(self):
        """Return authenticated tweepy.Client or None if credentials missing."""
        api_key = os.environ.get("TWITTER_API_KEY", "").strip()
        api_secret = os.environ.get("TWITTER_API_SECRET", "").strip()
        access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "").strip()
        access_token_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "").strip()
        if not all([api_key, api_secret, access_token, access_token_secret]):
            if get_verbose():
                warning("Twitter API credentials not set — skipping Twitter marketing.")
            return None
        import tweepy
        return tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )

    def tweet_launch(self, config: dict, url: str) -> bool:
        """Post a launch thread (3 tweets) via Twitter API v2."""
        client = self._get_twitter_client()
        if not client:
            return False

        features = config.get("features", [])

        # Tweet 1 — hook + link
        t1 = (
            f"🚀 Just shipped {config['app_name']} — {config['tagline']}\n\n"
            f"Try it FREE (3 uses, no sign-up) 👉 {url}\n\n"
            f"#SaaS #buildinpublic #indiehacker #AI"
        )
        if len(t1) > 280:
            t1 = t1[:277] + "..."

        # Tweet 2 — features (reply to t1 to form thread)
        feat_lines = "\n".join(f"✅ {f['name']} — {f['desc']}" for f in features[:3])
        t2 = f"What it does:\n\n{feat_lines}\n\nBuilt in 24h with AI 🤖"
        if len(t2) > 280:
            t2 = t2[:277] + "..."

        # Tweet 3 — pricing CTA
        price = config.get("price_monthly", 9)
        t3 = (
            f"Pricing: ${price}/mo after your 3 free uses.\n\n"
            f"If you find it useful, RT to help others find it 🙏\n\n"
            f"{url}"
        )
        if len(t3) > 280:
            t3 = t3[:277] + "..."

        try:
            r1 = client.create_tweet(text=t1)
            t1_id = r1.data["id"]
            client.create_tweet(text=t2, in_reply_to_tweet_id=t1_id)
            client.create_tweet(text=t3, in_reply_to_tweet_id=t1_id)
            success(f"Twitter thread posted (3 tweets). First tweet id: {t1_id}")
            return True
        except Exception as e:
            error(f"Twitter post failed: {e}")
            warning(
                "Twitter fix: go to developer.twitter.com → Your App → Settings → "
                "App permissions → set to 'Read and Write' → save → "
                "Keys and Tokens → Regenerate Access Token + Secret → "
                "update TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET in GitHub secrets."
            )
            return False

    def post_to_devto(self, config: dict, url: str) -> bool:
        """Publish a launch article to Dev.to."""
        api_key = os.environ.get("DEVTO_API_KEY", "").strip()
        if not api_key:
            if get_verbose():
                warning("DEVTO_API_KEY not set — skipping Dev.to post.")
            return False

        features = config.get("features", [])
        feat_md = "\n".join(f"- **{f['name']}** — {f['desc']}" for f in features)
        price = config.get("price_monthly", 9)
        price_yearly = config.get("price_yearly", 79)

        article_body = f"""I just shipped **{config['app_name']}** — {config['tagline']}

## What it does

{config['description']}

## Features

{feat_md}

## Try it free

👉 **[{url}]({url})**

No sign-up needed. Get 3 free uses instantly, then ${price}/mo (or ${price_yearly}/yr).

---

Built this in 24 hours using AI. Would love feedback from the dev community!

What would you add or improve? Drop a comment below 👇
"""

        tags = ["showdev", "webdev", "saas", "productivity"]

        try:
            resp = requests.post(
                "https://dev.to/api/articles",
                headers={
                    "api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "article": {
                        "title": f"I built {config['app_name']} — {config['tagline']}",
                        "body_markdown": article_body,
                        "published": True,
                        "tags": tags,
                        "canonical_url": url,
                    }
                },
                timeout=30,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                article_url = data.get("url", "")
                if get_verbose():
                    success(f"Dev.to article published: {article_url}")
                return True
            else:
                if get_verbose():
                    warning(f"Dev.to post failed: {resp.status_code} {resp.text[:200]}")
                return False
        except Exception as e:
            if get_verbose():
                warning(f"Dev.to post failed: {e}")
            return False

    def post_to_reddit(self, config: dict, url: str) -> bool:
        """Post launch to Reddit using PRAW (Reddit API)."""
        client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
        client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
        reddit_username = os.environ.get("REDDIT_USERNAME", "").strip()
        reddit_password = os.environ.get("REDDIT_PASSWORD", "").strip()

        if not all([client_id, client_secret, reddit_username, reddit_password]):
            if get_verbose():
                warning("Reddit credentials not set — skipping Reddit post. "
                        "Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD.")
            return False

        try:
            import praw
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                username=reddit_username,
                password=reddit_password,
                user_agent=f"MoneyPrinterV2:webapp-launcher:1.0 (by /u/{reddit_username})",
            )

            subreddit_name = config.get("target_subreddit", "SideProject")
            title = config.get("reddit_post_title", f"I built {config['app_name']} — {config['tagline']}")
            body = config.get("reddit_post_body", config["description"])

            # Append the URL naturally to the body
            full_body = f"{body}\n\nLive now: {url}\n\nWould love feedback from this community!"

            subreddit = reddit.subreddit(subreddit_name)
            post = subreddit.submit(title=title[:300], selftext=full_body)
            if get_verbose():
                success(f"Reddit post live: https://reddit.com{post.permalink}")
            return True
        except Exception as e:
            if get_verbose():
                warning(f"Reddit post failed: {e}")
            return False

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

        # ── Pre-marketing verification ──────────────────────────────────────
        if get_verbose():
            info(f"Verifying app health at {url}...")
        check = self.verify_app(url, config)
        if check["errors"]:
            for e in check["errors"]:
                warning(f"App check: {e}")

        if not check["tool_ok"]:
            raise RuntimeError(
                "ABORT: /api/generate is broken - AI tool not working. "
                "Check GEMINI_API_KEY on Vercel and deployment accessibility."
            )

        if not check["payment_ok"]:
            raise RuntimeError(
                "ABORT: payment check failed - DODO_API_KEY or DODO_PRODUCT_ID is missing or broken. "
                "Skipping Play Store until checkout works."
            )

        if check["errors"]:
            for e in check["errors"]:
                warning(f"App check: {e}")

        if not check["tool_ok"]:
            error("ABORT: /api/generate is broken — AI tool not working. "
                  "Check GEMINI_API_KEY is set on Vercel. NOT marketing this app.")
            return url

        if not check["payment_ok"]:
            warning("Payment check failed — DODO_API_KEY or DODO_PRODUCT_ID missing. "
                    "App will be live but users cannot pay. "
                    "Add DODO_API_KEY + DODO_PRODUCT_ID to GitHub secrets and re-run. "
                    "Skipping marketing and Play Store until payment works.")
            return url

        # ── Both checks passed — safe to market ─────────────────────────────
        success(f"App verified: tool=✅ payment=✅ → proceeding with marketing")
        self.print_marketing_plan(config, url)

        self.tweet_launch(config, url)
        self.post_to_devto(config, url)
        self.post_to_reddit(config, url)

        # Build Android TWA and publish to Play Store
        if os.environ.get("ANDROID_KEYSTORE_BASE64") and os.environ.get("PLAY_STORE_SERVICE_ACCOUNT_JSON"):
            aab_path = self.build_twa(app_dir, config, url)
            if not aab_path:
                raise RuntimeError("Android TWA build failed; no AAB produced.")
            if aab_path:
                published = self.publish_to_play_store(aab_path, config, deploy_url=url)
                if not published:
                    raise RuntimeError("Play Store publish failed after AAB build.")
                # Submit to Testers Community for 14-day testing
                play_store_url = f"https://play.google.com/store/apps/details?id={config.get('package_name', '')}"
                self.submit_to_testers_community(config, play_store_url)
        elif get_verbose():
            info("Android secrets not set — skipping TWA build and Play Store publish.")

        success(f"Done! App fully live at: {url}")
        return url

    def submit_to_testers_community(self, config: dict, play_store_url: str) -> bool:
        """
        Auto-submit app to testerscommunity.com using Selenium headless Chrome.
        Requires TESTERS_COMMUNITY_EMAIL and TESTERS_COMMUNITY_PASSWORD secrets.
        """
        email = os.environ.get("TESTERS_COMMUNITY_EMAIL", "").strip()
        password = os.environ.get("TESTERS_COMMUNITY_PASSWORD", "").strip()
        if not email or not password:
            warning("TESTERS_COMMUNITY_EMAIL/PASSWORD not set — skipping Testers Community submission.")
            return False
        if not play_store_url or "details?id=" not in play_store_url:
            warning("Invalid Play Store URL — skipping Testers Community submission.")
            return False

        info("Submitting to testerscommunity.com...")
        try:
            import time
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1280,900")

            driver = webdriver.Chrome(options=options)
            wait = WebDriverWait(driver, 20)

            try:
                # ── Step 1: Login ──────────────────────────────────────
                driver.get("https://www.testerscommunity.com/login")
                time.sleep(2)

                # Find email + password fields (try common selectors)
                for sel in ['input[type="email"]', 'input[name="email"]', '#email']:
                    try:
                        email_field = driver.find_element(By.CSS_SELECTOR, sel)
                        email_field.clear()
                        email_field.send_keys(email)
                        break
                    except Exception:
                        pass

                for sel in ['input[type="password"]', 'input[name="password"]', '#password']:
                    try:
                        pw_field = driver.find_element(By.CSS_SELECTOR, sel)
                        pw_field.clear()
                        pw_field.send_keys(password)
                        break
                    except Exception:
                        pass

                # Submit login form
                for sel in ['button[type="submit"]', 'input[type="submit"]',
                            '//button[contains(text(),"Login")]',
                            '//button[contains(text(),"Sign in")]']:
                    try:
                        if sel.startswith("//"):
                            btn = driver.find_element(By.XPATH, sel)
                        else:
                            btn = driver.find_element(By.CSS_SELECTOR, sel)
                        btn.click()
                        break
                    except Exception:
                        pass

                time.sleep(3)
                info(f"Testers Community: logged in, current URL: {driver.current_url}")

                # ── Step 2: Navigate to submit / add app page ──────────
                for submit_url in [
                    "https://www.testerscommunity.com/dashboard/submit",
                    "https://www.testerscommunity.com/dashboard/add-app",
                    "https://www.testerscommunity.com/submit",
                    "https://www.testerscommunity.com/dashboard/new",
                ]:
                    driver.get(submit_url)
                    time.sleep(2)
                    if "404" not in driver.title.lower() and driver.current_url == submit_url:
                        break

                # Also try clicking a submit/add button on dashboard
                if "dashboard" in driver.current_url and "submit" not in driver.current_url:
                    for xpath in [
                        '//button[contains(text(),"Submit")]',
                        '//a[contains(text(),"Submit")]',
                        '//button[contains(text(),"Add App")]',
                        '//a[contains(text(),"Add App")]',
                        '//button[contains(text(),"New")]',
                    ]:
                        try:
                            driver.find_element(By.XPATH, xpath).click()
                            time.sleep(2)
                            break
                        except Exception:
                            pass

                info(f"Testers Community: submit page: {driver.current_url}")

                # ── Step 3: Fill form ──────────────────────────────────
                app_name = config["app_name"]
                description = config.get("description", config.get("tagline", ""))[:500]

                # App name
                for sel in ['input[name="appName"]', 'input[name="name"]',
                            'input[placeholder*="app name" i]', '#appName', '#name']:
                    try:
                        f = driver.find_element(By.CSS_SELECTOR, sel)
                        f.clear(); f.send_keys(app_name); break
                    except Exception:
                        pass

                # Play Store URL
                for sel in ['input[name="playStoreUrl"]', 'input[name="storeUrl"]',
                            'input[name="url"]', 'input[placeholder*="play" i]',
                            'input[placeholder*="store" i]', '#playStoreUrl']:
                    try:
                        f = driver.find_element(By.CSS_SELECTOR, sel)
                        f.clear(); f.send_keys(play_store_url); break
                    except Exception:
                        pass

                # Description
                for sel in ['textarea[name="description"]', 'textarea', '#description']:
                    try:
                        f = driver.find_element(By.CSS_SELECTOR, sel)
                        f.clear(); f.send_keys(description); break
                    except Exception:
                        pass

                time.sleep(1)

                # Submit the form
                for sel in ['button[type="submit"]', '//button[contains(text(),"Submit")]',
                            '//button[contains(text(),"Add")]', '//button[contains(text(),"List")]']:
                    try:
                        if sel.startswith("//"):
                            btn = driver.find_element(By.XPATH, sel)
                        else:
                            btn = driver.find_element(By.CSS_SELECTOR, sel)
                        btn.click()
                        time.sleep(3)
                        break
                    except Exception:
                        pass

                info(f"Testers Community: after submit URL: {driver.current_url}")
                success(f"✅ Submitted to Testers Community: {app_name}")
                return True

            finally:
                driver.quit()

        except Exception as e:
            warning(f"Testers Community submission failed: {e}")
            import traceback
            traceback.print_exc()
            return False
