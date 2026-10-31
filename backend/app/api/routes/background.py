from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/background", tags=["background"])


class Command(BaseModel):
    action: Literal["activate", "pause", "resume", "emergency_stop", "exit"]


class AudioSettings(BaseModel):
    microphone_device: int | None = None
    language: Literal["en", "ta", "auto"] = "auto"
    wake_threshold: float = Field(default=0.55, ge=0.1, le=0.95)
    followup_seconds: int = Field(default=15, ge=3, le=120)
    speech_volume: float = Field(default=0.8, ge=0, le=1)


@router.get("/status")
def status(request: Request):
    engine = getattr(request.app.state, "background", None)
    return (
        engine.status()
        if engine
        else {"running": False, "state": "not_started", "microphone_active": False, "paused": False}
    )


@router.get("/devices")
def devices():
    try:
        import sounddevice as sd

        return [
            {"id": index, "name": d["name"], "inputs": d["max_input_channels"]}
            for index, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        ]
    except Exception as error:
        raise HTTPException(503, "Windows microphone devices are unavailable") from error


@router.post("/command")
def command(body: Command, request: Request):
    engine = getattr(request.app.state, "background", None)
    if not engine:
        raise HTTPException(409, "Start JARVIS from the system tray launcher first")
    if body.action == "exit":
        request.app.state.exit_background()
        return {"running": False, "state": "exiting"}
    if body.action in {"pause", "emergency_stop"}:
        engine.pause()
    elif body.action == "resume":
        engine.resume()
    else:
        engine.activate()
    return engine.status()


@router.put("/settings")
def settings(body: AudioSettings, request: Request):
    values = body.model_dump()
    request.app.state.records.set_preferences(values)
    for key, value in values.items():
        setattr(request.app.state.settings, key, value)
    engine = getattr(request.app.state, "background", None)
    if engine and not engine.paused.is_set():
        engine.pause()
        engine.resume()
    return {"saved": True}


@router.get("/settings")
def get_settings(request: Request):
    return AudioSettings.model_validate(request.app.state.settings, from_attributes=True)
