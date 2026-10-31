# Verification report — 30 October 2026

## Final checks

- Python 3.14.5, Node 24.15.0, npm 11.12.1 on Windows 11.
- `python -m pytest -q --tb=short`: **33 passed**.
- `python -m ruff check backend`: **passed**.
- `python -m pip check`: **no broken requirements**.
- `npm run lint --prefix frontend`: React Hooks checks **passed**, zero warnings.
- `npm run build --prefix frontend`: TypeScript and Vite production build **passed** (about 390 kB JS / 123 kB gzip).
- PowerShell script syntax was checked. The packaging script was actually executed; using `npm.cmd` failed in this environment, so scripts were corrected to use the working PowerShell `npm` entry point.
- Python dependency locks and npm lockfile are saved; local speech assets have a SHA256 manifest.

## Phase 3 — real model evidence

Ollama was already installed and listening outside the execution sandbox. The original sandbox connection failure was not proof that Ollama was absent. The installed qwen2.5-coder model was left unchanged. A 523 MB qwen3:0.6b model was downloaded, then configured in `.env` with Offline mode.

A real browser form submission through React → Vite → FastAPI → Ollama returned **17 + 25 = 42**. The visible provider label was **ollama / qwen3:0.6b**. A separate actual API result is recorded in `phase3-live-result.json`; it returned **17 plus 25 is 42.**, with `fallback: false` and no persisted conversation.

The small model can still answer incorrectly. A previous coding-model arithmetic test returned 32, which prompted the model change rather than claiming that response was correct.

## Voice and wake evidence

Downloaded Whisper tiny multilingual, Piper en_US-lessac-medium, and openWakeWord Hey Jarvis/melspectrogram/embedding ONNX assets. No microphone was recorded during generated-audio tests.

- Piper generated **Hello Jarvis. What is seventeen plus twenty five?**
- After normal 16 kHz resampling, actual local Whisper transcribed **Hello Jarvis, what is 17 plus 25?**
- Hey Jarvis model silence inference: **0.0**.
- Generated **Hey Jarvis** utterance peak: **0.998001**, above the **0.55** configured threshold.
- An isolated actual HTTP integration server verified Piper synthesis → validated PCM WAV → Whisper transcription → real Ollama answer **17 plus 25 is 42.**

Testing caught a PyAV 19/faster-whisper incompatibility. The voice API now passes its already-validated mono 16 kHz PCM samples directly to Whisper, avoiding that decoder path. Native Piper output is resampled for the test; browser microphone frames are resampled by AudioWorklet.

Browser microphone permission remained pending; the request was stopped. Stop/mute visibly returned the UI to idle. A permission timeout and late-stream cleanup were added. Actual microphone capture, acoustic feedback, real-room wake accuracy, Tamil speech quality, and live cloud Realtime remain unverified.

## Agent and tools

The actual local model chose `create_folder` for **Create a new folder named Jarvis Demo in the workspace.** JARVIS returned an approval request instead of executing the model's action. The task was subsequently shown as rejected; no approval was forced.

Automated tests use isolated temporary databases/workspaces to verify approval before writes, rejection, one-time execution, no overwrite, path restrictions, blocked shell apps/scripts, record consent/CRUD, offline network errors, bounded agent loops, and private-DNS page rejection. Provider contract tests use HTTPX MockTransport; those are separate from the genuine local-model checks.

## Internet evidence

- DuckDuckGo returned real results for **Python official tutorial**, including Python's official tutorial URL.
- DNS-pinned/TLS-verified retrieval read `https://docs.python.org/3/tutorial/index.html` successfully.
- Open-Meteo returned an actual Chennai weather response with timestamp, temperature, units, and source.
- Brave key and OpenAI key were not configured. Their successful authenticated paths are not claimed.

## Desktop evidence

`build-desktop.ps1` produced `release/JarvisAI/JarvisAI.exe`, runtime assets, and bundled speech models. The executable's isolated `--smoke-test` returned `desktop_backend: ok`, `ui: ok`, and real local capability status. The full source launcher `--smoke-test --speech-test` also passed speech and Ollama checks. The final rebuilt executable also passed `--smoke-test --speech-test`: Piper audio was transcribed as **Hello Jarvis, what is 17 plus 25?**, and Ollama replied **17 + 25 = 42.** It reported Offline mode, local-whisper, qwen3:0.6b, and no persisted conversation. The complete Windows directory bundle is about 578 MB.

Optional training/quantization dependencies produced PyInstaller collection warnings; they are not used by the assistant runtime. A build is not proof of native GUI rendering, microphone permissions, signed installation, or clean-machine compatibility. WebView2 and Ollama remain machine prerequisites.

## Limits

This report is evidence for the implemented local personal-assistant paths, not a production certification. No arbitrary generated command was executed. No user file was overwritten/deleted. No private API key is present in these test records. UI and model behavior still require user acceptance on actual hardware.

## Native background expansion — 31 October 2026

The latest brief adds a tray application independent of dashboard/browser lifetime. Real native microphone capture opened at 16 kHz mono; short test bytes were discarded. The live background API reported standby with microphone_active=true and no error. Pause reported paused=true, microphone_active=false and level=0. Resume returned to standby with microphone_active=true. No human microphone audio was saved. Startup HKCU Run was installed and its fully quoted pythonw command read back; Windows was not logged out or rebooted for testing.

A real generated-audio native Conversation check produced:

```json
{"transcript":"Hello Jarvis, what is 17 plus 25?","native_agent_reply":"17 plus 25 is 42.","spoken_seconds":2.37,"provider":"ollama","model":"qwen3:0.6b"}
```

An earlier shorter generated phrase was transcribed incorrectly as 2017; decoding now uses beam size 5. The passing phrase does not establish general accent or multilingual reliability. The default remains lightweight multilingual Whisper tiny. all-minilm was downloaded; actual Ollama embedding produced two 384-dimensional vectors. Vectors stay in memory and approved facts remain in SQLite, with lexical fallback if local embeddings fail.

Added regression coverage includes Windows mutex duplicates, wake cooldown/follow-up states, exact spoken confirmation, privacy capture abort/tool halt, SHA-protected edits/backups, ZIP traversal rejection, bounded organization/rollback, mocked fixed power arguments, download approval/no-overwrite, and native memory consent. Shutdown/restart/lock, user-file deletion and arbitrary generated scripts were not executed during verification.

The new UI was inspected at desktop and mobile dimensions. Native voice settings expose real microphone devices and persisted wake/language/follow-up/volume settings. Dashboard controls target the background engine; closing the dashboard leaves the native process running. Development labels, checklists and extra explanatory cards were removed. Screenshot: screenshots/dashboard.png.

The windowless build's first launch exposed Uvicorn console logging assumptions; setting log_config=None and using a rotating file handler fixed it. A real packaged tray launch subsequently logged successful startup. Final bundle smoke writes background-smoke.json with tray visibility, backend state, paused state and microphone status. Only English installed system voices were observed. Edge Tamil speech and authenticated OpenAI paths remain unverified. Existing earlier reports describe the previous browser-first build; the new native phase report supersedes their startup/voice limitations where stated above.

Final verification: **44 backend tests passed**, Ruff passed, React Hooks/TypeScript lint passed, production build passed, and pip check reported no broken requirements. The final packaged executable reached real microphone standby with no error; Pause changed microphone_active to false. Evidence is stored in packaged-background-result.json. Its separate paused tray smoke reported tray=true, running=true, paused=true, microphone_active=false. The starting state in that short smoke reflects wake-model initialization; the subsequent live packaged check verifies those models loaded successfully.

The optional qwen3:1.7b download failed because an upstream redirect resolved to a non-public NAT64 address. It is not installed or selected. The verified default remains qwen3:0.6b; all-minilm is installed. No cloud/Tamil success is implied by these results.

Crash recovery was exercised on the actual source worker: only the verified process owning port 8000 was terminated. The supervisor restarted it, the process changed, and the replacement reported standby with microphone_active=true. A duplicate launcher invocation did not replace the working backend. See crash-recovery-result.json. This single failure test is not proof of long-term reliability or startup after a real login.

Additional live checks: the real local native agent selected create_folder, created an isolated generated test folder and returned a completed audit record; a filesystem check confirmed it. See native-tool-result.json. Optional online Tamil speech using ta-IN-PallaviNeural returned 30,096 bytes, decoded successfully with soundfile at 24 kHz for 5.02 seconds; no microphone was used. See tamil-speech-result.json. This supersedes the earlier unverified Edge synthesis statement; human Tamil/Tanglish recognition remains unverified and offline Tamil playback is still unavailable without a Tamil voice.

## Cloud backend and browser voice — 31 October 2026

The production project now deploys one Node.js Vercel Function, routing /api/* to the cloud handler. GET /api/health returns deployment=cloud and mode=online. POST /api/chat uses the verified model ID openai/gpt-4.1-mini through AI Gateway. Project-scoped OIDC is enabled; only the narrowly required identity setting changed. Automatic broad system-environment exposure was rejected by approval review and was not enabled. Runtime authentication reads the platform's rotating x-vercel-oidc-token request header first, with supported server credential fallbacks.

Cloud tests passed for routing, request bounds/validation, cross-origin rejection, desktop-tool isolation, mocked provider success, identity non-disclosure and mocked provider billing failure. React lint, TypeScript and production build passed. Real production GET health succeeded. A real production POST chat reached Gateway but was rejected for account verification/available credits; **no successful cloud generation is claimed**. The same actionable error was verified in the actual hosted chat UI. Account activation requires the owner to update Vercel AI Gateway settings.

The hosted UI switches to browser SpeechRecognition and synthesis, offers English/Tamil, and disables desktop records/tools/history controls. Actual hosted Start and Stop control states were inspected. This was not a completed human voice/STT→AI→speech conversation: the provider is blocked, and microphone/recognition acceptance remains hardware/browser dependent. Permission handling now uses the browser's onstart acknowledgment and a 30-second timeout. Screenshot: screenshots/cloud-backend.png. The desktop's existing local inference and microphone worker are independent and unchanged.
