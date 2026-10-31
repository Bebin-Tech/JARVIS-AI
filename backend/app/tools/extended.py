"""Additional scoped file and Windows tools. Every mutation is approval-gated."""

import fnmatch
import hashlib
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

import psutil
from pydantic import Field

from backend.app.tools.registry import AppArgs, Args, Empty, PathArgs, scoped_path


class FileArgs(Args):
    root: Literal["workspace", "downloads"] = "workspace"
    path: str = Field(min_length=1, max_length=240)


class TransferArgs(FileArgs):
    destination_root: Literal["workspace", "downloads"] = "workspace"
    destination: str = Field(min_length=1, max_length=240)


class EditArgs(FileArgs):
    content: str = Field(max_length=40000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class SearchArgs(FileArgs):
    pattern: str = Field(default="*", min_length=1, max_length=80)


class PercentArgs(Args):
    percent: int = Field(ge=0, le=100)


class PowerArgs(Args):
    action: Literal["lock", "restart", "shutdown"]


class ScriptArgs(PathArgs):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    arguments: list[str] = Field(default_factory=list, max_length=10)


class DependencyArgs(PathArgs):
    manager: Literal["pip", "npm"] = "pip"
    packages: list[str] = Field(min_length=1, max_length=10)


class DownloadArgs(Args):
    url: str = Field(min_length=8, max_length=2000)
    path: str = Field(min_length=1, max_length=240)


class OrganizeArgs(FileArgs):
    pattern: str = Field(default="*.pdf", min_length=1, max_length=80)
    destination: str = Field(min_length=1, max_length=240)


EXTRA_TOOLS = {
    "download_file": (
        DownloadArgs,
        True,
        "Download an approved HTTPS PDF/text/ZIP (max 10 MB) into workspace; never execute it.",
    ),
    "organize_files": (
        OrganizeArgs,
        True,
        "Move up to 100 matching files into a new permitted folder; approval required.",
    ),
    "system_details": (Empty, False, "Read storage, battery, and current system information."),
    "search_files": (SearchArgs, False, "Search permitted workspace or Downloads files by glob."),
    "inspect_file": (
        FileArgs,
        False,
        "Read permitted text and its SHA256 before proposing an edit.",
    ),
    "copy_file": (TransferArgs, True, "Copy one file without overwriting; max 100 MB."),
    "move_file": (TransferArgs, True, "Move or rename one permitted file without overwriting."),
    "edit_file": (
        EditArgs,
        True,
        "Edit a text file only if its reviewed SHA256 still matches; keep backup.",
    ),
    "recycle_file": (FileArgs, True, "Move one permitted file to the Windows Recycle Bin."),
    "compress_zip": (
        TransferArgs,
        True,
        "Compress a permitted directory into a new ZIP; bounded file count.",
    ),
    "extract_zip": (
        TransferArgs,
        True,
        "Extract a ZIP into a new directory; rejects traversal, links and zip bombs.",
    ),
    "set_volume": (PercentArgs, True, "Set Windows master volume after approval."),
    "set_brightness": (PercentArgs, True, "Set supported screen brightness after approval."),
    "power_control": (
        PowerArgs,
        True,
        "Lock, restart or shut down Windows; explicit confirmation required.",
    ),
    "switch_app": (AppArgs, True, "Focus an approved application's visible window."),
    "run_python": (
        ScriptArgs,
        True,
        "Run a reviewed Python script by SHA256 with user permissions, not a sandbox.",
    ),
    "install_dependencies": (
        DependencyArgs,
        True,
        "Install reviewed PyPI packages in a project-local virtual environment.",
    ),
}


def roots(config, root):
    return config.workspace_dir if root == "workspace" else Path.home() / "Downloads"


def source(config, args):
    return scoped_path(roots(config, args.root), args.path)


def checked_file(path):
    if not path.is_file() or path.stat().st_size > 100_000_000:
        raise ValueError("Expected an existing file smaller than 100 MB")
    return path


def text_file(path):
    checked_file(path)
    if (
        path.suffix.lower()
        not in {".txt", ".md", ".py", ".json", ".csv", ".ts", ".tsx", ".css", ".html"}
        or path.stat().st_size > 40000
    ):
        raise ValueError("Expected a permitted text file under 40 KB")
    return path.read_text(encoding="utf-8")


def zip_members(archive, destination):
    members = archive.infolist()
    if len(members) > 1000 or sum(m.file_size for m in members) > 100_000_000:
        raise ValueError("ZIP exceeds extraction limits")
    result = []
    for member in members:
        target = scoped_path(destination, member.filename)
        if (member.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("ZIP symlinks are blocked")
        if member.file_size > 10_000_000 or member.file_size / max(1, member.compress_size) > 200:
            raise ValueError("ZIP entry exceeds decompression limits")
        result.append((member, target))
    return result


def execute(name, args, config, stop_event=None):
    if name == "organize_files":
        folder = source(config, args)
        destination = scoped_path(roots(config, args.root), args.destination)
        if not folder.is_dir() or destination.exists():
            raise ValueError("Source must be a directory and destination must be new")
        files = [
            scoped_path(roots(config, args.root), str(p.relative_to(roots(config, args.root))))
            for p in folder.iterdir()
            if p.is_file() and fnmatch.fnmatch(p.name.lower(), args.pattern.lower())
        ]
        if not files or len(files) > 100 or sum(p.stat().st_size for p in files) > 100_000_000:
            raise ValueError("Select 1–100 files totaling at most 100 MB")
        destination.mkdir(parents=True)
        moved = []
        try:
            for path in files:
                if stop_event and stop_event.is_set():
                    raise ValueError("Emergency stop")
                target = destination / path.name
                path.rename(target)
                moved.append((path, target))
        except Exception:
            for original, target in reversed(moved):
                if not original.exists():
                    target.rename(original)
            raise
        return {
            "moved": [p.name for p in files],
            "destination": args.destination,
            "verified": all(
                target.is_file() and not original.exists() for original, target in moved
            ),
        }
    if name == "system_details":
        from backend.app.api.routes.system import system_info

        disk = psutil.disk_usage(str(config.workspace_dir.anchor))
        battery = psutil.sensors_battery()
        return {
            **system_info(),
            "storage_free_gb": round(disk.free / 1024**3, 2),
            "battery_percent": battery.percent if battery else None,
            "plugged_in": battery.power_plugged if battery else None,
        }
    if name == "search_files":
        root = source(config, args)
        result = []
        visited = 0
        for current, directories, files in os.walk(root, followlinks=False):
            directories[:] = [
                d
                for d in directories
                if not d.startswith(".")
                and not (Path(current) / d).is_symlink()
                and not (Path(current) / d).is_junction()
            ]
            for file in files:
                visited += 1
                if fnmatch.fnmatch(file.lower(), args.pattern.lower()):
                    path = Path(current) / file
                    result.append(str(path.relative_to(roots(config, args.root))))
                if visited >= 10000 or len(result) >= 200:
                    return {"files": result, "truncated": True}
        return {"files": result, "truncated": False}
    if name == "inspect_file":
        path = source(config, args)
        return {"content": text_file(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if name in {"copy_file", "move_file", "compress_zip", "extract_zip"}:
        src = source(config, args)
        dest = scoped_path(roots(config, args.destination_root), args.destination)
        if dest.exists():
            raise ValueError("Destination exists; overwriting is blocked")
        if name in {"copy_file", "move_file"}:
            checked_file(src)
            if name == "copy_file":
                with src.open("rb") as source_file, dest.open("xb") as output:
                    shutil.copyfileobj(source_file, output)
            else:
                src.rename(dest)
            return {
                "source": args.path,
                "destination": args.destination,
                "verified": dest.is_file(),
            }
        if name == "compress_zip":
            if not src.is_dir() or dest.suffix.lower() != ".zip" or dest.is_relative_to(src):
                raise ValueError("Select a directory and a ZIP outside that directory")
            files = []
            total = 0
            for current, directories, names in os.walk(src, followlinks=False):
                directories[:] = [
                    d
                    for d in directories
                    if not (Path(current) / d).is_junction()
                    and not (Path(current) / d).is_symlink()
                    and not d.startswith(".")
                ]
                for file in names:
                    relative = str((Path(current) / file).relative_to(roots(config, args.root)))
                    path = scoped_path(roots(config, args.root), relative)
                    total += path.stat().st_size
                    files.append(path)
                    if len(files) > 1000 or total > 100_000_000:
                        raise ValueError("Directory exceeds ZIP limits")
            with zipfile.ZipFile(dest, "x", zipfile.ZIP_DEFLATED) as archive:
                for path in files:
                    archive.write(path, path.relative_to(src))
            return {"created": args.destination, "files": len(files)}
        with zipfile.ZipFile(checked_file(src)) as archive:
            members = zip_members(archive, dest)
            dest.mkdir()
            for member, target in members:
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as entry, target.open("xb") as output:
                        shutil.copyfileobj(entry, output)
        return {"extracted": len(members), "destination": args.destination}
    if name == "edit_file":
        path = source(config, args)
        text_file(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != args.sha256:
            raise ValueError("File changed after review; inspect it again")
        backup = path.with_name(path.name + f".jarvis-backup-{uuid4().hex[:8]}")
        with backup.open("xb") as output:
            output.write(path.read_bytes())
        path.write_text(args.content, encoding="utf-8")
        return {"edited": args.path, "backup": backup.name}
    if name == "recycle_file":
        from send2trash import send2trash

        path = checked_file(source(config, args))
        send2trash(str(path))
        return {"recycled": args.path, "verified": not path.exists()}
    if name == "set_volume":
        import comtypes
        from pycaw.pycaw import AudioUtilities

        comtypes.CoInitialize()
        try:
            device = AudioUtilities.GetSpeakers()
            device.EndpointVolume.SetMasterVolumeLevelScalar(args.percent / 100, None)
            return {"volume": round(device.EndpointVolume.GetMasterVolumeLevelScalar() * 100)}
        finally:
            comtypes.CoUninitialize()
    if name == "set_brightness":
        import screen_brightness_control as brightness

        brightness.set_brightness(args.percent)
        return {"brightness": brightness.get_brightness()}
    if name == "power_control":
        if args.action == "lock":
            import ctypes

            if not ctypes.windll.user32.LockWorkStation():
                raise OSError("Windows rejected the lock request")
            return {"requested": "lock", "completion": "Windows confirmation unavailable"}
        executable = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/shutdown.exe"
        # /t 0 avoids the implicit forced-app-close behavior of positive shutdown timeouts.
        subprocess.run(
            [str(executable), "/r" if args.action == "restart" else "/s", "/t", "0"],
            shell=False,
            check=True,
            timeout=10,
        )
        return {"requested": args.action}
    if name == "switch_app":
        import win32gui
        import win32process

        matches = []
        names = {
            "code": "code.exe",
            "notepad": "notepad.exe",
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
        }

        def visit(handle, _):
            if win32gui.IsWindowVisible(handle):
                try:
                    pid = win32process.GetWindowThreadProcessId(handle)[1]
                    if psutil.Process(pid).name().lower() == names.get(args.app):
                        matches.append(handle)
                except psutil.Error:
                    pass

        win32gui.EnumWindows(visit, None)
        if not matches:
            raise ValueError("No visible approved app window found")
        win32gui.ShowWindow(matches[0], 9)
        win32gui.SetForegroundWindow(matches[0])
        return {"focused": args.app, "verified": win32gui.GetForegroundWindow() == matches[0]}
    if name == "run_python":
        from backend.app.security.process import python_runtime, run_bounded

        path = scoped_path(config.workspace_dir, args.path)
        text_file(path)
        if path.suffix != ".py" or hashlib.sha256(path.read_bytes()).hexdigest() != args.sha256:
            raise ValueError("Reviewed script hash does not match")
        return run_bounded(
            [python_runtime(), "-I", str(path), *args.arguments], path.parent, 30, stop_event
        )
    if name == "install_dependencies":
        import re

        from backend.app.security.process import python_runtime, run_bounded

        path = scoped_path(config.workspace_dir, args.path)
        if not path.is_dir():
            raise ValueError("Project directory does not exist")
        if args.manager == "npm":
            node = shutil.which("node")
            cli = Path(node).parent / "node_modules/npm/bin/npm-cli.js" if node else None
            if (
                not cli
                or not cli.is_file()
                or not all(
                    re.fullmatch(
                        r"(?:@[A-Za-z0-9_.-]+/)?[A-Za-z0-9][A-Za-z0-9_.-]*(?:@[0-9][A-Za-z0-9_.+-]*)?",
                        p,
                    )
                    for p in args.packages
                )
            ):
                raise ValueError("Node/npm and named registry packages are required")
            return run_bounded(
                [node, str(cli), "install", "--ignore-scripts", "--", *args.packages],
                path,
                180,
                stop_event,
            )
        if not all(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*(?:==[A-Za-z0-9_.+-]+)?", p)
            for p in args.packages
        ):
            raise ValueError("Only named PyPI packages or exact versions are allowed")
        env = path / ".venv"
        if env.is_symlink() or env.is_junction():
            raise ValueError("Virtual environment cannot be a link")
        if not env.exists():
            result = run_bounded([python_runtime(), "-m", "venv", str(env)], path, 60, stop_event)
            if result["exit_code"]:
                return result
        return run_bounded(
            [
                str(env / "Scripts/python.exe"),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--",
                *args.packages,
            ],
            path,
            180,
            stop_event,
        )
    raise ValueError("Unknown extended tool")
