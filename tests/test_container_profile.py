"""Static checks for the autonomous-mode container profile (shell/runners/container/).

No Docker required: these assert on the *content* of the Dockerfile/run.sh (the no-host-mount
and no-baked-in-credential properties docs/CONTAINER.md promises), plus one behavioural check
of run.sh's own early refusal, which doesn't need Docker either since it exits before ever
calling it.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

CONTAINER_DIR = Path(__file__).resolve().parents[1] / "shell" / "runners" / "container"
DOCKERFILE = CONTAINER_DIR / "Dockerfile"
RUN_SH = CONTAINER_DIR / "run.sh"
DOCKERIGNORE = CONTAINER_DIR / ".dockerignore"


def test_dockerfile_exists_and_has_no_hardcoded_credentials():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=" not in text.replace("ARG CLAUDE_CODE_VERSION=latest", "")
    assert "sk-" not in text


def test_dockerfile_never_copies_host_home_or_claude_dir():
    text = DOCKERFILE.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("COPY", "ADD")):
            assert ".claude" not in stripped
            assert "$HOME" not in stripped and "~" not in stripped


def test_dockerfile_runs_as_non_root():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "USER foundry" in text
    assert "USER root" not in text.split("USER foundry")[-1]


def test_run_sh_mounts_only_the_given_project_dir():
    text = RUN_SH.read_text(encoding="utf-8")
    assert '-v "${PROJECT_DIR}:/workspace"' in text

    code_lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    code = "\n".join(code_lines)
    assert "-v" in code  # the one mount flag, for PROJECT_DIR
    assert code.count("-v ") == 1
    assert "$HOME" not in code
    assert ".claude" not in code
    assert "docker.sock" not in code


def test_run_sh_requires_api_key_before_touching_docker():
    text = RUN_SH.read_text(encoding="utf-8")
    key_check_pos = text.index("ANTHROPIC_API_KEY")
    docker_run_pos = text.index("docker run")
    assert key_check_pos < docker_run_pos


def test_dockerignore_excludes_local_state():
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    assert "company/*.db" in text
    assert ".git" in text


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available on this machine")
def test_run_sh_refuses_without_api_key(tmp_path):
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        ["bash", str(RUN_SH), str(tmp_path)],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 1
    assert "ANTHROPIC_API_KEY" in result.stderr
