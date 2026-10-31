"""Lazy offline speech engines. Model downloads only happen in the setup command."""

import io
import threading
import wave

import numpy as np

from backend.app.config import Settings


class LocalVoice:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = threading.Lock()
        self.whisper = None
        self.piper = None

    def status(self):
        return {
            "stt": (self.settings.models_dir / "whisper" / "model.bin").is_file(),
            "tts": (
                self.settings.models_dir / "piper" / f"{self.settings.piper_voice}.onnx"
            ).is_file(),
            "wake": (self.settings.models_dir / "wake" / "hey_jarvis_v0.1.onnx").is_file(),
            "recognition_languages": ["en", "ta"],
            "local_speech_language": "en",
        }

    def transcribe(self, audio: bytes, language: str):
        if not self.status()["stt"]:
            raise ValueError("Local Whisper model is missing. Run scripts/setup-models.ps1.")
        if len(audio) > 2_000_000:
            raise ValueError("Audio exceeds the 60-second mono recording limit")
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if (
                    wav.getnchannels() != 1
                    or wav.getsampwidth() != 2
                    or wav.getframerate() != 16000
                    or wav.getnframes() > 960000
                ):
                    raise ValueError("Expected at most 60 seconds of 16 kHz mono PCM WAV")
                raw = wav.readframes(wav.getnframes())
                if len(raw) != wav.getnframes() * 2:
                    raise ValueError("Truncated PCM recording")
                samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
        except wave.Error as error:
            raise ValueError("Invalid PCM WAV recording") from error
        with self.lock:
            if self.whisper is None:
                from faster_whisper import WhisperModel

                self.whisper = WhisperModel(
                    str(self.settings.models_dir / "whisper"),
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=2,
                    num_workers=1,
                    local_files_only=True,
                )
            segments, info = self.whisper.transcribe(
                samples,
                language=None if language == "auto" else language,
                beam_size=5,
                condition_on_previous_text=False,
                vad_filter=True,
            )
            return {
                "text": " ".join(s.text.strip() for s in segments).strip(),
                "language": info.language,
                "provider": "local-whisper",
            }

    def speak(self, text: str):
        if not self.status()["tts"]:
            raise ValueError("Piper voice model is missing. Run scripts/setup-models.ps1.")
        if any("\u0b80" <= char <= "\u0bff" for char in text):
            raise ValueError("This Piper voice is English. Choose a Tamil system voice in the UI.")
        with self.lock:
            if self.piper is None:
                from piper import PiperVoice

                self.piper = PiperVoice.load(
                    str(self.settings.models_dir / "piper" / f"{self.settings.piper_voice}.onnx")
                )
            stream = io.BytesIO()
            with wave.open(stream, "wb") as wav:
                self.piper.synthesize_wav(text, wav)
            return stream.getvalue()
