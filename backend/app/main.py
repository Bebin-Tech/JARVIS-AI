"""Local-only API foundation. No model or automation is invoked at startup."""

import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.routes.background import router as background_router
from backend.app.api.routes.chat import router as chat_router
from backend.app.api.routes.system import router as system_router
from backend.app.api.routes.voice import router as voice_router
from backend.app.api.routes.workspace import router as workspace_router
from backend.app.config import ROOT, Settings
from backend.app.core.agent import Agent
from backend.app.memory.database import History
from backend.app.memory.records import Records
from backend.app.memory.semantic import SemanticMemory
from backend.app.security.body_limit import BodyLimitMiddleware
from backend.app.security.secrets import get_secret
from backend.app.services.ai_engine import AIEngine
from backend.app.tools.registry import ToolRegistry
from backend.app.voice.local import LocalVoice

ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    allowed_origins = ORIGINS | {
        f"http://127.0.0.1:{settings.port}",
        f"http://localhost:{settings.port}",
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        app.state.loop = asyncio.get_running_loop()
        app.state.history = History(settings.data_dir)
        app.state.records = Records(app.state.history.engine)
        app.state.preferences = app.state.records.preferences()
        for name in [
            "mode",
            "ollama_model",
            "openai_model",
            "search_provider",
            "microphone_device",
            "language",
            "wake_threshold",
            "followup_seconds",
            "speech_volume",
        ]:
            if name in app.state.preferences:
                setattr(settings, name, app.state.preferences[name])
        if not settings.openai_api_key.get_secret_value():
            from pydantic import SecretStr

            settings.openai_api_key = SecretStr(get_secret("openai"))
        app.state.chat_lock = asyncio.Lock()
        app.state.voice_lock = asyncio.Lock()
        app.state.voice = LocalVoice(settings)
        async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
            app.state.ai = AIEngine(settings, client)
            app.state.tools = ToolRegistry(settings, app.state.records, client)
            app.state.agent = Agent(app.state.ai, app.state.tools)
            app.state.semantic = SemanticMemory(settings, app.state.records, client)
            try:
                yield
            finally:
                app.state.history.engine.dispose()

    app = FastAPI(title="JARVIS AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.allowed_origins = allowed_origins
    app.include_router(system_router)
    app.include_router(background_router)
    app.include_router(chat_router)
    app.include_router(voice_router)
    app.include_router(workspace_router)
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        try:
            limit = 2_000_000 if request.url.path == "/api/voice/transcribe" else 65536
            if int(request.headers.get("content-length", "0")) > limit:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        origin = request.headers.get("origin")
        if origin and origin not in allowed_origins:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse({"detail": "Local access only"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "name": "JARVIS AI",
            "version": "0.1.0",
            "phase": 12,
            "mode": settings.mode,
            "capabilities": {
                "chat": True,
                "voice": app.state.voice.status()["stt"],
                "computer_control": True,
            },
            "openai_configured": bool(settings.openai_api_key.get_secret_value()),
        }

    frontend = ROOT / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
