import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from shell.usage.tracker import UsageTracker

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def tracker(tmp_path):
    return UsageTracker(tmp_path / "usage.db")


def test_unknown_provider_rejected(tracker):
    with pytest.raises(KeyError):
        tracker.record(provider="bogus", window="session", remaining=0.5)


def test_unknown_window_rejected(tracker):
    with pytest.raises(ValueError):
        tracker.record(provider="claude", window="lunar", remaining=0.5)


def test_remaining_out_of_range_rejected(tracker):
    with pytest.raises(ValueError):
        tracker.record(provider="claude", window="session", remaining=1.5)


def test_record_and_latest(tracker):
    reset = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    tracker.record(
        provider="claude", window="session", remaining=0.58,
        limit_desc="from /usage", reset_at=reset, note="manual check",
    )
    obs = tracker.latest("claude", "session")
    assert obs["remaining"] == 0.58
    assert obs["reset_at"] == reset


def test_status_computes_seconds_until_reset(tracker):
    reset = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    tracker.record(provider="claude", window="session", remaining=0.2, reset_at=reset)

    status = tracker.status(provider="claude")
    session = status["claude"]["windows"]["session"]
    assert session["observed"] is True
    assert 3500 < session["seconds_until_reset"] <= 3600


def test_status_marks_unobserved_window(tracker):
    status = tracker.status(provider="claude")
    assert status["claude"]["windows"]["weekly"]["observed"] is False


def test_status_flags_stub_providers(tracker):
    status = tracker.status(provider="codex")
    assert status["codex"]["status"] == "stub"
    assert status["codex"]["note"]


def test_session_events_logged(tracker):
    tracker.log_session_event("claude", "start", session_id="s1", cwd="/repo")
    tracker.log_session_event("claude", "end", session_id="s1", cwd="/repo")
    events = tracker.recent_sessions("claude")
    assert [e["event"] for e in events] == ["start", "end"]


def _run_cli(db_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "shell.usage.cli", "--db", str(db_path), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_record_and_status(tmp_path):
    db_path = tmp_path / "usage.db"

    out = _run_cli(
        db_path, "record", "--provider", "claude", "--window", "session",
        "--remaining", "0.4", "--reset", "2026-09-01T17:00:00+00:00",
    )
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["remaining"] == 0.4

    out = _run_cli(db_path, "status", "--provider", "claude")
    assert out.returncode == 0, out.stderr
    status = json.loads(out.stdout)
    assert status["claude"]["windows"]["session"]["remaining"] == 0.4


def test_cli_providers_lists_stub_status(tmp_path):
    out = _run_cli(tmp_path / "usage.db", "providers")
    assert out.returncode == 0, out.stderr
    providers = json.loads(out.stdout)
    assert providers["codex"]["status"] == "stub"
    assert providers["claude"]["status"] == "active"


def test_cli_rejects_unknown_provider(tmp_path):
    out = _run_cli(
        tmp_path / "usage.db", "record", "--provider", "bogus",
        "--window", "session", "--remaining", "0.1",
    )
    assert out.returncode != 0
