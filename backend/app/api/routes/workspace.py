from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.concurrency import run_in_threadpool

from backend.app.api.routes.chat import sensitive
from backend.app.security.secrets import get_secret, set_secret
from backend.app.tools.registry import TOOLS, applications

router = APIRouter(prefix="/api", tags=["workspace"])


class PreferencesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["online", "offline", "hybrid"] = "offline"
    ollama_model: str = Field(
        default="qwen3:0.6b", min_length=1, max_length=100, pattern=r"^[\w.:-]+$"
    )
    openai_model: str = Field(
        default="gpt-4.1-mini", min_length=1, max_length=100, pattern=r"^[\w.:-]+$"
    )
    theme: Literal["dark", "dim"] = "dark"
    memory_enabled: bool = False
    search_provider: Literal["duckduckgo", "brave"] = "duckduckgo"


class ToolInput(BaseModel):
    name: str
    arguments: dict = Field(default_factory=dict)
    mode: Literal["online", "offline", "hybrid"] = "offline"


class DecisionInput(BaseModel):
    approve: bool


class RecordInput(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    due_at: str | None = None


@router.get("/settings")
def settings(request: Request):
    config = request.app.state.settings
    return {
        "mode": config.mode,
        "ollama_model": config.ollama_model,
        "openai_model": config.openai_model,
        "theme": request.app.state.preferences.get("theme", "dark"),
        "memory_enabled": request.app.state.preferences.get("memory_enabled", False),
        "search_provider": config.search_provider,
        "openai_configured": bool(config.openai_api_key.get_secret_value()),
        "brave_configured": bool(get_secret("brave")),
        "workspace": str(config.workspace_dir),
        "applications": applications(),
    }


@router.put("/settings")
def update_settings(body: PreferencesInput, request: Request):
    values = body.model_dump()
    request.app.state.records.set_preferences(values)
    request.app.state.preferences = values
    config = request.app.state.settings
    config.mode, config.ollama_model, config.openai_model = (
        body.mode,
        body.ollama_model,
        body.openai_model,
    )
    config.search_provider = body.search_provider
    return {"saved": True}


@router.put("/settings/keys/{provider}")
async def key(provider: Literal["openai", "brave"], request: Request):
    try:
        payload = await request.json()
        value = payload.get("key")
        if not isinstance(value, str) or len(value) > 512:
            raise ValueError("Invalid key")
        await run_in_threadpool(set_secret, provider, value.strip())
        if provider == "openai":
            request.app.state.settings.openai_api_key = SecretStr(value.strip())
        return {"configured": bool(value.strip())}
    except (ValueError, AttributeError) as error:
        raise HTTPException(422, "Could not save key in Windows Credential Manager") from error


@router.get("/models")
async def models(request: Request):
    try:
        response = await request.app.state.ai.client.get(
            request.app.state.settings.ollama_url + "/api/tags", timeout=5
        )
        response.raise_for_status()
        return {"models": [m["name"] for m in response.json().get("models", [])]}
    except Exception:
        return {"models": [], "error": "Ollama is unavailable"}


@router.get("/tools")
def tools():
    return [
        {
            "name": name,
            "approval": approval,
            "description": description,
            "schema": model.model_json_schema(),
        }
        for name, (model, approval, description) in TOOLS.items()
    ]


@router.post("/tools")
async def propose_tool(body: ToolInput, request: Request):
    return await request.app.state.tools.call(body.name, body.arguments, body.mode)


@router.get("/tasks")
def tasks(request: Request):
    return request.app.state.records.tasks()


@router.post("/tasks/{task_id}/decision")
async def decide(task_id: UUID, body: DecisionInput, request: Request):
    try:
        return await request.app.state.tools.decide(
            str(task_id), body.approve, request.app.state.settings.mode
        )
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@router.get("/records/{kind}")
def records(kind: Literal["memory", "note", "reminder"], request: Request):
    return request.app.state.records.list(kind)


@router.put("/records/{kind}/{record_id}")
def edit_record(
    kind: Literal["memory", "note", "reminder"],
    record_id: UUID,
    body: RecordInput,
    request: Request,
):
    if sensitive(body.content):
        raise HTTPException(422, "Potential secrets cannot be saved")
    try:
        return request.app.state.records.save(kind, body.content, body.due_at, str(record_id))
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


@router.delete("/records/{record_id}")
def delete_record(record_id: UUID, request: Request):
    try:
        return request.app.state.records.delete(str(record_id))
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
