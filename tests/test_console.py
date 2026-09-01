import json
import threading
import urllib.error
import urllib.request

import pytest

from shell.console import api
from shell.console.server import make_server
from shell.ledger.ledger import Ledger
from shell.ledger.projects import Portfolio
from shell.usage.tracker import UsageTracker


@pytest.fixture()
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.db")


@pytest.fixture()
def portfolio(tmp_path, ledger):
    return Portfolio(tmp_path / "ledger.db")


# -- pure api functions -------------------------------------------------------

def test_build_team_reads_real_plugin_agents():
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    team = api.build_team(repo_root)
    names = {a["name"] for a in team["agents"]}
    assert "engineer" in names
    assert "qa" in names


def test_build_team_empty_when_no_agents_dir(tmp_path):
    team = api.build_team(tmp_path)
    assert team["agents"] == []


def test_build_memory_reads_real_files():
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    memory = api.build_memory(repo_root)
    assert memory["memory"] is not None
    assert memory["knowledge_index"] is not None


def test_build_memory_none_when_missing(tmp_path):
    memory = api.build_memory(tmp_path)
    assert memory["memory"] is None
    assert memory["knowledge_index"] is None


def test_build_dashboard_counts_tickets_and_projects(tmp_path, ledger, portfolio):
    ledger.add_ticket(brief="a", done_when="x")
    portfolio.add_project("p-1", name="p-1", brief="x")
    usage = UsageTracker(tmp_path / "usage.db")

    dashboard = api.build_dashboard(ledger, portfolio, usage)
    assert dashboard["tickets_by_state"] == {"queued": 1}
    assert dashboard["projects_by_state"] == {"proposed": 1}
    assert dashboard["usage"]["claude"]["status"] == "active"
    assert len(dashboard["recent_events"]) == 2  # "created" and the auto-queue transition
    usage.close()


def test_build_board_filters_by_project(ledger):
    ledger.add_ticket(brief="a", done_when="x", project_id="p-1")
    ledger.add_ticket(brief="b", done_when="x", project_id="p-2")

    board = api.build_board(ledger, project_id="p-1")
    assert len(board["tickets"]) == 1
    assert board["tickets"][0]["project_id"] == "p-1"


def test_build_portfolio_separates_shelf(portfolio):
    portfolio.add_project("p-1", name="A", brief="x")
    portfolio.add_project("p-2", name="B", brief="x")
    portfolio.greenlight("p-2", rationale="go")
    portfolio.start("p-2", rationale="go")
    portfolio.shelve("p-2", reason="r", revive_when="w")

    result = api.build_portfolio(portfolio)
    assert {p["id"] for p in result["projects"]} == {"p-1", "p-2"}
    assert [p["id"] for p in result["shelf"]] == ["p-2"]


# -- live server smoke test ---------------------------------------------------

@pytest.fixture()
def running_server(tmp_path):
    ledger = Ledger(tmp_path / "ledger.db")
    ledger.add_ticket(brief="a real ticket", done_when="tests pass")
    ledger.close()

    server = make_server(repo_root=tmp_path, ledger_db=tmp_path / "ledger.db",
                          usage_db=tmp_path / "usage.db", host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def test_server_refuses_non_loopback_by_default():
    with pytest.raises(ValueError):
        make_server(host="0.0.0.0", port=0)


def test_server_serves_index_html(running_server):
    with urllib.request.urlopen(running_server + "/", timeout=5) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
        assert "Mission Control" in body


def test_server_dashboard_endpoint(running_server):
    status, payload = _get(running_server + "/api/dashboard")
    assert status == 200
    assert payload["tickets_by_state"] == {"queued": 1}


def test_server_board_endpoint(running_server):
    status, payload = _get(running_server + "/api/board")
    assert status == 200
    assert len(payload["tickets"]) == 1


def test_server_unknown_path_404s(running_server):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(running_server + "/nope", timeout=5)
    assert exc_info.value.code == 404
