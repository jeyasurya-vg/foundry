from pathlib import Path

from shell.bridge import fence

AGENT_MD = """---
name: engineer
description: Implementation, in a dedicated worktree, on a dedicated branch.
tools: Read, Edit, Write, Bash
---

You implement tickets, always in a dedicated worktree on a dedicated branch.
"""


def _write_agent(repo_root, name=".", level="plugin", text=AGENT_MD, agent_name="engineer"):
    agents_dir = Path(repo_root) / level / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{agent_name}.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_remember_returns_none_for_unknown_agent(tmp_path):
    assert fence.remember("ghost", "do a thing", repo_root=tmp_path) is None


def test_remember_creates_remembered_list_when_absent(tmp_path):
    _write_agent(tmp_path)
    path = fence.remember("engineer", "push to main for t-1", repo_root=tmp_path)
    assert path is not None

    text = path.read_text(encoding="utf-8")
    assert "remembered:" in text
    assert "push to main for t-1" in text
    # original fields and body untouched
    assert "name: engineer" in text
    assert "tools: Read, Edit, Write, Bash" in text
    assert "You implement tickets" in text


def test_remember_appends_to_existing_list(tmp_path):
    _write_agent(tmp_path)
    fence.remember("engineer", "note one", repo_root=tmp_path)
    path = fence.remember("engineer", "note two", repo_root=tmp_path)

    text = path.read_text(encoding="utf-8")
    assert text.count("remembered:") == 1
    assert "note one" in text
    assert "note two" in text


def test_remember_is_idempotent(tmp_path):
    _write_agent(tmp_path)
    fence.remember("engineer", "push to main for t-1", repo_root=tmp_path)
    path = fence.remember("engineer", "push to main for t-1", repo_root=tmp_path)

    text = path.read_text(encoding="utf-8")
    assert text.count("push to main for t-1") == 1


def test_remember_prefers_project_level_claude_agents_dir(tmp_path):
    _write_agent(tmp_path, level="plugin")
    _write_agent(tmp_path, level=".claude", text=AGENT_MD.replace("engineer", "engineer-project"))

    path = fence.remember("engineer", "a note", repo_root=tmp_path)
    assert ".claude" in str(path).replace("\\", "/")


def test_remember_falls_back_to_plugin_agents_when_no_project_copy(tmp_path):
    _write_agent(tmp_path, level="plugin")
    path = fence.remember("engineer", "a note", repo_root=tmp_path)
    assert "plugin" in str(path).replace("\\", "/")
