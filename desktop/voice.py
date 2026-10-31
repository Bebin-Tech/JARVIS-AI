"""Always-ready local microphone worker. No standby audio is sent to cloud services."""

import asyncio
import io
import logging
import math
import queue
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pythoncom
import sounddevice as sd

from desktop.conversation import Conversation

LOG = logging.getLogger("jarvis.voice")


def to_wav(frames):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"".join(frames))
    return stream.getvalue()


class NativeVoice(threading.Thread):
    def __init__(self, app, loop):
        super().__init__(name="jarvis-microphone", daemon=True)
        self.app, self.loop = app, loop
        self.config = app.state.settings
        self.queue = queue.Queue(maxsize=25)
        self.shutdown = threading.Event()
        self.paused = threading.Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jarvis-turn")
        self.conversation = Conversation(app)
        self.state = "starting"
        self.error = ""
        self.stream = None
        self.generation = 0
        self.frames = []
        self.silence = 0
        self.heard = False
        self.last_wake = 0.0
        self.deadline = 0.0
        self.level = 0.0
        self.rate = 16000
        self.mode = "personal"
        self.reminded = set()
        self.active_request = None
        self.last_reminder_check = 0.0

    def status(self):
        try:
            microphone_active = bool(
                self.stream and self.stream.active and not self.paused.is_set()
            )
        except sd.PortAudioError:
            microphone_active = False
        return {
            "running": self.is_alive(),
            "state": self.state,
            "paused": self.paused.is_set(),
            "error": self.error,
            "microphone_active": microphone_active,
            "level": round(self.level, 3),
            "mode": self.mode,
            "device": self.config.microphone_device,
            "wake_threshold": self.config.wake_threshold,
        }

    def pause(self):
        self.paused.set()
        self.generation += 1
        self.app.state.tools.halted.set()
        if self.active_request:
            self.active_request.cancel()
        self.conversation.pending = None
        sd.stop()
        self.frames, self.level = [], 0.0
        if self.stream:
            try:
                self.stream.abort()
            except sd.PortAudioError:
                pass
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        self.queue.put_nowait(b"")
        self.state = "paused"

    def resume(self):
        self.error = ""
        self.app.state.tools.halted.clear()
        self.paused.clear()

    def activate(self):
        if self.paused.is_set():
            self.resume()
        self.generation += 1
        sd.stop()
        self.state = "activating"
        self.pool.submit(self.speak, "Yes, I'm listening.", self.generation)

    def stop(self):
        self.shutdown.set()
        self.pause()

    def callback(self, data, frames, timestamp, status):
        if self.paused.is_set() or self.shutdown.is_set():
            return
        try:
            self.queue.put_nowait(bytes(data))
        except queue.Full:
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(bytes(data))
            except queue.Empty:
                pass

    def resample(self, data):
        if self.rate == 16000:
            return data
        from scipy.signal import resample_poly

        divisor = math.gcd(self.rate, 16000)
        samples = np.frombuffer(data, dtype="<i2").astype(np.float32)
        return (
            np.clip(resample_poly(samples, 16000 // divisor, self.rate // divisor), -32768, 32767)
            .astype("<i2")
            .tobytes()
        )

    def begin_utterance(self):
        self.frames, self.heard, self.silence = [], False, 0
        self.deadline = time.monotonic() + self.config.followup_seconds
        self.state = "listening"

    def speak(self, text, generation, followup=True):
        if generation != self.generation or self.paused.is_set():
            return
        self.state = "speaking"
        pythoncom.CoInitialize()
        try:
            if any("\u0b80" <= c <= "\u0bff" for c in text):
                import win32com.client

                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                voices = speaker.GetVoices()
                selected = next(
                    (
                        voices.Item(i)
                        for i in range(voices.Count)
                        if "tamil" in voices.Item(i).GetDescription().lower()
                    ),
                    None,
                )
                if selected is None:
                    if self.config.mode == "offline":
                        raise ValueError("No offline Tamil voice is installed.")
                    import edge_tts
                    import soundfile as sf

                    async def edge_audio():
                        chunks = []
                        async for chunk in edge_tts.Communicate(
                            text[:2000], "ta-IN-PallaviNeural"
                        ).stream():
                            if chunk["type"] == "audio":
                                chunks.append(chunk["data"])
                        return b"".join(chunks)

                    audio = asyncio.run(edge_audio())
                    samples, rate = sf.read(io.BytesIO(audio), dtype="float32")
                    if generation == self.generation:
                        sd.play(samples * self.config.speech_volume, rate)
                        sd.wait()
                    if generation == self.generation:
                        self.begin_utterance()
                    return
                speaker.Voice = selected
                speaker.Speak(text[:2500], 1)
                while not speaker.WaitUntilDone(80):
                    if generation != self.generation or self.paused.is_set():
                        speaker.Speak("", 3)
                        return
            else:
                audio = self.app.state.voice.speak(text[:2500])
                if generation != self.generation:
                    return
                with wave.open(io.BytesIO(audio), "rb") as wav:
                    samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
                    rate = wav.getframerate()
                sd.play(samples.astype(np.float32) / 32768 * self.config.speech_volume, rate)
                while sd.get_stream().active:
                    if generation != self.generation or self.paused.is_set():
                        sd.stop()
                        return
                    time.sleep(0.05)
        except Exception as error:
            self.error = str(error)[:200]
            LOG.warning("Speech output failed: %s", type(error).__name__)
        finally:
            pythoncom.CoUninitialize()
        if generation == self.generation and not self.paused.is_set():
            if followup:
                self.begin_utterance()
            else:
                self.state = "standby"

    def handle_turn(self, audio, generation):
        try:
            text = self.app.state.voice.transcribe(audio, self.config.language)["text"]
            if generation != self.generation:
                return
            if not text.strip():
                self.begin_utterance()
                return
            self.state = "thinking"
            categories = {
                "developer": ["code", "python", "program", "project", "debug"],
                "research": ["search", "research", "weather", "internet"],
                "productivity": ["remind", "schedule", "note", "task"],
                "computer": ["open", "file", "folder", "volume", "brightness"],
            }
            self.mode = next(
                (
                    name
                    for name, words in categories.items()
                    if any(word in text.lower() for word in words)
                ),
                "personal",
            )
            normalized = text.lower().strip().rstrip(".!?")
            if normalized in {"mute microphone", "privacy mode", "pause listening"}:
                self.pause()
                return
            if normalized in {"goodbye", "go to sleep", "stop listening"}:
                self.speak("Going back to standby.", generation, followup=False)
                return
            future = asyncio.run_coroutine_threadsafe(self.conversation.turn(text), self.loop)
            self.active_request = future
            answer = future.result(timeout=120)
            self.active_request = None
            if generation == self.generation:
                self.speak(answer, generation)
        except Exception as error:
            self.error = "Request failed. Check local logs or model connectivity."
            LOG.warning("Voice turn failed: %s", type(error).__name__)
            if generation == self.generation:
                self.state = "standby"

    def process(self, frame, wake):
        samples = np.frombuffer(frame, dtype="<i2")
        self.level = min(
            1.0, float(np.sqrt(np.mean((samples.astype(np.float32) / 32768) ** 2))) * 12
        )
        now = time.monotonic()
        if self.state == "standby" and now - self.last_reminder_check > 5:
            self.last_reminder_check = now
            from datetime import UTC, datetime

            due_records = self.app.state.records.list("reminder") + self.app.state.records.list(
                "schedule"
            )
            for reminder in due_records:
                if (
                    reminder["due_at"]
                    and reminder["id"] not in self.reminded
                    and datetime.fromisoformat(reminder["due_at"]) <= datetime.now(UTC)
                ):
                    self.reminded.add(reminder["id"])
                    self.state = "activating"
                    self.pool.submit(
                        self.speak, "Reminder. " + reminder["content"], self.generation, False
                    )
                    return
        if self.state in {"standby", "speaking"}:
            scores = wake.predict(samples)
            if (
                max(float(v) for v in scores.values()) > self.config.wake_threshold
                and now - self.last_wake > 3
            ):
                self.last_wake = now
                self.generation += 1
                sd.stop()
                # Acknowledgment on first wake; interruption immediately starts capture.
                if self.state == "speaking":
                    self.begin_utterance()
                else:
                    self.state = "activating"
                    self.pool.submit(self.speak, "Yes, I'm listening.", self.generation)
            return
        if self.state != "listening":
            return
        self.frames.append(frame)
        if self.level > self.config.vad_threshold * 12:
            self.heard, self.silence = True, 0
        else:
            self.silence += 1
        if not self.heard and now > self.deadline:
            self.frames = []
            self.state = "standby"
            return
        if (self.heard and self.silence >= 10) or len(self.frames) >= 750:
            audio = to_wav(self.frames)
            self.frames = []
            self.state = "transcribing"
            self.pool.submit(self.handle_turn, audio, self.generation)

    def run(self):
        from openwakeword.model import Model

        root = self.config.models_dir / "wake"
        try:
            wake = Model(
                wakeword_models=[str(root / "hey_jarvis_v0.1.onnx")],
                inference_framework="onnx",
                melspec_model_path=str(root / "melspectrogram.onnx"),
                embedding_model_path=str(root / "embedding_model.onnx"),
            )
        except Exception as error:
            self.error = "Wake model could not load; run setup-models.ps1."
            self.state = "error"
            LOG.warning("Wake initialization failed: %s", type(error).__name__)
            return
        while not self.shutdown.is_set():
            if self.paused.wait(0.1):
                self.state = "paused"
                self.shutdown.wait(0.25)
                continue
            try:
                device = self.config.microphone_device
                try:
                    sd.check_input_settings(
                        device=device, channels=1, dtype="int16", samplerate=16000
                    )
                    self.rate = 16000
                except sd.PortAudioError:
                    self.rate = int(sd.query_devices(device, "input")["default_samplerate"])
                while not self.queue.empty():
                    self.queue.get_nowait()
                with sd.RawInputStream(
                    device=device,
                    channels=1,
                    dtype="int16",
                    samplerate=self.rate,
                    blocksize=int(self.rate * 0.08),
                    callback=self.callback,
                ) as stream:
                    self.stream = stream
                    self.state, self.error = "standby", ""
                    while not self.shutdown.is_set() and not self.paused.is_set():
                        try:
                            raw = self.queue.get(timeout=2)
                            if not raw or not stream.active:
                                break
                            frame = self.resample(raw)
                        except queue.Empty:
                            raise RuntimeError("No microphone frames received") from None
                        self.process(frame, wake)
            except Exception as error:
                if self.paused.is_set():
                    self.state, self.error = "paused", ""
                    continue
                self.state = "error"
                self.error = "Microphone unavailable. Retrying in five seconds."
                LOG.warning("Microphone recovery: %s", type(error).__name__)
                self.shutdown.wait(5)
            finally:
                self.stream = None
        self.pool.shutdown(wait=False, cancel_futures=True)
