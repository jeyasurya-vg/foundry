import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from shell.bridge.allowlist import is_allowed
from shell.bridge.approvals import ApprovalStore
from shell.bridge.base import InboundCallback, InboundMessage
from shell.bridge.env import load_dotenv
from shell.bridge.telegram import TelegramBridge

REPO_ROOT = Path(__file__).resolve().parents[1]


# -- allowlist ----------------------------------------------------------------

def test_is_allowed_matches_string_or_int():
    assert is_allowed(965676894, ["965676894"]) is True
    assert is_allowed("965676894", [965676894]) is True


def test_is_allowed_rejects_unknown_id():
    assert is_allowed(111, ["965676894"]) is False


def test_is_allowed_empty_allowlist_rejects_everyone():
    assert is_allowed(965676894, []) is False


# -- env loader -----------------------------------------------------------

def test_load_dotenv_reads_file_without_overwriting_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=from_file\nBAR=also_from_file\n# a comment\n\nBAZ=quoted\n".replace(
        "BAZ=quoted", 'BAZ="quoted value"'
    ))
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAR", "already_set")
    monkeypatch.delenv("BAZ", raising=False)

    load_dotenv(env_file)

    import os
    assert os.environ["FOO"] == "from_file"
    assert os.environ["BAR"] == "already_set"  # not overwritten
    assert os.environ["BAZ"] == "quoted value"


def test_load_dotenv_missing_file_is_a_noop(tmp_path):
    load_dotenv(tmp_path / "nope.env")  # must not raise


# -- approvals ------------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    return ApprovalStore(tmp_path / "bridge.db")


def test_request_starts_pending(store):
    rid = store.request("delete the old branch?", ticket_id="t-1")
    row = store.get(rid)
    assert row["status"] == "pending"
    assert row["ticket_id"] == "t-1"


def test_resolve_approved(store):
    rid = store.request("push to main?")
    row = store.resolve(rid, "approved", remember=True)
    assert row["status"] == "approved"
    assert row["remember"] == 1
    assert row["resolved_at"] is not None


def test_resolve_rejects_bad_decision(store):
    rid = store.request("x")
    with pytest.raises(ValueError):
        store.resolve(rid, "maybe")


def test_resolve_unknown_request(store):
    with pytest.raises(KeyError):
        store.resolve("nonexistent", "approved")


def test_resolve_twice_raises(store):
    rid = store.request("x")
    store.resolve(rid, "denied")
    with pytest.raises(ValueError):
        store.resolve(rid, "approved")


def test_list_pending_excludes_resolved(store):
    a = store.request("a")
    b = store.request("b")
    store.resolve(a, "approved")
    assert [r["request_id"] for r in store.list_pending()] == [b]


def test_request_stores_optional_agent_and_action_fields(store):
    rid = store.request(
        "ship it?", project_id="p-1", agent="engineer",
        action_kind="portfolio.ship", action_payload='{"rationale": "go"}',
    )
    row = store.get(rid)
    assert row["agent"] == "engineer"
    assert row["action_kind"] == "portfolio.ship"
    assert row["action_payload"] == '{"rationale": "go"}'


def test_request_without_optional_fields_leaves_them_null(store):
    rid = store.request("x")
    row = store.get(rid)
    assert row["agent"] is None
    assert row["action_kind"] is None
    assert row["action_payload"] is None


def test_list_remembered(store):
    a = store.request("a")
    store.request("b")
    store.resolve(a, "approved", remember=True)
    assert [r["request_id"] for r in store.list_remembered()] == [a]


# -- TelegramBridge (fully mocked HTTP, no real network) ----------------------

def test_telegram_bridge_requires_nonempty_allowlist():
    with pytest.raises(ValueError):
        TelegramBridge(allowlist=[])


def test_telegram_bridge_refuses_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    bridge = TelegramBridge(allowlist=["1"], request_fn=lambda url, payload: {})
    with pytest.raises(RuntimeError):
        bridge.send("1", "hi")


def test_telegram_bridge_send_calls_sendmessage(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    captured = {}

    def fake_request(url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {"ok": True}

    bridge = TelegramBridge(allowlist=["1"], request_fn=fake_request)
    bridge.send("1", "hello")
    assert "sendMessage" in captured["url"]
    assert captured["payload"] == {"chat_id": "1", "text": "hello"}


def test_telegram_bridge_approval_request_includes_three_buttons(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    captured = {}

    def fake_request(url, payload):
        captured["payload"] = payload
        return {"ok": True}

    bridge = TelegramBridge(allowlist=["1"], request_fn=fake_request)
    bridge.send_approval_request("1", "push to main?", "req-1")

    buttons = captured["payload"]["reply_markup"]["inline_keyboard"][0]
    labels = [b["text"] for b in buttons]
    assert labels == ["Approve", "Deny", "Approve and remember"]
    assert buttons[0]["callback_data"] == "req-1:approved:0"
    assert buttons[2]["callback_data"] == "req-1:approved:1"


def test_telegram_bridge_send_without_thread_id_omits_it(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    captured = {}
    bridge = TelegramBridge(allowlist=["1"], request_fn=lambda url, p: captured.update(payload=p) or {})
    bridge.send("1", "hello")
    assert "message_thread_id" not in captured["payload"]


def test_telegram_bridge_send_with_thread_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    captured = {}
    bridge = TelegramBridge(allowlist=["1"], request_fn=lambda url, p: captured.update(payload=p) or {})
    bridge.send("1", "hello", thread_id=7)
    assert captured["payload"]["message_thread_id"] == 7


def test_telegram_bridge_approval_request_with_thread_id(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    captured = {}
    bridge = TelegramBridge(allowlist=["1"], request_fn=lambda url, p: captured.update(payload=p) or {})
    bridge.send_approval_request("1", "push to main?", "req-1", thread_id=7)
    assert captured["payload"]["message_thread_id"] == 7


def test_telegram_bridge_poll_parses_message(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def fake_request(url, payload):
        return {"result": [{
            "update_id": 100,
            "message": {"from": {"id": 965676894}, "chat": {"id": 965676894}, "text": "hi"},
        }]}

    bridge = TelegramBridge(allowlist=["965676894"], request_fn=fake_request)
    events = bridge.poll()
    assert len(events) == 1
    assert isinstance(events[0], InboundMessage)
    assert events[0].text == "hi"


def test_telegram_bridge_poll_drops_messages_not_on_allowlist(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def fake_request(url, payload):
        return {"result": [{
            "update_id": 100,
            "message": {"from": {"id": 111}, "chat": {"id": 111}, "text": "hi"},
        }]}

    bridge = TelegramBridge(allowlist=["965676894"], request_fn=fake_request)
    assert bridge.poll() == []


def test_telegram_bridge_poll_advances_offset(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    calls = []

    def fake_request(url, payload):
        calls.append(payload)
        return {"result": [{
            "update_id": 42,
            "message": {"from": {"id": 1}, "chat": {"id": 1}, "text": "hi"},
        }]}

    bridge = TelegramBridge(allowlist=["1"], request_fn=fake_request)
    bridge.poll()
    bridge.poll()
    assert "offset" not in calls[0]
    assert calls[1]["offset"] == 43


def test_telegram_bridge_poll_parses_callback(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def fake_request(url, payload):
        return {"result": [{
            "update_id": 1,
            "callback_query": {
                "id": "cbq-1", "from": {"id": 1},
                "message": {"chat": {"id": 1}},
                "data": "req-1:approved:1",
            },
        }]}

    bridge = TelegramBridge(allowlist=["1"], request_fn=fake_request)
    events = bridge.poll()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, InboundCallback)
    assert event.request_id == "req-1"
    assert event.decision == "approved"
    assert event.remember is True


# -- CLI smoke tests (no network: missing token/allowlist paths only) --------

def _run_cli(*args, env=None, cwd_tmp_path=None):
    import os
    full_env = os.environ.copy()
    full_env.pop("TELEGRAM_BOT_TOKEN", None)
    full_env.pop("FOUNDRY_BRIDGE_ALLOWLIST", None)
    full_env["PYTHONPATH"] = str(REPO_ROOT)
    if env:
        full_env.update(env)
    # Run from a directory with no .env of its own — the real repo-root .env (this
    # machine's actual bot token) must never leak into a test asserting the no-token path.
    cwd = cwd_tmp_path or Path(tempfile.mkdtemp())
    return subprocess.run(
        [sys.executable, "-m", "shell.bridge.cli", *args],
        capture_output=True, text=True, cwd=cwd, env=full_env,
    )


def test_cli_send_without_allowlist_fails_clearly(tmp_path):
    result = _run_cli("--db", str(tmp_path / "bridge.db"), "send", "--chat-id", "1", "--text", "hi")
    assert result.returncode == 1
    assert "allowlist" in result.stderr.lower()


def test_cli_send_without_token_fails_clearly(tmp_path):
    result = _run_cli(
        "--db", str(tmp_path / "bridge.db"), "--allow", "1", "send",
        "--chat-id", "1", "--text", "hi",
    )
    assert result.returncode == 1
    assert "TELEGRAM_BOT_TOKEN" in result.stderr


def test_cli_list_pending_smoke(tmp_path):
    result = _run_cli("--db", str(tmp_path / "bridge.db"), "list-pending")
    assert result.returncode == 0
    assert result.stdout.strip() == "[]"
