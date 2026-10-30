import asyncio
import time
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SpeechInput(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


@router.get("/status")
def status(request: Request):
    return request.app.state.voice.status()


@router.post("/transcribe")
async def transcribe(request: Request, language: Literal["en", "ta"] = "en"):
    if request.headers.get("content-type", "").split(";")[0] != "audio/wav":
        raise HTTPException(415, "Send mono 16 kHz PCM WAV audio")
    try:
        if request.app.state.voice_lock.locked():
            raise HTTPException(409, "Speech engine is busy; wait for the current utterance")
        async with request.app.state.voice_lock:
            return await run_in_threadpool(
                request.app.state.voice.transcribe, await request.body(), language
            )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/speak")
async def speak(body: SpeechInput, request: Request):
    try:
        if request.app.state.voice_lock.locked():
            raise HTTPException(409, "Speech engine is busy; wait for the current utterance")
        async with request.app.state.voice_lock:
            audio = await run_in_threadpool(request.app.state.voice.speak, body.text)
        return Response(audio, media_type="audio/wav")
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post("/realtime")
async def realtime(request: Request, mode: Literal["online", "offline", "hybrid"] | None = None):
    config = request.app.state.settings
    key = config.openai_api_key.get_secret_value()
    if (mode or config.mode) == "offline":
        raise HTTPException(409, "Realtime cloud voice is disabled in offline mode")
    if not key:
        raise HTTPException(503, "Configure an OpenAI key for cloud Realtime voice")
    offer = await request.body()
    if len(offer) > 65536 or not offer.startswith(b"v=0"):
        raise HTTPException(422, "Invalid SDP offer")
    import json

    response = await request.app.state.ai.client.post(
        "https://api.openai.com/v1/realtime/calls",
        headers={"Authorization": f"Bearer {key}"},
        files={
            "sdp": (None, offer, "application/sdp"),
            "session": (
                None,
                json.dumps(
                    {
                        "type": "realtime",
                        "model": config.realtime_model,
                        "instructions": "You are JARVIS. Speak naturally in English or Tamil. "
                        "This voice session has no computer tools. "
                        "Never claim to execute computer actions.",
                        "audio": {
                            "input": {"turn_detection": {"type": "server_vad"}},
                            "output": {"voice": "marin"},
                        },
                    }
                ),
                "application/json",
            ),
        },
    )
    if not response.is_success:
        raise HTTPException(502, "Realtime session failed. Check API access and billing.")
    return Response(response.content, media_type="application/sdp")


@router.websocket("/wake")
async def wake(websocket: WebSocket):
    if (
        websocket.headers.get("origin") not in websocket.app.state.allowed_origins
        or not websocket.client
        or websocket.client.host not in {"127.0.0.1", "::1"}
        or websocket.headers.get("host", "").split(":")[0] not in {"127.0.0.1", "localhost"}
    ):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    root = websocket.app.state.settings.models_dir / "wake"
    if not (root / "hey_jarvis_v0.1.onnx").is_file():
        await websocket.send_json({"error": "Wake model is missing"})
        await websocket.close()
        return
    try:
        from openwakeword.model import Model

        model = await run_in_threadpool(
            Model,
            wakeword_models=[str(root / "hey_jarvis_v0.1.onnx")],
            inference_framework="onnx",
            melspec_model_path=str(root / "melspectrogram.onnx"),
            embedding_model_path=str(root / "embedding_model.onnx"),
        )
        last = 0.0
        while True:
            frame = await asyncio.wait_for(websocket.receive_bytes(), timeout=30)
            if len(frame) != 2560:
                await websocket.close(code=1009)
                return
            score = await run_in_threadpool(model.predict, np.frombuffer(frame, dtype=np.int16))
            if max(float(v) for v in score.values()) > 0.55 and time.monotonic() - last > 3:
                last = time.monotonic()
                await websocket.send_json({"wake": True})
    except (WebSocketDisconnect, TimeoutError):
        pass
    except Exception:
        try:
            await websocket.send_json({"error": "Wake engine failed; use push-to-talk"})
            await websocket.close(code=1011)
        except RuntimeError:
            pass
