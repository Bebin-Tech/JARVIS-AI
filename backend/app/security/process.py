"""Bounded approved process execution. This is not an OS sandbox."""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil


def python_runtime():
    if not getattr(sys, "frozen", False):
        return sys.executable
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    candidates = [
        local / "Python/pythoncore-3.14-64/python.exe",
        local / "Programs/Python/Python313/python.exe",
    ]
    found = shutil.which("python")
    if found and "WindowsApps" not in found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise ValueError("Approved script execution requires an installed Python interpreter")


def run_bounded(arguments, cwd, timeout=30, stop_event=None):
    environment = {
        k: v
        for k, v in os.environ.items()
        if not any(word in k.upper() for word in ["KEY", "TOKEN", "SECRET", "PASSWORD"])
    }
    with tempfile.TemporaryFile() as output:
        child = subprocess.Popen(
            arguments,
            cwd=cwd,
            shell=False,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        started = time.monotonic()
        reason = None
        while child.poll() is None:
            if stop_event and stop_event.is_set():
                reason = "Emergency stop"
            elif time.monotonic() - started > timeout:
                reason = "Process timed out"
            elif output.tell() > 1_000_000:
                reason = "Process output limit reached"
            if reason:
                try:
                    parent = psutil.Process(child.pid)
                    for process in parent.children(recursive=True):
                        process.kill()
                    parent.kill()
                except psutil.NoSuchProcess:
                    pass
                child.wait(timeout=5)
                break
            time.sleep(0.1)
        output.seek(0)
        text = output.read(1_000_000).decode("utf-8", errors="replace")
        return {"exit_code": child.returncode, "output": text[-12000:], "interrupted": reason}
