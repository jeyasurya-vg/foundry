import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_quickstart_runs_end_to_end():
    """Phase 9's gate is "a stranger ships something in under an hour" — this makes sure the
    documented walkthrough (examples/quickstart.md) actually still works, on every test run,
    instead of trusting prose to stay in sync with the code."""
    result = subprocess.run(
        [sys.executable, "examples/quickstart.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Quickstart complete" in result.stdout
