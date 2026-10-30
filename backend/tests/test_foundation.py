import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.main import create_app


@pytest.fixture
def client(tmp_path):
    config = Settings(_env_file=None, data_dir=tmp_path, OPENAI_API_KEY="test-secret")
    with TestClient(create_app(config)) as session:
        yield session


def test_health_does_not_leak_secrets(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["openai_configured"] is True
    assert "test-secret" not in response.text
    assert response.json()["capabilities"]["voice"] == client.get("/api/voice/status").json()["stt"]


def test_untrusted_origin_rejected(client):
    assert client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 403


def test_dns_rebinding_host_rejected(client):
    assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400


def test_allowed_frontend_origin(client):
    response = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_remote_configuration_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, host="0.0.0.0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ollama_url="http://remote.example:11434")


def test_system_telemetry(client):
    response = client.get("/api/system")
    assert response.status_code == 200
    assert 0 <= response.json()["cpu_percent"] <= 100
    assert response.json()["ram_total_gb"] > 0


def test_oversized_request_rejected(client):
    assert client.post("/api/system", content="x" * 65537).status_code == 413


def test_chunked_oversized_request_rejected(client):
    def chunks():
        yield b"x" * 40000
        yield b"y" * 40000

    assert client.post("/api/chat", content=chunks()).status_code == 413
