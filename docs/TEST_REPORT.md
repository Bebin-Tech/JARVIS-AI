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
