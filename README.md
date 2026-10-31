# JARVIS AI

Local-first Windows personal voice assistant. Python 3.13+, FastAPI, React/TypeScript, SQLite, Ollama, faster-whisper, Piper, and openWakeWord. The app runs real model inference and typed tools; it never executes model-generated shell commands.

## Ready on this machine

Ollama was already installed. Qwen3 0.6B has now been downloaded and configured as the local default. The multilingual Whisper tiny model, Piper English voice, and Hey Jarvis ONNX models are downloaded under `models/`. `.env` defaults to Offline mode. The installed coding model remains untouched.

Real browser verification returned **17 + 25 = 42** with provider `ollama / qwen3:0.6b`. Piper audio was transcribed by local Whisper as **Hello Jarvis, what is 17 plus 25?** A synthetic Hey Jarvis utterance scored **0.998** against the 0.55 wake threshold; silence scored zero. These checks are not substitutes for testing your microphone, accent, room, and speakers.

## Always-ready Windows assistant

Run the native tray application independently of a browser or VS Code:

```powershell
.\scripts\start-background.ps1
.\scripts\enable-startup.ps1
.\.venv\Scripts\python.exe -m desktop.main --startup-status
```

Startup is registered for the current Windows user **after login**, once the user session and audio devices are available. It is enabled on this machine. Keep this project and its virtual environment available at their registered paths. The supervisor restarts a crashed worker with backoff, stops after five crashes in ten minutes, and uses Windows named mutexes to prevent duplicate supervisors/workers.

The tray menu provides Open dashboard, Start conversation, Pause/privacy, Resume, Emergency stop, and Exit. Closing the dashboard leaves the native microphone worker running. Exit stops both the microphone and backend. Pause aborts microphone capture, clears queued audio, stops playback, cancels the active AI request, and prevents new tool executions. A script already started is stopped with its child processes; an OS action already dispatched cannot be undone.

Say **Hey Jarvis**, wait for the acknowledgment, then speak. Silence ends the utterance. Follow-up conversation stays open for 15 seconds before returning to standby. Saying Hey Jarvis during speech interrupts playback. Standby wake detection is local; no continuous cloud audio stream runs. Microphone frames are processed in memory and discarded. Logs contain status/error information, not voice transcripts. Approved tool arguments/results are recorded in the SQLite task journal.

Open [the dashboard](http://127.0.0.1:8000) or the development preview at [port 5173](http://127.0.0.1:5173). Voice options controls the native microphone, language, wake threshold, follow-up timeout, and speech volume. A lower wake threshold is more sensitive. Start/Pause buttons control the tray worker when it is running. Browser voice remains available when running the development API without the native worker.

English local recognition and speech passed generated-audio tests. Multilingual Whisper supports selectable Tamil/auto recognition; Tamil/Tanglish accuracy on your speech has not been verified. The installed Piper voice is English. Offline Tamil playback needs an installed Tamil SAPI voice (none found here). Online/hybrid native speech can use optional Edge Tamil TTS; generated Tamil speech and native-library decoding passed; your speech/accent remains unverified. Cloud Realtime is a separate browser session requiring an OpenAI key; it has no computer tools and must be explicitly started.

## Tools and permissions

The agent chooses typed tools and observes their actual results. Each request is bounded to four model turns/six tool calls. Native voice automatically performs routine actions such as opening approved applications/websites, reading permitted files, creating new workspace files/projects, and saving notes/reminders/to-do items. The browser agent retains review for mutations. Long-term memories always require consent.

High-impact actions create a pending task with exact arguments: edits, moves, copies, ZIP extraction/compression, recycling files, downloads, scripts, package installs, volume/brightness, lock/restart/shutdown, and application closing. Review Tasks or use the exact spoken confirmation phrase. Shutdown requires **confirm shutdown**, restart requires **confirm restart**; a generic yes is rejected. Approvals expire after five minutes, cannot be replayed, and are invalidated on backend restart. Native conversation continues after a confirmed action using the execution result.

File operations are scoped to the JARVIS workspace, with explicit Downloads access for the expanded file tools. Absolute paths, traversal, Windows reserved names, alternate streams, sensitive dotfiles, and symlink/junction escapes are blocked. New files never overwrite existing files. Edits require a matching reviewed SHA256 and retain a sibling backup. Organize moves at most 100 matching files/100 MB into a new folder and rolls back on interruption where possible. Recycle uses the Windows Recycle Bin. ZIP extraction rejects traversal, links, and decompression bombs.

Approved Python execution verifies the script hash, runs without a shell, bounds time/output, and supports emergency termination. It runs with your Windows user permissions; **it is not an OS sandbox**. Review code before approval. Pip installs use a project-local virtual environment; npm installs disable lifecycle scripts. Download accepts a reviewed final public HTTPS URL and PDF/text/ZIP files up to 10 MB; it pins validated public DNS, checks TLS for the original host, blocks redirects and never executes downloads. Approval is your trust decision about the source.

System tools report actual CPU, memory, disk, and battery data. Supported hardware can expose brightness and Windows master volume. Application control is limited to installed approved apps; closing is limited to tracked processes. No credential extraction, arbitrary shell command, administrator elevation, security disabling, email/message sending, or unrestricted GUI control is exposed. External calendar integration is not connected; local schedules are available.

## Memory, productivity, and research

SQLite stores approved memories, notes, to-do items, schedules, reminders, settings, and the task journal. The dashboard supports viewing/editing/deleting records and opt-in browser conversation history. Native short-term conversation context remains in memory and is not automatically persisted. Enable memory retrieval in Settings to use approved facts. `all-minilm` produces local semantic embeddings; lexical retrieval is the explicit fallback if embeddings fail. Facts are labeled untrusted data, separate from instructions.

The tray worker announces due reminders/schedules while in standby, once per running session. Paused or exited JARVIS is silent; missed items remain stored. The daily summary tool reads saved productivity records. There is no connected external calendar account.

Offline mode uses Ollama, Whisper, Piper and local tools. Hybrid preserves conversation context when falling back from cloud to Ollama. Internet tools fail explicitly offline. Live research supports DuckDuckGo/Brave search, bounded public article retrieval, Open-Meteo weather, and source links. Brave and OpenAI require configured keys in Windows Credential Manager or backend `.env`; no key is shipped in the frontend. No authenticated cloud session is claimed without a real key.

The local 0.6B default fits this computer but can misinterpret speech and tool requests. Treat tool results as authoritative and use Actions when a request is misunderstood. A stronger optional Ollama model can be selected when memory permits.

## Development and packaging

Do not start a second backend on port 8000 while the tray worker runs. For frontend development only:

```powershell
.\scripts\start-frontend.ps1
```

For browser-only development, exit the tray app, then start backend and frontend in separate terminals:

```powershell
.\scripts\start-backend.ps1
.\scripts\start-frontend.ps1
```

Build the native tray bundle:

```powershell
.\scripts\build-background.ps1
.\release\JarvisBackground\JarvisBackground.exe --supervise
```

Keep the entire `release/JarvisBackground` directory, including `_internal` and `models`. This is an unsigned Windows directory bundle, not a signed installer. Ollama and a downloaded language model remain prerequisites. The source startup command remains registered until explicitly replaced with the bundled executable's `--install-startup` option. Packaged writable data defaults to `%LOCALAPPDATA%/JARVIS AI`; source mode uses `data/`.

To stop or disable startup:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/background/command -Method Post -ContentType application/json -Body '{"action":"exit"}'
.\scripts\disable-startup.ps1
```

See [the phase report](docs/ROADMAP.md) and [verification evidence](docs/TEST_REPORT.md). Windows login/reboot, room/accent wake reliability, Tamil/Tanglish speech, authenticated cloud Realtime and clean-machine installation still require acceptance testing.

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
backend/app/security/         credential vault, bounded processes and HTTP bodies
backend/tests/               critical security and behavior regression tests
desktop/                    native tray, wake microphone, startup, supervisor
backend/desktop.py           optional dashboard-window launcher
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
