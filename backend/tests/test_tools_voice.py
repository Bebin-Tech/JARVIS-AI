import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app.config import Settings
from backend.app.core.agent import Agent
from backend.app.main import create_app
from backend.app.services.ai_engine import AIEngine
from backend.app.tools.registry import public_url, scoped_path
from backend.app.tools.web import fetch_page


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.app.main.get_secret", lambda name: "")
    config = Settings(
        mode="offline",
        _env_file=None,
        data_dir=tmp_path,
        models_dir=tmp_path / "models",
        workspace_dir=tmp_path / "workspace",
        OPENAI_API_KEY="",
    )
    with TestClient(create_app(config)) as session:
        yield session


@pytest.mark.parametrize(
    "path",
    [
        "../outside.txt",
        "C:/Windows/x.txt",
        "a.txt:secret",
        ".env",
        "NUL.txt",
        "trailing. /x.txt",
        "a/../../b.txt",
    ],
)
def test_path_escape_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        scoped_path(tmp_path, path)


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/Windows",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://localhost/",
        "https://example.com:8000/",
        "https://user:password@example.com/",
        "http://[::1]/",
    ],
)
def test_unsafe_urls_rejected(url):
    with pytest.raises(ValueError):
        public_url(url)


def test_approval_no_overwrite_and_no_replay(client):
    proposal = client.post(
        "/api/tools",
        json={"name": "write_file", "arguments": {"path": "hello.txt", "content": "hello"}},
    ).json()
    assert proposal["approval_required"]
    assert not (client.app.state.settings.workspace_dir / "hello.txt").exists()
    url = f"/api/tasks/{proposal['task_id']}/decision"
    assert client.post(url, json={"approve": True}).json()["status"] == "completed"
    assert client.post(url, json={"approve": True}).status_code == 409
    again = client.post(
        "/api/tools",
        json={"name": "write_file", "arguments": {"path": "hello.txt", "content": "overwrite"}},
    ).json()
    result = client.post(f"/api/tasks/{again['task_id']}/decision", json={"approve": True})
    assert result.json()["status"] == "failed"
    assert (client.app.state.settings.workspace_dir / "hello.txt").read_text() == "hello"


def test_rejection_and_validation(client):
    task = client.post(
        "/api/tools", json={"name": "create_folder", "arguments": {"path": "safe"}}
    ).json()
    assert (
        client.post(f"/api/tasks/{task['task_id']}/decision", json={"approve": False}).json()[
            "status"
        ]
        == "rejected"
    )
    assert not (client.app.state.settings.workspace_dir / "safe").exists()
    for tool, args in [
        ("open_app", {"app": "powershell"}),
        ("save_memory", {"content": "password=secret"}),
        ("write_file", {"path": "x.ps1", "content": "Remove-Item"}),
        ("create_folder", {"path": "../outside"}),
    ]:
        assert "error" in client.post("/api/tools", json={"name": tool, "arguments": args}).json()


def test_reminders_and_memories(client):
    for name, args in [
        ("save_memory", {"content": "I prefer blue interfaces"}),
        (
            "set_reminder",
            {
                "content": "Test reminder",
                "due_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            },
        ),
    ]:
        task = client.post("/api/tools", json={"name": name, "arguments": args}).json()
        assert (
            client.post(f"/api/tasks/{task['task_id']}/decision", json={"approve": True}).json()[
                "status"
            ]
            == "completed"
        )
    memory = client.get("/api/records/memory").json()[0]
    assert (
        client.put(
            f"/api/records/memory/{memory['id']}", json={"content": "I prefer cyan"}
        ).status_code
        == 200
    )
    assert len(client.get("/api/records/reminder").json()) == 1
    assert client.delete(f"/api/records/{memory['id']}").status_code == 200
    assert client.get("/api/records/memory").json() == []


def test_offline_network_and_voice_validation(client):
    result = client.post(
        "/api/tools", json={"name": "weather", "arguments": {"query": "Chennai"}, "mode": "offline"}
    )
    assert "unavailable in offline" in result.json()["error"]
    assert client.post("/api/voice/realtime", content=b"v=0").status_code == 409
    assert (
        client.post(
            "/api/voice/transcribe", content=b"bad", headers={"Content-Type": "audio/wav"}
        ).status_code
        == 422
    )
    assert client.post("/api/voice/transcribe", content=b"bad").status_code == 415
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/voice/wake", headers={"Origin": "https://evil.example"}),
    ):
        pass


def test_agent_stops_at_approval(client):
    registry = client.app.state.tools
    count = 0

    async def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "write_file",
                                "arguments": {"path": "agent.txt", "content": "proposed"},
                            }
                        }
                    ],
                }
            },
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            engine = AIEngine(client.app.state.settings, transport)
            reply = await Agent(engine, registry).run(
                [{"role": "user", "content": "create file"}], "offline"
            )
            assert "has not run" in reply.text

    asyncio.run(scenario())
    assert count == 1
    assert not (client.app.state.settings.workspace_dir / "agent.txt").exists()
    assert client.get("/api/tasks").json()[0]["status"] == "pending"


def test_fetch_page_blocks_private_dns(monkeypatch):
    import socket

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="private"):
        asyncio.run(fetch_page("https://example.com/article"))


def test_agent_tool_loop_is_bounded(client):
    count = 0

    async def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "list_files", "arguments": {"path": "."}}}
                    ],
                }
            },
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
            reply = await Agent(
                AIEngine(client.app.state.settings, transport), client.app.state.tools
            ).run([], "offline")
            assert "step limit" in reply.text

    asyncio.run(scenario())
    assert count == 4
