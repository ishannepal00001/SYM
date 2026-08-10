from faster_whisper import WhisperModel
import sounddevice as sd
from helpers import calculate_rms


class Ear:
    def __init__(self) -> None:
        self.fs = 44100
        self.duration = 0.6
        self.silence_counter = 1
        self.net = WhisperModel("small", device="cpu", compute_type="int8")

    def hear(self):
        while self.silence_counter != 0:
            rec = sd.rec(int(self.duration * self.fs), samplerate=self.fs, channels=2)
            sd.wait()
            rms = calculate_rms(rec)
            if rms <= 0.03:
                print("Silence Detected!")
                self.silence_counter -= 1
            else:
                self.silence_counter = 1
