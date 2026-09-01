#!/usr/bin/env python3
"""PostToolUse hook: makes checkpointing mechanical instead of a courtesy.

Rule from docs/LEDGER.md / plugin/CLAUDE.md: every step ends in a commit, and a checkpoint
is written before doing anything else. This hook enforces the second half. It does not (and
cannot, from PostToolUse) stop a commit from happening — but the moment one has, it blocks
every subsequent tool call with a corrective message until the agent runs
`shell.ledger.cli checkpoint` for the current ticket.

State is a tiny per-session counter file, not the ledger itself: this hook only needs to know
"has there been a commit since the last checkpoint call", not ticket details.
"""

import json
import re
import sys
from pathlib import Path

COMMIT_RE = re.compile(r"\bgit\s+commit\b")
CHECKPOINT_RE = re.compile(r"(shell\.ledger\.cli|foundry-ledger)\s+.*\bcheckpoint\b")

STATE_DIR = "company/.hook_state"


def _state_path(cwd, session_id):
    return Path(cwd) / STATE_DIR / f"{session_id or 'unknown'}.json"


def _read_state(path):
    if not path.exists():
        return {"pending_commits": 0}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"pending_commits": 0}


def _write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # nothing we can act on; don't block the agent over a malformed payload

    cwd = payload.get("cwd") or "."
    session_id = payload.get("session_id")
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}
    command = tool_input.get("command", "") if tool_name == "Bash" else ""

    state_path = _state_path(cwd, session_id)
    state = _read_state(state_path)

    if tool_name == "Bash" and CHECKPOINT_RE.search(command):
        state["pending_commits"] = 0
        _write_state(state_path, state)
        return 0

    was_pending = state.get("pending_commits", 0) > 0

    if tool_name == "Bash" and COMMIT_RE.search(command):
        state["pending_commits"] = state.get("pending_commits", 0) + 1
        _write_state(state_path, state)
        # Fall through: this call itself is allowed (the commit already happened);
        # the block applies starting with the *next* tool call.
        return 0

    if was_pending:
        print(
            "A git commit happened without a checkpoint recorded for it. "
            "Run `python -m shell.ledger.cli checkpoint <ticket-id> --summary ... "
            "--next-step ...` for the current ticket before doing anything else.",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
