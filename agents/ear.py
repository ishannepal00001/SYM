from typing import BinaryIO
from faster_whisper import WhisperModel
import sounddevice as sd
from agents.helpers import calculate_rms


class Ear:
    def __init__(self) -> None:
        self.fs = 44100
        self.duration = 0.6
        self.silence_counter = 1
        self.net = WhisperModel("small", device="cpu", compute_type="int8")
        self.stream = []

    def _callback(self, indata):
        rms = calculate_rms(indata)
        if rms <= 0.03:
            self.silence_counter -= 1

        elif self.silence_counter == 0:
            self.stream = []

        else:
            self.silence_counter = 1
            self.stream.append(indata)

    def listen(self):
        try:
            self.net.transcribe(audio=self.stream)
        except Exception as e:
            return e

    def hear(self):
        while True:
            rec = sd.rec(int(self.duration * self.fs), samplerate=self.fs, channels=2)
            sd.wait()
            rms = calculate_rms(rec)
            if rms <= 0.03:
                print("Silence Detected!")
                self.silence_counter -= 1
            if self.silence_counter == 0:
                self.listen()
                break
            else:
                self.silence_counter = 1
                self.stream.append(rec)
                print(self.stream)
