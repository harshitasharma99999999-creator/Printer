import os
import shutil
import subprocess

from config import ROOT_DIR


class TradingVoice:
    """Linux-safe TTS adapter for Tradingclub GitHub Actions workflows."""

    def synthesize(self, text: str, output_file: str = None) -> str:
        output_file = output_file or os.path.join(ROOT_DIR, ".mp", "audio.wav")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            text_path = output_file + ".txt"
            with open(text_path, "w", encoding="utf-8") as file:
                file.write(str(text or ""))
            subprocess.run(
                [
                    espeak,
                    "-v",
                    "en-us",
                    "-s",
                    "148",
                    "-p",
                    "42",
                    "-a",
                    "145",
                    "-f",
                    text_path,
                    "-w",
                    output_file,
                ],
                check=True,
                timeout=600,
            )
            return output_file

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            duration = max(12, min(420, int(len(str(text or "").split()) * 0.55)))
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"anullsrc=channel_layout=mono:sample_rate=24000:d={duration}",
                    output_file,
                ],
                check=True,
                timeout=120,
            )
            return output_file

        raise RuntimeError("No Linux TTS fallback available. Install espeak-ng or ffmpeg.")
