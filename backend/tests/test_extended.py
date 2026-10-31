import hashlib
import threading
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.app.tools.extended import EditArgs, OrganizeArgs, PowerArgs, TransferArgs, execute
from desktop.voice import NativeVoice


def test_edit_requires_reviewed_hash_and_preserves_backup(tmp_path):
    config = SimpleNamespace(workspace_dir=tmp_path)
    file = tmp_path / "code.py"
    file.write_text("old", encoding="utf-8")
    args = EditArgs(path="code.py", content="new", sha256="0" * 64)
    with pytest.raises(ValueError, match="changed"):
        execute("edit_file", args, config)
    assert file.read_text() == "old"
    args.sha256 = hashlib.sha256(file.read_bytes()).hexdigest()
    result = execute("edit_file", args, config)
    assert file.read_text() == "new"
    assert (tmp_path / result["backup"]).read_text() == "old"


def test_zip_traversal_rejected_before_destination_creation(tmp_path):
    with zipfile.ZipFile(tmp_path / "bad.zip", "w") as archive:
        archive.writestr("../outside.txt", "bad")
    with pytest.raises(ValueError):
        execute(
            "extract_zip",
            TransferArgs(path="bad.zip", destination="out"),
            SimpleNamespace(workspace_dir=tmp_path),
        )
    assert not (tmp_path / "out").exists()


def test_organize_is_bounded_and_rolls_back_on_stop(tmp_path):
    config = SimpleNamespace(workspace_dir=tmp_path)
    (tmp_path / "one.pdf").write_bytes(b"pdf")
    (tmp_path / "keep.txt").write_text("keep")
    event = threading.Event()
    event.set()
    with pytest.raises(ValueError, match="Emergency"):
        execute("organize_files", OrganizeArgs(path=".", destination="cancelled"), config, event)
    assert (tmp_path / "one.pdf").exists()
    event.clear()
    result = execute("organize_files", OrganizeArgs(path=".", destination="pdfs"), config, event)
    assert result["verified"]
    assert (tmp_path / "pdfs/one.pdf").exists()
    assert (tmp_path / "keep.txt").exists()


def test_power_only_fixed_arguments_mocked(monkeypatch):
    run = Mock()
    monkeypatch.setattr("backend.app.tools.extended.subprocess.run", run)
    execute("power_control", PowerArgs(action="restart"), None)
    assert run.call_args.args[0][1:] == ["/r", "/t", "0"]
    assert run.call_args.kwargs["shell"] is False


def test_privacy_pause_aborts_input_and_halts_new_tools(monkeypatch):
    from backend.app.config import Settings

    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=Settings(_env_file=None), tools=SimpleNamespace(halted=threading.Event())
        )
    )
    voice = NativeVoice(app, None)
    monkeypatch.setattr("desktop.voice.sd.stop", lambda: None)
    stream = Mock(active=True)
    voice.stream = stream
    voice.frames = [b"private"]
    voice.queue.put(b"private")
    voice.pause()
    assert voice.status()["microphone_active"] is False
    assert voice.frames == []
    assert voice.queue.get_nowait() == b""
    assert app.state.tools.halted.is_set()
    stream.abort.assert_called_once()
    voice.resume()
    assert not app.state.tools.halted.is_set()
    voice.pool.shutdown()
