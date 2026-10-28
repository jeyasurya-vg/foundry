"""Integration tests for the bridge CLI's approval-point wiring: request-action building a
structured payload, and poll applying it / updating an agent's fence on resolution. The
network layer (TelegramBridge) is swapped for a fake via monkeypatching `cli._bridge` —
same dependency-injection spirit as `tests/test_bridge.py`'s `request_fn`, just one layer up
since `cli._bridge` is where a real `TelegramBridge` gets constructed.
"""

import argparse
from pathlib import Path

import shell.bridge.cli as cli
from shell.bridge.approvals import ApprovalStore
from shell.bridge.base import InboundCallback
from shell.ledger.projects import Portfolio

AGENT_MD = """---
name: release
description: Versioning, changelog assembly, tagging, and the PR.
tools: Read, Bash, Write
---

You own versioning, changelog assembly, tagging and the PR.
"""


class FakeBridge:
    def __init__(self):
        self.sent = []
        self.answered = []

    def send_approval_request(self, chat_id, text, request_id, thread_id=None):
        self.sent.append({"chat_id": chat_id, "text": text, "request_id": request_id, "thread_id": thread_id})

    def poll(self, timeout=25):
        return self._events

    def answer_callback(self, callback_query_id, text=None):
        self.answered.append(callback_query_id)


def _base_args(tmp_path, **overrides):
    ns = argparse.Namespace(
        db=str(tmp_path / "bridge.db"),
        ledger_db=str(tmp_path / "ledger.db"),
        repo_root=str(tmp_path),
        channels=str(tmp_path / "bridge_channels.json"),
        allow=["1"],
        chat_id="1", project=None, department=None, text="test", agent=None, ticket=None,
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


def _active_project(ledger_db, project_id="p-1"):
    portfolio = Portfolio(ledger_db)
    portfolio.add_project(project_id, name=project_id, brief="x")
    portfolio.greenlight(project_id, rationale="go")
    portfolio.start(project_id, rationale="go")
    portfolio.close()


def test_request_action_builds_ship_payload_and_sends(tmp_path, monkeypatch):
    _active_project(str(tmp_path / "ledger.db"))
    fake = FakeBridge()
    monkeypatch.setattr(cli, "_bridge", lambda args: fake)

    args = _base_args(
        tmp_path, kind="portfolio.ship", project="p-1", text="ship p-1?", agent="release",
        rationale="ready", version=None, tag=None, changelog_path=None,
        reason=None, revive_when=None,
    )
    cli.cmd_request_action(args)

    assert len(fake.sent) == 1
    request_id = fake.sent[0]["request_id"]

    store = ApprovalStore(str(tmp_path / "bridge.db"))
    row = store.get(request_id)
    assert row["action_kind"] == "portfolio.ship"
    assert row["agent"] == "release"
    import json
    assert json.loads(row["action_payload"])["project_id"] == "p-1"
    store.close()


def test_request_action_missing_rationale_fails_clearly(tmp_path, capsys, monkeypatch):
    fake = FakeBridge()
    monkeypatch.setattr(cli, "_bridge", lambda args: fake)
    args = _base_args(
        tmp_path, kind="portfolio.ship", project="p-1", text="ship p-1?", agent=None,
        rationale=None, version=None, tag=None, changelog_path=None,
        reason=None, revive_when=None,
    )
    import pytest
    with pytest.raises(SystemExit):
        cli.cmd_request_action(args)
    assert "rationale" in capsys.readouterr().err


def test_poll_applies_action_on_approval(tmp_path, monkeypatch):
    ledger_db = str(tmp_path / "ledger.db")
    _active_project(ledger_db)

    store = ApprovalStore(str(tmp_path / "bridge.db"))
    request_id = store.request(
        "ship p-1?", project_id="p-1", action_kind="portfolio.ship",
        action_payload='{"project_id": "p-1", "rationale": "ready"}',
    )
    store.close()

    fake = FakeBridge()
    fake._events = [InboundCallback(
        user_id="1", chat_id="1", request_id=request_id, decision="approved",
        remember=False, callback_query_id="cbq-1",
    )]
    monkeypatch.setattr(cli, "_bridge", lambda args: fake)

    args = _base_args(tmp_path, timeout=25)
    cli.cmd_poll(args)

    assert fake.answered == ["cbq-1"]
    portfolio = Portfolio(ledger_db)
    assert portfolio.get_project("p-1")["state"] == "shipped"
    portfolio.close()


def test_poll_denied_does_not_apply_action(tmp_path, monkeypatch):
    ledger_db = str(tmp_path / "ledger.db")
    _active_project(ledger_db)

    store = ApprovalStore(str(tmp_path / "bridge.db"))
    request_id = store.request(
        "ship p-1?", project_id="p-1", action_kind="portfolio.ship",
        action_payload='{"project_id": "p-1", "rationale": "ready"}',
    )
    store.close()

    fake = FakeBridge()
    fake._events = [InboundCallback(
        user_id="1", chat_id="1", request_id=request_id, decision="denied",
        remember=False, callback_query_id="cbq-1",
    )]
    monkeypatch.setattr(cli, "_bridge", lambda args: fake)

    cli.cmd_poll(_base_args(tmp_path, timeout=25))

    portfolio = Portfolio(ledger_db)
    assert portfolio.get_project("p-1")["state"] == "active"
    portfolio.close()


def test_poll_remember_updates_agent_fence(tmp_path, monkeypatch):
    agents_dir = Path(tmp_path) / "plugin" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "release.md").write_text(AGENT_MD, encoding="utf-8")

    store = ApprovalStore(str(tmp_path / "bridge.db"))
    request_id = store.request("push to main?", agent="release")
    store.close()

    fake = FakeBridge()
    fake._events = [InboundCallback(
        user_id="1", chat_id="1", request_id=request_id, decision="approved",
        remember=True, callback_query_id="cbq-1",
    )]
    monkeypatch.setattr(cli, "_bridge", lambda args: fake)

    cli.cmd_poll(_base_args(tmp_path, timeout=25))

    text = (agents_dir / "release.md").read_text(encoding="utf-8")
    assert "push to main?" in text
    assert "remembered:" in text


def test_poll_without_remember_does_not_touch_fence(tmp_path, monkeypatch):
    agents_dir = Path(tmp_path) / "plugin" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "release.md").write_text(AGENT_MD, encoding="utf-8")

    store = ApprovalStore(str(tmp_path / "bridge.db"))
    request_id = store.request("push to main?", agent="release")
    store.close()

    fake = FakeBridge()
    fake._events = [InboundCallback(
        user_id="1", chat_id="1", request_id=request_id, decision="approved",
        remember=False, callback_query_id="cbq-1",
    )]
    monkeypatch.setattr(cli, "_bridge", lambda args: fake)

    cli.cmd_poll(_base_args(tmp_path, timeout=25))

    text = (agents_dir / "release.md").read_text(encoding="utf-8")
    assert "remembered:" not in text
