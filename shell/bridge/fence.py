"""Safe, idempotent mutation of an agent's frontmatter `remembered:` list — what "Approve
and remember" is supposed to do (Part 5.1): leave a human-reviewable trail of what's already
been approved for this agent, attached to the agent that asked.

This does not claim the platform enforces anything written here. Plugin-shipped agents
cannot be fenced to specific `Bash` commands by Claude Code itself — only a project-level
`.claude/agents/*.md` copy gets that (see `company/ORG.md` and every agent file's own
caveat) — so `remember()` checks for that project-level copy first (where it *would* be
enforced) and falls back to the plugin-shipped `plugin/agents/*.md` (where it's a
human-reviewable note, same spirit as those files' own self-imposed rules).
"""

import re
from datetime import datetime, timezone
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^(---\n)(.*?)(\n---)", re.DOTALL)
REMEMBERED_KEY = "remembered:"


def _agent_path(agent_name, repo_root="."):
    repo_root = Path(repo_root)
    project_level = repo_root / ".claude" / "agents" / f"{agent_name}.md"
    if project_level.exists():
        return project_level
    plugin_level = repo_root / "plugin" / "agents" / f"{agent_name}.md"
    if plugin_level.exists():
        return plugin_level
    return None


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _existing_notes(lines):
    notes = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        if item.startswith('"') :
            item = item.strip('"')
        notes.append(item.rsplit(" (remembered ", 1)[0])
    return notes


def remember(agent_name, note, repo_root="."):
    """Appends `note` to `agent_name`'s frontmatter `remembered:` list, creating the list if
    it's not there yet. Idempotent: a `note` already recorded (ignoring its timestamp) is
    not added again. Returns the path touched, or `None` if no agent file could be found or
    it has no frontmatter to safely mutate."""
    path = _agent_path(agent_name, repo_root)
    if path is None:
        return None

    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None

    lines = match.group(2).split("\n")
    if note in _existing_notes(lines):
        return path

    stamped = f'  - "{note} (remembered {_now_iso()})"'
    key_positions = [i for i, line in enumerate(lines) if line.strip() == REMEMBERED_KEY]
    if key_positions:
        insert_at = key_positions[0] + 1
        while insert_at < len(lines) and lines[insert_at].strip().startswith("- "):
            insert_at += 1
        lines.insert(insert_at, stamped)
    else:
        lines.append(REMEMBERED_KEY)
        lines.append(stamped)

    new_block = "\n".join(lines)
    new_text = text[:match.start(2)] + new_block + text[match.end(2):]
    path.write_text(new_text, encoding="utf-8")
    return path
