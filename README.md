# JARVIS AI

Local-first Windows personal voice assistant. Python 3.13+, FastAPI, React/TypeScript, SQLite, Ollama, faster-whisper, Piper, and openWakeWord. The app runs real model inference and typed tools; it never executes model-generated shell commands.

## Ready on this machine

Ollama was already installed. Qwen3 0.6B has now been downloaded and configured as the local default. The multilingual Whisper tiny model, Piper English voice, and Hey Jarvis ONNX models are downloaded under `models/`. `.env` defaults to Offline mode. The installed coding model remains untouched.

Real browser verification returned **17 + 25 = 42** with provider `ollama / qwen3:0.6b`. Piper audio was transcribed by local Whisper as **Hello Jarvis, what is 17 plus 25?** A synthetic Hey Jarvis utterance scored **0.998** against the 0.55 wake threshold; silence scored zero. These checks are not substitutes for testing your microphone, accent, room, and speakers.

## Start

For development, open two PowerShell terminals in this directory:

```powershell
# Terminal 1
.\scripts\start-backend.ps1
```

```powershell
# Terminal 2
.\scripts\start-frontend.ps1
```

Open [JARVIS](http://127.0.0.1:5173). Stop with Ctrl+C. If servers are already running, use the open preview instead of starting duplicates.

For the desktop app, stop the development backend on port 8000, then run:

```powershell
.\scripts\start-desktop.ps1
# Or the bundled Windows build:
.\release\JarvisAI\JarvisAI.exe
```

The complete `release/JarvisAI` folder is needed, including `_internal` and `models`. Ollama and a downloaded model must still be installed on a new computer. WebView2 must be installed for the native desktop window. The current executable is a development build with diagnostic console output, not a signed installer.

## Use voice

1. Keep Offline mode selected for local-only conversation.
2. Click **Start voice**, then grant microphone access in your browser. Speak a sentence; silence ends the utterance automatically, or click **Finish utterance**. Whisper transcribes, the selected AI replies, and Piper speaks the answer.
3. **Stop / mute** stops microphone tracks, wake streaming, playback, and the active voice request. Pending microphone permission times out after 30 seconds. Device failure/disconnection produces an error instead of silently continuing.
4. To use the wake word, opt in to **Continuous local listening for Hey Jarvis**, then start it. Audio is streamed only to the localhost wake engine. Say Hey Jarvis, pause briefly, then speak the command. It returns to wake listening after responding. Saying the wake phrase during playback interrupts it. Stop/mute always works.
5. Pick the microphone after permission reveals device names. Volume affects playback. The waveform is derived from real microphone frame levels.

English local STT/TTS has been tested with generated audio. Tamil recognition is selectable through multilingual Whisper, but Tamil accuracy is **not yet verified on user speech**. The downloaded Piper voice is English; Tamil playback requires an installed Tamil system voice or configured cloud Realtime. Only English system voices were observed on this machine. The UI does not claim that English Piper can speak Tamil.

Browser microphone permission remained pending during automated UI verification; the request was stopped. You must grant access for a real microphone test. Nothing records automatically on startup. Audio is processed in memory and is not saved by the voice routes. `data/voice-smoke.wav` contains generated test speech only.

## Chat, agent tools, and approvals

Type or speak in Conversation. Enable **agent tools** to let the model choose validated tools. The local 0.6B model is deliberately small for this machine; its reasoning and tool selection can be unreliable. Larger Ollama models can be selected in Settings when memory permits.

Read-only tools include CPU/RAM, workspace listing/text reading, recent task status, search, article retrieval, and weather. Side effects create a pending task with exact arguments. Review it in **Tasks**, then approve or reject it. Pending tasks expire after five minutes or a backend restart. Approval is one-time; failures are shown and never silently retried.

Supported approved actions:

- Open installed Notepad, VS Code, Chrome, Edge, or Downloads.
- Create a folder or a Python project; create new text/code files without overwriting.
- Create a text note and open it in Notepad.
- Open a public HTTP/HTTPS URL or save a screenshot locally.
- Close only an application process JARVIS itself launched and still tracks. Modern apps that detach into another process may not be closable this way; unrelated apps are never killed.
- Save a note, reminder, or explicitly approved long-term memory.

The **Actions** tab also exposes the same validated tools directly when a model misinterprets a request. File tools are limited to `data/workspace` in source mode. Absolute paths, traversal, alternate data streams, reserved names, symlinks/junctions, sensitive dotfiles, executables, and shell scripts are blocked. No file overwrite or deletion tool is exposed. Coding assistance can generate/explain files, but cannot run arbitrary code. This app is a local personal assistant, not an unrestricted desktop agent.

A multi-step read task is bounded to four model turns and six tool calls. A mutating task pauses at its first approval boundary. After approving it, ask JARVIS to check task status and continue; it will propose the next change for review.

## Memory and reminders

Conversation saving is off by default; opt in with **Save future turns locally**. History supports load/delete, with confirmation for deletion. New unsaved conversation context lives in browser memory. Approved memories, notes, reminders, settings, and task history live in SQLite. Use their tabs to view, edit, or delete them. Enable relevant memory retrieval in Settings if desired; retrieved facts are separately labeled untrusted data, not system instructions.

Common password/API-key patterns are blocked from records and skipped in conversation history, but detection is not comprehensive. Do not share secrets in chat. SQLite is plaintext. Deleting records does not securely erase disk sectors, OneDrive copies, or backups.

Due reminders appear as an in-app banner wherever you are in the workspace. JARVIS must be open for the banner to appear; missed reminders remain stored after restart. This release does not install an always-running Windows notification service.

## Internet and cloud options

Offline chat, Whisper, Piper, wake detection, records, and approved local tools require no network after provisioning. Internet tools fail explicitly in Offline mode.

For internet tasks, select Hybrid or Online for the conversation/action. DuckDuckGo search works without a key and returns actual source URLs; availability depends on the upstream service. Brave Search is selectable in Settings and requires its own key. Public article retrieval pins a validated public DNS address, verifies TLS for the original host, disables redirects, limits downloads to 1 MB, strips scripts/styles, and labels page text untrusted. Some sites, redirects, paywalls, or bot protections will therefore fail. Weather uses Open-Meteo with source attribution.

OpenAI chat and cloud Realtime require an API key and model access. Add the key in Settings; Windows Credential Manager stores it with no plaintext fallback. At startup a nonempty `.env` key takes precedence; otherwise the credential vault is used. Remove a key from `.env` when migrating it to the vault. Clearing a credential does not remove a key you separately put in `.env`. No API key is shipped to the frontend bundle.

**Cloud Realtime** uses microphone WebRTC audio, server VAD, natural speech, and interruption. It is unavailable in Offline mode. Its session has no computer tools; use the local voice pipeline for agent actions. Realtime code and missing-configuration handling are implemented, but a real cloud session has **not** been verified because no OpenAI key was supplied. Cloud audio is sent to OpenAI when explicitly started. A configured key alone does not establish billing or model access.

## Fresh Windows setup

Install Python 3.13+ and Node.js 22.12+ (tested here: Python 3.14.5, Node 24.15.0). Install and start [Ollama for Windows](https://ollama.com/download/windows), then:

```powershell
Set-Location 'C:\Users\bbebi\OneDrive\Documents\Jarvis AI'
.\scripts\setup.ps1
.\scripts\setup-ollama.ps1
.\scripts\setup-models.ps1
.\scripts\test.ps1
```

Setup preserves an existing `.env`. Speech-model downloads are explicit and never occur at application startup. Caches and temporary files stay in `.cache`. The Windows Store Python aliases failed here; the setup script found the real interpreter. You can pass it explicitly:

```powershell
.\scripts\setup.ps1 -PythonPath 'C:\Users\bbebi\AppData\Local\Python\pythoncore-3.14-64\python.exe'
```

If PowerShell blocks local scripts, invoke one with a process-only policy: `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1`. Do not permanently weaken execution policy.

`requirements.txt` contains backend foundations; `requirements-desktop.txt` adds speech, search, credential storage, automation, and packaging. `requirements.lock.txt` records the tested Python 3.14 environment. `frontend/package-lock.json` locks the npm graph. Run `python -m pip check` after installation. No virtual environment is portable between machines.

## Verify and build

```powershell
.\scripts\test.ps1
# Critical backend tests, Ruff, React Hooks lint, TypeScript and production build
.\scripts\build-desktop.ps1
# Creates release\JarvisAI\JarvisAI.exe plus runtime and speech assets
```

An isolated executable check (no microphone capture):

```powershell
$env:JARVIS_PORT = '8001'
$env:JARVIS_DATA_DIR = Join-Path $PWD '.cache\desktop-smoke-data'
$env:JARVIS_WORKSPACE_DIR = Join-Path $PWD '.cache\desktop-smoke-workspace'
.\release\JarvisAI\JarvisAI.exe --smoke-test --speech-test
Remove-Item Env:JARVIS_PORT, Env:JARVIS_DATA_DIR, Env:JARVIS_WORKSPACE_DIR
```

Source mode uses the repository data/workspace/models. The packaged app stores user data under `%LOCALAPPDATA%/JARVIS AI` and reads speech models alongside the executable. Model/credential downloads and personal databases are not embedded in frontend assets. Model SHA256 hashes are recorded in `models/manifest.json`; these record provisioned files, not independent publisher attestations.

The API binds only to loopback and rejects remote binding, untrusted browser origins, and Host headers. Local programs can still access it; it is not a multi-user authenticated service. Do not expose it through a tunnel. Custom backend ports require changing the development Vite proxy too. The packaged app permits its configured loopback origin automatically.

## Project layout

```text
backend/app/api/routes/       chat, voice, system, settings, tasks, records
backend/app/core/             bounded agent orchestration
backend/app/services/         provider adapters and explicit failover
backend/app/voice/            local Whisper and Piper engines
backend/app/tools/            validated local tools, research and SSRF defenses
backend/app/memory/           conversations, records, preferences, task journal
backend/app/security/         credential vault and bounded HTTP bodies
backend/tests/               critical security and behavior regression tests
backend/desktop.py           desktop launcher and isolated smoke mode
backend/setup_models.py      explicit model provisioning
backend/verify_voice.py       generated-audio/real-model integration check
frontend/src/                dashboard, voice, chat, workspace UI
frontend/public/pcm-worklet.js streaming 16 kHz microphone resampling
scripts/                    PowerShell setup, launch, test and build
models/                     downloaded offline assets; ignored by Git
data/                       personal SQLite/workspace; ignored by Git
release/                    desktop build; ignored by Git
```

See [the test report](docs/TEST_REPORT.md) and [phase status](docs/ROADMAP.md) for exact verification and remaining limitations. This is a working development release; hardware acceptance, cloud credentials, signed installation, and clean-machine QA are not implied by a successful build.

References: [Ollama Windows](https://docs.ollama.com/windows), [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling), [OpenAI Realtime](https://developers.openai.com/api/docs/guides/realtime), [Piper](https://github.com/OHF-Voice/piper1-gpl), [openWakeWord](https://github.com/dscripka/openWakeWord). Review upstream runtime licenses and voice/wake model cards before redistributing a desktop build.
