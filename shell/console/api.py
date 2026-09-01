"""Pure data-building functions for Mission Control's JSON API.

Kept separate from the HTTP plumbing (server.py) so every payload is testable by calling a
function directly, with no server, no sockets, no port. "No new backend" (Part 5.2) means
these functions only ever read the ledger, the portfolio, the usage tracker, and a handful of
files already on disk — nothing here writes anything.
"""

import re
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(text):
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def build_team(repo_root):
    """The Team screen (Part 5.2): 'the index the orchestrator reads to route work'."""
    agents_dir = Path(repo_root) / "plugin" / "agents"
    roster = []
    if agents_dir.exists():
        for path in sorted(agents_dir.glob("*.md")):
            fields = _parse_frontmatter(path.read_text(encoding="utf-8"))
            roster.append({
                "name": fields.get("name", path.stem),
                "description": fields.get("description", ""),
                "tools": fields.get("tools", ""),
                "file": str(path.relative_to(repo_root)).replace("\\", "/"),
            })
    return {"agents": roster}


def build_memory(repo_root):
    """The Memory screen (Part 5.2): all layers, read directly — L2 (MEMORY.md) and the L3
    entry point (knowledge/INDEX.md). L1 raw logs are intentionally excluded: they're noisy,
    machine-facing, and gitignored per-checkout state, not something to render whole."""

    def _read(rel_path):
        path = Path(repo_root) / rel_path
        return path.read_text(encoding="utf-8") if path.exists() else None

    return {
        "memory": _read("company/MEMORY.md"),
        "knowledge_index": _read("company/knowledge/INDEX.md"),
    }


def build_dashboard(ledger, portfolio, usage_tracker):
    return {
        "tickets_by_state": ledger.status_summary(),
        "projects_by_state": _count_by(portfolio.list_projects(), "state"),
        "usage": usage_tracker.status(),
        "recent_events": ledger.recent_events(limit=25),
    }


def build_board(ledger, project_id=None):
    return {"tickets": ledger.list_tickets(project_id=project_id)}


def build_portfolio(portfolio):
    return {"projects": portfolio.list_projects(), "shelf": portfolio.shelf()}


def _count_by(rows, key):
    counts = {}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return counts
