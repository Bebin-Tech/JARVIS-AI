"""After-login tray runtime and crash supervisor. Run independently of a browser."""

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def configure():
    if getattr(sys, "frozen", False):
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "JARVIS AI"
        os.environ.setdefault("JARVIS_DATA_DIR", str(root / "data"))
        os.environ.setdefault("JARVIS_WORKSPACE_DIR", str(root / "workspace"))
        os.environ.setdefault("JARVIS_MODELS_DIR", str(Path(sys.executable).parent / "models"))
    from backend.app.config import Settings

    config = Settings()
    logs = config.data_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        logs / "background.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # Only statuses and exception types are logged; never transcripts or API request bodies.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return config


def supervise():
    from desktop.instance import SingleInstance

    lock = SingleInstance("JarvisAI.Supervisor")
    if not lock.acquired:
        lock.close()
        return
    log = logging.getLogger("jarvis.supervisor")
    try:
        crashes = []
        while True:
            args = (
                [sys.executable, "--worker"]
                if getattr(sys, "frozen", False)
                else [sys.executable, str(Path(__file__).resolve()), "--worker"]
            )
            child = subprocess.Popen(
                args,
                cwd=Path(__file__).resolve().parent.parent,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            code = child.wait()
            if code == 0:
                return
            log.warning("Worker exited with code %s", code)
            now = time.monotonic()
            crashes = [t for t in crashes if now - t < 600] + [now]
            if len(crashes) >= 5:
                log.error("Crash retry limit reached; restart JARVIS from its launcher")
                return
            time.sleep(5)
    finally:
        lock.close()


def worker(config, paused=False, smoke=False):
    import httpx
    import pystray
    import uvicorn
    from PIL import Image, ImageDraw

    from backend.app.main import create_app
    from desktop.instance import SingleInstance
    from desktop.voice import NativeVoice

    lock = SingleInstance()
    if not lock.acquired:
        lock.close()
        return
    app = create_app(config)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=config.port,
            log_level="warning",
            log_config=None,
            access_log=False,
            ws_max_size=4096,
            ws_max_queue=8,
        )
    )
    thread = threading.Thread(target=server.run, name="jarvis-api", daemon=True)
    thread.start()
    engine = None
    icon = None
    try:
        for _ in range(200):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError("Backend port unavailable; stop the development backend first")
            time.sleep(0.1)
        else:
            raise RuntimeError("Backend startup timed out")
        engine = NativeVoice(app, app.state.loop)
        app.state.background = engine
        if paused or smoke:
            engine.paused.set()
        engine.start()
        address = f"http://127.0.0.1:{config.port}"
        image = Image.new("RGB", (64, 64), "#0a141b")
        draw = ImageDraw.Draw(image)
        draw.ellipse((6, 6, 58, 58), outline="#6ee8d0", width=3)
        draw.line((25, 19, 39, 19, 39, 42, 34, 47, 25, 47, 21, 42), fill="#a6ffea", width=4)

        def resume(*_):
            nonlocal engine
            if not engine.is_alive():
                engine = NativeVoice(app, app.state.loop)
                app.state.background = engine
                engine.start()
            engine.resume()

        def pause(*_):
            engine.pause()

        def exit_app(*_):
            engine.stop()
            icon.stop()

        app.state.exit_background = exit_app

        menu = pystray.Menu(
            pystray.MenuItem("Open dashboard", lambda *_: webbrowser.open(address), default=True),
            pystray.MenuItem("Start conversation", lambda *_: engine.activate()),
            pystray.MenuItem("Pause / privacy mode", pause),
            pystray.MenuItem("Resume listening", resume),
            pystray.MenuItem("Emergency stop", pause),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit JARVIS", exit_app),
        )
        icon = pystray.Icon("JarvisAI", image, "JARVIS · starting", menu)

        def monitor():
            deadline = time.monotonic() + 5 if smoke else float("inf")
            while not engine.shutdown.wait(1):
                icon.title = f"JARVIS · {engine.state}"
                if smoke and time.monotonic() >= deadline:
                    with httpx.Client(trust_env=False) as client:
                        result = client.get(address + "/api/background/status").json()
                    report = {"tray": bool(icon.visible), "background": result}
                    (config.data_dir / "background-smoke.json").write_text(
                        json.dumps(report, indent=2), encoding="utf-8"
                    )
                    logging.info("Tray smoke check: %s", json.dumps(report))
                    if sys.stdout is not None:
                        print(json.dumps(report))
                    exit_app()
                    return

        def setup(tray):
            tray.visible = True
            threading.Thread(target=monitor, daemon=True).start()

        logging.info("Native tray process started; microphone permission controlled by Windows")
        icon.run(setup=setup)
    finally:
        if engine:
            engine.stop()
            engine.join(timeout=5)
        server.should_exit = True
        thread.join(timeout=5)
        lock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--supervise", action="store_true")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--paused", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--install-startup", action="store_true")
    parser.add_argument("--uninstall-startup", action="store_true")
    parser.add_argument("--startup-status", action="store_true")
    args = parser.parse_args()
    config = configure()
    from desktop import startup

    if args.install_startup:
        print(startup.install())
    elif args.uninstall_startup:
        startup.uninstall()
        print("Startup disabled")
    elif args.startup_status:
        print(json.dumps({"command": startup.status()}))
    elif args.supervise:
        supervise()
    else:
        worker(config, args.paused, args.smoke_test)


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    try:
        main()
    except Exception:
        logging.exception("Background launcher failed")
        raise
