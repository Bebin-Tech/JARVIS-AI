"""Backend configuration. Secret values never belong in public API models."""

import os
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JARVIS AI"
    if getattr(sys, "frozen", False)
    else ROOT
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=CONFIG_ROOT / ".env", env_prefix="JARVIS_", extra="ignore"
    )
    host: Literal["127.0.0.1", "localhost", "::1"] = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    mode: Literal["online", "offline", "hybrid"] = "offline"
    openai_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4.1-mini"
    ollama_model: str = "qwen3:0.6b"
    ollama_url: str = "http://127.0.0.1:11434"
    data_dir: Path = ROOT / "data"
    models_dir: Path = ROOT / "models"
    workspace_dir: Path = ROOT / "data" / "workspace"
    whisper_model: str = "tiny"
    piper_voice: str = "en_US-lessac-medium"
    realtime_model: str = "gpt-realtime-2.1"
    search_provider: Literal["duckduckgo", "brave"] = "duckduckgo"

    @field_validator("ollama_url")
    @classmethod
    def local_ollama_only(cls, value: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Ollama must use a local HTTP origin")
        return value.rstrip("/")
