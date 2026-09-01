from dataclasses import dataclass

import pytest

from shell.runners.anthropic_api import AnthropicAPIRunner
from shell.runners.attended import AttendedRunner
from shell.runners.backoff import Backoff, delay_seconds
from shell.runners.base import ResumePacket
from shell.runners.quota import classify
from shell.runners.stubs import BedrockRunner, LocalRunner, OpenAIRunner, VertexRunner


@dataclass
class FakeProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


PACKET = ResumePacket(ticket_id="t-1", brief="build x", done_when="tests pass")


# -- attended runner -----------------------------------------------------------

def test_attended_runner_refuses_to_run():
    runner = AttendedRunner()
    assert runner.headroom() is True
    assert runner.busy() is False
    with pytest.raises(RuntimeError):
        runner.run(PACKET)


# -- stub runners ----------------------------------------------------------

@pytest.mark.parametrize("cls", [BedrockRunner, VertexRunner, OpenAIRunner, LocalRunner])
def test_stub_runners_refuse_clearly(cls):
    runner = cls()
    assert runner.headroom() is False
    result = runner.run(PACKET)
    assert result.ok is False
    assert "not implemented" in result.error


# -- anthropic-api runner ----------------------------------------------------

def test_anthropic_runner_refuses_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner = AnthropicAPIRunner(cwd=str(tmp_path))
    assert runner.headroom() is False
    result = runner.run(PACKET)
    assert result.ok is False
    assert "ANTHROPIC_API_KEY" in result.error


def test_anthropic_runner_builds_expected_argv(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    captured = {}

    def fake_invoke(argv, env, cwd):
        captured["argv"] = argv
        return FakeProcess(returncode=0, stdout='{"ok": true}')

    runner = AnthropicAPIRunner(cwd=str(tmp_path), invoke=fake_invoke)
    assert runner.headroom() is True

    packet = ResumePacket(
        ticket_id="t-1", brief="build x", done_when="tests pass",
        next_step="write the function", session_id="sess-123",
    )
    result = runner.run(packet)

    assert result.ok is True
    argv = captured["argv"]
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "--resume" in argv and "sess-123" in argv
    assert any("t-1" in a for a in argv)


def test_anthropic_runner_detects_quota_exhaustion(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")

    def fake_invoke(argv, env, cwd):
        return FakeProcess(returncode=1, stderr="Error: usage limit reached, try again later")

    runner = AnthropicAPIRunner(cwd=str(tmp_path), invoke=fake_invoke)
    result = runner.run(PACKET)
    assert result.ok is False
    assert result.quota_exhausted is True


def test_anthropic_runner_reports_plain_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")

    def fake_invoke(argv, env, cwd):
        return FakeProcess(returncode=1, stderr="SyntaxError in generated code")

    runner = AnthropicAPIRunner(cwd=str(tmp_path), invoke=fake_invoke)
    result = runner.run(PACKET)
    assert result.ok is False
    assert result.quota_exhausted is False
    assert "SyntaxError" in result.error


def test_anthropic_runner_busy_reflects_concurrency(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-not-real")
    runner = AnthropicAPIRunner(cwd=str(tmp_path), invoke=lambda argv, env, cwd: FakeProcess(0))
    assert runner.busy() is False


# -- quota classification ----------------------------------------------------

def test_classify_matches_pattern():
    exhausted, raw = classify(exit_code=1, stdout="", stderr="you are rate limited, try again later")
    assert exhausted is True
    assert "rate limited" in raw


def test_classify_prefers_provider_metadata():
    exhausted, raw = classify(provider_metadata={"status": "exceeded"}, stdout="", stderr="")
    assert exhausted is True


def test_classify_no_match():
    exhausted, raw = classify(exit_code=1, stdout="", stderr="a normal error")
    assert exhausted is False
    assert raw is None


# -- backoff ------------------------------------------------------------------

def test_delay_seconds_respects_cap():
    for attempt in range(1, 20):
        assert 0 <= delay_seconds(attempt, base=5, cap=60) <= 60


def test_delay_seconds_grows_with_attempt():
    import random
    rng = random.Random(0)
    small = delay_seconds(1, base=5, cap=3600, rng=rng)
    rng = random.Random(0)
    large = delay_seconds(6, base=5, cap=3600, rng=rng)
    assert large >= small


def test_backoff_persists_and_blocks_until_ready(tmp_path):
    state_path = tmp_path / "backoff.json"
    backoff = Backoff("anthropic-api", state_path=state_path, base=1000, cap=2000)
    assert backoff.ready() is True

    backoff.record_failure()
    assert backoff.ready() is False

    # a fresh Backoff instance (new process) reads the same persisted state
    fresh = Backoff("anthropic-api", state_path=state_path, base=1000, cap=2000)
    assert fresh.ready() is False

    fresh.reset()
    assert Backoff("anthropic-api", state_path=state_path).ready() is True


def test_backoff_keys_are_independent(tmp_path):
    state_path = tmp_path / "backoff.json"
    a = Backoff("provider-a", state_path=state_path, base=1000, cap=2000)
    b = Backoff("provider-b", state_path=state_path, base=1000, cap=2000)
    a.record_failure()
    assert a.ready() is False
    assert b.ready() is True
