import os
import random
import time
import zipfile
import requests
import platform

from status import *
from config import *

DEFAULT_SONG_ARCHIVE_URLS = []


def close_running_selenium_instances() -> None:
    """
    Closes any running Selenium instances.

    Returns:
        None
    """
    try:
        info(" => Closing running Selenium instances...")

        # Kill all running Firefox instances
        if platform.system() == "Windows":
            os.system("taskkill /f /im firefox.exe")
        else:
            os.system("pkill firefox")

        success(" => Closed running Selenium instances.")

    except Exception as e:
        error(f"Error occurred while closing running Selenium instances: {str(e)}")


def build_url(youtube_video_id: str) -> str:
    """
    Builds the URL to the YouTube video.

    Args:
        youtube_video_id (str): The YouTube video ID.

    Returns:
        url (str): The URL to the YouTube video.
    """
    return f"https://www.youtube.com/watch?v={youtube_video_id}"


def _get_youtube_upload_timeout_sec() -> int:
    raw = str(os.environ.get("YOUTUBE_UPLOAD_TIMEOUT_SEC", "7200")).strip()
    try:
        timeout = int(raw)
        return timeout if timeout > 0 else 7200
    except Exception:
        return 7200


def run_youtube_resumable_upload(request, *, verbose: bool, label: str) -> dict:
    """
    Runs a resumable YouTube Data API upload request until completion with retries.

    Args:
        request: googleapiclient upload request (from youtube.videos().insert(...)).
        verbose: Whether to print progress logs.
        label: Human label for logs (e.g. "Short" / "Long-form").

    Returns:
        dict: The final API response containing the uploaded video id, etc.
    """
    try:
        from googleapiclient.errors import HttpError
    except Exception:  # pragma: no cover
        HttpError = None

    started = time.time()
    timeout_sec = _get_youtube_upload_timeout_sec()
    last_progress = -1
    response = None

    while response is None:
        if time.time() - started > timeout_sec:
            raise TimeoutError(
                f"{label} upload timed out after {timeout_sec}s. "
                "Increase with env var YOUTUBE_UPLOAD_TIMEOUT_SEC."
            )

        try:
            status, response = request.next_chunk(num_retries=5)
            if status is not None and hasattr(status, "progress"):
                progress = int(status.progress() * 100)
                if verbose and progress != last_progress and progress % 5 == 0:
                    info(f"{label} upload progress: {progress}%")
                    last_progress = progress
        except Exception as exc:
            # Retry common transient API failures.
            if HttpError is not None and isinstance(exc, HttpError):
                code = getattr(getattr(exc, "resp", None), "status", None)
                if code in (500, 502, 503, 504):
                    if verbose:
                        warning(f"{label} upload transient HTTP {code}; retrying...")
                    time.sleep(5)
                    continue
            raise

    return response


def _parse_google_http_error(exc) -> dict:
    """
    Best-effort parse of googleapiclient.errors.HttpError.

    Returns:
        dict with keys: status (int|None), reason (str), message (str)
    """
    import json as _json

    status = getattr(getattr(exc, "resp", None), "status", None)
    reason = ""
    message = str(exc)

    content = getattr(exc, "content", None)
    if content:
        try:
            raw = content.decode("utf-8", errors="replace")
            payload = _json.loads(raw)
            err = payload.get("error", {}) if isinstance(payload, dict) else {}
            message = err.get("message", message)
            errors = err.get("errors", []) or []
            if errors and isinstance(errors, list):
                reason = str(errors[0].get("reason") or "")
        except Exception:
            pass

    return {"status": status, "reason": reason, "message": message}


def format_youtube_http_error(exc) -> str:
    """
    Formats a YouTube Data API HttpError into an actionable message.
    """
    import re as _re

    parsed = _parse_google_http_error(exc)
    status = parsed.get("status")
    reason = (parsed.get("reason") or "").strip()
    message = (parsed.get("message") or "").strip()

    project_number = ""
    m = _re.search(r"project\\s+(\\d+)", message)
    if m:
        project_number = m.group(1)

    if status == 403 and reason == "accessNotConfigured":
        return (
            "YouTube upload failed: YouTube Data API v3 is disabled (or never enabled) for the Google Cloud project "
            f"{project_number or '(unknown)'} used by your OAuth client.\n"
            "- Enable `YouTube Data API v3` in that Google Cloud project.\n"
            "- Wait ~5–10 minutes for it to propagate.\n"
            "- Re-run the workflow.\n"
            "If you don't have access to that project, create a new OAuth client in a project you own and "
            "regenerate `YOUTUBE_TOKEN_JSON`."
        )

    if status == 403 and reason == "insufficientPermissions":
        return (
            "YouTube upload failed: the OAuth token does not have the required upload scope.\n"
            "- Re-generate `YOUTUBE_TOKEN_JSON` using `python scripts/setup_youtube_auth.py` (it must request "
            "`https://www.googleapis.com/auth/youtube.upload`).\n"
            "- If you previously authenticated without upload scope, re-run auth and explicitly approve the new consent.\n"
            "- Update the GitHub secret `YOUTUBE_TOKEN_JSON` with the new token.\n"
            "- Re-run the workflow.\n"
            "Tip: make sure you sign in with the same Google account that owns the target YouTube channel."
        )

    if status and reason:
        return f"YouTube upload failed: HTTP {status} ({reason}): {message}"
    if status:
        return f"YouTube upload failed: HTTP {status}: {message}"
    return f"YouTube upload failed: {message or str(exc)}"


def preflight_youtube_api(creds, *, verbose: bool) -> None:
    """
    Fast check that the token works and YouTube Data API is enabled.

    Raises:
        RuntimeError on failure with a human-readable message.
    """
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        # Scope check: channels().list can succeed on readonly tokens; uploads require youtube.upload.
        required_scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        has_scopes = getattr(creds, "has_scopes", None)
        if callable(has_scopes) and not creds.has_scopes(required_scopes):
            observed = getattr(creds, "scopes", None)
            observed_str = ", ".join(observed) if observed else "unknown (not stored in token)"
            raise RuntimeError(
                "YouTube upload scope missing from credentials.\n"
                f"- Current token scopes: {observed_str}\n"
                "- Re-generate `YOUTUBE_TOKEN_JSON` using `python scripts/setup_youtube_auth.py`.\n"
                "- Ensure the consent screen grants `youtube.upload`.\n"
                "- Update the GitHub secret and re-run."
            )

        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        youtube.channels().list(part="id", mine=True).execute()
        if verbose:
            info("YouTube API preflight OK.")
    except HttpError as exc:
        raise RuntimeError(format_youtube_http_error(exc)) from exc


def rem_temp_files() -> None:
    """
    Removes temporary files in the `.mp` directory.

    Returns:
        None
    """
    # Path to the `.mp` directory
    mp_dir = os.path.join(ROOT_DIR, ".mp")

    files = os.listdir(mp_dir)

    for file in files:
        if not file.endswith(".json"):
            os.remove(os.path.join(mp_dir, file))


def fetch_songs() -> None:
    """
    Downloads songs into songs/ directory to use with geneated videos.

    Returns:
        None
    """
    try:
        info(f" => Fetching songs...")

        files_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.exists(files_dir):
            os.mkdir(files_dir)
            if get_verbose():
                info(f" => Created directory: {files_dir}")
        else:
            existing_audio_files = [
                name
                for name in os.listdir(files_dir)
                if os.path.isfile(os.path.join(files_dir, name))
                and name.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))
            ]
            if len(existing_audio_files) > 0:
                return

        configured_url = get_zip_url().strip()
        download_urls = [configured_url] if configured_url else []
        download_urls.extend(DEFAULT_SONG_ARCHIVE_URLS)

        archive_path = os.path.join(files_dir, "songs.zip")
        downloaded = False

        for download_url in download_urls:
            try:
                response = requests.get(download_url, timeout=60)
                response.raise_for_status()

                with open(archive_path, "wb") as file:
                    file.write(response.content)

                SAFE_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for member in zf.namelist():
                        basename = os.path.basename(member)
                        if not basename or not basename.lower().endswith(SAFE_EXTENSIONS):
                            warning(f"Skipping non-audio file in archive: {member}")
                            continue
                        if ".." in member or member.startswith("/"):
                            warning(f"Skipping suspicious path in archive: {member}")
                            continue
                        zf.extract(member, files_dir)

                downloaded = True
                break
            except Exception as err:
                warning(f"Failed to fetch songs from {download_url}: {err}")

        if not downloaded:
            raise RuntimeError(
                "Could not download a valid songs archive from any configured URL"
            )

        # Remove the zip file
        if os.path.exists(archive_path):
            os.remove(archive_path)

        success(" => Downloaded Songs to ../Songs.")

    except Exception as e:
        error(f"Error occurred while fetching songs: {str(e)}")


def choose_random_song():
    """
    Chooses a random song from the Songs/ directory.
    Returns None if the directory doesn't exist or is empty (CI/headless mode).

    Returns:
        str | None: The path to the chosen song, or None if unavailable.
    """
    try:
        songs_dir = os.path.join(ROOT_DIR, "Songs")
        if not os.path.exists(songs_dir):
            if get_verbose():
                warning("Songs directory not found — running without background music.")
            return None
        songs = [
            name
            for name in os.listdir(songs_dir)
            if os.path.isfile(os.path.join(songs_dir, name))
            and name.lower().endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg"))
        ]
        if not songs:
            if get_verbose():
                warning("No audio files in Songs directory — running without background music.")
            return None
        song = random.choice(songs)
        success(f" => Chose song: {song}")
        return os.path.join(ROOT_DIR, "Songs", song)
    except Exception as e:
        warning(f"Error choosing random song: {str(e)} — continuing without background music.")
        return None
