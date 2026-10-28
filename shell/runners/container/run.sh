#!/usr/bin/env bash
# Reference launch script for Foundry's autonomous-mode container profile.
#
# Mounts ONLY the project repository you point it at - never $HOME, never ~/.claude, never the
# Docker socket. That is the entire point of this script: AnthropicAPIRunner's subprocess calls
# to the `claude` CLI happen inside the sandbox this builds, instead of directly on the host.
#
# Usage:
#   shell/runners/container/run.sh [project-dir] [-- <command to run in the container>]
#
#   project-dir defaults to the current directory.
#   With no trailing command, runs the scheduler daemon (the Dockerfile's default CMD).
#
# Build the image first:
#   docker build -t foundry-runner shell/runners/container

set -euo pipefail

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY is not set. Autonomous mode requires an explicit API key" \
       "(COMPLIANCE.md rule 2) - no fallback, no auto-detection. Refusing to start." >&2
  exit 1
fi

PROJECT_DIR="${1:-$(pwd)}"
if [ "${1:-}" != "" ]; then
  shift
fi
if [ "${1:-}" = "--" ]; then
  shift
fi

exec docker run --rm \
  -e ANTHROPIC_API_KEY \
  -v "${PROJECT_DIR}:/workspace" \
  -w /workspace \
  foundry-runner \
  "$@"
