from typing import BinaryIO
from faster_whisper import WhisperModel
import sounddevice as sd
from agents.helpers import calculate_rms
import librosa as ls
import numpy as np


class Ear:
    def __init__(self) -> None:
        self.fs = 44100
        self.duration = 0.8
        self.silence_counter = 2
        self.net = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )
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
            resampled_rec = ls.resample(
                np.concatenate(self.stream), orig_sr=self.fs, target_sr=16000
            )
            segs, info = self.net.transcribe(
                audio=np.mean(resampled_rec, axis=1),
                language="en",
                condition_on_previous_text=False,
            )
            for seg in segs:
                print(seg.text)

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
                self.stream.append(rec)
                self.listen()
                break
            else:
                self.stream.append(rec)
                print(self.stream)
