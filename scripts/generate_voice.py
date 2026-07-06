"""Generate narration with ElevenLabs, with an explicit local dry-run fallback."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

import requests

from grand_forno_common import read_json


def elevenlabs_voice(text: str, output: Path) -> None:
    voice_id = os.getenv("VOICE_ID") or "EXAVITQu4vr4xnSDxMaL"
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={
            "xi-api-key": os.environ["VOICE_API_KEY"],
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": os.getenv("VOICE_MODEL_ID", "eleven_multilingual_v2"),
            "voice_settings": {"stability": 0.48, "similarity_boost": 0.78, "style": 0.2},
        },
        timeout=120,
    )
    response.raise_for_status()
    output.write_bytes(response.content)


def local_voice(text: str, output: Path) -> None:
    executable = shutil.which("espeak-ng") or shutil.which("espeak")
    if not executable:
        raise RuntimeError(
            "VOICE_API_KEY is absent and espeak-ng is not installed for fallback narration"
        )
    command = [executable, "-v", "en-in+f3", "-s", "158", "-w", str(output), text]
    subprocess.run(command, check=True)


def generate(content_path: Path, output: Path, allow_fallback: bool) -> None:
    content = read_json(content_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if os.getenv("VOICE_API_KEY"):
        try:
            elevenlabs_voice(content["script"], output)
            return
        except Exception:
            if not allow_fallback:
                raise
    elif not allow_fallback:
        raise RuntimeError("VOICE_API_KEY is required when fallback mode is disabled")

    # espeak requires WAV output regardless of the requested extension.
    local_voice(content["script"], output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-fallback", action="store_true")
    args = parser.parse_args()
    generate(Path(args.content), Path(args.output), args.allow_fallback)


if __name__ == "__main__":
    main()
