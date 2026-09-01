import json
import subprocess
import sys
from pathlib import Path

import pytest

from shell.ledger.projects import Portfolio

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def portfolio(tmp_path):
    return Portfolio(tmp_path / "ledger.db")


def test_add_project_starts_proposed(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="build a widget")
    assert portfolio.get_project("p-1")["state"] == "proposed"


def test_happy_path_lifecycle(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="build a widget")

    portfolio.greenlight("p-1", rationale="worth doing")
    assert portfolio.get_project("p-1")["state"] == "greenlit"

    portfolio.start("p-1", rationale="kicking off")
    assert portfolio.get_project("p-1")["state"] == "active"

    portfolio.ship("p-1", rationale="v1 out", version="0.1.0", tag="v0.1.0")
    project = portfolio.get_project("p-1")
    assert project["state"] == "shipped"
    assert project["shipped_at"] is not None
    releases = portfolio.list_releases("p-1")
    assert releases[0]["version"] == "0.1.0"

    portfolio.maintain("p-1", rationale="steady state")
    assert portfolio.get_project("p-1")["state"] == "maintained"


def test_rejected_is_terminal(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="x")
    portfolio.reject("p-1", rationale="not worth it")
    assert portfolio.get_project("p-1")["state"] == "rejected"
    with pytest.raises(ValueError):
        portfolio.greenlight("p-1", rationale="changed my mind")


def test_shelve_requires_reason_and_revive_when(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="x")
    portfolio.greenlight("p-1", rationale="go")
    portfolio.start("p-1", rationale="go")

    with pytest.raises(ValueError):
        portfolio.shelve("p-1", reason="", revive_when="market shifts")
    with pytest.raises(ValueError):
        portfolio.shelve("p-1", reason="no traction", revive_when="")

    portfolio.shelve("p-1", reason="no traction", revive_when="market shifts")
    project = portfolio.get_project("p-1")
    assert project["state"] == "shelved"
    assert project["shelve_reason"] == "no traction"
    assert project["revive_when"] == "market shifts"
    assert project["shelved_at"] is not None


def test_revive_then_restart(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="x")
    portfolio.greenlight("p-1", rationale="go")
    portfolio.start("p-1", rationale="go")
    portfolio.shelve("p-1", reason="paused", revive_when="Q3")

    portfolio.revive("p-1", rationale="Q3 arrived")
    project = portfolio.get_project("p-1")
    assert project["state"] == "revived"
    assert project["shelve_reason"] is None  # cleared on revival

    portfolio.start("p-1", rationale="back to work")
    assert portfolio.get_project("p-1")["state"] == "active"


def test_archive_is_terminal(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="x")
    portfolio.greenlight("p-1", rationale="go")
    portfolio.start("p-1", rationale="go")
    portfolio.shelve("p-1", reason="dead", revive_when="never")
    portfolio.archive("p-1", rationale="closing the book")
    assert portfolio.get_project("p-1")["state"] == "archived"
    with pytest.raises(ValueError):
        portfolio.revive("p-1", rationale="actually no")


def test_illegal_transition_rejected(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="x")
    with pytest.raises(ValueError):
        portfolio.ship("p-1", rationale="too soon")


def test_rationale_is_mandatory(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="x")
    with pytest.raises(ValueError):
        portfolio.greenlight("p-1", rationale="")


def test_shelf_lists_only_shelved(portfolio):
    portfolio.add_project("p-1", name="A", brief="x")
    portfolio.add_project("p-2", name="B", brief="x")
    portfolio.greenlight("p-1", rationale="go")
    portfolio.start("p-1", rationale="go")
    portfolio.shelve("p-1", reason="r", revive_when="w")

    shelf = portfolio.shelf()
    assert [p["id"] for p in shelf] == ["p-1"]


def test_events_are_append_only_audit_trail(portfolio):
    portfolio.add_project("p-1", name="Widget", brief="x")
    portfolio.greenlight("p-1", rationale="go")
    portfolio.start("p-1", rationale="go")
    events = portfolio.list_events("p-1")
    transitions = [(e["from_state"], e["to_state"]) for e in events]
    assert transitions == [(None, "proposed"), ("proposed", "greenlit"), ("greenlit", "active")]


def _run_cli(db_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "shell.ledger.cli", "--db", str(db_path), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )


def test_cli_project_lifecycle_smoke(tmp_path):
    db_path = tmp_path / "ledger.db"

    out = _run_cli(db_path, "project", "add", "--id", "p-1", "--name", "Widget", "--brief", "x")
    assert out.returncode == 0, out.stderr

    out = _run_cli(db_path, "project", "greenlight", "p-1", "--rationale", "go")
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["state"] == "greenlit"

    out = _run_cli(db_path, "project", "start", "p-1", "--rationale", "go")
    assert json.loads(out.stdout)["state"] == "active"

    out = _run_cli(
        db_path, "project", "ship", "p-1", "--rationale", "v1",
        "--version", "0.1.0",
    )
    assert json.loads(out.stdout)["state"] == "shipped"

    out = _run_cli(db_path, "project", "status", "p-1")
    assert out.returncode == 0, out.stderr
    status = json.loads(out.stdout)
    assert status["project"]["state"] == "shipped"
    assert status["releases"][0]["version"] == "0.1.0"


def test_cli_shelve_requires_both_flags(tmp_path):
    db_path = tmp_path / "ledger.db"
    _run_cli(db_path, "project", "add", "--id", "p-1", "--name", "W", "--brief", "x")
    _run_cli(db_path, "project", "greenlight", "p-1", "--rationale", "go")
    _run_cli(db_path, "project", "start", "p-1", "--rationale", "go")

    out = _run_cli(db_path, "project", "shelve", "p-1", "--reason", "no traction", "--revive-when", "later")
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["state"] == "shelved"


def test_cli_project_list_filters_by_state(tmp_path):
    db_path = tmp_path / "ledger.db"
    _run_cli(db_path, "project", "add", "--id", "p-1", "--name", "A", "--brief", "x")
    _run_cli(db_path, "project", "add", "--id", "p-2", "--name", "B", "--brief", "x")
    _run_cli(db_path, "project", "greenlight", "p-1", "--rationale", "go")

    out = _run_cli(db_path, "project", "list", "--state", "proposed")
    assert out.returncode == 0, out.stderr
    ids = [p["id"] for p in json.loads(out.stdout)]
    assert ids == ["p-2"]
