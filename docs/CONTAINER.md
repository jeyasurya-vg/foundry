# Container profile for autonomous mode

`AnthropicAPIRunner` (`shell/runners/anthropic_api.py`) shells out to the official `claude` CLI
directly. By default that happens on whatever host the scheduler process runs on. This profile
(`shell/runners/container/`) gives it somewhere else to run instead: a container with no host
mounts beyond the one project directory you explicitly hand it.

## What it is

- **`Dockerfile`** — `node:20-slim` (for the official `claude` CLI, an npm package) plus
  `python3`/`git`. Installs a pinned version of `@anthropic-ai/claude-code`, runs as a non-root
  user, and bakes in no credentials of any kind. Default `CMD` runs the scheduler daemon
  (`shell/scheduler/cli.py`) against whatever gets mounted at `/workspace`.
- **`run.sh`** — the reference launch wrapper. Refuses to start if `ANTHROPIC_API_KEY` isn't
  set (same refusal `AnthropicAPIRunner` itself does — this script just fails faster, before
  ever invoking `docker run`). Mounts exactly one host path at `/workspace`: the project
  directory you pass it (or the current directory) — never `$HOME`, never `~/.claude`, never
  the Docker socket.
- **`.dockerignore`** — keeps local sqlite state (`company/*.db`) and other per-checkout files
  out of the build context; they live on the mounted volume, not in the image.

## Build and run

```bash
docker build -t foundry-runner shell/runners/container
ANTHROPIC_API_KEY=sk-... shell/runners/container/run.sh /path/to/foundry
```

Override the container's command to run something other than the scheduler daemon, e.g. a
single ledger command:

```bash
ANTHROPIC_API_KEY=sk-... shell/runners/container/run.sh /path/to/foundry -- \
  python3 -m shell.ledger.cli status
```

## Which `COMPLIANCE.md` rules this satisfies, and how

| Rule | How the container profile holds it |
|---|---|
| 1 — never touch `~/.claude/` | The image has no host filesystem in scope until `run.sh` mounts one, and it mounts only the project directory. `~/.claude`, `.config/claude`, and every OS credential store are simply unreachable from inside the container. |
| 2 — explicit API key, no fallback | `run.sh` checks `ANTHROPIC_API_KEY` before ever calling `docker run`; `AnthropicAPIRunner` checks it again inside the container. Two independent refusals, no auto-detection either place. |
| 4 — concurrency defaults to 1 | The container changes nothing about `AnthropicAPIRunner`'s own default; raising it is still an explicit per-user choice made in the command the container runs. |
| 6 — self-hosted, no credential relay | You build and run this image yourself, on infrastructure you control; nothing here is a hosted service or a proxy. |

This profile is one way to run the autonomous shell, not a requirement — running
`shell/scheduler/cli.py` directly on your own machine (`docs/AUTONOMOUS.md`) is equally valid
and exactly what this image does on your behalf, just inside a sandbox.
