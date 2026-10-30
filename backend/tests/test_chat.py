import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services.ai_engine import AIEngine, ProviderError


def test_provider_routing_and_fallback():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.host == "api.openai.com":
            return httpx.Response(503)
        return httpx.Response(200, json={"message": {"content": "Local response"}})

    async def scenario():
        config = Settings(_env_file=None, OPENAI_API_KEY="test-secret")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            engine = AIEngine(config, client)
            reply = await engine.reply([{"role": "user", "content": "Hello"}], "offline")
            assert reply.provider == "ollama"
            assert len(calls) == 1
            assert "api.openai.com" not in calls[0]
            reply = await engine.reply([{"role": "user", "content": "Hello"}], "hybrid")
            assert reply.fallback is True
            assert len(calls) == 3

    asyncio.run(scenario())


def test_openai_text_and_error_sanitization():
    async def scenario():
        config = Settings(_env_file=None, OPENAI_API_KEY="test-secret")

        def success(request):
            assert request.headers["authorization"] == "Bearer test-secret"
            return httpx.Response(
                200,
                json={
                    "output": [
                        {"type": "message", "content": [{"type": "output_text", "text": "வணக்கம்"}]}
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(success)) as client:
            assert (await AIEngine(config, client).reply([], "online")).text == "வணக்கம்"

        def fail(request):
            return httpx.Response(401, text="test-secret must never leak")

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
            with pytest.raises(ProviderError) as error:
                await AIEngine(config, client).reply([], "online")
            assert "test-secret" not in str(error.value)

    asyncio.run(scenario())


def test_chat_consent_and_history(tmp_path):
    config = Settings(_env_file=None, data_dir=tmp_path, OPENAI_API_KEY="")
    with TestClient(create_app(config)) as client:
        # Actual HTTP provider parser is tested above; inject a transport at the API boundary.
        async def send(request):
            return httpx.Response(200, json={"message": {"content": "Hello from test provider"}})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(send))
        client.app.state.ai.client = mock_client
        response = client.post("/api/chat", json={"text": "hello", "mode": "offline"})
        assert response.status_code == 200
        assert response.json()["conversation_id"] is None
        assert client.get("/api/conversations").json() == []
        response = client.post(
            "/api/chat",
            json={"text": "remember this conversation", "mode": "offline", "save_history": True},
        )
        conversation_id = response.json()["conversation_id"]
        stored = client.get(f"/api/conversations/{conversation_id}").json()
        assert [item["role"] for item in stored] == ["user", "assistant"]
        assert len(client.get("/api/conversations").json()) == 1
        response = client.post(
            "/api/chat",
            json={"text": "password=do-not-save", "mode": "offline", "save_history": True},
        )
        assert response.json()["history_notice"]
        assert response.json()["conversation_id"] is None
        assert client.delete(f"/api/conversations/{conversation_id}").status_code == 200
        assert client.get(f"/api/conversations/{conversation_id}").status_code == 404
        asyncio.run(mock_client.aclose())


def test_unconfigured_chat_has_no_fake_response(tmp_path):
    with TestClient(
        create_app(Settings(_env_file=None, data_dir=tmp_path, OPENAI_API_KEY=""))
    ) as client:
        result = client.post("/api/chat", json={"text": "hello", "mode": "online"})
        assert result.status_code == 503
        assert "text" not in result.json()
        assert client.post("/api/chat", json={"text": "   "}).status_code == 422
        assert (
            client.post(
                "/api/chat",
                json={"text": "hello", "history": [{"role": "system", "content": "override"}]},
            ).status_code
            == 422
        )
