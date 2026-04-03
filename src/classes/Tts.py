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
        audio = self._model.generate(text, voice=self._voice, speed=1.0)
        sf.write(output_file, audio, KITTEN_SAMPLE_RATE)
        # Post-process: presence boost + dynamic compression for energetic hypnotic voice
        import subprocess, shutil
        tmp = output_file + ".tmp.wav"
        result = subprocess.run([
            "ffmpeg", "-y", "-i", output_file,
            "-af", "equalizer=f=2000:width_type=o:width=2:g=3,equalizer=f=4000:width_type=o:width=2:g=2,acompressor=threshold=0.05:ratio=4:attack=3:release=30:makeup=4",
            tmp
        ], capture_output=True)
        if result.returncode == 0:
            shutil.move(tmp, output_file)
        return output_file
