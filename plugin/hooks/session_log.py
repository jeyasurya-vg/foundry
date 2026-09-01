#!/usr/bin/env python3
"""SessionStart / SessionEnd hook.

Two jobs, both best-effort and both silent on failure — a missing `shell/` (a plugin-only
install elsewhere) or an unwritable `company/` must never block a Claude Code session:

1. Layer-1 memory (docs/blueprint Part 4): on SessionEnd, append a lightweight record to
   company/logs/YYYY-MM-DD-HHMM.md pointing at the session's transcript, rather than copying
   the transcript itself. Copying full transcripts here would duplicate a lot of data for
   little benefit before a real distillation job (L1 -> L2) exists to consume it; that job
   reads `transcript_path` directly when it's built.
2. Usage tracking: record a session start/end boundary via `shell.usage.cli log-session`, used
   as a rough elapsed-time proxy alongside real /usage observations (see docs/USAGE.md).
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _log_usage_event(cwd, event, session_id):
    try:
        subprocess.run(
            [
                sys.executable, "-m", "shell.usage.cli", "log-session",
                "--provider", "claude", "--event", event,
                *(["--session-id", session_id] if session_id else []),
                "--cwd", cwd,
            ],
            cwd=cwd,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass  # shell/ not present or not importable here; usage tracking is best-effort


def _write_l1_log(cwd, payload):
    try:
        logs_dir = Path(cwd) / "company" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
        entry = (
            f"## {stamp} session end\n\n"
            f"- session_id: {payload.get('session_id')}\n"
            f"- cwd: {payload.get('cwd')}\n"
            f"- transcript: {payload.get('transcript_path')}\n"
        )
        (logs_dir / f"{stamp}.md").write_text(entry, encoding="utf-8")
    except OSError:
        pass


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "start"
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}

    cwd = payload.get("cwd") or "."
    session_id = payload.get("session_id")

    _log_usage_event(cwd, event, session_id)
    if event == "end":
        _write_l1_log(cwd, payload)

    return 0


if __name__ == "__main__":
    sys.exit(main())
