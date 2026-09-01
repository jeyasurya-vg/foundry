import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_GATE = REPO_ROOT / "plugin" / "hooks" / "checkpoint_gate.py"
SESSION_LOG = REPO_ROOT / "plugin" / "hooks" / "session_log.py"


def _run_hook(script, payload, *argv):
    return subprocess.run(
        [sys.executable, str(script), *argv],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_checkpoint_gate_allows_plain_edit(tmp_path):
    result = _run_hook(
        CHECKPOINT_GATE,
        {"cwd": str(tmp_path), "session_id": "s1", "tool_name": "Edit", "tool_input": {}},
    )
    assert result.returncode == 0


def test_checkpoint_gate_blocks_after_uncommitted_checkpoint(tmp_path):
    commit_payload = {
        "cwd": str(tmp_path), "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'did a thing'"},
    }
    result = _run_hook(CHECKPOINT_GATE, commit_payload)
    assert result.returncode == 0  # the commit call itself is never blocked

    next_call = {
        "cwd": str(tmp_path), "session_id": "s1", "tool_name": "Edit", "tool_input": {},
    }
    result = _run_hook(CHECKPOINT_GATE, next_call)
    assert result.returncode == 2
    assert "checkpoint" in result.stderr.lower()


def test_checkpoint_gate_clears_after_checkpoint_call(tmp_path):
    commit_payload = {
        "cwd": str(tmp_path), "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'did a thing'"},
    }
    _run_hook(CHECKPOINT_GATE, commit_payload)

    checkpoint_payload = {
        "cwd": str(tmp_path), "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "python -m shell.ledger.cli checkpoint t-1 --summary x --next-step y"},
    }
    result = _run_hook(CHECKPOINT_GATE, checkpoint_payload)
    assert result.returncode == 0

    next_call = {
        "cwd": str(tmp_path), "session_id": "s1", "tool_name": "Edit", "tool_input": {},
    }
    result = _run_hook(CHECKPOINT_GATE, next_call)
    assert result.returncode == 0


def test_checkpoint_gate_tracks_sessions_independently(tmp_path):
    commit_payload = {
        "cwd": str(tmp_path), "session_id": "s1", "tool_name": "Bash",
        "tool_input": {"command": "git commit -m 'x'"},
    }
    _run_hook(CHECKPOINT_GATE, commit_payload)

    other_session_call = {
        "cwd": str(tmp_path), "session_id": "s2", "tool_name": "Edit", "tool_input": {},
    }
    result = _run_hook(CHECKPOINT_GATE, other_session_call)
    assert result.returncode == 0


def test_checkpoint_gate_survives_malformed_stdin(tmp_path):
    result = subprocess.run(
        [sys.executable, str(CHECKPOINT_GATE)],
        input="not json",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_session_log_writes_l1_entry_on_end(tmp_path):
    payload = {
        "cwd": str(tmp_path), "session_id": "s1",
        "transcript_path": str(tmp_path / "transcript.jsonl"),
    }
    result = _run_hook(SESSION_LOG, payload, "end")
    assert result.returncode == 0
    logs = list((tmp_path / "company" / "logs").glob("*.md"))
    assert len(logs) == 1
    assert "s1" in logs[0].read_text()


def test_session_log_does_not_write_on_start(tmp_path):
    payload = {"cwd": str(tmp_path), "session_id": "s1"}
    result = _run_hook(SESSION_LOG, payload, "start")
    assert result.returncode == 0
    assert not (tmp_path / "company" / "logs").exists()
