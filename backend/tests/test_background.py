import asyncio
import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from backend.app.config import Settings
from desktop.conversation import Conversation
from desktop.voice import NativeVoice, to_wav


def test_native_wav_frames():
    with wave.open(io.BytesIO(to_wav([bytes(2560), bytes(2560)]))) as wav:
        assert wav.getframerate() == 16000
        assert wav.getnchannels() == 1
        assert wav.getnframes() == 2560


def test_wake_and_followup_state_machine(monkeypatch):
    config = Settings(_env_file=None)
    app = SimpleNamespace(
        state=SimpleNamespace(settings=config, records=SimpleNamespace(list=lambda kind: []))
    )
    engine = NativeVoice(app, None)
    original_pool = engine.pool
    engine.pool = Mock()
    original_pool.shutdown()
    monkeypatch.setattr("desktop.voice.sd.stop", lambda: None)
    engine.state = "standby"
    wake = Mock()
    wake.predict.return_value = {"hey_jarvis": 0.99}
    engine.process(bytes(2560), wake)
    assert engine.state == "activating"
    assert engine.pool.submit.call_count == 1
    # Cooldown prevents repeated activation.
    engine.state = "standby"
    engine.process(bytes(2560), wake)
    assert engine.pool.submit.call_count == 1
    engine.begin_utterance()
    speech = np.full(1280, 5000, dtype=np.int16).tobytes()
    engine.process(speech, wake)
    for _ in range(10):
        engine.process(bytes(2560), wake)
    assert engine.state == "transcribing"
    assert engine.pool.submit.call_count == 2
    engine.begin_utterance()
    engine.deadline = 0
    engine.process(bytes(2560), wake)
    assert engine.state == "standby"


def test_voice_confirmation_is_exact():
    tools = SimpleNamespace(decide=AsyncMock(return_value={"status": "rejected"}))
    app = SimpleNamespace(
        state=SimpleNamespace(tools=tools, settings=SimpleNamespace(mode="offline"))
    )
    conversation = Conversation(app)
    conversation.pending = ("pending-id", "confirm power control")
    assert asyncio.run(conversation.turn("yes")) == "Cancelled."
    tools.decide.assert_awaited_once_with("pending-id", False, "offline")


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows mutex")
def test_single_instance_mutex():
    from desktop.instance import SingleInstance

    first = SingleInstance("JarvisAI.TestMutex")
    second = SingleInstance("JarvisAI.TestMutex")
    try:
        assert first.acquired
        assert not second.acquired
    finally:
        second.close()
        first.close()
