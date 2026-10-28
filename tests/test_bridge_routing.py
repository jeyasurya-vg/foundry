import json

import pytest

from shell.bridge.routing import ChannelRouter, RouteNotFound


def _write_config(tmp_path, config):
    path = tmp_path / "bridge_channels.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_resolve_project_route(tmp_path):
    path = _write_config(tmp_path, {
        "default": {"chat_id": "1"},
        "projects": {"p-1": {"chat_id": "2", "thread_id": 5}},
    })
    router = ChannelRouter(path)
    assert router.resolve(project_id="p-1") == ("2", 5)


def test_resolve_department_route(tmp_path):
    path = _write_config(tmp_path, {
        "default": {"chat_id": "1"},
        "departments": {"security": {"chat_id": "3"}},
    })
    router = ChannelRouter(path)
    assert router.resolve(department="security") == ("3", None)


def test_project_route_wins_over_department(tmp_path):
    path = _write_config(tmp_path, {
        "projects": {"p-1": {"chat_id": "project-chat"}},
        "departments": {"security": {"chat_id": "dept-chat"}},
    })
    router = ChannelRouter(path)
    assert router.resolve(project_id="p-1", department="security") == ("project-chat", None)


def test_falls_back_to_default(tmp_path):
    path = _write_config(tmp_path, {"default": {"chat_id": "1"}})
    router = ChannelRouter(path)
    assert router.resolve(project_id="unknown-project") == ("1", None)


def test_raises_when_nothing_resolves(tmp_path):
    path = _write_config(tmp_path, {})
    router = ChannelRouter(path)
    with pytest.raises(RouteNotFound):
        router.resolve(project_id="p-1")


def test_missing_config_file_is_a_noop_until_resolve(tmp_path):
    router = ChannelRouter(tmp_path / "does_not_exist.json")
    with pytest.raises(RouteNotFound):
        router.resolve()
