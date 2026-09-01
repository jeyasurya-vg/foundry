import pytest

from shell.ledger.ledger import Ledger
from shell.ledger.projects import Portfolio
from shell.runners.base import Runner, RunResult
from shell.scheduler.fairshare import eligible_projects, score, next_ticket
from shell.scheduler.tick import scheduler_tick


class FakeRunner(Runner):
    name = "fake"

    def __init__(self, headroom=True, result=None):
        self._headroom = headroom
        self._busy = False
        self.result = result or RunResult(ok=True)
        self.calls = []

    def headroom(self):
        return self._headroom

    def busy(self):
        return self._busy

    def run(self, packet):
        self.calls.append(packet)
        return self.result


@pytest.fixture()
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.db")


@pytest.fixture()
def portfolio(tmp_path, ledger):
    return Portfolio(tmp_path / "ledger.db")  # same file as `ledger`


def _make_active_project(portfolio, project_id, priority=5, wip_limit=3):
    portfolio.add_project(project_id, name=project_id, brief="x", priority=priority, wip_limit=wip_limit)
    portfolio.greenlight(project_id, rationale="go")
    portfolio.start(project_id, rationale="go")


# -- score / eligible_projects (pure) ----------------------------------------

def test_score_penalizes_high_consumption():
    project = {"priority": 10, "budget_share": 0.5}
    assert score(project, consumed_share=0.0) == 10
    assert score(project, consumed_share=0.5) == 0
    assert 0 < score(project, consumed_share=0.25) < 10


def test_eligible_projects_focus_picks_highest_priority_active():
    projects = [
        {"id": "a", "state": "active", "priority": 3},
        {"id": "b", "state": "active", "priority": 9},
        {"id": "c", "state": "maintained", "priority": 100},
    ]
    assert [p["id"] for p in eligible_projects(projects, "focus")] == ["b"]


def test_eligible_projects_balanced_includes_active_and_maintained():
    projects = [
        {"id": "a", "state": "active"},
        {"id": "b", "state": "maintained"},
        {"id": "c", "state": "shelved"},
    ]
    assert {p["id"] for p in eligible_projects(projects, "balanced")} == {"a", "b"}


def test_eligible_projects_unknown_mode_raises():
    with pytest.raises(ValueError):
        eligible_projects([], "bogus")


# -- next_ticket (integration with real Ledger/Portfolio) --------------------

def test_next_ticket_respects_runner_headroom(ledger, portfolio):
    _make_active_project(portfolio, "p-1")
    ledger.add_ticket(brief="x", done_when="y", project_id="p-1")
    runner = FakeRunner(headroom=False)
    assert next_ticket(ledger, portfolio, runner) is None


def test_next_ticket_respects_wip_limit(ledger, portfolio):
    _make_active_project(portfolio, "p-1", wip_limit=1)
    t1 = ledger.add_ticket(brief="a", done_when="y", project_id="p-1")
    ledger.add_ticket(brief="b", done_when="y", project_id="p-1")
    ledger.claim(t1, "engineer")
    ledger.start_running(t1)  # p-1 is now at its WIP limit of 1

    runner = FakeRunner()
    assert next_ticket(ledger, portfolio, runner) is None


def test_next_ticket_prefers_higher_score(ledger, portfolio):
    _make_active_project(portfolio, "low", priority=1)
    _make_active_project(portfolio, "high", priority=10)
    ledger.add_ticket(brief="a", done_when="y", project_id="low")
    hi_ticket = ledger.add_ticket(brief="b", done_when="y", project_id="high")

    runner = FakeRunner()
    ticket = next_ticket(ledger, portfolio, runner)
    assert ticket["id"] == hi_ticket


def test_next_ticket_only_considers_eligible_states(ledger, portfolio):
    portfolio.add_project("p-1", name="p-1", brief="x")  # stays `proposed`
    ledger.add_ticket(brief="a", done_when="y", project_id="p-1")

    runner = FakeRunner()
    assert next_ticket(ledger, portfolio, runner, mode="balanced") is None
    assert next_ticket(ledger, portfolio, runner, mode="discovery") is not None


# -- scheduler_tick / execute -------------------------------------------------

def test_scheduler_tick_runs_a_ticket_end_to_end(ledger, portfolio):
    _make_active_project(portfolio, "p-1")
    tid = ledger.add_ticket(brief="x", done_when="y", project_id="p-1")

    runner = FakeRunner(result=RunResult(ok=True))
    events = []
    ticket = scheduler_tick(ledger, portfolio, runner, notify=events.append)

    assert ticket["id"] == tid
    assert len(runner.calls) == 1
    assert runner.calls[0].ticket_id == tid
    # the runner "succeeded" but never called checkpoint itself, so the ticket is left
    # `running` -- an orphan the next tick's resume path picks up, not silently advanced.
    assert ticket["state"] == "running"


def test_scheduler_tick_does_nothing_when_runner_busy(ledger, portfolio):
    _make_active_project(portfolio, "p-1")
    ledger.add_ticket(brief="x", done_when="y", project_id="p-1")

    class BusyRunner(FakeRunner):
        def busy(self):
            return True

    runner = BusyRunner()
    assert scheduler_tick(ledger, portfolio, runner) is None
    assert runner.calls == []


def test_scheduler_tick_handles_quota_exhaustion(ledger, portfolio):
    _make_active_project(portfolio, "p-1")
    tid = ledger.add_ticket(brief="x", done_when="y", project_id="p-1")

    runner = FakeRunner(result=RunResult(ok=False, quota_exhausted=True, raw_message="rate limited"))
    ticket = scheduler_tick(ledger, portfolio, runner)
    assert ticket["state"] == "blocked_quota"
    assert ticket["blocked_until"] is not None


def test_scheduler_tick_handles_failure_and_retries(ledger, portfolio):
    _make_active_project(portfolio, "p-1")
    tid = ledger.add_ticket(brief="x", done_when="y", project_id="p-1")

    runner = FakeRunner(result=RunResult(ok=False, error="boom"))
    ticket = scheduler_tick(ledger, portfolio, runner)
    assert ticket["state"] == "queued"
    assert ticket["attempts"] == 1


def test_scheduler_tick_releases_expired_quota_blocks(ledger, portfolio):
    from datetime import datetime, timedelta, timezone

    _make_active_project(portfolio, "p-1")
    tid = ledger.add_ticket(brief="x", done_when="y", project_id="p-1")
    ledger.claim(tid, "engineer")
    ledger.start_running(tid)
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    ledger.block_quota(tid, blocked_until=past)

    events = []
    runner = FakeRunner()
    scheduler_tick(ledger, portfolio, runner, notify=events.append)
    assert any("resumed: quota window reopened" in e for e in events)
    assert ledger.get_ticket(tid)["state"] in ("running", "queued")  # released, and likely re-picked
