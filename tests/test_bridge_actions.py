import json

import pytest

from shell.bridge import actions
from shell.ledger.projects import Portfolio


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "ledger.db"


def _make_active_project(db_path, project_id="p-1"):
    portfolio = Portfolio(db_path)
    portfolio.add_project(project_id, name=project_id, brief="x")
    portfolio.greenlight(project_id, rationale="go")
    portfolio.start(project_id, rationale="go")
    portfolio.close()


def test_apply_ship(db_path):
    _make_active_project(db_path)
    result = actions.apply("portfolio.ship", {"project_id": "p-1", "rationale": "ready"}, db_path)
    assert result == "shipped"

    portfolio = Portfolio(db_path)
    assert portfolio.get_project("p-1")["state"] == "shipped"
    portfolio.close()


def test_apply_shelve(db_path):
    _make_active_project(db_path)
    result = actions.apply(
        "portfolio.shelve",
        {"project_id": "p-1", "reason": "deprioritized", "revive_when": "Q3"},
        db_path,
    )
    assert result == "shelved"


def test_apply_archive(db_path):
    _make_active_project(db_path)
    portfolio = Portfolio(db_path)
    portfolio.shelve("p-1", reason="r", revive_when="w")
    portfolio.close()

    result = actions.apply("portfolio.archive", {"project_id": "p-1", "rationale": "done"}, db_path)
    assert result == "archived"


def test_apply_accepts_json_string_payload(db_path):
    _make_active_project(db_path)
    payload = json.dumps({"project_id": "p-1", "rationale": "ready"})
    assert actions.apply("portfolio.ship", payload, db_path) == "shipped"


def test_apply_unknown_kind_raises(db_path):
    with pytest.raises(KeyError):
        actions.apply("portfolio.delete-everything", {}, db_path)
