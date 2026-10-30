"""Explicit, repeatable model provisioning; never run at server startup."""

import hashlib
import json

import httpx

from backend.app.config import Settings


def provision():
    from huggingface_hub import snapshot_download
    from piper.download_voices import download_voice

    config = Settings()
    root = config.models_dir
    root.mkdir(exist_ok=True, parents=True)
    snapshot_download(
        "Systran/faster-whisper-tiny",
        local_dir=root / "whisper",
        allow_patterns=["model.bin", "config.json", "tokenizer.json", "vocabulary.*"],
    )
    (root / "piper").mkdir(exist_ok=True)
    download_voice(config.piper_voice, root / "piper")
    (root / "wake").mkdir(exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for name in ["melspectrogram.onnx", "embedding_model.onnx", "hey_jarvis_v0.1.onnx"]:
            destination = root / "wake" / name
            if not destination.is_file():
                response = client.get(
                    "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/" + name
                )
                response.raise_for_status()
                destination.write_bytes(response.content)
    manifest = {}
    for file in root.rglob("*"):
        if file.is_file() and ".cache" not in file.parts:
            manifest[str(file.relative_to(root))] = hashlib.sha256(file.read_bytes()).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Whisper, Piper, and Hey Jarvis models provisioned; SHA256 manifest saved.")


if __name__ == "__main__":
    provision()
