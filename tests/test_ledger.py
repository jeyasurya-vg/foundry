import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from shell.ledger.ledger import Ledger

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.db")


def test_add_auto_queues(ledger):
    tid = ledger.add_ticket(brief="build thing", done_when="tests pass")
    assert ledger.get_ticket(tid)["state"] == "queued"


def test_full_happy_path(ledger):
    tid = ledger.add_ticket(brief="build thing", done_when="tests pass")

    ledger.claim(tid, assignee="engineer")
    assert ledger.get_ticket(tid)["state"] == "claimed"

    ledger.start_running(tid, session_id="sess-1")
    assert ledger.get_ticket(tid)["state"] == "running"

    ledger.checkpoint(tid, summary="step 1", artifacts=["a.py"], next_step="step 2")
    assert ledger.get_ticket(tid)["state"] == "checkpointed"

    ledger.resume_running(tid)
    assert ledger.get_ticket(tid)["state"] == "running"

    ledger.checkpoint(tid, summary="step 2", artifacts=["b.py"], next_step="-")
    ledger.advance_to_review(tid)
    assert ledger.get_ticket(tid)["state"] == "review"

    ledger.approve(tid)
    assert ledger.get_ticket(tid)["state"] == "done"

    checkpoints = ledger.list_checkpoints(tid)
    assert [c["step_no"] for c in checkpoints] == [1, 2]


def test_rejected_returns_to_queue(ledger):
    tid = ledger.add_ticket(brief="x", done_when="y")
    ledger.claim(tid, "engineer")
    ledger.start_running(tid)
    ledger.checkpoint(tid, "s", [], "n")
    ledger.advance_to_review(tid)

    ledger.reject(tid, reason="missing tests")
    assert ledger.get_ticket(tid)["state"] == "rejected"

    ledger.requeue(tid)
    assert ledger.get_ticket(tid)["state"] == "queued"


def test_quota_block_and_release(ledger):
    tid = ledger.add_ticket(brief="x", done_when="y")
    ledger.claim(tid, "engineer")
    ledger.start_running(tid)

    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    ledger.block_quota(tid, blocked_until=past)
    assert ledger.get_ticket(tid)["state"] == "blocked_quota"
    assert ledger.get_ticket(tid)["assignee"] is None

    released = ledger.release_expired_blocks()
    assert tid in released
    assert ledger.get_ticket(tid)["state"] == "queued"


def test_failure_retries_then_dies(ledger):
    tid = ledger.add_ticket(brief="x", done_when="y")

    for attempt in (1, 2):
        ledger.claim(tid, "engineer")
        ledger.start_running(tid)
        state = ledger.fail(tid)
        assert state == "queued"
        assert ledger.get_ticket(tid)["attempts"] == attempt

    ledger.claim(tid, "engineer")
    ledger.start_running(tid)
    state = ledger.fail(tid)
    assert state == "dead"
    assert ledger.get_ticket(tid)["attempts"] == 3


def test_illegal_transition_rejected(ledger):
    tid = ledger.add_ticket(brief="x", done_when="y", auto_queue=False)
    assert ledger.get_ticket(tid)["state"] == "draft"
    with pytest.raises(ValueError):
        ledger.claim(tid, "engineer")


def test_dependencies_gate_readiness(ledger):
    dep = ledger.add_ticket(brief="dep", done_when="d")
    tid = ledger.add_ticket(brief="needs dep", done_when="y", depends_on=[dep])

    ready = ledger.next_ready()
    assert ready["id"] == dep, "dependency-free ticket should be offered before its dependent"

    ledger.claim(dep, "engineer")
    ledger.start_running(dep)
    ledger.checkpoint(dep, "s", [], "n")
    ledger.advance_to_review(dep)
    ledger.approve(dep)

    ready = ledger.next_ready()
    assert ready["id"] == tid


def test_status_summary(ledger):
    ledger.add_ticket(brief="a", done_when="x")
    ledger.add_ticket(brief="b", done_when="x")
    summary = ledger.status_summary()
    assert summary == {"queued": 2}


def _run_cli(db_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "shell.ledger.cli", "--db", str(db_path), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_smoke(tmp_path):
    db_path = tmp_path / "ledger.db"

    out = _run_cli(db_path, "add", "--brief", "cli ticket", "--done-when", "it works")
    assert out.returncode == 0, out.stderr
    tid = json.loads(out.stdout)["id"]

    out = _run_cli(db_path, "next")
    assert out.returncode == 0, out.stderr
    packet = json.loads(out.stdout)
    assert packet["id"] == tid
    assert packet["state"] == "running"

    out = _run_cli(
        db_path, "checkpoint", tid,
        "--summary", "did it", "--artifacts", "[]", "--next-step", "-", "--final",
    )
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["state"] == "review"

    out = _run_cli(db_path, "status", tid)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["ticket"]["state"] == "review"
