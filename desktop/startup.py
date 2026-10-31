"""Per-user after-login startup; no elevation or pre-login audio access."""

import subprocess
import sys
from pathlib import Path

VALUE_NAME = "JarvisAI"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def command():
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable, "--supervise"])
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = Path(__file__).resolve().parent / "main.py"
    return subprocess.list2cmdline([str(pythonw), str(launcher), "--supervise"])


def install():
    import winreg

    value = command()
    if len(value) > 260:
        raise ValueError("Startup command exceeds the Windows Run key limit")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, value)
    return value


def uninstall():
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass


def status():
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, VALUE_NAME)[0]
    except FileNotFoundError:
        return None
