"""Generated-audio verification; no microphone recording or cloud call."""

import asyncio
import io
import json
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import Settings
from backend.app.main import create_app
from desktop.conversation import Conversation
from desktop.voice import to_wav


async def verify():
    directory = Path(".cache/native-verification").resolve()
    directory.mkdir(parents=True, exist_ok=True)
    config = Settings(
        _env_file=None,
        mode="offline",
        data_dir=directory,
        workspace_dir=directory / "workspace",
    )
    app = create_app(config)
    async with app.router.lifespan_context(app):
        audio = await asyncio.to_thread(
            app.state.voice.speak, "Hello Jarvis, what is seventeen plus twenty five?"
        )
        with wave.open(io.BytesIO(audio)) as wav:
            rate = wav.getframerate()
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        pcm = resample_poly(samples.astype(np.float32), 16000, rate).astype("<i2").tobytes()
        transcript = await asyncio.to_thread(app.state.voice.transcribe, to_wav([pcm]), "en")
        answer = await Conversation(app).turn(transcript["text"])
        spoken = await asyncio.to_thread(app.state.voice.speak, answer)
        with wave.open(io.BytesIO(spoken)) as wav:
            duration = round(wav.getnframes() / wav.getframerate(), 2)
        print(
            json.dumps(
                {
                    "transcript": transcript["text"],
                    "native_agent_reply": answer,
                    "spoken_seconds": duration,
                    "provider": "ollama",
                    "model": config.ollama_model,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(verify())
