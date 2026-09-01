"""Autonomous runner backed by an Anthropic API key.

This shells out to the *official* `claude` CLI in headless mode (`-p`), authenticated by
`ANTHROPIC_API_KEY` in its environment — it does not hand-roll calls to the Messages API.
That keeps exactly one code path talking to Anthropic at all (the official client), and means
this runner inherits Claude Code's own tool use, not a reimplementation of it.

Compliance rule 2 (COMPLIANCE.md): refuses to start without an explicit API key. No fallback,
no auto-detection — in particular, this never reads the official CLI's own config directory
looking for a subscription session; that credential store is off limits by rule 1,
unconditionally.

Headless mode skips auto-discovery of CLAUDE.md, hooks and skills (Part 4 note), so the
context this runner needs is injected explicitly via `--append-system-prompt`, kept to the
two files a dispatched agent actually needs: the plugin charter and the org chart.
"""

import json
import os
import subprocess
from pathlib import Path

from .base import Runner, RunResult
from .quota import classify

CONTEXT_FILES = ("plugin/CLAUDE.md", "company/ORG.md")


class AnthropicAPIRunner(Runner):
    name = "anthropic-api"

    def __init__(self, api_key_env="ANTHROPIC_API_KEY", cli="claude", concurrency=1,
                 cwd=".", invoke=None):
        self.api_key_env = api_key_env
        self.cli = cli
        self.concurrency = concurrency
        self.cwd = cwd
        self._busy_count = 0
        self._invoke = invoke or self._invoke_cli

    @property
    def api_key(self):
        return os.environ.get(self.api_key_env)

    def headroom(self):
        return bool(self.api_key)

    def busy(self):
        return self._busy_count >= self.concurrency

    def run(self, packet):
        if not self.api_key:
            return RunResult(ok=False, error=(
                f"{self.api_key_env} is not set. Autonomous mode requires an explicit API "
                "key (compliance rule 2) — no fallback, no auto-detection. Use attended mode "
                "(/foundry:next in official Claude Code) instead."
            ))

        argv = self._build_argv(packet)
        self._busy_count += 1
        try:
            result = self._invoke(argv, env=os.environ.copy(), cwd=self.cwd)
        finally:
            self._busy_count -= 1

        quota_exhausted, raw = classify(
            exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr,
        )
        if quota_exhausted:
            return RunResult(ok=False, quota_exhausted=True, raw_message=raw)
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "")[:2000]
            return RunResult(ok=False, error=message, raw_message=message)
        return RunResult(ok=True, raw_message=(result.stdout or "")[:2000])

    def _build_argv(self, packet):
        argv = [
            self.cli, "-p", self._build_prompt(packet),
            "--append-system-prompt", self._build_context(),
            "--output-format", "json",
        ]
        if packet.session_id:
            argv += ["--resume", packet.session_id]
        return argv

    def _build_prompt(self, packet):
        lines = [
            f"Ticket {packet.ticket_id}: {packet.brief}",
            f"Done when: {packet.done_when}",
        ]
        if packet.last_checkpoint_summary:
            lines.append(f"Last checkpoint: {packet.last_checkpoint_summary}")
        if packet.next_step:
            lines.append(f"Next step: {packet.next_step}")
        if packet.artifacts:
            lines.append(f"Artifacts so far: {json.dumps(packet.artifacts)}")
        lines.append(
            "Checkpoint after every atomic step via `python -m shell.ledger.cli checkpoint` "
            "before doing anything else."
        )
        return "\n".join(lines)

    def _build_context(self):
        parts = []
        for rel_path in CONTEXT_FILES:
            path = Path(self.cwd) / rel_path
            if path.exists():
                parts.append(path.read_text(encoding="utf-8"))
        return "\n\n---\n\n".join(parts)

    def _invoke_cli(self, argv, env, cwd):
        return subprocess.run(argv, capture_output=True, text=True, env=env, cwd=cwd)
