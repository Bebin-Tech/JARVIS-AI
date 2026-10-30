"""Windows desktop launcher; no native bridge exposes shell or filesystem APIs to the UI."""

import json
import os
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn


def main():
    if getattr(sys, "frozen", False):
        app_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JARVIS AI"
        app_data.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("JARVIS_DATA_DIR", str(app_data / "data"))
        os.environ.setdefault("JARVIS_WORKSPACE_DIR", str(app_data / "workspace"))
        os.environ.setdefault("JARVIS_MODELS_DIR", str(Path(sys.executable).parent / "models"))
    from backend.app.config import Settings
    from backend.app.main import app

    settings = Settings()
    address = f"http://127.0.0.1:{settings.port}"
    try:
        if httpx.get(address + "/api/health", timeout=1, trust_env=False).is_success:
            raise RuntimeError(
                "Port is already in use. Stop the existing backend before desktop mode."
            )
    except httpx.HTTPError:
        pass
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=settings.port, log_level="warning", ws_max_size=65536
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if not thread.is_alive():
                raise RuntimeError("Backend failed to start")
            if server.started:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Backend startup timed out")
        if "--smoke-test" in sys.argv:
            with httpx.Client(trust_env=False) as client:
                response = client.get(address + "/api/health")
                response.raise_for_status()
                assert client.get(address + "/").status_code == 200
                report = {"desktop_backend": "ok", "ui": "ok", "health": response.json()}
                if "--speech-test" in sys.argv:
                    from backend.verify_voice import verify

                    report["voice_verification"] = verify(address)
                print(json.dumps(report))
            return
        import webview

        webview.create_window(
            "JARVIS AI",
            address,
            width=1280,
            height=900,
            min_size=(680, 600),
            background_color="#050b12",
        )
        webview.start(gui="edgechromium")
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
