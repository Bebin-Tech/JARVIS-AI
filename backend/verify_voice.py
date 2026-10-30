"""Generated-audio integration verification; never records a microphone."""

import io
import wave

import httpx
import numpy as np


def pcm16_wav(audio: bytes):
    with wave.open(io.BytesIO(audio), "rb") as wav:
        rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    if rate != 16000:
        positions = np.arange(int(len(samples) * 16000 / rate)) * rate / 16000
        samples = np.interp(positions, np.arange(len(samples)), samples).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


def verify(address: str):
    with httpx.Client(timeout=120, trust_env=False) as client:
        response = client.post(
            address + "/api/voice/speak",
            json={"text": "Hello Jarvis. What is seventeen plus twenty five?"},
        )
        response.raise_for_status()
        audio = pcm16_wav(response.content)
        response = client.post(
            address + "/api/voice/transcribe?language=en",
            content=audio,
            headers={"Content-Type": "audio/wav"},
        )
        response.raise_for_status()
        transcription = response.json()
        assert "jarvis" in transcription["text"].lower(), transcription
        response = client.post(
            address + "/api/chat",
            json={"text": "What is 17 plus 25? Reply with just the number.", "mode": "offline"},
        )
        response.raise_for_status()
        reply = response.json()
        assert "42" in reply["text"], reply
        assert reply["provider"] == "ollama"
        return {"speech": transcription, "real_local_ai": reply, "wav_bytes": len(audio)}
