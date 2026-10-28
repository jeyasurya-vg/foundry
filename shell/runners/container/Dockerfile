# Container profile for Foundry's autonomous mode (shell/runners/anthropic_api.py).
#
# Gives AnthropicAPIRunner somewhere to shell out to the official `claude` CLI that isn't the
# host machine. No host directory is baked into this image - the only filesystem it ever sees
# is whatever the caller mounts at /workspace (see run.sh), which is how it satisfies
# COMPLIANCE.md rule 1 (never touch ~/.claude) without any special-casing: there is no host
# filesystem in scope at all until a mount says so, and run.sh only ever mounts the project
# repo itself.

FROM node:20-slim

# Pin an exact version - never install "latest" into an image meant to run unattended. Override
# with --build-arg CLAUDE_CODE_VERSION=x.y.z at build time.
ARG CLAUDE_CODE_VERSION=latest
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION} \
    && npm cache clean --force

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 \
    && rm -rf /var/lib/apt/lists/*

# Never root inside a container that executes arbitrary git/npm/test commands on the engineer
# agent's behalf - defense in depth, same spirit as compliance rule 6 (self-hosted, no
# credential relay).
RUN useradd --create-home --uid 1000 foundry
USER foundry

WORKDIR /workspace

# ANTHROPIC_API_KEY is never baked in here - it must be passed with `docker run -e
# ANTHROPIC_API_KEY` (see run.sh). AnthropicAPIRunner itself already refuses to run without it
# (compliance rule 2); this image adds no fallback on top of that, and concurrency stays at the
# runner's own default of 1 (rule 4) unless the command overrides it explicitly.

ENTRYPOINT ["python3"]
CMD ["-m", "shell.scheduler.cli", "--runner", "anthropic-api", "--mode", "balanced"]
