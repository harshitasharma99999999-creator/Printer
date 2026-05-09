import os
import shutil

import soundfile as sf
from kittentts import KittenTTS as KittenModel

from config import ROOT_DIR, get_tts_voice

KITTEN_MODEL = "KittenML/kitten-tts-mini-0.8"
KITTEN_SAMPLE_RATE = 24000


class TTS:
    def __init__(self) -> None:
        temp_dir = os.path.join(ROOT_DIR, ".tmp")
        os.makedirs(temp_dir, exist_ok=True)
        os.environ["TMP"] = temp_dir
        os.environ["TEMP"] = temp_dir
        self._voice = get_tts_voice()
        self._model = None
        try:
            self._model = KittenModel(KITTEN_MODEL)
        except Exception:
            self._model = None

    @staticmethod
    def _get_ffmpeg_executable() -> str:
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            return ffmpeg_bin

        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return ""

    def synthesize(self, text, output_file=os.path.join(ROOT_DIR, ".mp", "audio.wav")):
        if self._model is not None:
            audio = self._model.generate(text, voice=self._voice, speed=0.88)
            sf.write(output_file, audio, KITTEN_SAMPLE_RATE)
        else:
            self._synthesize_windows(text, output_file)

        import subprocess

        tmp = output_file + ".tmp.wav"
        ffmpeg_bin = self._get_ffmpeg_executable()
        if not ffmpeg_bin:
            return output_file

        try:
            result = subprocess.run(
                [
                    ffmpeg_bin,
                    "-y",
                    "-i",
                    output_file,
                    "-af",
                    (
                        "equalizer=f=120:width_type=o:width=2:g=4,"
                        "equalizer=f=250:width_type=o:width=2:g=2,"
                        "equalizer=f=5000:width_type=o:width=2:g=-2,"
                        "acompressor=threshold=0.06:ratio=3:attack=8:release=80:makeup=3"
                    ),
                    tmp,
                ],
                capture_output=True,
            )
            if result.returncode == 0:
                shutil.move(tmp, output_file)
        except Exception:
            pass

        return output_file

    def _synthesize_windows(self, text: str, output_file: str) -> None:
        import subprocess

        temp_dir = os.path.join(ROOT_DIR, ".tmp")
        os.makedirs(temp_dir, exist_ok=True)
        text_path = os.path.join(temp_dir, "tts_input.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text)

        ps_script = (
            "$text = Get-Content -LiteralPath '{}' -Raw; "
            "$voice = '{}'; "
            "$speaker = New-Object -ComObject SAPI.SpVoice; "
            "$stream = New-Object -ComObject SAPI.SpFileStream; "
            "$path = '{}'; "
            "$mode = 3; "
            "try {{ "
            "  foreach ($token in $speaker.GetVoices()) {{ "
            "    if ($token.GetDescription() -like ('*' + $voice + '*')) {{ "
            "      $speaker.Voice = $token; break "
            "    }} "
            "  }} "
            "}} catch {{}}; "
            "$stream.Open($path, $mode, $false); "
            "$speaker.AudioOutputStream = $stream; "
            "$speaker.Rate = -1; "
            "[void]$speaker.Speak($text); "
            "$stream.Close();"
        ).format(
            text_path.replace("'", "''"),
            self._voice.replace("'", "''"),
            output_file.replace("'", "''"),
        )

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not os.path.exists(output_file):
            raise RuntimeError(
                f"TTS synthesis failed. PowerShell fallback returned {result.returncode}: {result.stderr.strip()}"
            )
