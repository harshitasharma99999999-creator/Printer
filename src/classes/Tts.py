import os
import soundfile as sf
from kittentts import KittenTTS as KittenModel

from config import ROOT_DIR, get_tts_voice

KITTEN_MODEL = "KittenML/kitten-tts-mini-0.8"
KITTEN_SAMPLE_RATE = 24000

class TTS:
    def __init__(self) -> None:
        self._model = KittenModel(KITTEN_MODEL)
        self._voice = get_tts_voice()

    def synthesize(self, text, output_file=os.path.join(ROOT_DIR, ".mp", "audio.wav")):
        audio = self._model.generate(text, voice=self._voice, speed=0.88)
        sf.write(output_file, audio, KITTEN_SAMPLE_RATE)
        # Post-process: warm deep guide voice — bass warmth + smooth compression
        import subprocess, shutil
        tmp = output_file + ".tmp.wav"
        result = subprocess.run([
            "ffmpeg", "-y", "-i", output_file,
            "-af", "equalizer=f=120:width_type=o:width=2:g=4,equalizer=f=250:width_type=o:width=2:g=2,equalizer=f=5000:width_type=o:width=2:g=-2,acompressor=threshold=0.06:ratio=3:attack=8:release=80:makeup=3",
            tmp
        ], capture_output=True)
        if result.returncode == 0:
            shutil.move(tmp, output_file)
        return output_file
