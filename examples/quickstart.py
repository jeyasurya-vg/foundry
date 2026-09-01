#!/usr/bin/env python3
"""Runnable version of the walkthrough in examples/quickstart.md.

Exercises the whole stack end to end against a scratch, throwaway database: propose and ship
a project, walk two dependent tickets from queued to done, record a usage observation. Every
command this script runs is the literal CLI a person would type by hand — this just runs them
for you and stops loudly if anything breaks. `tests/test_quickstart.py` runs this on every
`pytest` invocation, so "a stranger ships something in under an hour" stays true, not aspirational.

Usage:
    python examples/quickstart.py [--db PATH] [--keep]

Exit code 0 means the whole walkthrough succeeded end to end.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(cmd)}")
    print(result.stdout.strip())
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="ledger db path (default: a fresh scratch directory)")
    parser.add_argument("--keep", action="store_true", help="keep the scratch directory instead of deleting it")
    args = parser.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="foundry-quickstart-"))
    db_path = Path(args.db) if args.db else scratch / "ledger.db"
    usage_db = scratch / "usage.db"
    print(f"Using scratch ledger at {db_path}\n")

    def ledger_cli(*a):
        return run([sys.executable, "-m", "shell.ledger.cli", "--db", str(db_path), *a], cwd=REPO_ROOT)

    # 1. Propose, greenlight, and start a project.
    ledger_cli("project", "add", "--id", "quickstart", "--name", "Quickstart Widget",
               "--brief", "prove the pipeline works")
    ledger_cli("project", "greenlight", "quickstart", "--rationale", "worth a demo")
    ledger_cli("project", "start", "quickstart", "--rationale", "kicking off")

    # 2. Two dependent tickets.
    schema = json.loads(ledger_cli(
        "add", "--brief", "design the widget schema", "--done-when", "schema documented",
        "--project", "quickstart",
    ))
    build = json.loads(ledger_cli(
        "add", "--brief", "build the widget", "--done-when", "tests pass",
        "--project", "quickstart", "--depends-on", schema["id"],
    ))

    # 3. `next` offers the dependency-free ticket first.
    claimed = json.loads(ledger_cli("next", "--project", "quickstart"))
    assert claimed["id"] == schema["id"], "expected the dependency-free ticket first"

    # 4. Walk it to review, then approve it. review -> done has no CLI command by design
    # (docs/LEDGER.md: approval belongs to an independent reviewer agent, not this CLI).
    ledger_cli("checkpoint", claimed["id"], "--summary", "wrote the schema",
               "--artifacts", '["schema.md"]', "--next-step", "-", "--final")
    run([
        sys.executable, "-c",
        f"from shell.ledger.ledger import Ledger; l = Ledger(r'{db_path}'); "
        f"l.approve('{claimed['id']}'); l.close()",
    ], cwd=REPO_ROOT)

    # 5. Now the dependent ticket is claimable.
    claimed2 = json.loads(ledger_cli("next", "--project", "quickstart"))
    assert claimed2["id"] == build["id"], "the dependent ticket should be ready now"
    ledger_cli("checkpoint", claimed2["id"], "--summary", "built it",
               "--artifacts", '["widget.py"]', "--next-step", "-", "--final")
    run([
        sys.executable, "-c",
        f"from shell.ledger.ledger import Ledger; l = Ledger(r'{db_path}'); "
        f"l.approve('{claimed2['id']}'); l.close()",
    ], cwd=REPO_ROOT)

    # 6. Ship the project.
    ledger_cli("project", "ship", "quickstart", "--rationale", "v1 done", "--version", "0.1.0")

    # 7. Record a usage observation -- this is the number Claude Code's own /usage shows you.
    run([
        sys.executable, "-m", "shell.usage.cli", "--db", str(usage_db),
        "record", "--provider", "claude", "--window", "session", "--remaining", "0.75",
        "--reset", "2026-09-01T20:00:00+00:00",
    ], cwd=REPO_ROOT)

    print(
        "\nQuickstart complete: a project went proposed -> greenlit -> active -> shipped, "
        "two dependent tickets went queued -> ... -> done, and a usage observation was "
        "recorded.\n\nSee it in Mission Control with:\n"
        f"  python -m shell.console.cli --repo-root . --ledger-db {db_path} --usage-db {usage_db}"
    )

    if args.keep:
        print(f"\nScratch directory kept at {scratch}")
    else:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
