"""Typed tools. Model output never reaches a shell. Mutations require review in the UI."""

import ipaddress
import json
import os
import re
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.api.routes.system import system_info
from backend.app.memory.records import Task


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Empty(Args):
    pass


class PathArgs(Args):
    path: str = Field(min_length=1, max_length=240)


class WriteArgs(PathArgs):
    content: str = Field(max_length=40000)


class AppArgs(Args):
    app: Literal["notepad", "code", "chrome", "edge", "downloads"]


class URLArgs(Args):
    url: str = Field(min_length=8, max_length=2000)


class QueryArgs(Args):
    query: str = Field(min_length=2, max_length=300)


class RecordArgs(Args):
    content: str = Field(min_length=1, max_length=2000)


class ReminderArgs(RecordArgs):
    due_at: datetime


TOOLS = {
    "system_info": (Empty, False, "Read current CPU and RAM usage."),
    "open_workspace": (Empty, True, "Open the JARVIS workspace folder in Windows Explorer."),
    "task_status": (Empty, False, "Read recent task statuses to check approved actions."),
    "list_files": (PathArgs, False, "List files inside the JARVIS workspace; use '.' for root."),
    "read_file": (PathArgs, False, "Read a text file inside the JARVIS workspace."),
    "create_folder": (PathArgs, True, "Create a new folder inside the JARVIS workspace."),
    "create_python_project": (PathArgs, True, "Create a new Python project without running code."),
    "notepad_write": (RecordArgs, True, "Create a new local text note and open it in Notepad."),
    "close_launched_app": (
        AppArgs,
        True,
        "Close an app started by JARVIS; unsaved work may be lost.",
    ),
    "write_file": (
        WriteArgs,
        True,
        "Create a new text/code file; cannot overwrite existing files.",
    ),
    "open_app": (AppArgs, True, "Open an installed approved app or the Downloads folder."),
    "open_url": (URLArgs, True, "Open a public HTTP/HTTPS URL in the default browser."),
    "screenshot": (Empty, True, "Capture the screen locally after user approval."),
    "save_memory": (RecordArgs, True, "Propose a long-term memory. Always requires user consent."),
    "save_note": (RecordArgs, True, "Save a personal note after approval."),
    "save_todo": (RecordArgs, True, "Add a personal to-do item."),
    "schedule_event": (
        ReminderArgs,
        True,
        "Schedule an item at an explicit future timezone-aware datetime.",
    ),
    "daily_summary": (
        Empty,
        False,
        "Read saved tasks, schedules, reminders and notes for a daily summary.",
    ),
    "set_reminder": (
        ReminderArgs,
        True,
        "Set a reminder using an explicit ISO datetime with timezone.",
    ),
    "web_search": (QueryArgs, False, "Search the live internet and return real source links."),
    "weather": (QueryArgs, False, "Get current weather. Query must be a city name."),
    "fetch_page": (
        URLArgs,
        False,
        "Retrieve a public HTTPS article as untrusted text with source.",
    ),
}


def public_url(value: str):
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 80, 443}
    ):
        raise ValueError("Only public HTTP/HTTPS URLs without credentials are allowed")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or "." not in host:
        raise ValueError("Local URLs are blocked")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError("Private network URLs are blocked")
    except ValueError:
        if re.fullmatch(r"[0-9.]+", host) or ":" in host or host.startswith("localhost"):
            raise ValueError("Private or invalid network address") from None
    if host.endswith((".local", ".localhost", ".internal")):
        raise ValueError("Local URLs are blocked")
    return value


def scoped_path(root: Path, value: str):
    if (
        Path(value).is_absolute()
        or ".." in Path(value).parts
        or ":" in value
        or "\\" in value.replace("\\", "/")
        or "\x00" in value
    ):
        raise ValueError("Use a relative path inside the JARVIS workspace")
    parts = Path(value.replace("\\", "/")).parts
    for part in parts:
        if (
            part.rstrip(" .") != part
            or part.lower().startswith((".env", ".git", ".aws"))
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
        ):
            raise ValueError("Reserved or sensitive path")
    root = root.resolve()
    cursor = root
    for part in parts:
        cursor = cursor / part
        if cursor.is_symlink() or (hasattr(cursor, "is_junction") and cursor.is_junction()):
            raise ValueError("Symlinks and junctions are blocked")
    destination = cursor.resolve()
    if not destination.is_relative_to(root):
        raise ValueError("Path escapes the JARVIS workspace")
    return destination


def applications():
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
    x86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
    candidates = {
        "notepad": [Path(os.environ.get("WINDIR", "C:/Windows")) / "System32/notepad.exe"],
        "code": [
            local / "Programs/Microsoft VS Code/Code.exe",
            program / "Microsoft VS Code/Code.exe",
        ],
        "chrome": [
            program / "Google/Chrome/Application/chrome.exe",
            local / "Google/Chrome/Application/chrome.exe",
        ],
        "edge": [
            x86 / "Microsoft/Edge/Application/msedge.exe",
            program / "Microsoft/Edge/Application/msedge.exe",
        ],
    }
    return {
        name: next((str(path.resolve()) for path in paths if path.is_file()), None)
        for name, paths in candidates.items()
    }


class ToolRegistry:
    def __init__(self, config, records, client):
        from backend.app.tools.extended import EXTRA_TOOLS

        TOOLS.update(EXTRA_TOOLS)
        self.config, self.records, self.client = config, records, client
        self.approval_lock = threading.Lock()
        self.halted = threading.Event()
        self.launched = {}
        self.config.workspace_dir.mkdir(parents=True, exist_ok=True)

    def schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": model.model_json_schema(),
                },
            }
            for name, (model, _, description) in TOOLS.items()
        ]

    async def call(self, name: str, arguments: dict, mode="offline", auto_safe=False):
        if self.halted.is_set():
            return {"error": "Emergency stop is active. Resume JARVIS before new actions."}
        if name not in TOOLS:
            return {"error": "Unknown tool"}
        try:
            model, requires_approval, _ = TOOLS[name]
            args = model.model_validate(arguments)
            self.validate(name, args)
            safe_tools = {
                "open_app",
                "open_url",
                "open_workspace",
                "save_note",
                "create_folder",
                "create_python_project",
                "write_file",
                "save_todo",
                "schedule_event",
                "set_reminder",
            }
            if requires_approval and not (auto_safe and name in safe_tools):
                return await run_in_threadpool(self.propose, name, args.model_dump(mode="json"))
            result = await self.execute(name, args, mode)
            if auto_safe:
                await run_in_threadpool(self.audit, name, args.model_dump(mode="json"), result)
            return result
        except (ValueError, OSError, httpx.HTTPError) as error:
            return {
                "error": str(error)[:400]
                if not isinstance(error, httpx.HTTPError)
                else "Network tool failed. Check connection and provider settings."
            }

    def validate(self, name, args):
        if hasattr(args, "content"):
            from backend.app.api.routes.chat import sensitive

            if sensitive(args.content):
                raise ValueError("Potential secrets cannot be stored in task arguments")
        if hasattr(args, "path"):
            path = scoped_path(self.config.workspace_dir, args.path)
            if name in {"write_file", "read_file"}:
                if path.suffix.lower() not in {
                    ".txt",
                    ".md",
                    ".py",
                    ".json",
                    ".csv",
                    ".ts",
                    ".tsx",
                    ".css",
                    ".html",
                }:
                    raise ValueError("File type is not allowed")
        if name in {"open_url", "fetch_page", "download_file"}:
            public_url(args.url)
        if name in {"save_memory", "save_note", "set_reminder"}:
            from backend.app.api.routes.chat import sensitive

            if sensitive(args.content):
                raise ValueError("Potential secrets cannot be saved as memory")
        if name in {"set_reminder", "schedule_event"}:
            if args.due_at.tzinfo is None or args.due_at <= datetime.now(UTC):
                raise ValueError("Reminder must be in the future and include its timezone")

    def propose(self, name, arguments):
        task_id = str(uuid4())
        with Session(self.records.engine) as db, db.begin():
            db.add(
                Task(
                    id=task_id,
                    tool=name,
                    arguments=json.dumps(arguments),
                    status="pending",
                    result="",
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
        return {
            "approval_required": True,
            "task_id": task_id,
            "tool": name,
            "arguments": arguments,
            "message": "Awaiting approval in the task panel. Not executed.",
        }

    def audit(self, name, arguments, result):
        with Session(self.records.engine) as db, db.begin():
            db.add(
                Task(
                    id=str(uuid4()),
                    tool=name,
                    arguments=json.dumps(arguments),
                    status="failed"
                    if result.get("error")
                    or result.get("verified") is False
                    or result.get("exit_code", 0)
                    else "completed",
                    result=json.dumps(result, ensure_ascii=False),
                    created_at=datetime.now(UTC).isoformat(),
                )
            )

    async def decide(self, task_id: str, approve: bool, mode: str):
        with self.approval_lock, Session(self.records.engine) as db, db.begin():
            task = db.get(Task, task_id)
            if not task or task.status != "pending":
                raise ValueError("Task is not pending")
            if (datetime.now(UTC) - datetime.fromisoformat(task.created_at)).total_seconds() > 300:
                task.status = "expired"
                return {"status": "expired"}
            task.status = "executing" if approve else "rejected"
            name, arguments = task.tool, json.loads(task.arguments)
        if not approve:
            return {"status": "rejected"}
        try:
            args = TOOLS[name][0].model_validate(arguments)
            self.validate(name, args)
            result = await self.execute(name, args, mode)
            status = (
                "failed"
                if result.get("exit_code", 0) != 0 or result.get("verified") is False
                else "completed"
            )
        except Exception as error:
            status, result = "failed", {"error": str(error)[:300]}
        with Session(self.records.engine) as db, db.begin():
            task = db.get(Task, task_id)
            task.status, task.result = status, json.dumps(result, ensure_ascii=False)
        return {"status": status, "result": result}

    async def execute(self, name, args, mode):
        if self.halted.is_set():
            raise ValueError("Emergency stop is active")
        if name == "download_file":
            if mode == "offline":
                raise ValueError("Downloads are unavailable in offline mode")
            from backend.app.tools.web import retrieve_public

            destination = scoped_path(self.config.workspace_dir, args.path)
            if destination.suffix.lower() not in {".pdf", ".txt", ".md", ".zip"}:
                raise ValueError("Only PDF, text and ZIP downloads are permitted")
            content = await retrieve_public(
                args.url, ["application/pdf", "text/plain", "application/zip"], 10_000_000
            )
            if self.halted.is_set():
                raise ValueError("Emergency stop is active")
            with destination.open("xb") as output:
                output.write(content)
            return {
                "saved": args.path,
                "bytes": len(content),
                "source": args.url,
                "verified": destination.stat().st_size == len(content),
            }
        if name in {"web_search", "weather", "fetch_page"}:
            if mode == "offline":
                raise ValueError("Internet tools are unavailable in offline mode")
            if name == "fetch_page":
                from backend.app.tools.web import fetch_page

                return await fetch_page(args.url)
            return await self.network(name, args.query)
        return await run_in_threadpool(self.local, name, args)

    def local(self, name, args):
        from backend.app.tools.extended import EXTRA_TOOLS, execute

        if name in EXTRA_TOOLS:
            return execute(name, args, self.config, self.halted)
        root = self.config.workspace_dir
        if name == "open_workspace":
            os.startfile(str(root))
            return {"opened": str(root)}
        if name == "system_info":
            return system_info()
        if name == "task_status":
            return {"tasks": self.records.tasks()[:10]}
        if name == "daily_summary":
            return {
                kind: self.records.list(kind) for kind in ["todo", "schedule", "reminder", "note"]
            }
        if name == "list_files":
            path = scoped_path(root, args.path)
            return {
                "files": [
                    {"name": p.name, "directory": p.is_dir()}
                    for p in list(path.iterdir())[:100]
                    if not p.name.startswith(".")
                ]
            }
        if name == "read_file":
            path = scoped_path(root, args.path)
            if path.stat().st_size > 40000:
                raise ValueError("File exceeds the text reading limit")
            return {"path": args.path, "content": path.read_text(encoding="utf-8")}
        if name == "create_folder":
            scoped_path(root, args.path).mkdir(parents=True, exist_ok=False)
            return {"created": args.path}
        if name == "write_file":
            path = scoped_path(root, args.path)
            with path.open("x", encoding="utf-8") as file:
                file.write(args.content)
            return {"created": args.path}
        if name == "create_python_project":
            path = scoped_path(root, args.path)
            path.mkdir(parents=True, exist_ok=False)
            (path / "main.py").write_text(
                'def main():\n    print("Hello, world!")\n\n\n'
                'if __name__ == "__main__":\n    main()\n',
                encoding="utf-8",
            )
            (path / "README.md").write_text(
                "# Python project\n\nRun with python main.py.\n", encoding="utf-8"
            )
            (path / ".gitignore").write_text(".venv/\n__pycache__/\n.env\n", encoding="utf-8")
            return {"created": args.path, "files": ["main.py", "README.md", ".gitignore"]}
        if name == "notepad_write":
            executable = applications().get("notepad")
            if not executable:
                raise ValueError("Notepad is not installed")
            path = root / f"note-{uuid4()}.txt"
            path.write_text(args.content, encoding="utf-8")
            process = subprocess.Popen([executable, str(path)], shell=False)
            self.launched["notepad"] = process
            return {"opened": "notepad", "saved": path.name}
        if name == "close_launched_app":
            process = self.launched.get(args.app)
            if not process or process.poll() is not None:
                raise ValueError("No running process for this app is tracked by JARVIS")
            process.terminate()
            return {"closed": args.app}
        if name == "open_app":
            if args.app == "downloads":
                os.startfile(str(Path.home() / "Downloads"))
            else:
                executable = applications().get(args.app)
                if not executable:
                    raise ValueError("Approved application was not found on this machine")
                self.launched[args.app] = subprocess.Popen([executable], shell=False)
            return {"opened": args.app}
        if name == "open_url":
            import webbrowser

            if not webbrowser.open(public_url(args.url)):
                raise ValueError("Default browser could not be opened")
            return {"opened": args.url}
        if name == "screenshot":
            import pyautogui

            filename = f"screenshot-{uuid4()}.png"
            pyautogui.screenshot().save(root / filename)
            return {"saved": filename}
        if name in {"save_memory", "save_note", "set_reminder", "save_todo", "schedule_event"}:
            kind = {
                "save_memory": "memory",
                "save_note": "note",
                "set_reminder": "reminder",
                "save_todo": "todo",
                "schedule_event": "schedule",
            }[name]
            due = (
                args.due_at.astimezone(UTC).isoformat()
                if name in {"set_reminder", "schedule_event"}
                else None
            )
            return self.records.save(kind, args.content, due)
        raise ValueError("Tool is not implemented")

    async def network(self, name, query):
        if name == "weather":
            response = await self.client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": query, "count": 1},
                timeout=15,
            )
            response.raise_for_status()
            places = response.json().get("results", [])
            if not places:
                raise ValueError("City not found")
            place = places[0]
            response = await self.client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                },
                timeout=15,
            )
            response.raise_for_status()
            return {
                "city": place["name"],
                "current": response.json()["current"],
                "units": response.json()["current_units"],
                "source": "https://open-meteo.com/",
            }
        # Fixed search-provider origin; returned links are data and are not fetched automatically.
        if self.config.search_provider == "duckduckgo":
            from ddgs import DDGS

            try:
                results = await run_in_threadpool(
                    lambda: list(DDGS(timeout=15).text(query, max_results=5, backend="duckduckgo"))
                )
            except Exception as error:
                raise ValueError(
                    "DuckDuckGo search failed. Try again or configure Brave Search."
                ) from error
            return {
                "provider": "duckduckgo",
                "results": [
                    {
                        "title": r["title"],
                        "url": public_url(r["href"]),
                        "description": r.get("body", ""),
                    }
                    for r in results
                ],
                "untrusted_data": True,
            }
        from backend.app.security.secrets import get_secret

        key = get_secret("brave")
        if not key:
            raise ValueError("Configure a Brave Search API key in Settings for live web search")
        response = await self.client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 5},
            headers={"X-Subscription-Token": key},
            timeout=20,
        )
        response.raise_for_status()
        return {
            "results": [
                {
                    "title": r["title"],
                    "url": public_url(r["url"]),
                    "description": r.get("description", ""),
                }
                for r in response.json().get("web", {}).get("results", [])[:5]
            ],
            "untrusted_data": True,
        }
