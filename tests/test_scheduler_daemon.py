import pytest

from shell.ledger.ledger import Ledger
from shell.ledger.projects import Portfolio
from shell.runners.base import Runner, RunResult
from shell.scheduler.cli import build_parser, _write_pidfile, _remove_pidfile
from shell.scheduler.daemon import run_forever


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


def test_run_forever_stops_after_max_ticks(ledger, portfolio):
    runner = FakeRunner()
    slept = []

    ticks = run_forever(
        ledger, portfolio, runner,
        max_ticks=3, sleep=slept.append, notify=lambda *_: None,
    )

    assert ticks == 3
    assert slept == [60, 60]  # no sleep after the final tick


def test_run_forever_honours_custom_interval(ledger, portfolio):
    runner = FakeRunner()
    slept = []

    run_forever(
        ledger, portfolio, runner,
        interval=5, max_ticks=2, sleep=slept.append, notify=lambda *_: None,
    )

    assert slept == [5]


def test_run_forever_stops_on_should_stop(ledger, portfolio):
    runner = FakeRunner()
    calls = {"n": 0}

    def should_stop():
        calls["n"] += 1
        return calls["n"] > 2

    ticks = run_forever(
        ledger, portfolio, runner,
        max_ticks=None, sleep=lambda _s: None, notify=lambda *_: None,
        should_stop=should_stop,
    )

    assert ticks == 2


def test_run_forever_runs_a_real_ready_ticket(ledger, portfolio):
    _make_active_project(portfolio, "p1")
    ledger.add_ticket(brief="do x", done_when="x done", project_id="p1")
    runner = FakeRunner()

    ticks = run_forever(
        ledger, portfolio, runner,
        max_ticks=1, sleep=lambda _s: None, notify=lambda *_: None,
    )

    assert ticks == 1
    assert len(runner.calls) == 1


def test_scheduler_cli_parser_requires_runner():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "balanced"])


def test_scheduler_cli_parser_defaults(tmp_path):
    parser = build_parser()
    args = parser.parse_args(["--runner", "attended", "--db", str(tmp_path / "x.db")])
    assert args.mode == "balanced"
    assert args.interval == 60
    assert args.max_ticks is None
    assert args.pidfile is None


def test_pidfile_write_and_remove(tmp_path):
    pidfile = tmp_path / "scheduler.pid"
    _write_pidfile(str(pidfile))
    assert pidfile.exists()
    assert pidfile.read_text().strip().isdigit()

    _remove_pidfile(str(pidfile))
    assert not pidfile.exists()


def test_pidfile_noop_when_not_configured(tmp_path):
    # Should not raise when no --pidfile was passed.
    _write_pidfile(None)
    _remove_pidfile(None)
