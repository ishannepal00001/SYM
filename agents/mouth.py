from piper import SynthesisConfig, PiperVoice
import sounddevice as sd


class Mouth:
    def __init__(self) -> None:
        self.volume = 1.0
        self.length_scale = 1.0
        self.noise_scale = 0.75
        self.noise_w_scale = 0.9
        self.normalize_audio = True

    def _get_voice(self, voice: str) -> PiperVoice:
        agent_voice = PiperVoice.load(voice)
        return agent_voice

    def speak(self, text: str, voice: str):
        syn_config = SynthesisConfig(
            volume=self.volume,
            length_scale=self.length_scale,
            noise_scale=self.noise_scale,
            noise_w_scale=self.noise_w_scale,
            normalize_audio=True,
        )

        agent_voice = self._get_voice(voice)

        for chunk in agent_voice.synthesize(text, syn_config):
            sd.play(chunk.audio_float_array, samplerate=chunk.sample_rate)
            sd.wait()
