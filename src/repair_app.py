"""
One-time repair script for already-deployed Vercel apps.
- Pushes all env vars (DODO_API_KEY, DODO_PRODUCT_ID, GEMINI_API_KEY) to an existing project
- Triggers a fresh redeploy via Vercel API so env vars take effect
- Verifies the app works
- Posts the launch tweet + Dev.to article if everything is OK

Run via: repair_app.yml workflow (workflow_dispatch with app_slug input)
"""
import os
import sys
import json
import time
import requests

sys.path.insert(0, os.path.dirname(__file__))

from config import get_verbose
from status import info, warning, success, error


APP_SLUG = os.environ.get("REPAIR_APP_SLUG", "task-automator-0330")
APP_URL   = os.environ.get("REPAIR_APP_URL",  f"https://{APP_SLUG}.vercel.app")

# Minimal config for tweet/devto (same as what the builder generated)
APP_CONFIG = {
    "app_name":      os.environ.get("REPAIR_APP_NAME",     "Task Automator"),
    "app_slug":      APP_SLUG,
    "tagline":       os.environ.get("REPAIR_APP_TAGLINE",  "Automate Repetitive Tasks Instantly"),
    "description":   os.environ.get("REPAIR_APP_DESC",
                                    "Task Automator helps you automate repetitive tasks using AI, "
                                    "freeing you to focus on meaningful work."),
    "features": [
        {"name": "Smart Automation",  "desc": "Describe your task and AI handles the repetition."},
        {"name": "Instant Output",    "desc": "Get results in seconds, not hours."},
        {"name": "No-Code Required",  "desc": "Anyone can use it — no technical skills needed."},
    ],
    "price_monthly": 9,
    "price_yearly":  79,
    "target_subreddit":   "SaaS",
    "reddit_post_title":  "I built Task Automator — an AI tool that automates repetitive tasks instantly",
    "reddit_post_body":   (
        "Tired of doing the same tasks over and over?\n\n"
        "Task Automator uses AI to automate repetitive work in seconds. "
        "No code, no complex setup — just describe what you need and get results.\n\n"
        f"Try it free (3 uses, no sign-up needed): {APP_URL}\n\n"
        "Would love feedback from this community!"
    ),
    "input_1_placeholder": "Enter your first input",
    "input_2_placeholder": "Enter your second input",
}


def push_env_vars():
    """Push all env vars to Vercel project."""
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        error("VERCEL_TOKEN not set")
        return False

    env_vars = {
        "DODO_API_KEY":        os.environ.get("DODO_API_KEY", ""),
        "DODO_PRODUCT_ID":     os.environ.get("DODO_PRODUCT_ID", ""),
        "GEMINI_API_KEY":      os.environ.get("GEMINI_API_KEY", ""),
        "NEXT_PUBLIC_BASE_URL": APP_URL,
    }

    missing = [k for k, v in env_vars.items() if not v]
    if missing:
        warning(f"Missing env vars (will skip): {missing}")

    ok = True
    for key, value in env_vars.items():
        if not value:
            continue
        # First delete existing (Vercel rejects duplicate keys)
        try:
            # List existing env vars to find the one to delete
            r = requests.get(
                f"https://api.vercel.com/v9/projects/{APP_SLUG}/env",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if r.ok:
                for env in r.json().get("envs", []):
                    if env["key"] == key:
                        requests.delete(
                            f"https://api.vercel.com/v9/projects/{APP_SLUG}/env/{env['id']}",
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=10,
                        )
                        break
        except Exception:
            pass

        # Now set it fresh
        try:
            r = requests.post(
                f"https://api.vercel.com/v10/projects/{APP_SLUG}/env",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"key": key, "value": value, "type": "encrypted", "target": ["production", "preview"]},
                timeout=15,
            )
            if r.ok:
                info(f"  Set {key}: ✅")
            else:
                warning(f"  Set {key}: ❌ {r.status_code} {r.text[:100]}")
                ok = False
        except Exception as e:
            warning(f"  Set {key}: ❌ {e}")
            ok = False

    return ok


def trigger_redeploy() -> str:
    """Trigger a new Vercel production deployment for the project."""
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        return ""

    try:
        # Get latest deployment ID
        r = requests.get(
            f"https://api.vercel.com/v6/deployments?projectId={APP_SLUG}&limit=1&target=production",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if not r.ok:
            warning(f"Could not get latest deployment: {r.status_code}")
            return ""

        deployments = r.json().get("deployments", [])
        if not deployments:
            warning("No existing deployments found to redeploy.")
            return ""

        dep = deployments[0]
        dep_id = dep.get("uid", "")
        if not dep_id:
            return ""

        # Redeploy it
        r2 = requests.post(
            f"https://api.vercel.com/v13/deployments?forceNew=1",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"deploymentId": dep_id, "name": APP_SLUG, "target": "production"},
            timeout=30,
        )

        if r2.ok:
            new_url = r2.json().get("url", "")
            success(f"Redeploy triggered → {new_url or APP_URL}")
            return new_url or APP_URL
        else:
            warning(f"Redeploy API failed ({r2.status_code}), waiting for env vars to propagate...")
            return APP_URL

    except Exception as e:
        warning(f"Redeploy trigger failed: {e}")
        return APP_URL


def verify(url: str) -> dict:
    """Check /api/generate and /api/checkout."""
    results = {"tool_ok": False, "payment_ok": False}
    info(f"Waiting 20s for deployment to propagate...")
    time.sleep(20)

    try:
        r = requests.post(
            f"{url}/api/generate",
            json={"input1": "test task", "input2": "automate emails"},
            timeout=30,
        )
        data = r.json()
        if r.status_code == 200 and data.get("result"):
            results["tool_ok"] = True
            success(f"/api/generate ✅  — {str(data['result'])[:60]}…")
        else:
            warning(f"/api/generate ❌ — {r.status_code} {str(data)[:100]}")
    except Exception as e:
        warning(f"/api/generate ❌ — {e}")

    try:
        r = requests.post(
            f"{url}/api/checkout",
            json={"email": "test@test.com", "yearly": False},
            timeout=20,
        )
        data = r.json()
        if r.status_code == 200 and data.get("url"):
            results["payment_ok"] = True
            success(f"/api/checkout ✅  — payment link returned")
        else:
            warning(f"/api/checkout ❌ — {r.status_code} {str(data)[:100]}")
    except Exception as e:
        warning(f"/api/checkout ❌ — {e}")

    return results


def post_tweet(url: str):
    """Post launch thread to Twitter."""
    import tweepy
    api_key    = os.environ.get("TWITTER_API_KEY", "").strip()
    api_secret = os.environ.get("TWITTER_API_SECRET", "").strip()
    acc_token  = os.environ.get("TWITTER_ACCESS_TOKEN", "").strip()
    acc_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "").strip()

    if not all([api_key, api_secret, acc_token, acc_secret]):
        warning("Twitter secrets missing — skipping tweet.")
        return

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=acc_token,
        access_token_secret=acc_secret,
    )

    t1 = (
        f"🚀 Just shipped {APP_CONFIG['app_name']} — {APP_CONFIG['tagline']}\n\n"
        f"Try it FREE (3 uses, no sign-up) 👉 {url}\n\n"
        f"#SaaS #buildinpublic #indiehacker #AI"
    )[:280]

    feats = APP_CONFIG["features"]
    feat_lines = "\n".join(f"✅ {f['name']} — {f['desc']}" for f in feats[:3])
    t2 = f"What it does:\n\n{feat_lines}\n\nBuilt with AI 🤖"[:280]

    t3 = (
        f"Pricing: ${APP_CONFIG['price_monthly']}/mo after your 3 free uses.\n\n"
        f"RT to help others find it 🙏\n\n{url}"
    )[:280]

    try:
        r1 = client.create_tweet(text=t1)
        t1_id = r1.data["id"]
        client.create_tweet(text=t2, in_reply_to_tweet_id=t1_id)
        client.create_tweet(text=t3, in_reply_to_tweet_id=t1_id)
        success(f"Twitter thread posted ✅ (tweet id: {t1_id})")
    except Exception as e:
        error(f"Twitter post failed: {e}")
        warning("Fix: Go to developer.twitter.com → Your App → Settings → App permissions → set to 'Read and Write' → regenerate Access Token + Secret → update GitHub secrets TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET")


def post_devto(url: str):
    """Post Dev.to article."""
    api_key = os.environ.get("DEVTO_API_KEY", "").strip()
    if not api_key:
        warning("DEVTO_API_KEY not set — skipping Dev.to.")
        return

    body = f"""Just shipped **{APP_CONFIG['app_name']}** — {APP_CONFIG['tagline']}

## What it does

{APP_CONFIG['description']}

## Features

""" + "\n".join(f"- **{f['name']}** — {f['desc']}" for f in APP_CONFIG['features']) + f"""

## Try it free

👉 **[{url}]({url})**

No sign-up needed. 3 free uses instantly, then ${APP_CONFIG['price_monthly']}/mo.

---

Built with AI in 24h. Would love feedback from the dev community! Drop a comment 👇
"""

    r = requests.post(
        "https://dev.to/api/articles",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={"article": {
            "title": f"I built {APP_CONFIG['app_name']} — {APP_CONFIG['tagline']}",
            "body_markdown": body,
            "published": True,
            "tags": ["showdev", "webdev", "saas", "AI"],
            "canonical_url": url,
        }},
        timeout=30,
    )
    if r.status_code in (200, 201):
        success(f"Dev.to article published ✅ → {r.json().get('url','')}")
    else:
        warning(f"Dev.to failed: {r.status_code} {r.text[:150]}")


def main():
    info(f"=== Repairing {APP_SLUG} ===")

    info("Step 1: Pushing env vars to Vercel...")
    push_env_vars()

    info("Step 2: Triggering redeploy...")
    live_url = trigger_redeploy() or APP_URL

    info("Step 3: Verifying app...")
    checks = verify(live_url)

    if not checks["tool_ok"]:
        error("AI tool still broken after repair. Check GEMINI_API_KEY.")
        sys.exit(1)

    if not checks["payment_ok"]:
        error("Payment still broken. Check DODO_API_KEY + DODO_PRODUCT_ID.")
        sys.exit(1)

    success("App fully working! Proceeding with marketing...")

    info("Step 4: Posting tweet thread...")
    post_tweet(live_url)

    info("Step 5: Posting Dev.to article...")
    post_devto(live_url)

    success(f"Done! {APP_SLUG} is live and marketed at {live_url}")


if __name__ == "__main__":
    main()
