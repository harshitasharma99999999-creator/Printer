#!/usr/bin/env python3
import json
import os
import shutil
import sys
import re
from typing import Tuple

import requests


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def check_url(url: str, timeout: int = 3) -> Tuple[bool, str]:
    try:
        response = requests.get(url, timeout=timeout)
        return True, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


def find_ffmpeg() -> str:
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def main() -> int:
    if not os.path.exists(CONFIG_PATH):
        fail(f"Missing config file: {CONFIG_PATH}")
        return 1

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    failures = 0

    stt_provider = str(cfg.get("stt_provider", "local_whisper")).lower()

    ok(f"stt_provider={stt_provider}")

    # LLM selection for unattended runs (cron/autopublish)
    groq_key = (cfg.get("groq_api_key", "") or os.environ.get("GROQ_API_KEY", "")).strip()
    ollama_model = str(cfg.get("ollama_model", "")).strip()
    if groq_key:
        ok("groq_api_key is set (Groq mode)")
    else:
        if ollama_model:
            ok(f"ollama_model is set: {ollama_model}")
        else:
            fail(
                "No LLM configured for unattended runs. "
                "Set `ollama_model` in config.json (or set GROQ_API_KEY / groq_api_key)."
            )
            failures += 1

    imagemagick_path = cfg.get("imagemagick_path", "")
    if imagemagick_path and os.path.exists(imagemagick_path):
        ok(f"imagemagick_path exists: {imagemagick_path}")
    else:
        warn(
            "imagemagick_path is not set to a valid executable path. "
            "MoviePy subtitle rendering may fail."
        )

    firefox_profile = cfg.get("firefox_profile", "")
    if firefox_profile:
        if os.path.isdir(firefox_profile):
            ok(f"firefox_profile exists: {firefox_profile}")
        else:
            warn(f"firefox_profile does not exist: {firefox_profile}")
    else:
        warn("firefox_profile is empty. Twitter/YouTube automation requires this.")

    # Ollama (LLM) - only required when not using Groq
    if not groq_key:
        base = str(cfg.get("ollama_base_url", "http://127.0.0.1:11434")).rstrip("/")
        reachable, detail = check_url(f"{base}/api/tags")
        if not reachable:
            fail(f"Ollama is not reachable at {base}: {detail}")
            failures += 1
        else:
            ok(f"Ollama reachable at {base}")
            try:
                tags = requests.get(f"{base}/api/tags", timeout=5).json()
                models = [m.get("name") for m in tags.get("models", [])]
                if models:
                    ok(f"Ollama models available: {', '.join(models[:10])}")
                else:
                    warn("No models found on Ollama. Pull a model first (e.g. 'ollama pull llama3.2:3b').")
            except Exception as exc:
                warn(f"Could not validate Ollama model list: {exc}")

    # Nano Banana 2 (image generation)
    api_key = cfg.get("nanobanana2_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
    nb2_base = str(
        cfg.get(
            "nanobanana2_api_base_url",
            "https://generativelanguage.googleapis.com/v1beta",
        )
    ).rstrip("/")
    if api_key:
        ok("nanobanana2_api_key is set")
    else:
        warn("nanobanana2_api_key is empty (and GEMINI_API_KEY is not set). The app will fall back to Picsum images.")

    reachable, detail = check_url(nb2_base, timeout=8)
    if not reachable:
        warn(f"Nano Banana 2 base URL could not be reached: {detail}")
    else:
        ok(f"Nano Banana 2 base URL reachable: {nb2_base}")

    if stt_provider == "local_whisper":
        try:
            import faster_whisper  # noqa: F401

            ok("faster-whisper is installed")
        except Exception as exc:
            warn(
                "faster-whisper is not importable: "
                f"{exc}. Short generation will continue without subtitles unless you install it."
            )

    # ffmpeg (required for MoviePy + long-form subtitle burn)
    ffmpeg_bin = find_ffmpeg()
    if ffmpeg_bin:
        ok(f"ffmpeg is available: {ffmpeg_bin}")
    else:
        fail("ffmpeg not found. TTS post-processing and some video flows will fail until ffmpeg is installed.")
        failures += 1

    # YouTube auth (required for uploads)
    if os.environ.get("YOUTUBE_TOKEN_JSON"):
        ok("YOUTUBE_TOKEN_JSON is set")
    else:
        token_path = os.path.join(ROOT_DIR, "token.json")
        if os.path.exists(token_path):
            ok(f"YouTube token file found: {token_path}")
        else:
            warn("YouTube token not found (token.json / YOUTUBE_TOKEN_JSON). Uploads will fail until auth is set up.")

    # YouTube Data API enabled + token works (required for uploads)
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError

        REQUIRED_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        token_json = os.environ.get("YOUTUBE_TOKEN_JSON")
        token_path = os.path.join(ROOT_DIR, "token.json")

        creds = None
        if token_json:
            creds = Credentials.from_authorized_user_info(json.loads(token_json))
        elif os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path)

        if creds is not None:
            if callable(getattr(creds, "has_scopes", None)) and not creds.has_scopes(REQUIRED_SCOPES):
                have = getattr(creds, "scopes", None)
                have_str = ", ".join(have) if have else "unknown (not stored in token)"
                fail(
                    "YouTube token is missing the `youtube.upload` scope.\n"
                    f"Current token scopes: {have_str}\n"
                    "Re-run: python scripts/setup_youtube_auth.py (and update YOUTUBE_TOKEN_JSON)."
                )
                failures += 1
                creds = None
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
            try:
                resp = youtube.channels().list(part="id", mine=True).execute()
                chan_id = ""
                items = resp.get("items") or []
                if items:
                    chan_id = str(items[0].get("id") or "")
                ok(f"YouTube API access OK (channel_id={chan_id or 'unknown'})")
            except HttpError as exc:
                raw = ""
                reason = ""
                msg = str(exc)
                try:
                    raw = exc.content.decode("utf-8", errors="replace")
                    payload = json.loads(raw)
                    msg = payload.get("error", {}).get("message", msg)
                    errors = payload.get("error", {}).get("errors", []) or []
                    if errors:
                        reason = str(errors[0].get("reason") or "")
                except Exception:
                    pass

                project_number = ""
                m = re.search(r"project\\s+(\\d+)", msg)
                if m:
                    project_number = m.group(1)

                if reason == "accessNotConfigured":
                    fail(
                        "YouTube Data API v3 is disabled (or never enabled) for the Google Cloud project "
                        f"{project_number or '(unknown)'} used by your OAuth client.\n"
                        "Enable `YouTube Data API v3` in that project, wait a few minutes, then re-run. "
                        "If you don't have access to that project, create a new OAuth client in a project you own "
                        "and regenerate `YOUTUBE_TOKEN_JSON`."
                    )
                else:
                    fail(f"YouTube API access failed: {reason or msg}")
                failures += 1
    except Exception as exc:
        # Don't hard-fail preflight if the deps aren't installed (e.g., before pip install).
        warn(f"Skipped YouTube API access check: {exc}")

    if failures:
        print("")
        print(f"Preflight completed with {failures} blocking issue(s).")
        return 1

    print("")
    print("Preflight passed. Local setup looks ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
